from __future__ import annotations

from math import hypot

from pydiag.flow_adapter import (
    EDGE_LABEL_GAP,
    EDGE_LABEL_HEIGHT,
    SNAKE_CELL_HEIGHT,
    SNAKE_COLUMNS,
    build_streamlit_edges,
    build_streamlit_nodes,
    flow_canvas_height,
)


def test_adapter_builds_domain_nodes_and_well_tokens(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells, selected_id="well::well_1001")
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    node_ids = {node.id for node in nodes}

    assert "proc_initial_review" in node_ids
    assert "well::well_1001" in node_ids
    assert "e_review_decision" in {edge.id for edge in edges}
    assert active_ids == {node.id for node in graph.nodes}


def test_edges_use_four_domain_kinds_with_usual_black_arrow(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    edge_by_id = {edge.id: edge for edge in edges}

    assert {edge.kind for edge in graph.edges} == {"usual", "dashed", "yes", "no"}
    assert edge_by_id["e_review_decision"].style["stroke"] == "#111827"
    assert edge_by_id["e_review_decision"].marker_end["color"] == "#111827"


def test_domain_edge_labels_are_not_rendered_as_tiny_canvas_bubbles(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")

    assert any(edge.label == "контекст" for edge in graph.edges)
    assert all(edge.label == "" for edge in edges)
    assert all("контекст" not in str(edge.asdict()) for edge in edges)


def test_adapter_search_highlights_matching_well_node(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells, search="1003")
    token = next(node for node in nodes if node.id == "well::well_1003")
    other_token = next(node for node in nodes if node.id == "well::well_1001")

    assert "proc_spud" in active_ids
    assert token.style["opacity"] == 1.0
    assert other_token.style["opacity"] == 0.24


def test_well_tokens_are_light_badges_without_connection_handles(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    token = next(node for node in nodes if node.id == "well::well_1004")
    token_dict = token.asdict()

    assert token_dict["className"] == "well-token-node"
    assert token.connectable is False
    assert token.style["pointerEvents"] == "none"
    assert token.style["width"] == "136px"
    assert token.style["height"] == "42px"
    assert token.style["fontSize"] == "13px"
    assert token.style["fontWeight"] == 750
    assert token.style["lineHeight"] == "1"
    assert "#f0fdfa" in str(token.style["background"])
    assert "react-flow__handle" in token.data["content"]
    assert "well-token-node .markdown-node" in token.data["content"]
    assert "justify-content: center" in token.data["content"]
    assert "Скв." in token.data["content"]


def test_shaped_nodes_use_svg_background_instead_of_clipping(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    input_node = next(node for node in nodes if node.id == "input_geo_license")
    diamond_node = next(node for node in nodes if node.id == "dec_data_complete")
    database_node = next(node for node in nodes if node.id == "db_offset_wells")

    assert input_node.style["border"] == "0"
    assert diamond_node.style["border"] == "0"
    assert database_node.style["border"] == "0"
    assert "clipPath" not in input_node.style
    assert "clipPath" not in diamond_node.style
    assert "clipPath" not in database_node.style
    assert str(input_node.style["backgroundImage"]).startswith('url("data:image/svg+xml,')
    assert str(diamond_node.style["backgroundImage"]).startswith('url("data:image/svg+xml,')
    assert str(database_node.style["backgroundImage"]).startswith('url("data:image/svg+xml,')
    assert "%23000000" in str(diamond_node.style["backgroundImage"])
    assert "stroke-width%3D%271.6%27" in str(diamond_node.style["backgroundImage"])
    assert "vector-effect%3D%27non-scaling-stroke%27" in str(diamond_node.style["backgroundImage"])
    assert "stroke-width%3D%271.6%27" in str(database_node.style["backgroundImage"])
    assert "stroke-width%3D%270.85%27" in str(database_node.style["backgroundImage"])
    assert "L8%2078%20C8%2092%2092%2092%2092%2078%20L92%2020%27" in str(
        database_node.style["backgroundImage"]
    )
    assert "vector-effect%3D%27non-scaling-stroke%27" in str(database_node.style["backgroundImage"])
    assert "%3Cellipse" in str(database_node.style["backgroundImage"])


def test_diamond_text_is_centered_inside_shape(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    diamond_node = next(node for node in nodes if node.id == "dec_operational_issue")
    diamond_dict = diamond_node.asdict()

    assert diamond_dict["className"] == "flow-node flow-node-decision-diamond"
    assert diamond_node.style["display"] == "flex"
    assert diamond_node.style["alignItems"] == "center"
    assert diamond_node.style["justifyContent"] == "center"
    assert diamond_node.style["padding"] == "24px 52px"
    assert "flow-node-decision-diamond .markdown-node" in diamond_node.data["content"]
    assert ".flow-node .markdown-node" in diamond_node.data["content"]
    assert "align-items: center" in diamond_node.data["content"]


def test_compact_input_node_keeps_note_out_of_canvas_content(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    input_node = next(node for node in nodes if node.id == "input_geo_license")

    assert "Контур участка" not in input_node.data["content"]
    assert "Лицензия и исходные геоданные" in input_node.data["content"]
    assert input_node.style["padding"] == "16px 48px"


def test_process_uses_first_responsible_for_color_and_external_secondary_badges(
    documents,
) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    process_node = next(node for node in nodes if node.id == "proc_initial_review")
    duration_node = next(node for node in nodes if node.id == "duration::proc_initial_review")
    geology_badge = next(
        node for node in nodes if node.id == "responsible::proc_initial_review::geology"
    )
    hse_badge = next(node for node in nodes if node.id == "responsible::proc_initial_review::hse")

    assert process_node.style["backgroundColor"] == graph.responsibles["planning"].fill
    assert "process-side-responsibles" not in process_node.data["content"]
    assert "ГЕО" not in process_node.data["content"]
    assert "ПБОТОС" not in process_node.data["content"]
    assert "Планирование" not in process_node.data["content"]
    assert ".react-flow__node.flow-node:hover" in process_node.data["content"]
    assert "outline: 3px solid rgba(20, 184, 166, 0.36)" in process_node.data["content"]
    assert "process-card-content::after" not in process_node.data["content"]
    assert "justify-content: center" in process_node.data["content"]
    assert process_node.style["textAlign"] == "center"
    assert process_node.style["overflow"] == "visible"
    assert geology_badge.asdict()["className"] == "responsible-badge-node"
    assert geology_badge.connectable is False
    assert geology_badge.selectable is False
    assert geology_badge.position["y"] == duration_node.position["y"]
    assert geology_badge.position["x"] > duration_node.position["x"]
    assert hse_badge.position["x"] > geology_badge.position["x"]
    assert geology_badge.style["backgroundColor"] == graph.responsibles["geology"].fill
    assert geology_badge.style["border"] == f"1px solid {graph.responsibles['geology'].border}"
    assert geology_badge.style["color"] == graph.responsibles["geology"].text
    assert "ГЕО" in geology_badge.data["content"]
    assert "ПБОТОС" in hse_badge.data["content"]
    assert "responsible-badge-node .react-flow__handle" in geology_badge.data["content"]


def test_decision_nodes_use_responsibles_for_color_and_external_secondary_badges(
    documents,
) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    diamond_node = next(node for node in nodes if node.id == "dec_data_complete")
    card_node = next(node for node in nodes if node.id == "card_mitigation")
    diamond_badge = next(
        node for node in nodes if node.id == "responsible::dec_data_complete::geology"
    )
    card_badge = next(node for node in nodes if node.id == "responsible::card_mitigation::hse")

    assert f"%23{graph.responsibles['planning'].fill.removeprefix('#')}" in str(
        diamond_node.style["backgroundImage"]
    )
    assert diamond_node.style["color"] == graph.responsibles["planning"].text
    assert "process-side-responsibles" not in diamond_node.data["content"]
    assert "ГЕО" not in diamond_node.data["content"]
    assert "ГЕО" in diamond_badge.data["content"]
    assert card_node.style["backgroundColor"] == graph.responsibles["drilling"].fill
    assert card_node.style["border"] == f"2px solid {graph.responsibles['drilling'].border}"
    assert "ПБОТОС" not in card_node.data["content"]
    assert "ПБОТОС" in card_badge.data["content"]
    assert card_badge.style["backgroundColor"] == graph.responsibles["hse"].fill


def test_event_node_type_has_dedicated_shape_and_filter_label(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells, kind_filter=["event"])
    event_node = next(node for node in nodes if node.id == "event_handover_done")

    assert "event_handover_done" in active_ids
    assert event_node.asdict()["className"] == "flow-node flow-node-event"
    assert event_node.style["borderRadius"] == "32px"
    assert event_node.style["backgroundColor"] == "#ffffff"
    assert event_node.style["border"] == "2px solid #111827"
    assert int(str(event_node.style["width"]).removesuffix("px")) >= 280
    assert int(str(event_node.style["height"]).removesuffix("px")) >= 86
    assert "Скважина передана в эксплуатацию" in event_node.data["content"]


def test_domain_nodes_share_the_same_hover_highlight_css(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    hover_css = "outline: 3px solid rgba(20, 184, 166, 0.36)"
    domain_nodes = [next(item for item in nodes if item.id == node.id) for node in graph.nodes]

    assert domain_nodes
    for node in domain_nodes:
        assert node.asdict()["className"].startswith("flow-node ")
        assert hover_css in node.data["content"]


def test_default_snake_layout_wraps_domain_nodes_into_rows(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    domain_nodes = [next(item for item in nodes if item.id == node.id) for node in graph.nodes]
    first_row = domain_nodes[:SNAKE_COLUMNS]
    second_row = domain_nodes[SNAKE_COLUMNS : SNAKE_COLUMNS * 2]

    assert first_row[0].position["x"] < first_row[-1].position["x"]
    assert second_row[0].position["x"] > second_row[-1].position["x"]
    assert second_row[0].position["y"] - first_row[0].position["y"] >= SNAKE_CELL_HEIGHT
    assert max(node.position["x"] for node in domain_nodes) < 1300
    assert flow_canvas_height(graph, wells, "snake") > 1000


def test_manual_layout_preserves_json_coordinates(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells, layout_mode="manual")
    input_node = next(node for node in nodes if node.id == "input_geo_license")

    assert input_node.position == {
        "x": graph.nodes[0].position.x,
        "y": graph.nodes[0].position.y,
    }


def test_database_node_grows_to_fit_canvas_text(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    database_node = next(node for node in nodes if node.id == "db_contracts")

    assert database_node.style["height"] != "96px"
    assert int(str(database_node.style["height"]).removesuffix("px")) >= 158
    assert database_node.style["padding"] == "38px 40px"
    assert "Договоры и заявки" in database_node.data["content"]


def test_duration_is_compact_and_does_not_use_code_badge(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    node = next(item for item in nodes if item.id == "db_contracts")
    duration = next(item for item in nodes if item.id == "duration::db_contracts")
    duration_dict = duration.asdict()

    assert "TIME" not in node.data["content"]
    assert "`" not in node.data["content"]
    assert "1 ч" not in node.data["content"]
    assert duration_dict["className"] == "duration-badge-node"
    assert duration.connectable is False
    assert duration.selectable is False
    assert duration.style["pointerEvents"] == "none"
    assert duration.style["width"] == "64px"
    assert duration.style["height"] == "24px"
    assert "1 ч" in duration.data["content"]
    assert "duration-badge-content" in duration.data["content"]
    assert "react-flow__handle" in duration.data["content"]


def test_duration_badge_width_grows_for_long_values(documents) -> None:
    graph, wells = documents
    graph.nodes[0].time = "1200 hours"

    nodes, _ = build_streamlit_nodes(graph, wells)
    duration = next(item for item in nodes if item.id == f"duration::{graph.nodes[0].id}")

    assert int(str(duration.style["width"]).removesuffix("px")) > 64
    assert "1200 ч" in duration.data["content"]
    assert (
        "1200 ч" not in next(item for item in nodes if item.id == graph.nodes[0].id).data["content"]
    )


def test_cycle_routing_splits_backward_edges_into_helper_lanes(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    node_by_id = {node.id: node for node in nodes}
    edge_by_id = {edge.id: edge for edge in edges}

    assert "route-anchor::e_rework_back::0" in node_by_id
    assert "route-anchor::e_rework_back::1" in node_by_id
    assert node_by_id["route-anchor::e_rework_back::0"].selectable is False
    assert node_by_id["route-anchor::e_rework_back::0"].style["width"] == "0px"
    assert node_by_id["route-anchor::e_rework_back::0"].style["height"] == "0px"
    assert node_by_id["route-anchor::e_rework_back::0"].style["opacity"] == 0.0
    assert node_by_id["route-anchor::e_rework_back::0"].style["visibility"] == "hidden"
    assert node_by_id["route-anchor::e_rework_back::0"].style["fontSize"] == "0"
    assert (
        "react-flow__node-route-anchor-node"
        in node_by_id["route-anchor::e_rework_back::0"].data["content"]
    )
    assert "left: 50%" in node_by_id["route-anchor::e_rework_back::0"].data["content"]
    assert "width: 1px" in node_by_id["route-anchor::e_rework_back::0"].data["content"]
    assert "route::e_rework_back::0" in edge_by_id
    assert "e_rework_back" in edge_by_id
    assert "route::e_rework_back::4" in edge_by_id
    assert edge_by_id["route::e_rework_back::4"].marker_end["type"] == "arrowclosed"
    assert edge_by_id["e_rework_back"].asdict()["data"]["domainEdgeId"] == "e_rework_back"
    assert edge_by_id["e_rework_back"].asdict()["pathOptions"]["offset"] == 22
    assert node_by_id["route-anchor::e_rework_back::0"].position["x"] > 1000
    assert node_by_id["route-anchor::e_rework_back::1"].position["y"] > 240


def test_forward_edges_route_around_intermediate_nodes_without_routing_adjacent_links(
    documents,
) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    node_by_id = {node.id: node for node in nodes}
    edge_by_id = {edge.id: edge for edge in edges}

    assert "e_input_review" in edge_by_id
    assert "route::e_input_review::0" in edge_by_id
    assert "route::e_input_review::4" in edge_by_id
    assert edge_by_id["route::e_input_review::4"].target == "proc_initial_review"
    assert node_by_id["route-anchor::e_input_review::1"].position["y"] > 240
    assert "e_review_decision" in edge_by_id
    assert "route::e_review_decision::0" not in edge_by_id
    assert edge_by_id["e_review_decision"].source == "proc_initial_review"
    assert edge_by_id["e_review_decision"].target == "dec_data_complete"
    assert edge_by_id["e_review_decision"].asdict()["pathOptions"]["offset"] == 14
    assert edge_by_id["e_review_decision"].style["stroke"] == "#111827"


def test_flow_uses_only_four_domain_edge_kinds(documents) -> None:
    graph, _ = documents

    assert {edge.kind for edge in graph.edges} == {"usual", "dashed", "yes", "no"}


def test_direct_yes_no_labels_use_source_near_anchor(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    node_by_id = {node.id: node for node in nodes}
    edge_by_id = {edge.id: edge for edge in edges}

    label_node = node_by_id["edge-label::e_design_yes"]
    source = node_by_id["dec_design_ok"]
    source_width = int(str(source.style["width"]).removesuffix("px"))
    source_height = int(str(source.style["height"]).removesuffix("px"))
    label_width = int(str(label_node.style["width"]).removesuffix("px"))
    label_center = (
        label_node.position["x"] + label_width / 2,
        label_node.position["y"] + EDGE_LABEL_HEIGHT / 2,
    )
    distance_to_source = distance_to_rect(
        label_center,
        (
            source.position["x"],
            source.position["y"],
            source.position["x"] + source_width,
            source.position["y"] + source_height,
        ),
    )

    assert edge_by_id["e_design_yes"].source == "dec_design_ok"
    assert edge_by_id["e_design_yes"].target == "proc_procurement"
    assert edge_by_id["e_design_yes"].label == ""
    assert edge_by_id["e_design_yes"].marker_end["type"] == "arrowclosed"
    assert edge_by_id["e_design_yes"].style["stroke"] == "#16834a"
    assert label_node.connectable is False
    assert label_node.selectable is False
    assert "Да" in label_node.data["content"]
    assert distance_to_source <= label_width + EDGE_LABEL_GAP + 1

    no_label_node = node_by_id["edge-label::e_design_no"]
    no_segments = [edge for edge in edges if edge.asdict()["data"]["domainEdgeId"] == "e_design_no"]
    assert "Нет" in no_label_node.data["content"]
    assert abs(no_label_node.position["y"] - label_node.position["y"]) > EDGE_LABEL_HEIGHT
    assert no_label_node.position["x"] > source.position["x"] + source_width
    assert no_label_node.position["y"] < source.position["y"]
    assert {segment.style["stroke"] for segment in no_segments} == {"#c2410c"}
    assert all(
        not segment.marker_end or segment.marker_end["color"] == "#c2410c"
        for segment in no_segments
    )


def test_issue_no_branch_routes_around_mitigation_card(documents) -> None:
    graph, wells = documents

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells, layout_mode="snake")
    node_by_id = {node.id: node for node in nodes}
    edge_by_id = {edge.id: edge for edge in edges}

    assert "route-anchor::e_issue_no::0" in node_by_id
    assert "route-anchor::e_issue_no::3" in node_by_id
    assert "e_issue_no" in edge_by_id
    assert edge_by_id["e_issue_no"].label == ""
    assert edge_by_id["e_issue_no"].source == "dec_operational_issue"
    assert edge_by_id["e_issue_no"].target == "route-anchor::e_issue_no::0"
    assert "Нет" in node_by_id["edge-label::e_issue_no"].data["content"]
    assert "route::e_issue_no::4" in edge_by_id
    assert edge_by_id["route::e_issue_no::4"].target == "proc_drilling_complete"
    assert "route::e_issue_yes::0" not in edge_by_id

    mitigation = node_by_id["card_mitigation"]
    mitigation_top = mitigation.position["y"]
    mitigation_bottom = mitigation_top + int(str(mitigation.style["height"]).removesuffix("px"))
    for anchor_id in ("route-anchor::e_issue_no::1", "route-anchor::e_issue_no::2"):
        lane_y = node_by_id[anchor_id].position["y"] + 1
        assert lane_y < mitigation_top or lane_y > mitigation_bottom


def distance_to_rect(
    point: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> float:
    left, top, right, bottom = rect
    dx = max(left - point[0], 0, point[0] - right)
    dy = max(top - point[1], 0, point[1] - bottom)
    return hypot(dx, dy)


def test_empty_active_node_set_keeps_all_edges_dimmed(documents) -> None:
    graph, wells = documents

    edges = build_streamlit_edges(graph, active_node_ids=set(), wells_doc=wells)

    assert edges
    assert {edge.style["opacity"] for edge in edges} == {0.12}


def test_self_loop_edges_get_explicit_loop_route(documents) -> None:
    graph, wells = documents
    loop_edge = graph.edges[0].model_copy(
        update={
            "id": "e_self_loop",
            "source": graph.nodes[0].id,
            "target": graph.nodes[0].id,
            "label": "повтор",
        }
    )
    graph.edges = [loop_edge]

    nodes, active_ids = build_streamlit_nodes(graph, wells)
    edges = build_streamlit_edges(graph, active_ids, wells_doc=wells)
    node_ids = {node.id for node in nodes}
    edge_by_id = {edge.id: edge for edge in edges}

    assert "route-anchor::e_self_loop::0" in node_ids
    assert "route-anchor::e_self_loop::1" in node_ids
    assert "route-anchor::e_self_loop::2" in node_ids
    assert "route::e_self_loop::0" in edge_by_id
    assert "e_self_loop" in edge_by_id
    assert "route::e_self_loop::3" in edge_by_id
    assert edge_by_id["route::e_self_loop::3"].marker_end["type"] == "arrowclosed"
