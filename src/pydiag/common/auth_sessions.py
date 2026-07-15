from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__ = ["AuthSessionRecord", "AuthSessionStore"]


@dataclass(frozen=True)
class AuthSessionRecord:
    session_id: str
    app_scope: str
    username: str
    password_fingerprint: str
    created_at: float
    expires_at: float


class AuthSessionStore(Protocol):
    def create_session(
        self,
        *,
        app_scope: str,
        username: str,
        password_fingerprint: str,
        ttl_seconds: int,
    ) -> AuthSessionRecord: ...

    def get_session(
        self,
        session_id: str,
        *,
        app_scope: str,
    ) -> AuthSessionRecord | None: ...

    def refresh_session(
        self,
        session_id: str,
        *,
        app_scope: str,
        ttl_seconds: int,
    ) -> AuthSessionRecord | None: ...

    def revoke_session(
        self,
        session_id: str,
        *,
        app_scope: str,
    ) -> bool: ...
