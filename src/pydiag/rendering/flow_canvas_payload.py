from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well, WellsDocument

from .flow_canvas_bounds import flow_canvas_bounds
from .flow_edge_labels import EDGE_LABEL_HEIGHT, edge_label_position
from .flow_edge_rendering import (
    edge_color,
    edge_label_text,
    edge_label_width,
    edge_opacity,
    edge_style,
)
from .flow_layout_positions import node_ports
from .flow_node_filters import KIND_LABELS, node_matches_filters
from .flow_node_overlays import (
    MAX_VISIBLE_WELL_TOKENS,
    duration_badge_style,
    duration_label,
    responsible_abbreviation,
    responsible_badge_style,
    short_well_name,
    well_token_style,
)
from .flow_node_render_specs import NodeRenderSpec
from .flow_node_styles import flow_node_class_name, node_style
from .flow_render_metrics import canvas_height_for_snapshot
from .flow_render_snapshot import FlowRenderSnapshot, build_flow_render_snapshot
from .flow_route_geometry import EdgeRoute, NodeGeometry, port_point

__all__ = ["build_flow_canvas_payload"]


def build_flow_canvas_payload(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    *,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    layout_mode: str = "snake",
    domain_nodes_draggable: bool = False,
    revision: int | None = None,
    snapshot: FlowRenderSnapshot | None = None,
    snapshot_cache: MutableMapping[Any, Any] | None = None,
    session_epoch: int | None = None,
) -> dict[str, Any]:
    cache_key = (
        revision,
        layout_mode,
        graph.version,
        wells_doc.version,
        tuple((node.id, node.position.x, node.position.y) for node in graph.nodes),
    )
    if snapshot is None and snapshot_cache is not None:
        cached = snapshot_cache.get(cache_key)
        if isinstance(cached, FlowRenderSnapshot):
            snapshot = cached
    if snapshot is None:
        snapshot = build_flow_render_snapshot(graph, wells_doc, layout_mode)
        if snapshot_cache is not None:
            snapshot_cache[cache_key] = snapshot
    # Responsible filter is applied in the canvas JS so legend toggles stay
    # instant and do not rebuild the scene. Search/kind still dim server-side.
    nodes, active_node_ids = build_flow_canvas_nodes_from_snapshot(
        snapshot,
        search=search,
        responsible_filter=[],
        kind_filter=kind_filter,
        selected_id=selected_id,
        domain_nodes_draggable=domain_nodes_draggable,
    )
    edges = build_flow_canvas_edges_from_snapshot(
        snapshot,
        active_node_ids=active_node_ids,
        selected_id=selected_id,
    )

    bounds = flow_canvas_bounds(nodes=nodes, edges=edges)
    payload = {
        "nodes": nodes,
        "edges": edges,
        "selected_id": selected_id,
        "position_edit_enabled": domain_nodes_draggable,
        "layout_mode": snapshot.layout_mode,
        "revision": revision if revision is not None else snapshot.graph.version,
        "canvas": {
            "width": max(1200, int(bounds["right"] - bounds["left"] + 160)),
            "height": max(canvas_height_for_snapshot(snapshot), 828),
        },
        "bounds": bounds,
        "responsible_legend": build_responsible_legend(snapshot.graph),
        "responsible_filter": list(responsible_filter or []),
    }
    if session_epoch is not None:
        payload["session_epoch"] = session_epoch
    return payload


def build_flow_canvas_nodes_from_snapshot(
    snapshot: FlowRenderSnapshot,
    *,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    domain_nodes_draggable: bool = False,
) -> tuple[list[dict[str, Any]], set[str]]:
    responsible_filter = responsible_filter or []
    kind_filter = kind_filter or []
    nodes: list[dict[str, Any]] = []
    active_node_ids: set[str] = set()

    for index, node in enumerate(snapshot.graph.nodes):
        wells_here = snapshot.wells_by_node.get(node.id, [])
        is_active = node_matches_filters(
            snapshot.graph,
            node,
            search,
            responsible_filter,
            kind_filter,
            wells_here,
        )
        if is_active:
            active_node_ids.add(node.id)
        nodes.append(
            build_flow_canvas_node(
                graph=snapshot.graph,
                node=node,
                wells_here=wells_here,
                geometry=snapshot.geometries[node.id],
                render_spec=snapshot.render_specs[node.id],
                node_index=index,
                layout_mode=snapshot.layout_mode,
                selected_id=selected_id,
                search=search,
                active=is_active,
                domain_nodes_draggable=domain_nodes_draggable,
            )
        )

    return nodes, active_node_ids


