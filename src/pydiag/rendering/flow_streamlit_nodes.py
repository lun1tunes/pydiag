from __future__ import annotations

from collections.abc import Mapping
from html import escape

from pydiag.domain.models import FlowEdge, FlowGraphDocument, FlowNode, Well, WellsDocument

from .flow_edge_labels import EDGE_LABEL_HEIGHT, edge_label_position
from .flow_edge_rendering import edge_color, edge_label_text, edge_label_width
from .flow_edge_routing import ROUTE_ANCHOR_SIZE
from .flow_layout_positions import node_ports
from .flow_node_filters import node_matches_filters
from .flow_node_markup import (
    FLOW_NODE_CSS,
    duration_badge_content,
    responsible_badge_content,
    well_token_content,
)
from .flow_node_overlays import (
    MAX_VISIBLE_WELL_TOKENS,
    duration_badge_position,
    duration_badge_style,
    responsible_badge_position,
    responsible_badge_style,
    well_token_position,
    well_token_style,
)
from .flow_node_styles import flow_node_class_name, node_style
from .flow_render_snapshot import FlowRenderSnapshot, build_flow_render_snapshot
from .flow_route_geometry import EdgeRoute, NodeGeometry, RouteAnchor
from .flow_streamlit_primitives import StreamlitFlowNode

__all__ = [
    "branch_anchor_node",
    "build_streamlit_nodes",
    "build_streamlit_nodes_from_snapshot",
    "edge_label_node",
    "overlay_nodes_for_domain_node",
    "route_anchor_node",
    "route_anchor_nodes_for_route",
    "route_label_node_for_route",
]


def build_streamlit_nodes(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    layout_mode: str = "snake",
    domain_nodes_draggable: bool = False,
) -> tuple[list[StreamlitFlowNode], set[str]]:
    snapshot = build_flow_render_snapshot(graph, wells_doc, layout_mode)
    return build_streamlit_nodes_from_snapshot(
        snapshot,
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        selected_id=selected_id,
        domain_nodes_draggable=domain_nodes_draggable,
    )


def build_streamlit_nodes_from_snapshot(
    snapshot: FlowRenderSnapshot,
    *,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    domain_nodes_draggable: bool = False,
) -> tuple[list[StreamlitFlowNode], set[str]]:
    responsible_filter = responsible_filter or []
    kind_filter = kind_filter or []
    nodes: list[StreamlitFlowNode] = []
    active_node_ids: set[str] = set()

    for node_index, node in enumerate(snapshot.graph.nodes):
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

        position = snapshot.positions[node.id]
        render_spec = snapshot.render_specs[node.id]
        source_position, target_position = node_ports(node_index, snapshot.layout_mode)
        nodes.append(
            StreamlitFlowNode(
                id=node.id,
                pos=position,
                data={"content": render_spec.content},
                node_type="default",
                source_position=source_position,
                target_position=target_position,
                draggable=domain_nodes_draggable,
                selectable=True,
                connectable=False,
                z_index=10 if node.id == selected_id else 1,
                className=flow_node_class_name(node),
                style=node_style(
                    node,
                    snapshot.graph,
                    node_width=render_spec.width,
                    node_height=render_spec.height,
                    selected=node.id == selected_id,
                    active=is_active,
                ),
            )
        )
        nodes.extend(
            overlay_nodes_for_domain_node(
                graph=snapshot.graph,
                node=node,
                wells_here=wells_here,
                node_position=position,
                node_height=render_spec.height,
                selected_id=selected_id,
                search=search,
                active=is_active,
            )
        )

    for route in snapshot.routes:
        nodes.extend(route_anchor_nodes_for_route(route))

    for route in snapshot.routes:
        label_node = route_label_node_for_route(
            route,
            snapshot.geometries,
            active_node_ids,
            snapshot.layout_mode,
        )
        if label_node is not None:
            nodes.append(label_node)

    return nodes, active_node_ids


