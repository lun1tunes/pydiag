from __future__ import annotations

import json
import os
from collections.abc import Mapping

from .auth_models import AuthUser

AUTH_USERS_ENV = "PYDIAG_AUTH_USERS_JSON"
LEGACY_ADMIN_USERNAME = "admin"

__all__ = [
    "AUTH_USERS_ENV",
    "LEGACY_ADMIN_USERNAME",
    "auth_users_from_env_json",
    "auth_users_from_mapping",
    "auth_users_from_streamlit_secrets",
    "configured_admin_password",
    "insecure_admin_mode_enabled",
    "streamlit_secrets_enabled",
]


def streamlit_secrets_enabled() -> bool:
    return os.getenv("PYDIAG_DISABLE_STREAMLIT_SECRETS") != "1"


def auth_users_from_env_json() -> dict[str, AuthUser]:
    raw = os.getenv(AUTH_USERS_ENV)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return auth_users_from_mapping(payload)


def auth_users_from_streamlit_secrets(st_module) -> dict[str, AuthUser]:
    try:
        secrets = st_module.secrets
        users: dict[str, AuthUser] = {}
        users.update(auth_users_from_mapping(secrets.get("users", {})))
        auth_section = secrets.get("auth", {})
        if isinstance(auth_section, Mapping):
            users.update(auth_users_from_mapping(auth_section.get("users", {})))
        return users
    except Exception:
        return {}


def auth_users_from_mapping(value: object) -> dict[str, AuthUser]:
    if not isinstance(value, Mapping):
        return {}

    users: dict[str, AuthUser] = {}
    for raw_username, raw_config in value.items():
        username = str(raw_username).strip()
        if not username:
            continue

        password: str | None = None
        display_name = username
        is_admin = True
        is_super_admin = username == "super_admin"
        if isinstance(raw_config, str):
            password = raw_config
        elif isinstance(raw_config, Mapping):
            raw_password = raw_config.get("password")
            if raw_password is not None:
                password = str(raw_password)
            display_name = str(
                raw_config.get("name") or raw_config.get("display_name") or username
            ).strip()
            is_admin = bool(raw_config.get("is_admin", True))
            is_super_admin = bool(raw_config.get("is_super_admin", is_super_admin))

        if not password:
            continue
        users[username] = AuthUser(
            username=username,
            display_name=display_name or username,
            password=password,
            is_admin=is_admin or is_super_admin,
            is_super_admin=is_super_admin,
        )
    return users


def configured_admin_password(st_module) -> str:
    env_value = os.getenv("PYDIAG_ADMIN_PASSWORD")
    if env_value:
        return env_value
    if streamlit_secrets_enabled():
        try:
            secret_value = st_module.secrets.get("admin_password")
            if secret_value:
                return str(secret_value)
        except Exception:
            pass
    return ""


def insecure_admin_mode_enabled() -> bool:
    return os.getenv("PYDIAG_ALLOW_INSECURE_ADMIN") == "1"
