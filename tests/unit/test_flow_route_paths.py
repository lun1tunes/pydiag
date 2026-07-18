from __future__ import annotations

from pydiag.domain.models import UsualEdge
from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_route_geometry import (
    NodeGeometry,
    line_intersects_rect,
    node_rect,
    port_point,
)
from pydiag.rendering.flow_route_paths import (
    build_edge_routes_for_geometries,
    direct_route_obstacles,
    orthogonal_route_for_edge,
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
    assert len(route_by_edge_id["e_data_yes"].anchors) >= 2
    assert route_by_edge_id["e_review_decision"].anchors == ()


def test_build_edge_routes_for_geometries_reselects_ports_after_manual_move(documents) -> None:
    graph, wells = documents
    graph = graph.model_copy(deep=True)
    node_by_id = {node.id: node for node in graph.nodes}
    node_by_id["proc_initial_review"].position.x = 800
    node_by_id["proc_initial_review"].position.y = 300
    node_by_id["dec_data_complete"].position.x = 420
    node_by_id["dec_data_complete"].position.y = 110

    snapshot = build_flow_render_snapshot(graph, wells, "manual")
    route = next(item for item in snapshot.routes if item.edge.id == "e_review_decision")

    assert route.source_side == "left"
    assert route.target_side == "right"
    assert len(route.anchors) >= 2


def test_orthogonal_route_for_edge_validates_against_obstacles_outside_bounded_window() -> None:
    source = NodeGeometry(id="s", index=0, x=0, y=0, width=100, height=60, row=0, visual_col=0)
    target = NodeGeometry(
        id="t",
        index=1,
        x=227,
        y=248,
        width=100,
        height=60,
        row=0,
        visual_col=1,
    )
    blockers = {
        "b0": NodeGeometry(
            id="b0",
            index=2,
            x=294,
            y=203,
            width=170,
            height=50,
            row=0,
            visual_col=0,
        ),
        "b1": NodeGeometry(
            id="b1",
            index=3,
            x=403,
            y=92,
            width=112,
            height=112,
            row=0,
            visual_col=0,
        ),
        "b2": NodeGeometry(
            id="b2",
            index=4,
            x=463,
            y=6,
            width=160,
            height=66,
            row=0,
            visual_col=0,
        ),
        "b3": NodeGeometry(
            id="b3",
            index=5,
            x=187,
            y=130,
            width=98,
            height=111,
            row=0,
            visual_col=0,
        ),
        "b4": NodeGeometry(
            id="b4",
            index=6,
            x=162,
            y=251,
            width=139,
            height=164,
            row=0,
            visual_col=0,
        ),
        "b5": NodeGeometry(
            id="b5",
            index=7,
            x=136,
            y=-119,
            width=110,
            height=180,
            row=0,
            visual_col=0,
        ),
    }
    edge = UsualEdge(id="e", kind="usual", source="s", target="t", label=None, metadata={})

    route = orthogonal_route_for_edge(
        edge,
        source,
        target,
        {"s": source, "t": target, **blockers},
        "manual",
    )

    assert route is not None
    source_side, target_side, anchors = route
    points = [port_point(source, source_side), *(anchor.pos for anchor in anchors), port_point(target, target_side)]

    for blocker in blockers.values():
        rect = node_rect(blocker, 18)
        assert all(
            not line_intersects_rect(start, end, rect)
            for start, end in zip(points[:-1], points[1:], strict=True)
        )
