from __future__ import annotations

from pydiag.domain.models import FlowEdge

from .flow_layout_positions import node_ports
from .flow_route_geometry import (
    NodeGeometry,
    RouteAnchor,
    opposite_side,
    port_point,
    route_source_anchor_id,
)

__all__ = [
    "resolve_route_sides",
    "decision_branch_source_side",
    "edge_source_anchor",
    "ordered_route_source_sides",
    "ordered_route_target_sides",
    "route_source_side",
    "route_target_side",
]

PORT_SIDE_ORDER = ("right", "left", "bottom", "top")


def route_source_side(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> str:
    return ordered_route_source_sides(edge, source, target, layout_mode)[0]


def route_target_side(target: NodeGeometry, layout_mode: str) -> str:
    _, target_side = node_ports(target.index, layout_mode)
    return target_side


def resolve_route_sides(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> tuple[str, str]:
    return (
        ordered_route_source_sides(edge, source, target, layout_mode)[0],
        ordered_route_target_sides(edge, source, target, layout_mode)[0],
    )


def ordered_route_source_sides(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> tuple[str, ...]:
    directional = directional_source_side(source, target)
    source_side, _ = node_ports(source.index, layout_mode)
    if edge.kind in {"yes", "no"}:
        branch = decision_branch_source_side(edge, source, target, layout_mode)
        return stable_side_order(branch, directional, source_side)
    if layout_mode == "snake":
        return stable_side_order(directional, source_side)
    return stable_side_order(directional)


def ordered_route_target_sides(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> tuple[str, ...]:
    _ = edge
    directional = directional_target_side(source, target)
    _, target_side = node_ports(target.index, layout_mode)
    if layout_mode == "snake":
        return stable_side_order(directional, target_side)
    return stable_side_order(directional)


def decision_branch_source_side(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> str:
    dx = target.center_x - source.center_x
    dy = target.center_y - source.center_y
    if layout_mode != "snake":
        if abs(dy) > abs(dx):
            return "bottom" if dy >= 0 else "top"
        return "right" if dx >= 0 else "left"

    if edge.kind == "yes":
        if source.row != target.row:
            return "bottom" if dy > 0 else "top"
        return "right" if dx >= 0 else "left"

    if source.row == target.row:
        return "top" if source.row > 0 else "bottom"
    if abs(dy) > abs(dx):
        return "right" if dx >= 0 else "left"
    return "right" if dx >= 0 else "left"


def directional_source_side(source: NodeGeometry, target: NodeGeometry) -> str:
    dx = target.center_x - source.center_x
    dy = target.center_y - source.center_y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def directional_target_side(source: NodeGeometry, target: NodeGeometry) -> str:
    dx = source.center_x - target.center_x
    dy = source.center_y - target.center_y
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def stable_side_order(*preferred: str) -> tuple[str, ...]:
    ordered: list[str] = []
    for side in (*preferred, *PORT_SIDE_ORDER):
        if side not in ordered:
            ordered.append(side)
    return tuple(ordered)


def edge_source_anchor(
    edge: FlowEdge,
    source: NodeGeometry,
    source_side: str,
) -> RouteAnchor | None:
    if edge.kind not in {"yes", "no"}:
        return None
    return RouteAnchor(
        id=route_source_anchor_id(edge.id),
        pos=port_point(source, source_side),
        source_position=source_side,
        target_position=opposite_side(source_side),
    )
