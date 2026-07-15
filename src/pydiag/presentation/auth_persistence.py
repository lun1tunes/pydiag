from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from pydiag.common.auth_sessions import AuthSessionStore

from .auth_models import AuthUser
from .auth_session import (
    DEFAULT_AUTH_SESSION_TTL_SECONDS,
    clear_persistent_auth_session,
    consume_persistent_auth_cookie_markup,
    current_auth_user,
    login_user,
    logout_user,
    pending_persistent_auth_cookie_command,
    persistent_auth_session_id,
    queue_persistent_auth_cookie_clear,
    queue_persistent_auth_cookie_set,
    set_persistent_auth_session,
)

__all__ = [
    "AuthCookieScope",
    "AuthRequestContext",
    "auth_request_context",
    "auth_session_ttl_seconds",
    "login_user_with_persistence",
    "logout_user_with_persistence",
    "sync_persistent_auth_session",
]

AUTH_SESSION_TTL_ENV = "PYDIAG_AUTH_SESSION_TTL_SECONDS"
MIN_AUTH_SESSION_TTL_SECONDS = 900
MAX_AUTH_SESSION_TTL_SECONDS = 2_592_000


@dataclass(frozen=True)
class AuthRequestContext:
    url: str | None
    cookies: Mapping[str, str]
    headers: Mapping[str, str]


@dataclass(frozen=True)
class AuthCookieScope:
    app_scope: str
    cookie_name: str
    cookie_path: str


def auth_request_context(st_module: Any) -> AuthRequestContext:
    cookies: Mapping[str, str] = {}
    headers: Mapping[str, str] = {}
    url: str | None = None
    context = getattr(st_module, "context", None)
    if context is not None:
        url = getattr(context, "url", None)
        raw_cookies = getattr(context, "cookies", {})
        raw_headers = getattr(context, "headers", {})
        cookies = _mapping_from_context(raw_cookies)
        headers = _mapping_from_context(raw_headers)
    return AuthRequestContext(url=url, cookies=cookies, headers=headers)


def auth_session_ttl_seconds() -> int:
    import os

    raw = os.getenv(AUTH_SESSION_TTL_ENV)
    if not raw:
        return DEFAULT_AUTH_SESSION_TTL_SECONDS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_AUTH_SESSION_TTL_SECONDS
    return max(MIN_AUTH_SESSION_TTL_SECONDS, min(MAX_AUTH_SESSION_TTL_SECONDS, parsed))


def login_user_with_persistence(
    session_state: MutableMapping[str, Any],
    user: AuthUser,
    *,
    session_store: AuthSessionStore | None,
    request_context: AuthRequestContext,
    session_ttl_seconds: int,
) -> None:
    login_user(session_state, user)
    if session_store is None:
        return

    scope = auth_cookie_scope(request_context)
    try:
        record = session_store.create_session(
            app_scope=scope.app_scope,
            username=user.username,
            password_fingerprint=password_fingerprint(user),
            ttl_seconds=session_ttl_seconds,
        )
    except Exception:
        return

    set_persistent_auth_session(
        session_state,
        session_id=record.session_id,
        cookie_name=scope.cookie_name,
        cookie_path=scope.cookie_path,
    )
    queue_persistent_auth_cookie_set(
        session_state,
        cookie_name=scope.cookie_name,
        session_id=record.session_id,
        cookie_path=scope.cookie_path,
        max_age_seconds=session_ttl_seconds,
    )


def logout_user_with_persistence(
    session_state: MutableMapping[str, Any],
    *,
    session_store: AuthSessionStore | None,
    request_context: AuthRequestContext,
) -> None:
    scope = auth_cookie_scope(request_context)
    session_id = persistent_auth_session_id(session_state)
    if session_id is None:
        cookie_value = request_context.cookies.get(scope.cookie_name)
        if isinstance(cookie_value, str) and cookie_value:
            session_id = cookie_value

    if session_store is not None and session_id is not None:
        try:
            session_store.revoke_session(session_id, app_scope=scope.app_scope)
        except Exception:
            pass

    logout_user(session_state)
    queue_persistent_auth_cookie_clear(
        session_state,
        cookie_name=scope.cookie_name,
        cookie_path=scope.cookie_path,
    )


