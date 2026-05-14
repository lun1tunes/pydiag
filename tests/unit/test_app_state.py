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


def test_route_segment_selection_resolves_to_domain_edge(documents) -> None:
    graph, wells = documents

    selection_kind, selected = streamlit_app.resolve_selection(
        "route::e_input_review::2",
        graph,
        wells,
    )

    assert selection_kind == "edge"
    assert selected is not None
    assert selected.id == "e_input_review"


def test_route_segment_selection_allows_colons_in_domain_edge_id(documents) -> None:
    graph, wells = documents
    graph.edges[0].id = "edge::with::colon"

    selection_kind, selected = streamlit_app.resolve_selection(
        "route::edge::with::colon::2",
        graph,
        wells,
    )

    assert selection_kind == "edge"
    assert selected is not None
    assert selected.id == "edge::with::colon"


def test_admin_password_rejects_short_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_ADMIN_PASSWORD", "123")
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)

    assert streamlit_app.admin_password() == ""
    assert "не короче" in streamlit_app.admin_password_warning()


def test_admin_password_allows_short_value_only_in_explicit_insecure_mode(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PYDIAG_ADMIN_PASSWORD", "123")
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv("PYDIAG_ALLOW_INSECURE_ADMIN", "1")

    assert streamlit_app.admin_password() == "123"
