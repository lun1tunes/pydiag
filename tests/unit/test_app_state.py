from __future__ import annotations

import json

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


def test_kind_filter_labels_are_unique() -> None:
    labels = list(streamlit_app.KIND_FILTER_LABELS.values())

    assert len(labels) == len(set(labels))
    assert streamlit_app.KIND_FILTER_LABELS["decision_diamond"] == "Решение (ромб)"
    assert streamlit_app.KIND_FILTER_LABELS["decision_card"] == "Решение (карточка)"
    assert streamlit_app.KIND_FILTER_LABELS["event"] == "Событие"


def test_legend_html_explains_block_types_and_responsible_colors(documents) -> None:
    graph, _ = documents

    html = streamlit_app.legend_html(graph)

    assert "Типы блоков" in html
    assert "Процесс" in html
    assert "Решение" in html
    assert "База данных" in html
    assert "Входные данные" in html
    assert "Событие" in html
    assert "Цвета ответственных" in html
    assert graph.responsibles["planning"].fill in html
    assert graph.responsibles["planning"].border in html
    assert "Планирование" in html
    assert html.count('class="legend-symbol-svg"') == 5
    assert 'fill="#ffffff"' in html
    assert 'stroke="#111827"' in html
    assert "transform:" not in html
    assert "clip-path" not in html
    assert '<polygon points="22,3 40,15 22,27 4,15"' in html
    assert '<polygon points="9,6 40,6 35,24 4,24"' in html
    assert '<rect x="6" y="5" width="32" height="20" rx="10"' in html
    assert '<ellipse cx="22" cy="8"' in html


def test_css_keeps_sidebar_expand_control_available(monkeypatch) -> None:
    rendered: list[str] = []

    def capture_markdown(body: str, *, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        rendered.append(body)

    monkeypatch.setattr(streamlit_app.st, "markdown", capture_markdown)

    streamlit_app.inject_css()

    css = rendered[0]
    header_block = css.split('[data-testid="stHeader"],', maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "display: none" not in header_block
    assert "pointer-events: none" in header_block
    assert '[data-testid="collapsedControl"]' in css
    assert '[data-testid="stExpandSidebarButton"]' in css
    assert '[data-testid="stHeader"] button' in css
    toolbar_block = css.split('[data-testid="stToolbar"] {', maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "display: none" not in toolbar_block


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


def test_configured_auth_users_loads_named_user_from_env(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv(
        "PYDIAG_AUTH_USERS_JSON",
        json.dumps(
            {
                "planner": {
                    "password": "strong-pass",
                    "name": "Иван Планировщик",
                }
            },
            ensure_ascii=False,
        ),
    )

    users = streamlit_app.configured_auth_users()

    assert users["planner"].display_name == "Иван Планировщик"
    assert users["planner"].is_admin is True


def test_authenticate_user_checks_username_and_password(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv(
        "PYDIAG_AUTH_USERS_JSON",
        json.dumps({"planner": {"password": "strong-pass"}}, ensure_ascii=False),
    )

    assert streamlit_app.authenticate_user("planner", "strong-pass") is not None
    assert streamlit_app.authenticate_user("planner", "bad-pass") is None
    assert streamlit_app.authenticate_user("unknown", "strong-pass") is None


def test_login_user_stores_display_name_and_admin_flag(monkeypatch) -> None:
    session_state = FakeSessionState()
    monkeypatch.setattr(streamlit_app.st, "session_state", session_state)

    streamlit_app.login_user(
        streamlit_app.AuthUser(
            username="planner",
            display_name="Иван Планировщик",
            password="strong-pass",
        )
    )

    assert session_state["authenticated_user"]["display_name"] == "Иван Планировщик"
    assert streamlit_app.current_user_is_admin() is True


def test_auth_config_warning_mentions_short_user_password(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv("PYDIAG_AUTH_USERS_JSON", json.dumps({"planner": "short"}))
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)

    assert streamlit_app.configured_auth_users() == {}
    assert "не короче" in streamlit_app.auth_config_warning()