def overlay_nodes_for_domain_node(
    *,
    graph: FlowGraphDocument,
    node: FlowNode,
    wells_here: list[Well],
    node_position: tuple[float, float],
    node_height: int,
    selected_id: str | None,
    search: str,
    active: bool,
) -> list[StreamlitFlowNode]:
    overlay_nodes: list[StreamlitFlowNode] = []
    if node.time is not None:
        overlay_nodes.append(duration_badge_node(node.id, node_position, node.time, active))

    overlay_nodes.extend(responsible_badge_nodes(graph, node, node_position, active))
    overlay_nodes.extend(
        well_token_nodes(
            node_id=node.id,
            wells_here=wells_here,
            node_position=node_position,
            node_height=node_height,
            selected_id=selected_id,
            search=search,
            node_active=active,
        )
    )
    return overlay_nodes


def duration_badge_node(
    node_id: str,
    node_position: tuple[float, float],
    time_value: str,
    active: bool,
) -> StreamlitFlowNode:
    return StreamlitFlowNode(
        id=f"duration::{node_id}",
        pos=duration_badge_position(node_position),
        data={"content": duration_badge_content(time_value)},
        node_type="default",
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=35,
        className="duration-badge-node",
        style=duration_badge_style(
            active=active,
            time_value=time_value,
        ),
    )


def responsible_badge_nodes(
    graph: FlowGraphDocument,
    node: FlowNode,
    node_position: tuple[float, float],
    active: bool,
) -> list[StreamlitFlowNode]:
    badges: list[StreamlitFlowNode] = []
    for responsible_index, responsible in enumerate(node.secondary_responsibles):
        style = graph.responsibles.get(responsible)
        if style is None:
            continue
        badges.append(
            StreamlitFlowNode(
                id=f"responsible::{node.id}::{responsible}",
                pos=responsible_badge_position(
                    node_position,
                    node,
                    graph,
                    responsible_index,
                ),
                data={"content": responsible_badge_content(style.label)},
                node_type="default",
                draggable=False,
                selectable=False,
                connectable=False,
                z_index=35,
                className="responsible-badge-node",
                style=responsible_badge_style(
                    active=active,
                    label=style.label,
                    fill=style.fill,
                    border=style.border,
                    text=style.text,
                ),
            )
        )
    return badges


def well_token_nodes(
    *,
    node_id: str,
    wells_here: list[Well],
    node_position: tuple[float, float],
    node_height: int,
    selected_id: str | None,
    search: str,
    node_active: bool,
) -> list[StreamlitFlowNode]:
    query = search.strip().lower()
    tokens: list[StreamlitFlowNode] = []

    for well_index, well in enumerate(wells_here[:MAX_VISIBLE_WELL_TOKENS]):
        token_id = f"well::{well.id}"
        token_active = node_active or query in (well.id + " " + well.name).lower()
        tokens.append(
            StreamlitFlowNode(
                id=token_id,
                pos=well_token_position(node_position, node_height, well_index),
                data={"content": well_token_content(well)},
                node_type="default",
                draggable=False,
                selectable=True,
                connectable=False,
                z_index=30 if token_id == selected_id else 20,
                className="well-token-node",
                style=well_token_style(
                    selected=token_id == selected_id,
                    active=token_active,
                ),
            )
        )

    if len(wells_here) > MAX_VISIBLE_WELL_TOKENS:
        tokens.append(
            StreamlitFlowNode(
                id=f"well-extra::{node_id}",
                pos=well_token_position(node_position, node_height, MAX_VISIBLE_WELL_TOKENS),
                data={
                    "content": (
                        f"{FLOW_NODE_CSS}\nСкв. **+{len(wells_here) - MAX_VISIBLE_WELL_TOKENS}**"
                    )
                },
                node_type="default",
                draggable=False,
                selectable=False,
                connectable=False,
                z_index=19,
                className="well-token-node",
                style=well_token_style(selected=False, active=node_active),
            )
        )
    return tokens


