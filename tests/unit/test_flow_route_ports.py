from __future__ import annotations

from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_route_ports import (
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
