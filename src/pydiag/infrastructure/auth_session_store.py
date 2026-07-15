from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydiag.common.auth_sessions import AuthSessionRecord

from .storage_io import json_file_lock, save_json_atomic
from .storage_paths import auth_sessions_path

SESSION_REGISTRY_VERSION = 1

__all__ = ["FileAuthSessionStore"]


def default_session_id() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class FileAuthSessionStore:
    path_fn: Callable[[], Path] = auth_sessions_path
    now_fn: Callable[[], float] = time.time
    session_id_factory: Callable[[], str] = default_session_id
    lock_timeout_seconds: float = 10.0

    def create_session(
        self,
        *,
        app_scope: str,
        username: str,
        password_fingerprint: str,
        ttl_seconds: int,
    ) -> AuthSessionRecord:
        now = self.now_fn()
        ttl = max(int(ttl_seconds), 1)
        record = AuthSessionRecord(
            session_id=self.session_id_factory(),
            app_scope=app_scope,
            username=username,
            password_fingerprint=password_fingerprint,
            created_at=now,
            expires_at=now + ttl,
        )

        def mutate(sessions: dict[str, dict[str, object]]) -> tuple[AuthSessionRecord, bool]:
            sessions[record.session_id] = _serialize_record(record)
            return record, True

        return self._with_registry(now=now, mutate=mutate)

    def get_session(
        self,
        session_id: str,
        *,
        app_scope: str,
    ) -> AuthSessionRecord | None:
        def mutate(
            sessions: dict[str, dict[str, object]],
        ) -> tuple[AuthSessionRecord | None, bool]:
            return _lookup_session(sessions, session_id, app_scope=app_scope), False

        return self._with_registry(mutate=mutate)

    def refresh_session(
        self,
        session_id: str,
        *,
        app_scope: str,
        ttl_seconds: int,
    ) -> AuthSessionRecord | None:
        now = self.now_fn()
        ttl = max(int(ttl_seconds), 1)

        def mutate(
            sessions: dict[str, dict[str, object]],
        ) -> tuple[AuthSessionRecord | None, bool]:
            record = _lookup_session(sessions, session_id, app_scope=app_scope)
            if record is None:
                return None, False
            refreshed = AuthSessionRecord(
                session_id=record.session_id,
                app_scope=record.app_scope,
                username=record.username,
                password_fingerprint=record.password_fingerprint,
                created_at=record.created_at,
                expires_at=now + ttl,
            )
            sessions[session_id] = _serialize_record(refreshed)
            return refreshed, True

        return self._with_registry(now=now, mutate=mutate)

    def revoke_session(
        self,
        session_id: str,
        *,
        app_scope: str,
    ) -> bool:
        def mutate(sessions: dict[str, dict[str, object]]) -> tuple[bool, bool]:
            record = _lookup_session(sessions, session_id, app_scope=app_scope)
            if record is None:
                return False, False
            sessions.pop(session_id, None)
            return True, True

        return self._with_registry(mutate=mutate)

    def _with_registry(
        self,
        *,
        mutate: Callable[[dict[str, dict[str, object]]], tuple[Any, bool]],
        now: float | None = None,
    ) -> Any:
        path = self.path_fn()
        with json_file_lock(path, timeout=self.lock_timeout_seconds):
            registry = _load_registry(path)
            sessions = registry.setdefault("sessions", {})
            changed = _cleanup_expired_sessions(
                sessions,
                self.now_fn() if now is None else now,
            )
            result, mutated = mutate(sessions)
            if changed or mutated:
                save_json_atomic(
                    path,
                    {
                        "version": SESSION_REGISTRY_VERSION,
                        "sessions": sessions,
                    },
                )
            return result


def _load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": SESSION_REGISTRY_VERSION, "sessions": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": SESSION_REGISTRY_VERSION, "sessions": {}}
    if not isinstance(payload, dict):
        return {"version": SESSION_REGISTRY_VERSION, "sessions": {}}
    sessions = payload.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
    return {"version": payload.get("version", SESSION_REGISTRY_VERSION), "sessions": sessions}


def _cleanup_expired_sessions(sessions: dict[str, dict[str, object]], now: float) -> bool:
    changed = False
    expired_ids: list[str] = []
    for session_id, payload in sessions.items():
        record = _deserialize_record(session_id, payload)
        if record is None or record.expires_at <= now:
            expired_ids.append(session_id)
    for session_id in expired_ids:
        sessions.pop(session_id, None)
        changed = True
    return changed


def _lookup_session(
    sessions: Mapping[str, dict[str, object]],
    session_id: str,
    *,
    app_scope: str,
) -> AuthSessionRecord | None:
    payload = sessions.get(session_id)
    record = _deserialize_record(session_id, payload)
    if record is None or record.app_scope != app_scope:
        return None
    return record


def _deserialize_record(session_id: str, payload: object) -> AuthSessionRecord | None:
    if not isinstance(payload, Mapping):
        return None
    app_scope = payload.get("app_scope")
    username = payload.get("username")
    password_fingerprint = payload.get("password_fingerprint")
    created_at = payload.get("created_at")
    expires_at = payload.get("expires_at")
    if not (
        isinstance(app_scope, str)
        and app_scope
        and isinstance(username, str)
        and username
        and isinstance(password_fingerprint, str)
        and password_fingerprint
        and isinstance(created_at, int | float)
        and isinstance(expires_at, int | float)
    ):
        return None
    return AuthSessionRecord(
        session_id=session_id,
        app_scope=app_scope,
        username=username,
        password_fingerprint=password_fingerprint,
        created_at=float(created_at),
        expires_at=float(expires_at),
    )


def _serialize_record(record: AuthSessionRecord) -> dict[str, object]:
    return {
        "app_scope": record.app_scope,
        "username": record.username,
        "password_fingerprint": record.password_fingerprint,
        "created_at": round(float(record.created_at), 6),
        "expires_at": round(float(record.expires_at), 6),
    }
