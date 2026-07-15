from __future__ import annotations

import json
from types import SimpleNamespace

from pydiag.infrastructure import FileAuthSessionStore
from pydiag.presentation.auth import AuthUser, StreamlitAuthContext
from pydiag.presentation.auth_config import (
    admin_password,
    admin_password_warning,
    auth_config_warning,
    authenticate_user,
    configured_auth_users,
)
from pydiag.presentation.auth_session import (
    current_user_is_admin,
    current_user_is_super_admin,
    login_user,
)


def fake_st_module(
    *,
    session_state: dict | None = None,
    secrets: dict | None = None,
    cookies: dict | None = None,
    headers: dict | None = None,
    url: str | None = "https://pydiag.example/app",
):
    html_calls: list[tuple[str, dict[str, object]]] = []

    def html(body: str, **kwargs) -> None:
        html_calls.append((body, kwargs))

    return SimpleNamespace(
        session_state=session_state or {},
        secrets=secrets or {},
        context=SimpleNamespace(
            cookies=cookies or {},
            headers=headers or {},
            url=url,
        ),
        html=html,
        html_calls=html_calls,
    )


def test_admin_password_rejects_short_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_ADMIN_PASSWORD", "123")
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)

    st_module = fake_st_module()

    assert admin_password(st_module) == ""
    assert "не короче" in admin_password_warning(st_module)


def test_admin_password_allows_short_value_only_in_explicit_insecure_mode(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PYDIAG_ADMIN_PASSWORD", "123")
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv("PYDIAG_ALLOW_INSECURE_ADMIN", "1")

    assert admin_password(fake_st_module()) == "123"


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

    users = configured_auth_users(fake_st_module())

    assert users["planner"].display_name == "Иван Планировщик"
    assert users["planner"].is_admin is True


def test_configured_auth_users_marks_super_admin_login(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv(
        "PYDIAG_AUTH_USERS_JSON",
        json.dumps({"super_admin": {"password": "super-strong-pass"}}, ensure_ascii=False),
    )

    users = configured_auth_users(fake_st_module())

    assert users["super_admin"].is_admin is True
    assert users["super_admin"].is_super_admin is True


def test_authenticate_user_checks_username_and_password(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv(
        "PYDIAG_AUTH_USERS_JSON",
        json.dumps({"planner": {"password": "strong-pass"}}, ensure_ascii=False),
    )

    st_module = fake_st_module()
    assert authenticate_user(st_module, "planner", "strong-pass") is not None
    assert authenticate_user(st_module, "planner", "bad-pass") is None
    assert authenticate_user(st_module, "unknown", "strong-pass") is None


def test_login_user_stores_display_name_and_admin_flag() -> None:
    session_state: dict[str, object] = {}

    login_user(
        session_state,
        AuthUser(
            username="planner",
            display_name="Иван Планировщик",
            password="strong-pass",
        ),
    )

    assert session_state["authenticated_user"]["display_name"] == "Иван Планировщик"
    assert current_user_is_admin(session_state) is True
    assert current_user_is_super_admin(session_state) is False


def test_login_user_stores_super_admin_flag() -> None:
    session_state: dict[str, object] = {}

    login_user(
        session_state,
        AuthUser(
            username="super_admin",
            display_name="Super Admin",
            password="super-strong-pass",
            is_super_admin=True,
        ),
    )

    assert current_user_is_admin(session_state) is True
    assert current_user_is_super_admin(session_state) is True


def test_streamlit_auth_context_persists_restores_and_revokes_session(tmp_path) -> None:
    user = AuthUser(
        username="planner",
        display_name="Иван Планировщик",
        password="strong-pass",
    )
    store = FileAuthSessionStore(
        path_fn=lambda: tmp_path / "auth_sessions.json",
        session_id_factory=lambda: "session-001",
    )

    login_module = fake_st_module(session_state={})
    login_context = StreamlitAuthContext(login_module, session_store=store)
    login_context.login_user(user)
    login_context.sync_persistent_auth()

    cookie_name = login_module.session_state["_pydiag_persistent_auth_cookie_name"]
    session_id = login_module.session_state["_pydiag_persistent_auth_session_id"]
    assert session_id == "session-001"
    assert cookie_name.startswith("__Secure-pydiag_auth_")
    assert len(login_module.html_calls) == 1
    assert login_module.html_calls[0][1]["unsafe_allow_javascript"] is True

    restored_module = fake_st_module(
        session_state={},
        secrets={
            "users": {
                "planner": {
                    "password": "strong-pass",
                    "name": "Иван Планировщик",
                }
            }
        },
        cookies={cookie_name: session_id},
    )
    restored_context = StreamlitAuthContext(restored_module, session_store=store)
    restored_context.sync_persistent_auth()

    assert restored_module.session_state["authenticated_user"]["display_name"] == (
        "Иван Планировщик"
    )
    assert len(restored_module.html_calls) == 1

    restored_context.logout_user()
    restored_context.sync_persistent_auth()

    assert "authenticated_user" not in restored_module.session_state
    assert restored_module.session_state["admin_authenticated"] is False
    assert "Max-Age=0" in restored_module.html_calls[-1][0]
    assert store.get_session(session_id, app_scope="https://pydiag.example/app") is None

    stale_cookie_module = fake_st_module(
        session_state=dict(restored_module.session_state),
        secrets=restored_module.secrets,
        cookies={cookie_name: session_id},
    )
    stale_cookie_context = StreamlitAuthContext(stale_cookie_module, session_store=store)
    stale_cookie_context.sync_persistent_auth()

    assert "authenticated_user" not in stale_cookie_module.session_state


def test_streamlit_auth_context_clears_session_after_password_rotation(tmp_path) -> None:
    store = FileAuthSessionStore(
        path_fn=lambda: tmp_path / "auth_sessions.json",
        session_id_factory=lambda: "session-001",
    )
    login_module = fake_st_module(session_state={})
    login_context = StreamlitAuthContext(login_module, session_store=store)
    login_context.login_user(
        AuthUser(
            username="planner",
            display_name="Иван Планировщик",
            password="strong-pass",
        )
    )
    login_context.sync_persistent_auth()

    cookie_name = login_module.session_state["_pydiag_persistent_auth_cookie_name"]
    session_id = login_module.session_state["_pydiag_persistent_auth_session_id"]
    rotated_module = fake_st_module(
        session_state={},
        secrets={
            "users": {
                "planner": {
                    "password": "new-strong-pass",
                    "name": "Иван Планировщик",
                }
            }
        },
        cookies={cookie_name: session_id},
    )

    rotated_context = StreamlitAuthContext(rotated_module, session_store=store)
    rotated_context.sync_persistent_auth()

    assert "authenticated_user" not in rotated_module.session_state
    assert len(rotated_module.html_calls) == 1
    assert "Max-Age=0" in rotated_module.html_calls[0][0]
    assert store.get_session(session_id, app_scope="https://pydiag.example/app") is None


def test_auth_config_warning_mentions_short_user_password(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv("PYDIAG_AUTH_USERS_JSON", json.dumps({"planner": "short"}))
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)

    st_module = fake_st_module()
    assert configured_auth_users(st_module) == {}
    assert "не короче" in auth_config_warning(st_module)
