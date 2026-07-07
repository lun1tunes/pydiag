from __future__ import annotations

import copy
from typing import Any

from pydiag.domain.models import FlowGraphDocument
from pydiag.infrastructure.figma_geometry import (
    Rect,
    infer_connector_terminal,
    secondary_nearest_terminal,
)
from pydiag.infrastructure.figma_metadata import (
    FlowEdgeSkeletonData,
    build_flow_edge_mapping,
    build_flow_edge_name,
    build_flow_node_mapping,
    build_flow_node_name,
    build_responsibles,
    parse_name_metadata,
    resolve_flow_edge_data,
    resolve_flow_node_data,
)
from pydiag.infrastructure.figma_schema import (
    FigmaConnectorNode,
    FigmaTextNode,
    extract_elements_container,
    extract_raw_elements,
    extract_typed_elements,
    load_payload,
    payload_version,
    text_like_payload,
)

__all__ = [
    "flow_graph_payload_from_figma_payload",
    "is_figma_skeleton_payload",
    "load_payload",
    "normalize_figma_skeleton_payload",
    "update_figma_payload_positions",
]


def is_figma_skeleton_payload(payload: object) -> bool:
    try:
        nodes = extract_raw_elements(payload)
    except ValueError:
        return False
    return any(node.type in {"TEXT", "CONNECTOR"} for node in nodes)


def flow_graph_payload_from_figma_payload(payload: object) -> dict[str, Any]:
    elements = extract_typed_elements(payload)
    text_nodes = [
        (raw, node)
        for raw, node in elements
        if isinstance(node, FigmaTextNode) and node.visible
    ]
    connector_nodes = [
        (raw, node)
        for raw, node in elements
        if isinstance(node, FigmaConnectorNode) and node.visible
    ]

    flow_nodes = [convert_text_node(raw_item, node) for raw_item, node in text_nodes]
    node_rects = {
        node_payload["id"]: Rect(
            left=float(node_payload["position"]["x"]),
            top=float(node_payload["position"]["y"]),
            right=float(node_payload["position"]["x"] + node_payload["size"]["w"]),
            bottom=float(node_payload["position"]["y"] + node_payload["size"]["h"]),
        )
        for node_payload in flow_nodes
    }
    flow_edges = [
        convert_connector_node(raw_item, node, node_rects)
        for raw_item, node in connector_nodes
    ]
    responsibles = build_responsibles(payload, flow_nodes)

    graph_payload = {
        "schema_version": "1.0",
        "version": payload_version(payload),
        "responsibles": responsibles,
        "nodes": flow_nodes,
        "edges": flow_edges,
    }
    FlowGraphDocument.model_validate(graph_payload, strict=True)
    return graph_payload


def normalize_figma_skeleton_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        raise ValueError(
            "Figma skeleton normalization requires an object payload with version and elements/nodes list"
        )

    normalized = copy.deepcopy(payload)
    elements = extract_typed_elements(normalized)
    text_nodes = [
        (raw, node) for raw, node in elements if isinstance(node, FigmaTextNode)
    ]
    connector_nodes = [
        (raw, node) for raw, node in elements if isinstance(node, FigmaConnectorNode)
    ]

    flow_nodes = [convert_text_node(raw_item, node) for raw_item, node in text_nodes]
    node_rects = {
        node_payload["id"]: Rect(
            left=float(node_payload["position"]["x"]),
            top=float(node_payload["position"]["y"]),
            right=float(node_payload["position"]["x"] + node_payload["size"]["w"]),
            bottom=float(node_payload["position"]["y"] + node_payload["size"]["h"]),
        )
        for node_payload in flow_nodes
    }
    flow_edges = [
        convert_connector_node(raw_item, node, node_rects)
        for raw_item, node in connector_nodes
    ]

    for raw_item, node in text_nodes:
        flow_node = resolve_flow_node_data(node, raw_item)
        raw_item["flowNode"] = build_flow_node_mapping(flow_node)
        raw_item["name"] = build_flow_node_name(
            flow_node, extras=parse_name_metadata(node.name)
        )

    for (raw_item, node), flow_edge in zip(connector_nodes, flow_edges, strict=True):
        flow_edge_data = FlowEdgeSkeletonData(
            id=str(flow_edge["id"]),
            kind=str(flow_edge["kind"]),
            source=str(flow_edge["source"]),
            target=str(flow_edge["target"]),
            label=str(flow_edge["label"]) if flow_edge["label"] is not None else None,
        )
        raw_item["flowEdge"] = build_flow_edge_mapping(flow_edge_data)
        raw_item["name"] = build_flow_edge_name(
            flow_edge_data,
            extras=parse_name_metadata(node.name),
        )

    normalized["schema_version"] = "figma-skeleton/2.0"
    return normalized