def build_flow_canvas_node(
    *,
    graph: FlowGraphDocument,
    node: FlowNode,
    wells_here: list[Well],
    geometry: NodeGeometry,
    render_spec: NodeRenderSpec,
    node_index: int,
    layout_mode: str,
    selected_id: str | None,
    search: str,
    active: bool,
    domain_nodes_draggable: bool,
) -> dict[str, Any]:
    source_position, target_position = node_ports(node_index, layout_mode)
    return {
        "id": node.id,
        "kind": node.kind,
        "kind_label": KIND_LABELS[node.kind],
        "text": node.text,
        "selected": node.id == selected_id,
        "active": active,
        "draggable": domain_nodes_draggable,
        "class_name": flow_node_class_name(node),
        "source_position": source_position,
        "target_position": target_position,
        "position": {"x": round(geometry.x, 2), "y": round(geometry.y, 2)},
        "size": {"w": geometry.width, "h": geometry.height},
        "responsible": list(node.responsible),
        "primary_responsible": node.primary_responsible,
        "style": node_style(
            node,
            graph,
            node_width=render_spec.width,
            node_height=render_spec.height,
            selected=False,
            active=active,
        ),
        "time_badge": build_time_badge(node, active),
        "responsible_badges": build_responsible_badges(graph, node, active),
        "well_tokens": build_well_tokens(
            node_id=node.id,
            wells_here=wells_here,
            selected_id=selected_id,
            search=search,
            node_active=active,
        ),
    }


def build_flow_canvas_edges_from_snapshot(
    snapshot: FlowRenderSnapshot,
    *,
    active_node_ids: set[str],
    selected_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        build_flow_canvas_edge(
            route=route,
            geometries=snapshot.geometries,
            active_node_ids=active_node_ids,
            layout_mode=snapshot.layout_mode,
            selected_id=selected_id,
        )
        for route in snapshot.routes
    ]


def build_flow_canvas_edge(
    *,
    route: EdgeRoute,
    geometries: Mapping[str, NodeGeometry],
    active_node_ids: set[str],
    layout_mode: str,
    selected_id: str | None,
) -> dict[str, Any]:
    edge = route.edge
    source = geometries[edge.source]
    target = geometries[edge.target]
    active = edge.source in active_node_ids and edge.target in active_node_ids
    points = edge_route_points(route, source=source, target=target, layout_mode=layout_mode)
    color = edge_color(edge)
    label_text = edge_label_text(edge)
    label = None
    if label_text:
        label_width = edge_label_width(edge)
        label_position = edge_label_position(route, source, target, label_width, layout_mode)
        label = {
            "text": label_text,
            "position": {"x": round(label_position[0], 2), "y": round(label_position[1], 2)},
            "width": label_width,
            "height": EDGE_LABEL_HEIGHT,
            "color": color,
            "active": active,
            "selected": edge.id == selected_id,
        }

    return {
        "id": edge.id,
        "kind": edge.kind,
        "source": edge.source,
        "target": edge.target,
        "selected": edge.id == selected_id,
        "active": active,
        "color": color,
        "style": edge_style(edge, edge_opacity(edge, active), is_route_segment=bool(route.anchors)),
        "points": [{"x": round(x, 2), "y": round(y, 2)} for x, y in points],
        "label": label,
    }


def build_time_badge(node: FlowNode, active: bool) -> dict[str, Any] | None:
    if node.time is None:
        return None
    return {
        "text": duration_label(node.time),
        "style": component_style(duration_badge_style(active, node.time)),
        "title": node.time,
    }


