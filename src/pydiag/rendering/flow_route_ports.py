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
    "decision_branch_source_side",
    "edge_source_anchor",
    "route_source_side",
    "route_target_side",
]


def route_source_side(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    layout_mode: str,
) -> str:
    if edge.kind in {"yes", "no"}:
        return decision_branch_source_side(edge, source, target, layout_mode)
    source_side, _ = node_ports(source.index, layout_mode)
    return source_side


def route_target_side(target: NodeGeometry, layout_mode: str) -> str:
    _, target_side = node_ports(target.index, layout_mode)
    return target_side


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
