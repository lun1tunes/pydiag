from __future__ import annotations

from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_streamlit_nodes import (
    route_anchor_nodes_for_route,
    route_label_node_for_route,
)


def test_route_anchor_nodes_for_route_include_branch_and_intermediate_anchors(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")
    route = next(item for item in snapshot.routes if item.edge.id == "e_data_yes")

    anchor_nodes = route_anchor_nodes_for_route(route)

    assert route.source_anchor is not None
    assert len(anchor_nodes) == 1 + len(route.anchors)
    assert anchor_nodes[0].id == route.source_anchor.id
    assert anchor_nodes[0].asdict()["className"] == "branch-anchor-node"
    assert all(node.asdict()["className"] == "route-anchor-node" for node in anchor_nodes[1:])


def test_route_label_node_for_route_only_builds_decision_labels(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")
    yes_route = next(item for item in snapshot.routes if item.edge.id == "e_data_yes")
    usual_route = next(item for item in snapshot.routes if item.edge.kind == "usual")

    label_node = route_label_node_for_route(
        yes_route, snapshot.geometries, set(), snapshot.layout_mode
    )

    assert label_node is not None
    assert label_node.id == "edge-label::e_data_yes"
    assert label_node.style["opacity"] == 0.24
    assert (
        route_label_node_for_route(
            usual_route,
            snapshot.geometries,
            {node.id for node in snapshot.graph.nodes},
            snapshot.layout_mode,
        )
        is None
    )
