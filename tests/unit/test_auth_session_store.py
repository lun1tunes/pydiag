from __future__ import annotations

from pydiag.infrastructure import FileAuthSessionStore


def test_file_auth_session_store_roundtrips_refreshes_and_revokes(tmp_path) -> None:
    now = {"value": 1_000.0}
    store = FileAuthSessionStore(
        path_fn=lambda: tmp_path / "auth_sessions.json",
        now_fn=lambda: now["value"],
        session_id_factory=lambda: "session-001",
    )

    created = store.create_session(
        app_scope="https://pydiag.example/app",
        username="planner",
        password_fingerprint="pw-hash",
        ttl_seconds=600,
    )

    assert created.session_id == "session-001"
    assert store.get_session("session-001", app_scope="https://pydiag.example/app") == created
    assert store.get_session("session-001", app_scope="https://other.example/app") is None

    now["value"] = 1_250.0
    refreshed = store.refresh_session(
        "session-001",
        app_scope="https://pydiag.example/app",
        ttl_seconds=600,
    )

    assert refreshed is not None
    assert refreshed.expires_at == 1_850.0
    assert store.revoke_session("session-001", app_scope="https://pydiag.example/app") is True
    assert store.get_session("session-001", app_scope="https://pydiag.example/app") is None


def test_file_auth_session_store_expires_sessions_and_recovers_from_corrupt_registry(
    tmp_path,
) -> None:
    now = {"value": 10.0}
    path = tmp_path / "auth_sessions.json"
    store = FileAuthSessionStore(
        path_fn=lambda: path,
        now_fn=lambda: now["value"],
        session_id_factory=lambda: "session-001",
    )

    store.create_session(
        app_scope="http://localhost:8501/",
        username="planner",
        password_fingerprint="pw-hash",
        ttl_seconds=10,
    )
    now["value"] = 21.0

    assert store.get_session("session-001", app_scope="http://localhost:8501/") is None

    path.write_text("{broken json", encoding="utf-8")
    created = store.create_session(
        app_scope="http://localhost:8501/",
        username="planner",
        password_fingerprint="pw-hash",
        ttl_seconds=30,
    )

    assert created.session_id == "session-001"
