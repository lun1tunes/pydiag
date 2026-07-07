from __future__ import annotations

from pydiag.rendering.flow_canvas_payload import build_flow_canvas_edges_from_snapshot
from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot


def test_build_flow_canvas_edges_from_snapshot_keeps_domain_edge_labels_and_routes(
    documents,
) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")

    edges = build_flow_canvas_edges_from_snapshot(
        snapshot,
        active_node_ids={node.id for node in graph.nodes},
    )
    edge_by_id = {edge["id"]: edge for edge in edges}

    assert edge_by_id["e_offsets_review"]["label"]["text"] == "контекст"
    assert edge_by_id["e_data_yes"]["label"]["text"] == "Да"
    assert edge_by_id["e_data_no"]["label"]["text"] == "Нет"
    assert len(edge_by_id["e_data_yes"]["points"]) > 2
