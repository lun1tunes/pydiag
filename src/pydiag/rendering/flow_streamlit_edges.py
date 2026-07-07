from __future__ import annotations

from pydiag.domain.models import FlowEdge, FlowGraphDocument, WellsDocument

from .flow_edge_rendering import edge_color, edge_opacity, edge_style
from .flow_render_snapshot import FlowRenderSnapshot, build_flow_render_snapshot
from .flow_route_geometry import EdgeRoute
from .flow_streamlit_primitives import StreamlitFlowEdge

__all__ = [
    "build_streamlit_edges",
    "build_streamlit_edges_from_snapshot",
]


def build_streamlit_edges(
    graph: FlowGraphDocument,
    active_node_ids: set[str] | None = None,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> list[StreamlitFlowEdge]:
    snapshot = build_flow_render_snapshot(graph, wells_doc, layout_mode)
    return build_streamlit_edges_from_snapshot(snapshot, active_node_ids)


def build_streamlit_edges_from_snapshot(
    snapshot: FlowRenderSnapshot,
    active_node_ids: set[str] | None = None,
) -> list[StreamlitFlowEdge]:
    if active_node_ids is None:
        active_node_ids = {node.id for node in snapshot.graph.nodes}
    edges: list[StreamlitFlowEdge] = []
    for route in snapshot.routes:
        edges.extend(route_to_streamlit_edges(route, active_node_ids))
    return edges


def route_to_streamlit_edges(
    route: EdgeRoute,
    active_node_ids: set[str],
) -> list[StreamlitFlowEdge]:
    edge = route.edge
    active = edge.source in active_node_ids and edge.target in active_node_ids
    color = edge_color(edge)
    opacity = edge_opacity(edge, active)
    source_id = route.source_anchor.id if route.source_anchor is not None else edge.source
    points = [source_id, *(anchor.id for anchor in route.anchors), edge.target]
    final_segment_index = len(points) - 2
    label_segment_index = edge_label_segment_index(edge, final_segment_index, bool(route.anchors))
    segment_edges: list[StreamlitFlowEdge] = []

    for segment_index, (source, target) in enumerate(zip(points[:-1], points[1:], strict=True)):
        is_final = segment_index == final_segment_index
        carries_label = segment_index == label_segment_index
        label = edge_rendered_label(edge, carries_label)
        segment_edges.append(
            StreamlitFlowEdge(
                id=route_segment_id(edge.id, segment_index, label_segment_index),
                source=source,
                target=target,
                edge_type=edge_route_type(route),
                marker_end={"type": "arrowclosed", "color": color} if is_final else {},
                label=label,
                label_show_bg=bool(label),
                label_style={
                    "fill": color,
                    "fontWeight": 760,
                    "fontSize": "12px",
                },
                label_bg_style={
                    "fill": "#ffffff",
                    "fillOpacity": 0.96,
                    "rx": 7,
                    "ry": 7,
                    "stroke": color,
                    "strokeOpacity": 0.18,
                    "strokeWidth": 1,
                },
                z_index=edge_z_index(route, segment_index),
                focusable=False,
                style=edge_style(edge, opacity, is_route_segment=bool(route.anchors)),
                pathOptions={
                    "borderRadius": 18,
                    "offset": 22 if route.anchors else 14,
                },
                data={"domainEdgeId": edge.id},
            )
        )
    return segment_edges


def route_segment_id(edge_id: str, segment_index: int, label_segment_index: int) -> str:
    if segment_index == label_segment_index:
        return edge_id
    return f"route::{edge_id}::{segment_index}"


def edge_label_segment_index(edge: FlowEdge, final_segment_index: int, has_route: bool) -> int:
    if not has_route:
        return 0
    if edge.kind in {"yes", "no"}:
        return 0
    return max(0, final_segment_index - 1)


def edge_rendered_label(edge: FlowEdge, carries_label: bool) -> str:
    # Domain edge labels stay in JSON for admin/inspector context. On the canvas
    # they render as tiny React Flow bubbles and visually compete with route labels.
    _ = edge
    _ = carries_label
    return ""


def edge_route_type(route: EdgeRoute) -> str:
    if not route.anchors:
        return direct_edge_type(route.edge)
    return "smoothstep"


def direct_edge_type(edge: FlowEdge) -> str:
    if edge.kind == "dashed":
        return "simplebezier"
    return "smoothstep"


def edge_z_index(route: EdgeRoute, segment_index: int) -> int:
    if not route.anchors:
        return 2 if route.edge.kind in {"yes", "no"} else 1
    if segment_index == len(route.anchors):
        return 3
    return 2