def sync_persistent_auth_session(
    session_state: MutableMapping[str, Any],
    users: Mapping[str, AuthUser],
    *,
    session_store: AuthSessionStore | None,
    request_context: AuthRequestContext,
    session_ttl_seconds: int,
) -> str | None:
    scope = auth_cookie_scope(request_context)
    pending = pending_persistent_auth_cookie_command(session_state)
    if pending and pending.get("action") == "clear":
        clear_persistent_auth_session(session_state)
        return consume_persistent_auth_cookie_markup(session_state)

    if current_auth_user(session_state) is None and session_store is not None:
        raw_session_id = request_context.cookies.get(scope.cookie_name)
        session_id = raw_session_id if isinstance(raw_session_id, str) and raw_session_id else None
        if session_id is not None:
            restored = restore_session_from_store(
                session_state,
                users,
                session_store=session_store,
                scope=scope,
                session_id=session_id,
                session_ttl_seconds=session_ttl_seconds,
            )
            if not restored:
                clear_persistent_auth_session(session_state)
                queue_persistent_auth_cookie_clear(
                    session_state,
                    cookie_name=scope.cookie_name,
                    cookie_path=scope.cookie_path,
                )

    return consume_persistent_auth_cookie_markup(session_state)


def restore_session_from_store(
    session_state: MutableMapping[str, Any],
    users: Mapping[str, AuthUser],
    *,
    session_store: AuthSessionStore,
    scope: AuthCookieScope,
    session_id: str,
    session_ttl_seconds: int,
) -> bool:
    try:
        record = session_store.get_session(session_id, app_scope=scope.app_scope)
    except Exception:
        return False
    if record is None:
        return False

    user = users.get(record.username)
    if user is None or record.password_fingerprint != password_fingerprint(user):
        try:
            session_store.revoke_session(session_id, app_scope=scope.app_scope)
        except Exception:
            pass
        return False

    try:
        refreshed = session_store.refresh_session(
            session_id,
            app_scope=scope.app_scope,
            ttl_seconds=session_ttl_seconds,
        )
    except Exception:
        return False
    if refreshed is None:
        return False

    login_user(session_state, user)
    set_persistent_auth_session(
        session_state,
        session_id=refreshed.session_id,
        cookie_name=scope.cookie_name,
        cookie_path=scope.cookie_path,
    )
    queue_persistent_auth_cookie_set(
        session_state,
        cookie_name=scope.cookie_name,
        session_id=refreshed.session_id,
        cookie_path=scope.cookie_path,
        max_age_seconds=session_ttl_seconds,
    )
    return True


def auth_cookie_scope(request_context: AuthRequestContext) -> AuthCookieScope:
    normalized_url = normalize_request_url(request_context)
    split = urlsplit(normalized_url)
    cookie_path = split.path or "/"
    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:16]
    prefix = "__Secure-" if split.scheme == "https" else ""
    return AuthCookieScope(
        app_scope=normalized_url,
        cookie_name=f"{prefix}pydiag_auth_{digest}",
        cookie_path=cookie_path,
    )


def normalize_request_url(request_context: AuthRequestContext) -> str:
    if isinstance(request_context.url, str) and request_context.url:
        split = urlsplit(request_context.url)
        return normalized_url_parts(split.scheme or "http", split.netloc, split.path)

    host = header_value(request_context.headers, "Host")
    scheme = header_value(request_context.headers, "X-Forwarded-Proto") or "http"
    return normalized_url_parts(scheme, host or "localhost", "/")


def normalized_url_parts(scheme: str, netloc: str, path: str) -> str:
    normalized_path = path or "/"
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    if normalized_path != "/":
        normalized_path = normalized_path.rstrip("/")
        if not normalized_path:
            normalized_path = "/"
    return f"{scheme}://{netloc}{normalized_path}"


def header_value(headers: Mapping[str, str], name: str) -> str | None:
    if name in headers:
        value = headers.get(name)
        return value if isinstance(value, str) and value else None
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered and isinstance(value, str) and value:
            return value
    return None


def password_fingerprint(user: AuthUser) -> str:
    payload = f"{user.username}\0{user.password}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _mapping_from_context(raw: object) -> Mapping[str, str]:
    if isinstance(raw, Mapping):
        return {
            str(key): str(value)
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    if hasattr(raw, "to_dict"):
        try:
            converted = raw.to_dict()
        except Exception:
            return {}
        if isinstance(converted, Mapping):
            return {
                str(key): str(value)
                for key, value in converted.items()
                if isinstance(key, str) and isinstance(value, str)
            }
    try:
        converted = dict(raw)
    except Exception:
        return {}
    return {
        str(key): str(value)
        for key, value in converted.items()
        if isinstance(key, str) and isinstance(value, str)
    }
