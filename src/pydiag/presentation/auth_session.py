from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from .auth_models import AuthUser

__all__ = [
    "current_auth_user",
    "current_user_is_admin",
    "current_user_is_super_admin",
    "login_user",
    "logout_user",
]


def current_auth_user(session_state: Mapping[str, Any]) -> dict[str, str | bool] | None:
    user = session_state.get("authenticated_user")
    return user if isinstance(user, dict) else None


def current_user_is_admin(session_state: Mapping[str, Any]) -> bool:
    user = current_auth_user(session_state)
    if user is not None:
        return bool(user.get("is_admin", False))
    return bool(session_state.get("admin_authenticated", False))


def current_user_is_super_admin(session_state: Mapping[str, Any]) -> bool:
    user = current_auth_user(session_state)
    return bool(user and user.get("is_super_admin", False))


def login_user(session_state: MutableMapping[str, Any], user: AuthUser) -> None:
    session_state["authenticated_user"] = {
        "username": user.username,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_super_admin": user.is_super_admin,
    }
    session_state["admin_authenticated"] = user.is_admin


def logout_user(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop("authenticated_user", None)
    session_state["admin_authenticated"] = False
