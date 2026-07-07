from __future__ import annotations

from dataclasses import dataclass

from pydiag.domain.models import FlowGraphDocument, Well, WellsDocument

from .flow_edge_routing import build_edge_routes_for_geometries
from .flow_layout_positions import build_node_geometries, layout_positions
from .flow_node_filters import wells_grouped_by_node
from .flow_node_render_specs import NodeRenderSpec, build_node_render_specs
from .flow_route_geometry import EdgeRoute, NodeGeometry

__all__ = [
    "FlowRenderSnapshot",
    "build_flow_render_snapshot",
]


@dataclass(frozen=True, slots=True)
class FlowRenderSnapshot:
    graph: FlowGraphDocument
    wells_by_node: dict[str, list[Well]]
    render_specs: dict[str, NodeRenderSpec]
    positions: dict[str, tuple[float, float]]
    geometries: dict[str, NodeGeometry]
    routes: list[EdgeRoute]
    layout_mode: str


def build_flow_render_snapshot(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> FlowRenderSnapshot:
    wells_by_node = wells_grouped_by_node(wells_doc) if wells_doc is not None else {}
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)
    geometries = build_node_geometries(graph, positions, render_specs, layout_mode)
    routes = build_edge_routes_for_geometries(graph, geometries, layout_mode)
    return FlowRenderSnapshot(
        graph=graph,
        wells_by_node=wells_by_node,
        render_specs=render_specs,
        positions=positions,
        geometries=geometries,
        routes=routes,
        layout_mode=layout_mode,
    )
