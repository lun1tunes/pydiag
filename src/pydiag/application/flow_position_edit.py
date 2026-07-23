from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from pydiag.common.layout_metadata import CUSTOM_LAYOUT_X_META, CUSTOM_LAYOUT_Y_META
from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.rendering import (
    build_node_render_specs,
    component_positions_from_state,
    layout_positions,
    wells_grouped_by_node,
)

POSITION_EDIT_SIGNATURE_KEY = "position_edit_signature"
POSITION_EDIT_POSITIONS_KEY = "position_edit_positions"
POSITION_EDIT_DIRTY_KEY = "position_edit_dirty"

__all__ = [
    "custom_layout_positions_for_graph",
    "ensure_position_edit_positions",
    "graph_node_positions",
    "graph_with_positions",
    "initial_position_edit_positions",
    "is_position_pair",
    "normalize_position_pair",
    "position_edit_positions_from_state",
    "position_edit_signature",
    "reset_position_edit_state",
    "update_position_edit_positions_from_component",
]


def position_edit_signature(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    layout_mode: str,
) -> tuple[Any, ...]:
    return (
        graph.version,
        wells.version,
        tuple(
            (node.id, node.position.x, node.position.y, node.size.w, node.size.h)
            for node in graph.nodes
        ),
        tuple((well.id, well.current_node_id, well.is_archived) for well in wells.wells),
        layout_mode,
    )


def initial_position_edit_positions(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    layout_mode: str,
) -> dict[str, tuple[float, float]]:
    render_specs = build_node_render_specs(graph, wells_grouped_by_node(wells))
    return {
        node_id: normalize_position_pair(position)
        for node_id, position in layout_positions(graph, layout_mode, render_specs).items()
    }


def ensure_position_edit_positions(
    session_state: MutableMapping[str, Any],
    graph: FlowGraphDocument,
    wells: WellsDocument,
    layout_mode: str,
) -> dict[str, tuple[float, float]]:
    signature = position_edit_signature(graph, wells, layout_mode)
    positions = session_state.get(POSITION_EDIT_POSITIONS_KEY)
    if session_state.get(POSITION_EDIT_SIGNATURE_KEY) != signature or not isinstance(
        positions, dict
    ):
        positions = initial_position_edit_positions(graph, wells, layout_mode)
        session_state[POSITION_EDIT_SIGNATURE_KEY] = signature
        session_state[POSITION_EDIT_POSITIONS_KEY] = positions
        session_state[POSITION_EDIT_DIRTY_KEY] = False
    return position_edit_positions_from_state(session_state, graph)


def position_edit_positions_from_state(
    session_state: Mapping[str, Any],
    graph: FlowGraphDocument,
) -> dict[str, tuple[float, float]]:
    raw_positions = session_state.get(POSITION_EDIT_POSITIONS_KEY)
    if not isinstance(raw_positions, dict):
        return graph_node_positions(graph)

    result: dict[str, tuple[float, float]] = {}
    for node in graph.nodes:
        value = raw_positions.get(node.id)
        if is_position_pair(value):
            result[node.id] = normalize_position_pair(value)
        else:
            result[node.id] = (node.position.x, node.position.y)
    return result


def is_position_pair(value: object) -> bool:
    return (
        isinstance(value, (tuple, list))
        and len(value) == 2
        and all(isinstance(item, int | float) for item in value)
    )


def normalize_position_pair(value: tuple[float, float] | list[float]) -> tuple[float, float]:
    return (round(float(value[0]), 2), round(float(value[1]), 2))


def graph_with_positions(
    graph: FlowGraphDocument,
    positions: dict[str, tuple[float, float]],
) -> FlowGraphDocument:
    payload = graph.model_dump(mode="json")
    for node_payload in payload["nodes"]:
        position = positions.get(node_payload["id"])
        if position is None:
            continue
        node_payload["position"] = {"x": position[0], "y": position[1]}
    return FlowGraphDocument.model_validate(payload, strict=True)


def update_position_edit_positions_from_component(
    session_state: MutableMapping[str, Any],
    graph: FlowGraphDocument,
    component_state: Mapping[str, object] | None,
) -> bool:
    positions = component_positions_from_state(graph, component_state)
    if positions is None:
        return False

    current = position_edit_positions_from_state(session_state, graph)
    changed = positions != current
    if changed:
        session_state[POSITION_EDIT_POSITIONS_KEY] = positions
        session_state[POSITION_EDIT_DIRTY_KEY] = True
    return changed


def reset_position_edit_state(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(POSITION_EDIT_SIGNATURE_KEY, None)
    session_state.pop(POSITION_EDIT_POSITIONS_KEY, None)
    session_state[POSITION_EDIT_DIRTY_KEY] = False


def graph_node_positions(graph: FlowGraphDocument) -> dict[str, tuple[float, float]]:
    return {node.id: (node.position.x, node.position.y) for node in graph.nodes}


def custom_layout_positions_for_graph(
    graph: FlowGraphDocument,
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    for node in graph.nodes:
        x = node.metadata.get(CUSTOM_LAYOUT_X_META)
        y = node.metadata.get(CUSTOM_LAYOUT_Y_META)
        if isinstance(x, int | float) and isinstance(y, int | float):
            positions[node.id] = (round(float(x), 2), round(float(y), 2))
        else:
            positions[node.id] = (node.position.x, node.position.y)
    return positions
