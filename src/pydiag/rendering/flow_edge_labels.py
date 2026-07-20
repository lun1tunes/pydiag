from __future__ import annotations

from math import hypot

from .flow_layout_positions import node_ports
from .flow_route_geometry import EdgeRoute, NodeGeometry, Point, port_point

EDGE_LABEL_GAP = 12
EDGE_LABEL_HEIGHT = 24
EDGE_LABEL_ROUTE_SIDE_GAP = 22

__all__ = [
    "EDGE_LABEL_GAP",
    "EDGE_LABEL_HEIGHT",
    "EDGE_LABEL_ROUTE_SIDE_GAP",
    "edge_label_position",
]


def edge_label_position(
    route: EdgeRoute,
    source: NodeGeometry,
    target: NodeGeometry,
    label_width: int,
    layout_mode: str,
) -> tuple[float, float]:
    source_side = route.source_side
    if route.edge.kind in {"yes", "no"} and (route.source_anchor is not None or route.anchors):
        return fallback_edge_label_position(
            source,
            label_width,
            layout_mode,
            route.edge.kind,
            source_side,
        )

    target_side = route.target_side
    points = (
        route.source_anchor.pos
        if route.source_anchor is not None
        else port_point(source, source_side),
        *(anchor.pos for anchor in route.anchors),
        port_point(target, target_side),
    )
    start, end = label_segment(
        points,
        label_width,
        prefer_horizontal=bool(route.anchors and route.edge.kind == "no"),
    )
    segment_dx = end[0] - start[0]
    segment_dy = end[1] - start[1]
    segment_length = hypot(segment_dx, segment_dy)
    if segment_length <= 0:
        return fallback_edge_label_position(source, label_width, layout_mode, route.edge.kind)

    unit = (segment_dx / segment_length, segment_dy / segment_length)
    along = min(
        max(EDGE_LABEL_GAP + EDGE_LABEL_HEIGHT, segment_length * 0.34),
        max(EDGE_LABEL_GAP, segment_length - EDGE_LABEL_GAP),
    )
    center = (start[0] + unit[0] * along, start[1] + unit[1] * along)

    if abs(segment_dy) >= abs(segment_dx):
        x = (
            center[0] + EDGE_LABEL_ROUTE_SIDE_GAP
            if route.edge.kind == "yes"
            else center[0] - label_width - EDGE_LABEL_ROUTE_SIDE_GAP
        )
        return (x, center[1] - EDGE_LABEL_HEIGHT / 2)

    y = (
        center[1] + EDGE_LABEL_GAP
        if route.edge.kind == "yes"
        else center[1] - EDGE_LABEL_HEIGHT - EDGE_LABEL_GAP
    )
    return (center[0] - label_width / 2, y)


def label_segment(
    points: tuple[Point, ...],
    label_width: int,
    prefer_horizontal: bool = False,
) -> tuple[Point, Point]:
    segments = list(zip(points[:-1], points[1:], strict=True))
    meaningful_length = max(label_width + EDGE_LABEL_ROUTE_SIDE_GAP, EDGE_LABEL_HEIGHT * 2)
    if prefer_horizontal:
        for start, end in segments:
            length = hypot(end[0] - start[0], end[1] - start[1])
            if abs(end[0] - start[0]) >= abs(end[1] - start[1]) and length >= meaningful_length:
                return start, end
    for start, end in segments:
        if hypot(end[0] - start[0], end[1] - start[1]) >= meaningful_length:
            return start, end
    return max(
        segments,
        key=lambda item: hypot(item[1][0] - item[0][0], item[1][1] - item[0][1]),
    )


def fallback_edge_label_position(
    source: NodeGeometry,
    label_width: int,
    layout_mode: str,
    edge_kind: str,
    source_side: str | None = None,
) -> tuple[float, float]:
    explicit_source_side = source_side is not None
    source_side = source_side or node_ports(source.index, layout_mode)[0]
    branch_offset = 0 if explicit_source_side else EDGE_LABEL_HEIGHT * 0.72
    if source_side == "left":
        y = source.center_y - EDGE_LABEL_HEIGHT / 2
        if edge_kind == "yes":
            y += branch_offset
        elif edge_kind == "no":
            y -= branch_offset
        return (
            source.x - EDGE_LABEL_GAP - label_width,
            y,
        )
    if source_side == "right":
        y = source.center_y - EDGE_LABEL_HEIGHT / 2
        if edge_kind == "yes":
            y += branch_offset
        elif edge_kind == "no":
            y -= branch_offset
        return (
            source.x + source.width + EDGE_LABEL_GAP,
            y,
        )
    x = source.center_x - label_width / 2
    if edge_kind == "yes":
        x -= label_width * 0.6
    elif edge_kind == "no":
        x += label_width * 0.6
    if source_side == "top":
        return (
            x,
            source.y - EDGE_LABEL_GAP - EDGE_LABEL_HEIGHT,
        )
    return (
        x,
        source.bottom + EDGE_LABEL_GAP,
    )
