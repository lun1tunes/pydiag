from __future__ import annotations

import hmac

from .auth_models import AuthUser
from .auth_sources import (
    LEGACY_ADMIN_USERNAME,
    auth_users_from_env_json,
    auth_users_from_streamlit_secrets,
    configured_admin_password,
    insecure_admin_mode_enabled,
    streamlit_secrets_enabled,
)

MIN_ADMIN_PASSWORD_LENGTH = 8

__all__ = [
    "MIN_ADMIN_PASSWORD_LENGTH",
    "admin_password",
    "admin_password_warning",
    "auth_config_warning",
    "authenticate_user",
    "configured_auth_users",
    "password_is_allowed",
]


def configured_auth_users(st_module) -> dict[str, AuthUser]:
    users: dict[str, AuthUser] = {}
    users.update(auth_users_from_env_json())
    if streamlit_secrets_enabled():
        users.update(auth_users_from_streamlit_secrets(st_module))

    legacy_password = configured_admin_password(st_module)
    if legacy_password:
        users.setdefault(
            LEGACY_ADMIN_USERNAME,
            AuthUser(
                username=LEGACY_ADMIN_USERNAME,
                display_name=LEGACY_ADMIN_USERNAME,
                password=legacy_password,
            ),
        )
    if insecure_admin_mode_enabled() and not users:
        users[LEGACY_ADMIN_USERNAME] = AuthUser(
            username=LEGACY_ADMIN_USERNAME,
            display_name=LEGACY_ADMIN_USERNAME,
            password="admin",
        )
    return {
        username: user for username, user in users.items() if password_is_allowed(user.password)
    }


def password_is_allowed(password: str) -> bool:
    return insecure_admin_mode_enabled() or len(password) >= MIN_ADMIN_PASSWORD_LENGTH


def admin_password(st_module) -> str:
    configured_password = configured_admin_password(st_module)
    if configured_password:
        if password_is_allowed(configured_password):
            return configured_password
        return ""
    if insecure_admin_mode_enabled():
        return "admin"
    return ""


def admin_password_warning(st_module) -> str:
    configured_password = configured_admin_password(st_module)
    if configured_password and not password_is_allowed(configured_password):
        return (
            f"Админ-пароль должен быть не короче {MIN_ADMIN_PASSWORD_LENGTH} символов. "
            "Для локальной отладки можно явно включить PYDIAG_ALLOW_INSECURE_ADMIN=1."
        )
    return (
        "Админ-пароль не настроен. Задайте PYDIAG_ADMIN_PASSWORD или st.secrets['admin_password']."
    )


def auth_config_warning(st_module) -> str:
    if configured_admin_password(st_module):
        return admin_password_warning(st_module)
    if auth_users_from_env_json() or (
        streamlit_secrets_enabled() and auth_users_from_streamlit_secrets(st_module)
    ):
        return (
            f"Пароли пользователей должны быть не короче {MIN_ADMIN_PASSWORD_LENGTH} символов. "
            "Для локальной отладки можно явно включить PYDIAG_ALLOW_INSECURE_ADMIN=1."
        )
    return (
        "Пользователи не настроены. Добавьте их в .streamlit/secrets.toml "
        "в формате [users.<login>] password = '...'."
    )


def authenticate_user(st_module, username: str, password: str) -> AuthUser | None:
    user = configured_auth_users(st_module).get(username.strip())
    if user is None:
        return None
    if hmac.compare_digest(password, user.password):
        return user
    return None
