from __future__ import annotations

from pydiag.domain.models import YesEdge
from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_route_geometry import NodeGeometry, port_point
from pydiag.rendering.flow_route_ports import (
    decision_branch_source_side,
    edge_source_anchor,
    route_source_side,
    route_target_side,
)


def test_route_source_side_uses_branch_specific_ports_in_snake_layout(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")

    yes_edge = next(edge for edge in graph.edges if edge.id == "e_design_yes")
    no_edge = next(edge for edge in graph.edges if edge.id == "e_design_no")
    normal_edge = next(edge for edge in graph.edges if edge.id == "e_review_decision")

    yes_source = snapshot.geometries[yes_edge.source]
    yes_target = snapshot.geometries[yes_edge.target]
    no_source = snapshot.geometries[no_edge.source]
    no_target = snapshot.geometries[no_edge.target]
    normal_source = snapshot.geometries[normal_edge.source]
    normal_target = snapshot.geometries[normal_edge.target]

    assert route_source_side(yes_edge, yes_source, yes_target, snapshot.layout_mode) == "bottom"
    assert route_source_side(no_edge, no_source, no_target, snapshot.layout_mode) == "top"
    assert (
        route_source_side(normal_edge, normal_source, normal_target, snapshot.layout_mode)
        == "right"
    )
    assert route_target_side(yes_target, snapshot.layout_mode) == "left"


def test_edge_source_anchor_exists_only_for_decision_branches(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")

    yes_edge = next(edge for edge in graph.edges if edge.id == "e_data_yes")
    usual_edge = next(edge for edge in graph.edges if edge.id == "e_review_decision")
    yes_source = snapshot.geometries[yes_edge.source]
    usual_source = snapshot.geometries[usual_edge.source]
    yes_side = route_source_side(
        yes_edge,
        yes_source,
        snapshot.geometries[yes_edge.target],
        snapshot.layout_mode,
    )

    anchor = edge_source_anchor(yes_edge, yes_source, yes_side)

    assert anchor is not None
    assert anchor.id == "route-anchor::e_data_yes::source"
    assert anchor.source_position == "bottom"
    assert anchor.target_position == "top"
    assert edge_source_anchor(usual_edge, usual_source, "right") is None


def test_manual_decision_branch_prefers_top_vertex_for_above_right_target() -> None:
    source = NodeGeometry("diamond", 0, 100, 200, 360, 220, 0, 0)
    right_target = NodeGeometry("right", 1, 520, 260, 200, 80, 0, 1)
    above_target = NodeGeometry("above", 2, 380, 20, 240, 70, 0, 1)
    yes_right = YesEdge(
        id="e_yes_right",
        kind="yes",
        source="diamond",
        target="right",
    )
    yes_up = YesEdge(
        id="e_yes_up",
        kind="yes",
        source="diamond",
        target="above",
    )

    assert decision_branch_source_side(yes_right, source, right_target, "manual") == "right"
    assert decision_branch_source_side(yes_up, source, above_target, "manual") == "top"


def test_manual_decision_branches_do_not_slot_off_diamond_vertices(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "manual")
    diamond_id = next(
        node.id for node in graph.nodes if node.kind == "decision_diamond"
    )
    branch_routes = [
        route
        for route in snapshot.routes
        if route.edge.source == diamond_id and route.edge.kind in {"yes", "no"}
    ]
    assert branch_routes
    for route in branch_routes:
        assert route.source_slot_offset == (0.0, 0.0)
        start = port_point(snapshot.geometries[diamond_id], route.source_side)
        assert route.source_anchor is not None
        assert route.source_anchor.pos == start
