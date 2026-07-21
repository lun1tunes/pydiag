from __future__ import annotations

from pydiag.presentation.html_utils import safe_text
from pydiag.presentation.inspector_models import (
    build_edge_inspector_model,
    build_node_inspector_model,
    build_overview_rows,
    build_well_inspector_model,
    details_grid_html,
    node_responsible_labels,
)


def test_node_responsible_labels_uses_human_labels(documents) -> None:
    graph, _ = documents
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    assert node_responsible_labels(graph, node) == "Планирование, Геология, ПБОТОС"


def test_build_node_inspector_model_contains_summary_and_tables(documents) -> None:
    graph, wells = documents
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")
    target = next(item for item in graph.nodes if item.id == "dec_data_complete")

    model = build_node_inspector_model(graph, wells, node)

    assert model.section.title == node.text
    assert "Процесс" in model.section.subtitle_html
    assert "Ответственные" in model.section.details_html
    assert any(row["id"] == "well_1001" for row in model.wells_rows)
    assert any(row["куда"] == target.text for row in model.transitions_rows)


def test_build_well_inspector_model_contains_history_rows(documents) -> None:
    graph, wells = documents
    well = next(item for item in wells.wells if item.id == "well_1001")

    model = build_well_inspector_model(graph, well)

    assert model.section.title == well.name
    assert "Текущий этап" in model.section.details_html
    assert model.history_rows
    assert model.history_rows[0]["action"] in {"create", "move", "rollback"}


def test_build_edge_inspector_model_shows_type_only(documents) -> None:
    graph, _ = documents
    edge = next(item for item in graph.edges if item.id == "e_data_yes")

    model = build_edge_inspector_model(graph, edge)

    assert model.section.title == "Да"
    assert "Тип" in model.section.details_html
    assert "Да" in model.section.details_html
    assert "Откуда" not in model.section.details_html
    assert "Куда" not in model.section.details_html


def test_build_overview_rows_only_includes_nodes_with_wells(documents) -> None:
    graph, wells = documents

    rows = build_overview_rows(graph, wells)
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    assert rows
    assert any(row["этап"] == node.text for row in rows)
    assert all(int(row["скважин"]) > 0 for row in rows)


def test_details_grid_html_renders_label_value_cells() -> None:
    html = details_grid_html([("Тип", "Процесс"), ("Скважины", "2")])

    assert html.startswith('<div class="mini-kv">')
    assert "<span>Тип</span><span>Процесс</span>" in html
    assert "<span>Скважины</span><span>2</span>" in html


def test_safe_text_escapes_html_markup() -> None:
    assert safe_text('<b>"x"</b>') == "&lt;b&gt;&quot;x&quot;&lt;/b&gt;"