def update_figma_payload_positions(
    payload: object,
    positions: dict[str, tuple[float, float]],
    expected_version: int,
) -> object:
    if not isinstance(payload, dict):
        raise ValueError(
            "Figma skeleton save requires an object payload with version and elements/nodes list"
        )
    current_version = payload_version(payload)
    if current_version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {current_version}"
        )

    updated = copy.deepcopy(payload)
    elements = extract_elements_container(updated)
    raw_text_ids = {
        resolve_flow_node_data(node, raw_item).id: node.id
        for raw_item, node in extract_typed_elements(updated)
        if isinstance(node, FigmaTextNode)
    }
    unknown_ids = sorted(set(positions) - set(raw_text_ids))
    if unknown_ids:
        raise ValueError(f"Unknown graph node positions: {', '.join(unknown_ids)}")

    for item in elements:
        if not isinstance(item, dict) or str(item.get("type")).upper() not in {
            "TEXT",
            "SHAPE_WITH_TEXT",
        }:
            continue
        node = FigmaTextNode.model_validate(text_like_payload(item))
        flow_node_id = resolve_flow_node_data(node, item).id
        position = positions.get(flow_node_id)
        if position is None:
            continue
        item["x"] = round(float(position[0]), 2)
        item["y"] = round(float(position[1]), 2)

    updated["version"] = current_version + 1
    return updated


def convert_text_node(
    raw_item: dict[str, object], node: FigmaTextNode
) -> dict[str, Any]:
    flow_node = resolve_flow_node_data(node, raw_item)
    legacy_metadata = parse_name_metadata(node.name)
    metadata: dict[str, str | int | float | bool | None] = {
        "figma_source_id": node.id,
        "figma_parent_id": node.parent,
        "figma_fixed_size": True,
        "figma_font_size": node.font_size,
        "figma_font_family": node.font_name.family if node.font_name else None,
        "figma_font_style": node.font_name.style if node.font_name else None,
        "figma_text_align_horizontal": node.text_align_horizontal,
        "figma_text_align_vertical": node.text_align_vertical,
        "figma_letter_spacing_unit": node.letter_spacing.unit
        if node.letter_spacing
        else None,
        "figma_letter_spacing_value": (
            node.letter_spacing.value if node.letter_spacing else None
        ),
        "figma_line_height_unit": node.line_height.unit if node.line_height else None,
        "figma_line_height_value": node.line_height.value if node.line_height else None,
        "figma_text_case": node.text_case,
        "figma_text_decoration": node.text_decoration,
        "figma_rotation": round(float(node.rotation), 2),
        "figma_opacity": round(float(node.opacity), 4),
        "figma_blend_mode": node.blend_mode,
        "figma_layout_align": node.layout_align,
        "figma_layout_grow": node.layout_grow,
        "figma_layout_sizing_horizontal": node.layout_sizing_horizontal,
        "figma_layout_sizing_vertical": node.layout_sizing_vertical,
        "figma_constraints_horizontal": (
            node.constraints.horizontal if node.constraints else None
        ),
        "figma_constraints_vertical": node.constraints.vertical
        if node.constraints
        else None,
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}

    return {
        "id": flow_node.id,
        "type": flow_node.kind,
        "text": (
            node.characters or legacy_metadata.get("label") or node.name or node.id
        ).strip(),
        "position": {
            "x": round(float(node.x), 2),
            "y": round(float(node.y), 2),
        },
        "size": {
            "w": max(
                80,
                min(
                    1200,
                    int(round(float(node.width or max(60, len(node.characters) * 8)))),
                ),
            ),
            "h": max(
                40,
                min(
                    800,
                    int(
                        round(
                            float(node.height or max(24, (node.font_size or 16) * 1.4))
                        )
                    ),
                ),
            ),
        },
        "responsible": flow_node.responsible,
        "time": flow_node.time,
        "metadata": metadata,
    }


def convert_connector_node(
    raw_item: dict[str, object],
    node: FigmaConnectorNode,
    node_rects: dict[str, Rect],
) -> dict[str, Any]:
    flow_edge = resolve_flow_edge_data(node, raw_item)
    source = flow_edge.source or infer_connector_terminal(node, node_rects, end="start")
    target = flow_edge.target or infer_connector_terminal(node, node_rects, end="end")
    if not source or not target:
        raise ValueError(f"Connector {node.id}: source/target could not be resolved")
    if source == target:
        nearest = secondary_nearest_terminal(node, node_rects, excluded=source)
        if nearest is not None:
            target = nearest

    return {
        "id": flow_edge.id,
        "kind": flow_edge.kind,
        "source": source,
        "target": target,
        "label": flow_edge.label,
        "metadata": {
            "figma_source_id": node.id,
            "figma_parent_id": node.parent,
            "figma_rotation": round(float(node.rotation), 2),
            "figma_opacity": round(float(node.opacity), 4),
            "figma_blend_mode": node.blend_mode,
        },
    }
