from __future__ import annotations

from pydiag.domain.models import FlowGraphDocument

from .flow_edge_labels import (
    EDGE_LABEL_GAP,
    EDGE_LABEL_HEIGHT,
    EDGE_LABEL_ROUTE_SIDE_GAP,
    edge_label_position,
)
from .flow_edge_routing import (
    ROUTE_ANCHOR_SIZE,
    ROUTE_CANVAS_PADDING,
    ROUTE_GUTTER_GAP,
    ROUTE_GUTTER_STEP,
    ROUTE_OBSTACLE_LANE_GAP,
    ROUTE_OBSTACLE_MARGIN,
    ROUTE_ROW_LANE_GAP,
    ROUTE_ROW_LANE_STEP,
    build_edge_routes_for_geometries,
    route_target_side,
)
from .flow_layout_positions import (
    SNAKE_CELL_HEIGHT,
    SNAKE_CELL_WIDTH,
    SNAKE_COLUMNS,
    SNAKE_ORIGIN_X,
    SNAKE_ORIGIN_Y,
    build_node_geometries,
    build_row_bounds,
    manual_row_lookup,
    node_ports,
)
from .flow_layout_positions import (
    layout_positions as base_layout_positions,
)
from .flow_node_render_specs import NodeRenderSpec
from .flow_route_geometry import (
    EdgeRoute,
    NodeGeometry,
    Rect,
    RouteAnchor,
    RowBounds,
    port_point,
    route_anchor_id,
    route_source_anchor_id,
)

__all__ = [
    "EDGE_LABEL_GAP",
    "EDGE_LABEL_HEIGHT",
    "EDGE_LABEL_ROUTE_SIDE_GAP",
    "EdgeRoute",
    "NodeGeometry",
    "ROUTE_ANCHOR_SIZE",
    "ROUTE_CANVAS_PADDING",
    "ROUTE_GUTTER_GAP",
    "ROUTE_GUTTER_STEP",
    "ROUTE_OBSTACLE_LANE_GAP",
    "ROUTE_OBSTACLE_MARGIN",
    "ROUTE_ROW_LANE_GAP",
    "ROUTE_ROW_LANE_STEP",
    "RouteAnchor",
    "RowBounds",
    "SNAKE_CELL_HEIGHT",
    "SNAKE_CELL_WIDTH",
    "SNAKE_COLUMNS",
    "SNAKE_ORIGIN_X",
    "SNAKE_ORIGIN_Y",
    "build_edge_routes",
    "build_node_geometries",
    "build_row_bounds",
    "edge_label_position",
    "layout_positions",
    "manual_row_lookup",
    "node_ports",
    "port_point",
    "Rect",
    "route_anchor_id",
    "route_source_anchor_id",
    "route_target_side",
]


def layout_positions(
    graph: FlowGraphDocument,
    layout_mode: str = "snake",
    render_specs: dict[str, NodeRenderSpec] | None = None,
) -> dict[str, tuple[float, float]]:
    return base_layout_positions(graph, layout_mode, render_specs)


def build_edge_routes(
    graph: FlowGraphDocument,
    positions: dict[str, tuple[float, float]],
    render_specs: dict[str, NodeRenderSpec],
    layout_mode: str,
) -> list[EdgeRoute]:
    geometries = build_node_geometries(graph, positions, render_specs, layout_mode)
    return build_edge_routes_for_geometries(graph, geometries, layout_mode)
