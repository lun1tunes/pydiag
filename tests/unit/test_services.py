from __future__ import annotations

import pytest

from pydiag.models import well_by_id
from pydiag.services import create_well, delete_well, move_well_to_node, rollback_well


def test_move_well_uses_only_allowed_graph_edges(documents) -> None:
    graph, wells = documents

    updated = move_well_to_node(
        graph,
        wells,
        well_id="well_1001",
        target_node_id="dec_data_complete",
        actor="pytest",
    )

    original = well_by_id(wells)["well_1001"]
    moved = well_by_id(updated)["well_1001"]
    assert original.current_node_id == "proc_initial_review"
    assert moved.current_node_id == "dec_data_complete"
    assert moved.history[-1].from_node_id == "proc_initial_review"
    assert moved.history[-1].to_node_id == "dec_data_complete"


def test_move_well_rejects_illegal_transition(documents) -> None:
    graph, wells = documents

    with pytest.raises(ValueError, match="Illegal transition"):
        move_well_to_node(
            graph,
            wells,
            well_id="well_1001",
            target_node_id="proc_procurement",
            actor="pytest",
        )


def test_rollback_returns_to_previous_history_node(documents) -> None:
    graph, wells = documents
    moved = move_well_to_node(
        graph,
        wells,
        well_id="well_1001",
        target_node_id="dec_data_complete",
        actor="pytest",
    )

    rolled = rollback_well(moved, well_id="well_1001", actor="pytest")

    assert well_by_id(rolled)["well_1001"].current_node_id == "proc_initial_review"
    assert well_by_id(rolled)["well_1001"].history[-1].action == "rollback"


def test_create_well_adds_initial_history_entry(documents) -> None:
    graph, wells = documents

    updated = create_well(
        graph,
        wells,
        well_id="well_new",
        name="Скв. NEW",
        start_node_id="input_geo_license",
        actor="pytest",
        metadata={"field": "Тестовый куст"},
    )

    created = well_by_id(updated)["well_new"]
    assert created.current_node_id == "input_geo_license"
    assert created.history[0].action == "create"
    assert created.metadata["field"] == "Тестовый куст"


def test_create_well_rejects_duplicate_id(documents) -> None:
    graph, wells = documents

    with pytest.raises(ValueError, match="already exists"):
        create_well(
            graph,
            wells,
            well_id="well_1001",
            name="Duplicate",
            start_node_id="input_geo_license",
            actor="pytest",
        )


def test_delete_well_removes_it_from_document(documents) -> None:
    _, wells = documents

    updated = delete_well(wells, "well_1004")

    assert "well_1004" not in well_by_id(updated)
    assert "well_1004" in well_by_id(wells)

