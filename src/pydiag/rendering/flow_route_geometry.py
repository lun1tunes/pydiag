from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from pydiag.domain.models import FlowEdge

__all__ = [
    "EdgeRoute",
    "NodeGeometry",
    "Point",
    "Rect",
    "RouteAnchor",
    "RowBounds",
    "distance_to_segment",
    "line_intersects_rect",
    "node_rect",
    "offset_point",
    "opposite_side",
    "outbound_gutter_side",
    "port_point",
    "route_anchor_id",
    "route_source_anchor_id",
    "route_waypoints_to_anchors",
    "row_span_bounds",
    "simplify_waypoints",
]


@dataclass(frozen=True)
class NodeGeometry:
    id: str
    index: int
    x: float
    y: float
    width: int
    height: int
    row: int
    visual_col: int

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class RowBounds:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(frozen=True)
class RouteAnchor:
    id: str
    pos: tuple[float, float]
    source_position: str
    target_position: str


@dataclass(frozen=True)
class EdgeRoute:
    edge: FlowEdge
    source_side: str
    target_side: str
    anchors: tuple[RouteAnchor, ...]
    source_anchor: RouteAnchor | None = None


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


Point = tuple[float, float]


def node_rect(geometry: NodeGeometry, margin: float = 0) -> Rect:
    return Rect(
        left=geometry.x - margin,
        top=geometry.y - margin,
        right=geometry.x + geometry.width + margin,
        bottom=geometry.y + geometry.height + margin,
    )


def port_point(geometry: NodeGeometry, side: str) -> Point:
    if side == "left":
        return (geometry.x, geometry.center_y)
    if side == "right":
        return (geometry.x + geometry.width, geometry.center_y)
    if side == "top":
        return (geometry.center_x, geometry.y)
    return (geometry.center_x, geometry.bottom)


def offset_point(point: Point, side: str, distance: float) -> Point:
    if side == "left":
        return (point[0] - distance, point[1])
    if side == "right":
        return (point[0] + distance, point[1])
    if side == "top":
        return (point[0], point[1] - distance)
    return (point[0], point[1] + distance)


def point_in_rect(point: Point, rect: Rect) -> bool:
    return rect.left <= point[0] <= rect.right and rect.top <= point[1] <= rect.bottom


def line_intersects_rect(start: Point, end: Point, rect: Rect) -> bool:
    if point_in_rect(start, rect) or point_in_rect(end, rect):
        return True

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    near_t = 0.0
    far_t = 1.0
    checks = (
        (-dx, start[0] - rect.left),
        (dx, rect.right - start[0]),
        (-dy, start[1] - rect.top),
        (dy, rect.bottom - start[1]),
    )
    for edge_delta, distance in checks:
        if edge_delta == 0:
            if distance < 0:
                return False
            continue
        t = distance / edge_delta
        if edge_delta < 0:
            if t > far_t:
                return False
            near_t = max(near_t, t)
        else:
            if t < near_t:
                return False
            far_t = min(far_t, t)
    return near_t <= far_t


def distance_to_segment(point: Point, start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    ratio = min(1.0, max(0.0, ratio))
    projection = (start[0] + ratio * dx, start[1] + ratio * dy)
    return hypot(point[0] - projection[0], point[1] - projection[1])


def simplify_waypoints(points: tuple[Point, ...]) -> tuple[Point, ...]:
    if len(points) <= 2:
        return tuple(points)
    simplified = [points[0]]
    for previous, current, next_point in zip(points[:-2], points[1:-1], points[2:], strict=True):
        if is_collinear(previous, current, next_point):
            continue
        simplified.append(current)
    simplified.append(points[-1])
    return tuple(simplified)


def is_collinear(first: Point, second: Point, third: Point) -> bool:
    return (first[0] == second[0] == third[0]) or (first[1] == second[1] == third[1])


def route_waypoints_to_anchors(
    edge: FlowEdge,
    waypoints: tuple[Point, ...],
    source_side: str,
    target_side: str,
) -> tuple[RouteAnchor, ...]:
    anchors: list[RouteAnchor] = []
    for index, point in enumerate(waypoints):
        previous_side = (
            opposite_side(source_side) if index == 0 else side_towards(point, waypoints[index - 1])
        )
        next_side = (
            opposite_side(target_side)
            if index == len(waypoints) - 1
            else side_towards(point, waypoints[index + 1])
        )
        anchors.append(
            RouteAnchor(
                id=route_anchor_id(edge.id, index),
                pos=point,
                source_position=next_side,
                target_position=previous_side,
            )
        )
    return tuple(anchors)


def side_towards(origin: Point, target: Point) -> str:
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def opposite_side(side: str) -> str:
    return {
        "left": "right",
        "right": "left",
        "top": "bottom",
        "bottom": "top",
    }[side]


def row_span_bounds(
    bounds: dict[int, RowBounds],
    source_row: int,
    target_row: int,
) -> RowBounds:
    start = min(source_row, target_row)
    end = max(source_row, target_row)
    selected = [bounds[row] for row in range(start, end + 1) if row in bounds]
    return RowBounds(
        x_min=min(item.x_min for item in selected),
        x_max=max(item.x_max for item in selected),
        y_min=min(item.y_min for item in selected),
        y_max=max(item.y_max for item in selected),
    )


def outbound_gutter_side(source: NodeGeometry) -> str:
    if source.row % 2 == 0:
        return "right"
    return "left"


def route_anchor_id(edge_id: str, index: int) -> str:
    return f"route-anchor::{edge_id}::{index}"


def route_source_anchor_id(edge_id: str) -> str:
    return f"route-anchor::{edge_id}::source"
