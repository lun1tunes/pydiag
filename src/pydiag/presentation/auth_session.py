from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping
from typing import Any

from .auth_models import AuthUser

__all__ = [
    "AUTH_COOKIE_SYNC_KEY",
    "DEFAULT_AUTH_SESSION_TTL_SECONDS",
    "clear_persistent_auth_session",
    "consume_persistent_auth_cookie_markup",
    "current_auth_user",
    "current_user_is_admin",
    "current_user_is_super_admin",
    "login_user",
    "logout_user",
    "pending_persistent_auth_cookie_command",
    "persistent_auth_session_id",
    "queue_persistent_auth_cookie_clear",
    "queue_persistent_auth_cookie_set",
    "set_persistent_auth_session",
]

DEFAULT_AUTH_SESSION_TTL_SECONDS = 86_400
AUTH_COOKIE_SYNC_KEY = "_pydiag_auth_cookie_sync"
PERSISTENT_AUTH_SESSION_ID_KEY = "_pydiag_persistent_auth_session_id"
PERSISTENT_AUTH_COOKIE_NAME_KEY = "_pydiag_persistent_auth_cookie_name"
PERSISTENT_AUTH_COOKIE_PATH_KEY = "_pydiag_persistent_auth_cookie_path"


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


def login_user(
    session_state: MutableMapping[str, Any],
    user: AuthUser,
) -> None:
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
    clear_persistent_auth_session(session_state)
    clear_workspace_ui_state(session_state)


def clear_workspace_ui_state(session_state: MutableMapping[str, Any]) -> None:
    """Drop selection/draft/canvas caches so the next login cannot inherit UI state."""
    for key in (
        "selected_id",
        "responsible_filter",
        "sidebar_responsible_filter",
        "_responsible_filter_last",
        "position_edit_positions",
        "position_edit_dirty",
        "well_drilling_flow_canvas",
        "_card_layout_sync_token",
        "_position_edit_rerun_requested",
        "_flow_selection_rerun_requested",
        "_flow_responsible_filter_rerun_requested",
        "_flow_render_snapshot_cache",
        "_flow_edit_undo",
        "_flow_edit_redo",
        "_flow_history_action_request_id",
        "_flow_position_autosave_sig",
        "_flow_skip_position_autosave_once",
        "_flow_inspector_collapsed",
        "_flow_canvas_pending_edge_request_id",
        "_flow_canvas_pending_node_edit_request_id",
        "_flow_canvas_pending_node_edits_request_id",
        "_flow_canvas_pending_node_create_request_id",
        "_flow_canvas_pending_node_creates_request_id",
        "_flow_canvas_pending_edge_edit_request_id",
        "_flow_canvas_pending_edge_edits_request_id",
        "_flow_canvas_pending_process_create_request_id",
        "_flow_canvas_pending_process_edit_request_id",
        "_flow_canvas_pending_process_delete_request_id",
    ):
        session_state.pop(key, None)
    for key in list(session_state):
        if isinstance(key, str) and (
            key.startswith("graph_source_node_") or key.startswith("graph_source_edge_")
        ):
            session_state.pop(key, None)
    session_state["_flow_canvas_session_epoch"] = (
        int(session_state.get("_flow_canvas_session_epoch", 0) or 0) + 1
    )


def set_persistent_auth_session(
    session_state: MutableMapping[str, Any],
    *,
    session_id: str,
    cookie_name: str,
    cookie_path: str,
) -> None:
    session_state[PERSISTENT_AUTH_SESSION_ID_KEY] = session_id
    session_state[PERSISTENT_AUTH_COOKIE_NAME_KEY] = cookie_name
    session_state[PERSISTENT_AUTH_COOKIE_PATH_KEY] = cookie_path


