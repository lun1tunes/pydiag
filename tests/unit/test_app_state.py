from __future__ import annotations

import app as streamlit_app


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_flow_state_timestamp_is_stable_for_same_view(documents, monkeypatch) -> None:
    graph, wells = documents
    session_state = FakeSessionState()
    monkeypatch.setattr(streamlit_app.st, "session_state", session_state)

    first = streamlit_app.flow_state_timestamp(
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )
    session_state["flow_component_timestamp"] = first + 1000

    second = streamlit_app.flow_state_timestamp(
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )

    assert second == first


def test_flow_state_timestamp_changes_only_when_view_signature_changes(
    documents,
    monkeypatch,
) -> None:
    graph, wells = documents
    session_state = FakeSessionState()
    monkeypatch.setattr(streamlit_app.st, "session_state", session_state)

    first = streamlit_app.flow_state_timestamp(
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )
    second = streamlit_app.flow_state_timestamp(
        graph=graph,
        wells=wells,
        search="1001",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )

    assert second > first
