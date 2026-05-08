from __future__ import annotations

from pydiag.flow_adapter import build_streamlit_edges, build_streamlit_nodes


def test_adapter_builds_domain_nodes_and_well_tokens(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells, selected_id="well::well_1001")
    edges = build_streamlit_edges(graph, active_ids)
    node_ids = {node.id for node in nodes}

    assert "proc_initial_review" in node_ids
    assert "well::well_1001" in node_ids
    assert "e_review_decision" in {edge.id for edge in edges}
    assert active_ids == {node.id for node in graph.nodes}


def test_adapter_search_highlights_matching_well_node(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells, search="1003")
    token = next(node for node in nodes if node.id == "well::well_1003")
    other_token = next(node for node in nodes if node.id == "well::well_1001")

    assert "proc_spud" in active_ids
    assert token.style["opacity"] == 1.0
    assert other_token.style["opacity"] == 0.24