def build_responsible_legend(graph: FlowGraphDocument) -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": style.label,
            "fill": style.fill,
            "border": style.border,
        }
        for key, style in graph.responsibles.items()
    ]


def build_responsible_badges(
    graph: FlowGraphDocument,
    node: FlowNode,
    active: bool,
) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for responsible in node.secondary_responsibles:
        style = graph.responsibles.get(responsible)
        if style is None:
            continue
        badges.append(
            {
                "id": f"responsible::{node.id}::{responsible}",
                "text": style.label,
                "abbr": responsible_abbreviation(style.label),
                "style": component_style(
                    responsible_badge_style(
                        active=active,
                        label=style.label,
                        fill=style.fill,
                        border=style.border,
                        text=style.text,
                    )
                ),
                "title": style.label,
            }
        )
    return badges


def build_well_tokens(
    *,
    node_id: str,
    wells_here: list[Well],
    selected_id: str | None,
    search: str,
    node_active: bool,
) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    query = search.strip().lower()
    for well in wells_here[:MAX_VISIBLE_WELL_TOKENS]:
        token_id = f"well::{well.id}"
        token_active = node_active or query in (well.id + " " + well.name).lower()
        tokens.append(
            {
                "id": token_id,
                "text": f"Скв. {short_well_name(well)}",
                "title": well.name,
                "selected": token_id == selected_id,
                "style": component_style(
                    well_token_style(selected=token_id == selected_id, active=token_active),
                    interactive=True,
                ),
            }
        )

    if len(wells_here) > MAX_VISIBLE_WELL_TOKENS:
        tokens.append(
            {
                "id": f"well-extra::{node_id}",
                "text": f"Скв. +{len(wells_here) - MAX_VISIBLE_WELL_TOKENS}",
                "title": "Показать этап",
                "selected": False,
                "style": component_style(
                    well_token_style(selected=False, active=node_active),
                    interactive=True,
                ),
            }
        )
    return tokens


def edge_route_points(
    route: EdgeRoute,
    *,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> list[tuple[float, float]]:
    _ = layout_mode
    source_side = route.source_side
    target_side = route.target_side
    start = (
        route.source_anchor.pos
        if route.source_anchor is not None
        else port_point(source, source_side)
    )
    end = port_point(target, target_side)
    sx, sy = route.source_slot_offset
    tx, ty = route.target_slot_offset
    start = (start[0] + sx, start[1] + sy)
    end = (end[0] + tx, end[1] + ty)
    middle: list[tuple[float, float]] = []
    last_index = len(route.anchors) - 1
    for index, anchor in enumerate(route.anchors):
        x, y = anchor.pos
        if index == 0:
            x += sx
            y += sy
        elif index == last_index:
            # Mutually exclusive with the first-anchor branch so a sole waypoint
            # does not receive both source and target slot offsets.
            x += tx
            y += ty
        middle.append((x, y))
    return ensure_orthogonal_polyline([start, *middle, end])


def ensure_orthogonal_polyline(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    result: list[tuple[float, float]] = [points[0]]
    for next_point in points[1:]:
        previous = result[-1]
        if previous == next_point:
            continue
        if previous[0] == next_point[0] or previous[1] == next_point[1]:
            result.append(next_point)
            continue
        corner = (next_point[0], previous[1])
        if corner != previous:
            result.append(corner)
        if corner != next_point:
            result.append(next_point)
    simplified: list[tuple[float, float]] = [result[0]]
    for previous, current, nxt in zip(result[:-2], result[1:-1], result[2:], strict=True):
        if (previous[0] == current[0] == nxt[0]) or (previous[1] == current[1] == nxt[1]):
            continue
        simplified.append(current)
    simplified.append(result[-1])
    return simplified


def component_style(style: Mapping[str, Any], *, interactive: bool = False) -> dict[str, Any]:
    adjusted = dict(style)
    if interactive:
        adjusted["pointerEvents"] = "auto"
    return adjusted
