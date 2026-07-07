from __future__ import annotations

import json
from types import SimpleNamespace

from pydiag.presentation.auth import AuthUser
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


def fake_st_module(*, session_state: dict | None = None, secrets: dict | None = None):
    return SimpleNamespace(session_state=session_state or {}, secrets=secrets or {})


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


def test_auth_config_warning_mentions_short_user_password(monkeypatch) -> None:
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.setenv("PYDIAG_AUTH_USERS_JSON", json.dumps({"planner": "short"}))
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)

    st_module = fake_st_module()
    assert configured_auth_users(st_module) == {}
    assert "не короче" in auth_config_warning(st_module)
