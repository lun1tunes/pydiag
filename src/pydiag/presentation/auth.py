from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from .auth_config import (
    admin_password,
    admin_password_warning,
    auth_config_warning,
    auth_users_from_env_json,
    auth_users_from_mapping,
    auth_users_from_streamlit_secrets,
    authenticate_user,
    configured_admin_password,
    configured_auth_users,
    insecure_admin_mode_enabled,
    password_is_allowed,
    streamlit_secrets_enabled,
)
from .auth_models import AuthUser
from .auth_session import (
    current_auth_user,
    current_user_is_admin,
    current_user_is_super_admin,
    login_user,
    logout_user,
)

__all__ = [
    "AuthUser",
    "StreamlitAuthContext",
    "admin_password",
    "admin_password_warning",
    "auth_config_warning",
    "auth_users_from_env_json",
    "auth_users_from_mapping",
    "auth_users_from_streamlit_secrets",
    "authenticate_user",
    "configured_admin_password",
    "configured_auth_users",
    "current_auth_user",
    "current_user_is_admin",
    "current_user_is_super_admin",
    "insecure_admin_mode_enabled",
    "login_user",
    "logout_user",
    "password_is_allowed",
    "streamlit_secrets_enabled",
]


@dataclass(frozen=True)
class StreamlitAuthContext:
    st_module: Any

    @property
    def session_state(self) -> MutableMapping[str, Any]:
        return self.st_module.session_state

    def configured_auth_users(self) -> dict[str, AuthUser]:
        return configured_auth_users(self.st_module)

    def configured_admin_password(self) -> str:
        return configured_admin_password(self.st_module)

    def insecure_admin_mode_enabled(self) -> bool:
        return insecure_admin_mode_enabled()

    def password_is_allowed(self, password: str) -> bool:
        return password_is_allowed(password)

    def streamlit_secrets_enabled(self) -> bool:
        return streamlit_secrets_enabled()

    def authenticate_user(self, username: str, password: str) -> AuthUser | None:
        return authenticate_user(self.st_module, username, password)

    def current_auth_user(self) -> dict[str, str | bool] | None:
        return current_auth_user(self.session_state)

    def current_user_is_admin(self) -> bool:
        return current_user_is_admin(self.session_state)

    def current_user_is_super_admin(self) -> bool:
        return current_user_is_super_admin(self.session_state)

    def admin_password(self) -> str:
        return admin_password(self.st_module)

    def admin_password_warning(self) -> str:
        return admin_password_warning(self.st_module)

    def auth_config_warning(self) -> str:
        return auth_config_warning(self.st_module)

    def login_user(self, user: AuthUser) -> None:
        login_user(self.session_state, user)

    def logout_user(self) -> None:
        logout_user(self.session_state)