def clear_persistent_auth_session(session_state: MutableMapping[str, Any]) -> None:
    session_state.pop(PERSISTENT_AUTH_SESSION_ID_KEY, None)
    session_state.pop(PERSISTENT_AUTH_COOKIE_NAME_KEY, None)
    session_state.pop(PERSISTENT_AUTH_COOKIE_PATH_KEY, None)


def persistent_auth_session_id(session_state: Mapping[str, Any]) -> str | None:
    value = session_state.get(PERSISTENT_AUTH_SESSION_ID_KEY)
    return value if isinstance(value, str) and value else None


def pending_persistent_auth_cookie_command(
    session_state: Mapping[str, Any],
) -> Mapping[str, str] | None:
    command = session_state.get(AUTH_COOKIE_SYNC_KEY)
    return command if isinstance(command, Mapping) else None


def queue_persistent_auth_cookie_set(
    session_state: MutableMapping[str, Any],
    *,
    cookie_name: str,
    session_id: str,
    cookie_path: str,
    max_age_seconds: int,
) -> None:
    session_state[AUTH_COOKIE_SYNC_KEY] = {
        "action": "set",
        "name": cookie_name,
        "value": session_id,
        "path": cookie_path,
        "max_age": str(max(int(max_age_seconds), 1)),
    }


def queue_persistent_auth_cookie_clear(
    session_state: MutableMapping[str, Any],
    *,
    cookie_name: str,
    cookie_path: str,
) -> None:
    session_state[AUTH_COOKIE_SYNC_KEY] = {
        "action": "clear",
        "name": cookie_name,
        "path": cookie_path,
    }


def consume_persistent_auth_cookie_markup(
    session_state: MutableMapping[str, Any],
) -> str | None:
    command = session_state.pop(AUTH_COOKIE_SYNC_KEY, None)
    if not isinstance(command, Mapping):
        return None

    action = command.get("action")
    if action == "set":
        name = command.get("name")
        value = command.get("value")
        path = command.get("path")
        max_age = command.get("max_age")
        if (
            isinstance(name, str)
            and name
            and isinstance(value, str)
            and value
            and isinstance(path, str)
            and path
            and isinstance(max_age, str)
            and max_age
        ):
            return persistent_auth_cookie_markup(
                cookie_name=name,
                session_id=value,
                cookie_path=path,
                max_age=max_age,
            )
        return None
    if action == "clear":
        name = command.get("name")
        path = command.get("path")
        if isinstance(name, str) and name and isinstance(path, str) and path:
            return clear_persistent_auth_cookie_markup(cookie_name=name, cookie_path=path)
    return None


def persistent_auth_cookie_markup(
    *,
    cookie_name: str,
    session_id: str,
    cookie_path: str,
    max_age: str,
) -> str:
    return cookie_sync_markup(
        script_body=(
            "document.cookie = `${payload.name}=${encodeURIComponent(payload.value)}; "
            "Path=${payload.path}; Max-Age=${payload.maxAge}; SameSite=Strict${secure}`;"
        ),
        payload={
            "name": cookie_name,
            "value": session_id,
            "path": cookie_path,
            "maxAge": max_age,
        },
    )


def clear_persistent_auth_cookie_markup(
    *,
    cookie_name: str,
    cookie_path: str,
) -> str:
    return cookie_sync_markup(
        script_body=(
            "document.cookie = `${payload.name}=; Path=${payload.path}; "
            "Max-Age=0; SameSite=Strict${secure}`;"
        ),
        payload={"name": cookie_name, "path": cookie_path},
    )


def cookie_sync_markup(*, script_body: str, payload: Mapping[str, str]) -> str:
    payload_json = json.dumps(dict(payload), ensure_ascii=True)
    return (
        "<div style=\"display:none\" aria-hidden=\"true\"></div>\n"
        "<script>\n"
        "(() => {\n"
        f"  const payload = {payload_json};\n"
        "  const secure = window.location.protocol === 'https:' ? '; Secure' : '';\n"
        f"  {script_body}\n"
        "})();\n"
        "</script>"
    )
