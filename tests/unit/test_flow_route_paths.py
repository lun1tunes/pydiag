from __future__ import annotations

from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_route_paths import (
    build_edge_routes_for_geometries,
    direct_route_obstacles,
)
from pydiag.rendering.flow_route_ports import route_source_side, route_target_side


def test_direct_route_obstacles_identifies_intermediate_blocking_node(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")
    edge = next(edge for edge in graph.edges if edge.id == "e_issue_no")
    source = snapshot.geometries[edge.source]
    target = snapshot.geometries[edge.target]

    obstacles = direct_route_obstacles(
        source,
        target,
        snapshot.geometries,
        snapshot.layout_mode,
        route_source_side(edge, source, target, snapshot.layout_mode),
        route_target_side(target, snapshot.layout_mode),
    )

    assert [geometry.id for geometry in obstacles] == ["card_mitigation"]


def test_build_edge_routes_for_geometries_keeps_branch_anchor_and_routed_segments(
    documents,
) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")

    routes = build_edge_routes_for_geometries(graph, snapshot.geometries, snapshot.layout_mode)
    route_by_edge_id = {route.edge.id: route for route in routes}

    assert route_by_edge_id["e_data_yes"].source_anchor is not None
    assert route_by_edge_id["e_data_yes"].source_anchor.id == "route-anchor::e_data_yes::source"
    assert len(route_by_edge_id["e_data_yes"].anchors) == 4
    assert len(route_by_edge_id["e_review_decision"].anchors) == 0
