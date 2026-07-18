from __future__ import annotations

from pydiag.rendering.flow_canvas_payload import build_flow_canvas_payload
from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_route_geometry import port_point


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


def test_flow_canvas_payload_keeps_node_shape_style_without_rectangular_selection_ring(
    documents,
) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells, selected_id="proc_initial_review")
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")

    assert node["selected"] is True
    assert node["style"]["boxShadow"] == "0 12px 26px rgba(15, 23, 42, 0.12)"
    assert "transform" not in node["style"]


def test_flow_canvas_payload_renders_domain_edge_labels_instead_of_fake_nodes(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells)
    edges = {edge["id"]: edge for edge in payload["edges"]}

    assert edges["e_offsets_review"]["label"]["text"] == "контекст"
    assert edges["e_data_yes"]["label"]["text"] == "Да"
    assert edges["e_data_no"]["label"]["text"] == "Нет"
    assert all("label" not in node["id"] for node in payload["nodes"])


def test_flow_canvas_payload_uses_taller_minimum_canvas_height(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells)

    assert payload["canvas"]["height"] >= 828


def test_flow_canvas_payload_uses_route_selected_ports_after_manual_move(documents) -> None:
    graph, wells = documents
    graph = graph.model_copy(deep=True)
    node_by_id = {node.id: node for node in graph.nodes}
    node_by_id["proc_initial_review"].position.x = 800
    node_by_id["proc_initial_review"].position.y = 300
    node_by_id["dec_data_complete"].position.x = 420
    node_by_id["dec_data_complete"].position.y = 110

    snapshot = build_flow_render_snapshot(graph, wells, "manual")
    route = next(item for item in snapshot.routes if item.edge.id == "e_review_decision")
    source = snapshot.geometries[route.edge.source]
    target = snapshot.geometries[route.edge.target]

    payload = build_flow_canvas_payload(graph, wells, layout_mode="manual")
    edge = next(item for item in payload["edges"] if item["id"] == "e_review_decision")

    assert route.source_side == "left"
    assert route.target_side == "right"
    assert edge["points"][0] == {
        "x": round(port_point(source, route.source_side)[0], 2),
        "y": round(port_point(source, route.source_side)[1], 2),
    }
    assert edge["points"][-1] == {
        "x": round(port_point(target, route.target_side)[0], 2),
        "y": round(port_point(target, route.target_side)[1], 2),
    }