def route_anchor_nodes_for_route(route: EdgeRoute) -> list[StreamlitFlowNode]:
    nodes: list[StreamlitFlowNode] = []
    if route.source_anchor is not None:
        nodes.append(branch_anchor_node(route.source_anchor))
    nodes.extend(route_anchor_node(anchor) for anchor in route.anchors)
    return nodes


def route_label_node_for_route(
    route: EdgeRoute,
    geometries: Mapping[str, NodeGeometry],
    active_node_ids: set[str],
    layout_mode: str,
) -> StreamlitFlowNode | None:
    edge = route.edge
    if edge.kind not in {"yes", "no"}:
        return None
    return edge_label_node(
        route,
        geometries[edge.source],
        geometries[edge.target],
        active=edge.source in active_node_ids and edge.target in active_node_ids,
        layout_mode=layout_mode,
    )


def route_anchor_node(anchor: RouteAnchor) -> StreamlitFlowNode:
    return StreamlitFlowNode(
        id=anchor.id,
        pos=(
            anchor.pos[0] - ROUTE_ANCHOR_SIZE / 2,
            anchor.pos[1] - ROUTE_ANCHOR_SIZE / 2,
        ),
        data={"content": FLOW_NODE_CSS},
        node_type="default",
        source_position=anchor.source_position,
        target_position=anchor.target_position,
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=0,
        focusable=False,
        className="route-anchor-node",
        style=route_anchor_style(),
    )


def branch_anchor_node(anchor: RouteAnchor) -> StreamlitFlowNode:
    size = 8
    return StreamlitFlowNode(
        id=anchor.id,
        pos=(anchor.pos[0] - size / 2, anchor.pos[1] - size / 2),
        data={"content": FLOW_NODE_CSS},
        node_type="default",
        source_position=anchor.source_position,
        target_position=anchor.target_position,
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=0,
        focusable=False,
        className="branch-anchor-node",
        style=branch_anchor_style(size),
    )


def branch_anchor_style(size: int) -> dict[str, str | float]:
    return {
        "width": f"{size}px",
        "height": f"{size}px",
        "minWidth": "0",
        "minHeight": "0",
        "boxSizing": "border-box",
        "padding": "0",
        "border": "0",
        "borderRadius": "0",
        "backgroundColor": "transparent",
        "background": "transparent",
        "color": "transparent",
        "fontSize": "0",
        "lineHeight": "0",
        "boxShadow": "none",
        "outline": "0",
        "opacity": 1.0,
        "pointerEvents": "none",
    }


def route_anchor_style() -> dict[str, str | float]:
    return branch_anchor_style(ROUTE_ANCHOR_SIZE)


def edge_label_node(
    route: EdgeRoute,
    source: NodeGeometry,
    target: NodeGeometry,
    active: bool,
    layout_mode: str,
) -> StreamlitFlowNode:
    edge = route.edge
    width = edge_label_width(edge)
    return StreamlitFlowNode(
        id=f"edge-label::{edge.id}",
        pos=edge_label_position(route, source, target, width, layout_mode),
        data={"content": edge_label_content(edge)},
        node_type="default",
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=34,
        focusable=False,
        className=f"edge-label-node edge-label-node-{edge.kind}",
        style=edge_label_style(edge, active, width),
    )


def edge_label_content(edge: FlowEdge) -> str:
    return f"{FLOW_NODE_CSS}\n<strong>{escape(edge_label_text(edge))}</strong>"


def edge_label_style(
    edge: FlowEdge,
    active: bool,
    width: int,
) -> dict[str, str | float]:
    color = edge_color(edge)
    return {
        "width": f"{width}px",
        "height": f"{EDGE_LABEL_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": f"1px solid {color}",
        "backgroundColor": "#ffffff",
        "color": color,
        "fontSize": "12px",
        "fontWeight": 780,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 7px 16px rgba(15, 23, 42, 0.10)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }
