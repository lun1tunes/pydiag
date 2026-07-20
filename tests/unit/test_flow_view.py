from __future__ import annotations

from pydiag.application.flow_view import (
    FLOW_CANVAS_COMPONENT_KEY,
    FLOW_RESPONSIBLE_FILTER_RERUN_REQUEST_KEY,
    FLOW_SELECTION_RERUN_REQUEST_KEY,
    RESPONSIBLE_FILTER_LAST_KEY,
    RESPONSIBLE_FILTER_SESSION_KEY,
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


def test_render_flow_mirrors_legend_responsible_filter_without_full_rerun(
    documents,
) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            FLOW_CANVAS_COMPONENT_KEY: {"responsible_filter": ["planning"]},
            RESPONSIBLE_FILTER_SESSION_KEY: [],
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

    assert captured["payload"]["responsible_filter"] == ["planning"]
    assert captured["kwargs"]["default_responsible_filter"] == ["planning"]
    node = next(
        item
        for item in captured["payload"]["nodes"]
        if item["id"] == "proc_initial_review"
    )
    # Responsible dimming is client-side; payload keeps search/kind active flags.
    assert node["active"] is True
    assert "planning" in node["responsible"]
    assert session_state[RESPONSIBLE_FILTER_SESSION_KEY] == ["planning"]
    assert session_state[RESPONSIBLE_FILTER_LAST_KEY] == ["planning"]
    assert FLOW_RESPONSIBLE_FILTER_RERUN_REQUEST_KEY not in session_state


def test_render_flow_sidebar_filter_wins_over_stale_legend_component_state(
    documents,
) -> None:
    graph, wells = documents
    session_state = FakeSessionState(
        {
            FLOW_CANVAS_COMPONENT_KEY: {"responsible_filter": ["planning"]},
            RESPONSIBLE_FILTER_SESSION_KEY: ["geology"],
            RESPONSIBLE_FILTER_LAST_KEY: ["planning"],
        }
    )
    captured: dict[str, object] = {}

    def fake_render_canvas(payload, **kwargs):
        captured["payload"] = payload
        return {}

    render_flow(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=["geology"],
        kind_filter=[],
        layout_mode="snake",
        position_edit_enabled=False,
        render_canvas=fake_render_canvas,
        component_key=FLOW_CANVAS_COMPONENT_KEY,
    )

    assert captured["payload"]["responsible_filter"] == ["geology"]
    assert session_state[RESPONSIBLE_FILTER_LAST_KEY] == ["geology"]
    assert session_state[FLOW_CANVAS_COMPONENT_KEY]["responsible_filter"] == ["geology"]


def test_responsible_filter_session_key_is_not_canvas_component_field() -> None:
    assert RESPONSIBLE_FILTER_SESSION_KEY == "sidebar_responsible_filter"
    assert RESPONSIBLE_FILTER_SESSION_KEY != "responsible_filter"
