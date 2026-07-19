from __future__ import annotations

from pydiag.application.flow_view import (
    FLOW_CANVAS_COMPONENT_KEY,
    FLOW_SELECTION_RERUN_REQUEST_KEY,
    render_flow,
)


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_render_flow_prefers_component_state_selection(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            FLOW_CANVAS_COMPONENT_KEY: {"selected_id": "e_review_decision"},
            "selected_id": "proc_initial_review",
        }
    )

    selected_id = render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=False,
        render_canvas=lambda *args, **kwargs: {"selected_id": "e_review_decision"},
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert selected_id == "e_review_decision"
    assert session_state["selected_id"] == "e_review_decision"
    assert FLOW_SELECTION_RERUN_REQUEST_KEY not in session_state


def test_render_flow_allows_component_state_to_clear_selection(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            FLOW_CANVAS_COMPONENT_KEY: {"selected_id": None},
            "selected_id": "proc_initial_review",
        }
    )

    selected_id = render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=False,
        render_canvas=lambda *args, **kwargs: {"selected_id": None},
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert selected_id is None
    assert session_state["selected_id"] is None
    assert FLOW_SELECTION_RERUN_REQUEST_KEY not in session_state


def test_render_flow_switches_to_manual_layout_in_position_edit_mode(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()
    captured: dict[str, object] = {}

    def fake_render_canvas(payload, **kwargs):
        captured["payload"] = payload
        captured["default_positions"] = kwargs["default_positions"]
        return {}

    selected_id = render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=True,
        render_canvas=fake_render_canvas,
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert selected_id is None
    assert captured["payload"] is not None
    assert captured["payload"]["layout_mode"] == "manual"
    assert len(captured["default_positions"]) == len(graph.nodes)


def test_render_flow_does_not_pass_persisted_view_state_to_canvas(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            FLOW_CANVAS_COMPONENT_KEY: {
                "view": {"x": 140.12567, "y": -88.33339, "scale": 0.94226},
                "user_moved_view": True,
            }
        }
    )
    captured: dict[str, object] = {}

    def fake_render_canvas(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {}

    render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=False,
        render_canvas=fake_render_canvas,
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert captured["payload"] is not None
    assert "persisted_view_state" not in captured["kwargs"]
    assert "persisted_view_state" not in captured["payload"]


def test_render_flow_does_not_request_rerun_when_selection_is_unchanged(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState({"selected_id": "proc_initial_review"})

    selected_id = render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=False,
        render_canvas=lambda *args, **kwargs: {"selected_id": "proc_initial_review"},
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert selected_id == "proc_initial_review"
    assert FLOW_SELECTION_RERUN_REQUEST_KEY not in session_state
