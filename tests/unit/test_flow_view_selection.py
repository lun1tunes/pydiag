from __future__ import annotations

from pydiag.application.flow_view_selection import (
    component_state_from_session,
    resolve_selected_id,
    sync_returned_selected_id,
)


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_component_state_from_session_ignores_non_mapping_values() -> None:
    session_state = FakeSessionState({"well_drilling_flow_canvas": ["bad-state"]})

    assert component_state_from_session(session_state, "well_drilling_flow_canvas") is None


def test_resolve_selected_id_falls_back_to_session_when_component_has_no_selection(
    documents,
) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            "well_drilling_flow_canvas": {"positions": {}},
            "selected_id": "proc_initial_review",
        }
    )

    selected_id = resolve_selected_id(
        session_state,
        graph,
        wells,
        component_state_from_session(session_state, "well_drilling_flow_canvas"),
    )

    assert selected_id == "proc_initial_review"
    assert session_state["selected_id"] == "proc_initial_review"


def test_resolve_selected_id_allows_component_to_clear_selection(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            "well_drilling_flow_canvas": {"selected_id": None},
            "selected_id": "proc_initial_review",
        }
    )

    selected_id = resolve_selected_id(
        session_state,
        graph,
        wells,
        component_state_from_session(session_state, "well_drilling_flow_canvas"),
    )

    assert selected_id is None
    assert session_state["selected_id"] is None


def test_sync_returned_selected_id_updates_session_when_selection_changes(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState({"selected_id": "proc_initial_review"})

    selected_id = sync_returned_selected_id(
        session_state,
        graph,
        wells,
        "proc_initial_review",
        {"selected_id": "e_review_decision"},
    )

    assert selected_id == "e_review_decision"
    assert session_state["selected_id"] == "e_review_decision"


def test_sync_returned_selected_id_allows_component_to_clear_session_selection(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState({"selected_id": "proc_initial_review"})

    selected_id = sync_returned_selected_id(
        session_state,
        graph,
        wells,
        "proc_initial_review",
        {"selected_id": None},
    )

    assert selected_id is None
    assert session_state["selected_id"] is None
