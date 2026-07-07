from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from pydiag.domain.models import FlowEdge, FlowGraphDocument

from .flow_layout_positions import build_row_bounds, node_ports
from .flow_route_geometry import (
    EdgeRoute,
    NodeGeometry,
    RouteAnchor,
    RowBounds,
    distance_to_segment,
    line_intersects_rect,
    node_rect,
    offset_point,
    outbound_gutter_side,
    port_point,
    route_anchor_id,
    route_waypoints_to_anchors,
    simplify_waypoints,
)
from .flow_route_lanes import (
    ROUTE_GUTTER_GAP,
    ROUTE_GUTTER_STEP,
    ROUTE_OBSTACLE_MARGIN,
    ROUTE_ROW_LANE_GAP,
    ROUTE_ROW_LANE_STEP,
    local_lane_key,
    row_route_lane_y,
)
from .flow_route_ports import edge_source_anchor, route_source_side, route_target_side

__all__ = [
    "build_edge_routes_for_geometries",
    "direct_route_obstacles",
]


def build_edge_routes_for_geometries(
    graph: FlowGraphDocument,
    geometries: Mapping[str, NodeGeometry],
    layout_mode: str,
) -> list[EdgeRoute]:
    bounds = build_row_bounds(geometries)
    routes: list[EdgeRoute] = []
    row_lane_counts: dict[tuple[int, str], int] = defaultdict(int)

    for edge in graph.edges:
        source = geometries[edge.source]
        target = geometries[edge.target]
        source_side = route_source_side(edge, source, target, layout_mode)
        target_side = route_target_side(target, layout_mode)
        source_anchor = edge_source_anchor(edge, source, source_side)
        if should_use_route_anchors(source, target):
            anchors = cycle_route_anchors(
                edge,
                source,
                target,
                bounds,
                row_lane_counts,
                source_side,
                target_side,
            )
        elif direct_route_obstacles(
            source,
            target,
            geometries,
            layout_mode,
            source_side,
            target_side,
        ):
            lane_key = local_lane_key(source, target, bounds)
            lane_index = row_lane_counts[lane_key]
            row_lane_counts[lane_key] += 1
            anchors = local_row_route_anchors(
                edge,
                source,
                target,
                bounds,
                lane_index,
                source_side,
                target_side,
            )
        else:
            anchors = ()

        routes.append(EdgeRoute(edge=edge, anchors=anchors, source_anchor=source_anchor))
    return routes


def should_use_route_anchors(source: NodeGeometry, target: NodeGeometry) -> bool:
    return source.id == target.id or target.index <= source.index


def cycle_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
    row_lane_counts: dict[tuple[int, str], int],
    source_side: str,
    target_side: str,
) -> tuple[RouteAnchor, ...]:
    if source.id == target.id:
        lane_key = (source.row, "self")
        lane_index = row_lane_counts[lane_key]
        row_lane_counts[lane_key] += 1
        return self_loop_route_anchors(edge, source, lane_index)

    lane_key = local_lane_key(source, target, bounds)
    lane_index = row_lane_counts[lane_key]
    row_lane_counts[lane_key] += 1
    return local_row_route_anchors(
        edge,
        source,
        target,
        bounds,
        lane_index,
        source_side,
        target_side,
    )


def direct_route_obstacles(
    source: NodeGeometry,
    target: NodeGeometry,
    geometries: Mapping[str, NodeGeometry],
    layout_mode: str,
    source_side: str | None = None,
    target_side: str | None = None,
) -> list[NodeGeometry]:
    source_side = source_side or node_ports(source.index, layout_mode)[0]
    target_side = target_side or node_ports(target.index, layout_mode)[1]
    start = port_point(source, source_side)
    end = port_point(target, target_side)
    obstacles = []
    for geometry in geometries.values():
        if geometry.id in {source.id, target.id}:
            continue
        if line_intersects_rect(start, end, node_rect(geometry, ROUTE_OBSTACLE_MARGIN)):
            obstacles.append(geometry)
    return sorted(
        obstacles,
        key=lambda item: distance_to_segment((item.center_x, item.center_y), start, end),
    )


def local_row_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
    lane_index: int,
    source_side: str,
    target_side: str,
) -> tuple[RouteAnchor, ...]:
    source_port = port_point(source, source_side)
    target_port = port_point(target, target_side)
    source_exit = offset_point(source_port, source_side, ROUTE_OBSTACLE_MARGIN)
    target_entry = offset_point(target_port, target_side, ROUTE_OBSTACLE_MARGIN)
    lane_y = row_route_lane_y(source, target, bounds, lane_index)
    waypoints = simplify_waypoints(
        (
            source_exit,
            (source_exit[0], lane_y),
            (target_entry[0], lane_y),
            target_entry,
        )
    )
    return route_waypoints_to_anchors(edge, waypoints, source_side, target_side)


def self_loop_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    lane_index: int,
) -> tuple[RouteAnchor, ...]:
    lane_offset = ROUTE_GUTTER_GAP + lane_index * ROUTE_GUTTER_STEP
    lane_y = source.y - ROUTE_ROW_LANE_GAP - lane_index * ROUTE_ROW_LANE_STEP
    if outbound_gutter_side(source) == "right":
        first_x = source.x + source.width + lane_offset
        second_x = source.x - lane_offset
        first_target = "left"
        first_source = "top"
        middle_source = "left"
        last_target = "right"
        last_source = "bottom"
    else:
        first_x = source.x - lane_offset
        second_x = source.x + source.width + lane_offset
        first_target = "right"
        first_source = "top"
        middle_source = "right"
        last_target = "left"
        last_source = "bottom"

    return (
        RouteAnchor(
            id=route_anchor_id(edge.id, 0),
            pos=(first_x, source.center_y),
            source_position=first_source,
            target_position=first_target,
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 1),
            pos=(first_x, lane_y),
            source_position=middle_source,
            target_position="bottom",
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 2),
            pos=(second_x, lane_y),
            source_position=last_source,
            target_position=last_target,
        ),
    )
