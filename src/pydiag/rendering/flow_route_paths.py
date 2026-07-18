from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from heapq import heappop, heappush

from pydiag.domain.models import FlowEdge, FlowGraphDocument

from .flow_layout_positions import build_row_bounds, node_ports
from .flow_route_geometry import (
    EdgeRoute,
    NodeGeometry,
    Point,
    Rect,
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
from .flow_route_ports import (
    edge_source_anchor,
    ordered_route_source_sides,
    ordered_route_target_sides,
    route_source_side,
    route_target_side,
)

__all__ = [
    "build_edge_routes_for_geometries",
    "direct_route_obstacles",
]

ROUTE_GRAPH_PADDING = 28
ROUTE_LINE_EPSILON = 1.0
ROUTE_BEND_PENALTY = 24.0
ROUTE_PORT_PREFERENCE_PENALTY = 16.0


def build_edge_routes_for_geometries(
    graph: FlowGraphDocument,
    geometries: Mapping[str, NodeGeometry],
    layout_mode: str,
) -> list[EdgeRoute]:
    bounds = build_row_bounds(geometries) if layout_mode == "snake" else {}
    routes: list[EdgeRoute] = []
    self_loop_counts: dict[str, int] = defaultdict(int)
    row_lane_counts: dict[tuple[int, str], int] = defaultdict(int)

    for edge in graph.edges:
        source = geometries[edge.source]
        target = geometries[edge.target]
        source_side = route_source_side(edge, source, target, layout_mode)
        target_side = route_target_side(target, layout_mode)
        source_anchor = edge_source_anchor(edge, source, source_side)
        if layout_mode == "snake" and should_use_route_anchors(source, target):
            anchors = cycle_route_anchors(
                edge,
                source,
                target,
                bounds,
                row_lane_counts,
                source_side,
                target_side,
            )
        elif layout_mode == "snake" and direct_route_obstacles(
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
        elif source.id == target.id:
            lane_index = self_loop_counts[edge.source]
            self_loop_counts[edge.source] += 1
            anchors = self_loop_route_anchors(edge, source, lane_index)
        elif layout_mode in {"manual", "custom"}:
            resolved = orthogonal_route_for_edge(
                edge,
                source,
                target,
                geometries,
                layout_mode,
            )
            if resolved is not None:
                source_side, target_side, anchors = resolved
                source_anchor = edge_source_anchor(edge, source, source_side)
            else:
                anchors = ()
        else:
            anchors = ()
        routes.append(
            EdgeRoute(
                edge=edge,
                source_side=source_side,
                target_side=target_side,
                anchors=anchors,
                source_anchor=source_anchor,
            )
        )
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


def orthogonal_route_for_edge(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    geometries: Mapping[str, NodeGeometry],
    layout_mode: str,
) -> tuple[str, str, tuple[RouteAnchor, ...]] | None:
    all_obstacles = routing_obstacles(source, target, geometries)
    source_options = ordered_route_source_sides(edge, source, target, layout_mode)
    target_options = ordered_route_target_sides(edge, source, target, layout_mode)
    preferred_route = quick_preferred_route(
        edge,
        source,
        target,
        all_obstacles,
        source_options[0],
        target_options[0],
    )
    if preferred_route is not None:
        return preferred_route
    best_route = best_orthogonal_route_for_edge(
        edge,
        source,
        target,
        all_obstacles,
        source_options,
        target_options,
        use_all_obstacles=False,
    )
    if best_route is not None:
        return best_route
    return best_orthogonal_route_for_edge(
        edge,
        source,
        target,
        all_obstacles,
        source_options,
        target_options,
        use_all_obstacles=True,
    )


def best_orthogonal_route_for_edge(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    all_obstacles: tuple[Rect, ...],
    source_options: tuple[str, ...],
    target_options: tuple[str, ...],
    *,
    use_all_obstacles: bool,
) -> tuple[str, str, tuple[RouteAnchor, ...]] | None:
    best_route: tuple[float, str, str, tuple[RouteAnchor, ...]] | None = None

    for source_rank, source_side in enumerate(source_options):
        source_port = port_point(source, source_side)
        source_exit = offset_point(source_port, source_side, ROUTE_OBSTACLE_MARGIN)
        source_anchor = edge_source_anchor(edge, source, source_side)
        start = source_anchor.pos if source_anchor is not None else source_port
        for target_rank, target_side in enumerate(target_options):
            target_port = port_point(target, target_side)
            target_entry = offset_point(target_port, target_side, ROUTE_OBSTACLE_MARGIN)
            result = orthogonal_route_for_sides(
                source_exit,
                target_entry,
                source_port=start,
                target_port=target_port,
                all_obstacles=all_obstacles,
                use_all_obstacles=use_all_obstacles,
            )
            if result is None:
                continue
            waypoints, route_cost = result
            anchors = route_waypoints_to_anchors(edge, waypoints, source_side, target_side)
            total_cost = (
                route_cost
                + orthogonal_terminal_cost(start, waypoints[0])
                + orthogonal_terminal_cost(waypoints[-1], target_port)
                + (source_rank + target_rank) * ROUTE_PORT_PREFERENCE_PENALTY
            )
            if best_route is None or total_cost < best_route[0]:
                best_route = (total_cost, source_side, target_side, anchors)

    if best_route is None:
        return None
    return best_route[1], best_route[2], best_route[3]


def quick_preferred_route(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    all_obstacles: tuple[Rect, ...],
    source_side: str,
    target_side: str,
) -> tuple[str, str, tuple[RouteAnchor, ...]] | None:
    source_port = port_point(source, source_side)
    source_exit = offset_point(source_port, source_side, ROUTE_OBSTACLE_MARGIN)
    target_port = port_point(target, target_side)
    target_entry = offset_point(target_port, target_side, ROUTE_OBSTACLE_MARGIN)
    waypoints = quick_orthogonal_route(source_exit, target_entry, all_obstacles)
    if waypoints is None:
        return None
    points = full_route_points(source_port, waypoints, target_port)
    if not orthogonal_candidate_clear(points, all_obstacles):
        return None
    return (
        source_side,
        target_side,
        route_waypoints_to_anchors(edge, waypoints, source_side, target_side),
    )


def orthogonal_route_for_sides(
    start: Point,
    end: Point,
    *,
    source_port: Point,
    target_port: Point,
    all_obstacles: tuple[Rect, ...],
    use_all_obstacles: bool,
) -> tuple[tuple[Point, ...], float] | None:
    obstacles = all_obstacles if use_all_obstacles else bounded_routing_obstacles(start, end, all_obstacles)
    result = orthogonal_route_between_points(start, end, obstacles)
    if result is None:
        return None
    if full_route_clear(source_port, result[0], target_port, all_obstacles):
        return result
    return None


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


def routing_obstacles(
    source: NodeGeometry,
    target: NodeGeometry,
    geometries: Mapping[str, NodeGeometry],
) -> tuple[Rect, ...]:
    return tuple(
        node_rect(geometry, ROUTE_OBSTACLE_MARGIN)
        for geometry in geometries.values()
        if geometry.id not in {source.id, target.id}
    )


def bounded_routing_obstacles(
    start: Point,
    end: Point,
    obstacles: tuple[Rect, ...],
) -> tuple[Rect, ...]:
    left = min(start[0], end[0]) - ROUTE_GRAPH_PADDING
    right = max(start[0], end[0]) + ROUTE_GRAPH_PADDING
    top = min(start[1], end[1]) - ROUTE_GRAPH_PADDING
    bottom = max(start[1], end[1]) + ROUTE_GRAPH_PADDING
    return tuple(
        rect
        for rect in obstacles
        if rect.right >= left and rect.left <= right and rect.bottom >= top and rect.top <= bottom
    )


def orthogonal_route_between_points(
    start: Point,
    end: Point,
    obstacles: tuple[Rect, ...],
) -> tuple[tuple[Point, ...], float] | None:
    if start == end:
        return ((start,), 0.0)
    quick_route = quick_orthogonal_route(start, end, obstacles)
    if quick_route is not None:
        simplified = simplify_waypoints(quick_route)
        return simplified, orthogonal_path_cost(simplified)

    points = orthogonal_route_points(start, end, obstacles)
    point_to_index = {point: index for index, point in enumerate(points)}
    adjacency = orthogonal_route_adjacency(points, obstacles)
    end_index = point_to_index[end]
    queue: list[tuple[float, int, str | None]] = [(0.0, point_to_index[start], None)]
    costs: dict[tuple[int, str | None], float] = {(point_to_index[start], None): 0.0}
    parents: dict[tuple[int, str | None], tuple[int, str | None] | None] = {
        (point_to_index[start], None): None
    }
    best_state: tuple[int, str | None] | None = None

    while queue:
        current_cost, point_index, direction = heappop(queue)
        state = (point_index, direction)
        if current_cost > costs.get(state, float("inf")):
            continue
        if point_index == end_index:
            best_state = state
            break
        for next_index, next_direction, segment_length in adjacency[point_index]:
            bend_penalty = (
                ROUTE_BEND_PENALTY
                if direction is not None and direction != next_direction
                else 0.0
            )
            next_cost = current_cost + segment_length + bend_penalty
            next_state = (next_index, next_direction)
            if next_cost >= costs.get(next_state, float("inf")):
                continue
            costs[next_state] = next_cost
            parents[next_state] = state
            heappush(queue, (next_cost, next_index, next_direction))

    if best_state is None:
        return None

    ordered: list[Point] = []
    state: tuple[int, str | None] | None = best_state
    while state is not None:
        ordered.append(points[state[0]])
        state = parents[state]
    ordered.reverse()
    simplified = simplify_waypoints(tuple(ordered))
    return simplified, costs[best_state]


def quick_orthogonal_route(
    start: Point,
    end: Point,
    obstacles: tuple[Rect, ...],
) -> tuple[Point, ...] | None:
    candidates = [
        (start, end),
        (start, (start[0], end[1]), end),
        (start, (end[0], start[1]), end),
    ]
    if start[0] != end[0] and start[1] != end[1]:
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        candidates.extend(
            [
                (start, (mid_x, start[1]), (mid_x, end[1]), end),
                (start, (start[0], mid_y), (end[0], mid_y), end),
            ]
        )

    for candidate in candidates:
        simplified = simplify_waypoints(candidate)
        if orthogonal_candidate_clear(simplified, obstacles):
            return simplified
    return None


def orthogonal_candidate_clear(
    points: tuple[Point, ...],
    obstacles: tuple[Rect, ...],
) -> bool:
    for point in points[1:-1]:
        if point_blocked(point, obstacles):
            return False
    return all(
        segment_clear(start, end, obstacles)
        for start, end in zip(points[:-1], points[1:], strict=True)
    )


def full_route_clear(
    source_port: Point,
    waypoints: tuple[Point, ...],
    target_port: Point,
    obstacles: tuple[Rect, ...],
) -> bool:
    return orthogonal_candidate_clear(
        full_route_points(source_port, waypoints, target_port),
        obstacles,
    )


def full_route_points(
    source_port: Point,
    waypoints: tuple[Point, ...],
    target_port: Point,
) -> tuple[Point, ...]:
    return (source_port, *waypoints, target_port)


def orthogonal_route_points(
    start: Point,
    end: Point,
    obstacles: tuple[Rect, ...],
) -> tuple[Point, ...]:
    x_min_candidates = [start[0], end[0], *(rect.left for rect in obstacles)]
    x_max_candidates = [start[0], end[0], *(rect.right for rect in obstacles)]
    y_min_candidates = [start[1], end[1], *(rect.top for rect in obstacles)]
    y_max_candidates = [start[1], end[1], *(rect.bottom for rect in obstacles)]
    min_x = min(x_min_candidates)
    max_x = max(x_max_candidates)
    min_y = min(y_min_candidates)
    max_y = max(y_max_candidates)
    x_coords = {
        start[0],
        end[0],
        min_x - ROUTE_GRAPH_PADDING,
        max_x + ROUTE_GRAPH_PADDING,
    }
    y_coords = {
        start[1],
        end[1],
        min_y - ROUTE_GRAPH_PADDING,
        max_y + ROUTE_GRAPH_PADDING,
    }
    for rect in obstacles:
        x_coords.add(rect.left - ROUTE_LINE_EPSILON)
        x_coords.add(rect.right + ROUTE_LINE_EPSILON)
        y_coords.add(rect.top - ROUTE_LINE_EPSILON)
        y_coords.add(rect.bottom + ROUTE_LINE_EPSILON)

    points: set[Point] = {start, end}
    for x in x_coords:
        for y in y_coords:
            point = (x, y)
            if point in points or not point_blocked(point, obstacles):
                points.add(point)
    return tuple(sorted(points))


def point_blocked(point: Point, obstacles: tuple[Rect, ...]) -> bool:
    return any(
        rect.left <= point[0] <= rect.right and rect.top <= point[1] <= rect.bottom
        for rect in obstacles
    )


def orthogonal_route_adjacency(
    points: tuple[Point, ...],
    obstacles: tuple[Rect, ...],
) -> dict[int, list[tuple[int, str, float]]]:
    adjacency: dict[int, list[tuple[int, str, float]]] = {index: [] for index in range(len(points))}
    grouped_by_x: dict[float, list[tuple[float, int]]] = defaultdict(list)
    grouped_by_y: dict[float, list[tuple[float, int]]] = defaultdict(list)
    for index, point in enumerate(points):
        grouped_by_x[point[0]].append((point[1], index))
        grouped_by_y[point[1]].append((point[0], index))

    for grouped in grouped_by_x.values():
        ordered = sorted(grouped)
        for (_, first_index), (_, second_index) in zip(ordered, ordered[1:]):
            first = points[first_index]
            second = points[second_index]
            if segment_clear(first, second, obstacles):
                length = abs(second[1] - first[1])
                adjacency[first_index].append((second_index, "v", length))
                adjacency[second_index].append((first_index, "v", length))

    for grouped in grouped_by_y.values():
        ordered = sorted(grouped)
        for (_, first_index), (_, second_index) in zip(ordered, ordered[1:]):
            first = points[first_index]
            second = points[second_index]
            if segment_clear(first, second, obstacles):
                length = abs(second[0] - first[0])
                adjacency[first_index].append((second_index, "h", length))
                adjacency[second_index].append((first_index, "h", length))
    return adjacency


def segment_clear(
    start: Point,
    end: Point,
    obstacles: tuple[Rect, ...],
) -> bool:
    return not any(line_intersects_rect(start, end, obstacle) for obstacle in obstacles)


def orthogonal_path_cost(points: tuple[Point, ...]) -> float:
    distance = 0.0
    turns = 0
    previous_direction: str | None = None
    for start, end in zip(points[:-1], points[1:], strict=True):
        distance += abs(end[0] - start[0]) + abs(end[1] - start[1])
        current_direction = "h" if start[1] == end[1] else "v"
        if previous_direction is not None and previous_direction != current_direction:
            turns += 1
        previous_direction = current_direction
    return distance + turns * ROUTE_BEND_PENALTY


def orthogonal_terminal_cost(start: Point, end: Point) -> float:
    return abs(end[0] - start[0]) + abs(end[1] - start[1])
