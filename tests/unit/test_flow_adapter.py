from __future__ import annotations

from pydiag.flow_adapter import (
    SNAKE_CELL_HEIGHT,
    SNAKE_COLUMNS,
    build_streamlit_edges,
    build_streamlit_nodes,
    flow_canvas_height,
)


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


def test_well_tokens_are_light_badges_without_connection_handles(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    token = next(node for node in nodes if node.id == "well::well_1004")
    token_dict = token.asdict()

    assert token_dict["className"] == "well-token-node"
    assert token.connectable is False
    assert token.style["pointerEvents"] == "none"
    assert token.style["width"] == "118px"
    assert token.style["height"] == "36px"
    assert "#f0fdfa" in str(token.style["background"])
    assert "react-flow__handle" in token.data["content"]
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
    assert "%3Cellipse" in str(database_node.style["backgroundImage"])


def test_compact_input_node_keeps_note_out_of_canvas_content(documents) -> None:
    graph, wells = documents

    nodes, _ = build_streamlit_nodes(graph, wells)
    input_node = next(node for node in nodes if node.id == "input_geo_license")

    assert "Контур участка" not in input_node.data["content"]
    assert "Лицензия и исходные геоданные" in input_node.data["content"]


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
    assert int(str(database_node.style["height"]).removesuffix("px")) >= 124
    assert "Единый реестр обеспеченности" in database_node.data["content"]


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
    graph.nodes[0].duration_hours = 1200

    nodes, _ = build_streamlit_nodes(graph, wells)
    duration = next(item for item in nodes if item.id == f"duration::{graph.nodes[0].id}")

    assert int(str(duration.style["width"]).removesuffix("px")) > 64
    assert "1200 ч" in duration.data["content"]
    assert (
        "1200 ч" not in next(item for item in nodes if item.id == graph.nodes[0].id).data["content"]
    )
