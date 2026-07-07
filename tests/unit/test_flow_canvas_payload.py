from __future__ import annotations

from pydiag.rendering.flow_canvas_payload import build_flow_canvas_payload


def test_flow_canvas_payload_contains_only_domain_nodes_and_edges(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells, selected_id="well::well_1001")

    assert {node["id"] for node in payload["nodes"]} == {node.id for node in graph.nodes}
    assert {edge["id"] for edge in payload["edges"]} == {edge.id for edge in graph.edges}
    assert not any(node["id"].startswith("route-anchor::") for node in payload["nodes"])
    assert not any(node["id"].startswith("edge-label::") for node in payload["nodes"])


def test_flow_canvas_payload_embeds_badges_and_well_tokens_into_domain_node(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells, selected_id="well::well_1001")
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")

    assert node["time_badge"] is not None
    assert node["time_badge"]["text"] == "16 ч"
    assert [badge["abbr"] for badge in node["responsible_badges"]] == ["ГЕО", "ПБОТОС"]
    assert node["well_tokens"][0]["id"] == "well::well_1001"
    assert node["well_tokens"][0]["selected"] is True
    assert node["well_tokens"][0]["style"]["pointerEvents"] == "auto"


def test_flow_canvas_payload_renders_domain_edge_labels_instead_of_fake_nodes(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells)
    edges = {edge["id"]: edge for edge in payload["edges"]}

    assert edges["e_offsets_review"]["label"]["text"] == "контекст"
    assert edges["e_data_yes"]["label"]["text"] == "Да"
    assert edges["e_data_no"]["label"]["text"] == "Нет"
    assert all("label" not in node["id"] for node in payload["nodes"])
