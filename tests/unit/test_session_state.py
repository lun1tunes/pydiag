from __future__ import annotations

from pydiag.application.session_state import (
    flash,
    load_app_data,
    persist_graph_positions_update,
    persist_wells_update,
    pop_flash,
)
from pydiag.infrastructure import FileLockTimeoutError, VersionConflictError


def test_load_app_data_caches_documents_until_forced(documents) -> None:
    graph, wells = documents
    session_state: dict[str, object] = {}
    calls: list[str] = []

    def loader():
        calls.append("load")
        return graph, wells

    first = load_app_data(session_state, loader)
    second = load_app_data(session_state, loader)
    forced = load_app_data(session_state, loader, force=True)

    assert calls == ["load", "load"]
    assert first.graph is graph
    assert first.wells is wells
    assert second.graph is graph
    assert second.wells is wells
    assert forced.graph is graph
    assert forced.wells is wells


def test_pop_flash_handles_valid_and_invalid_payloads() -> None:
    session_state: dict[str, object] = {}

    assert pop_flash(session_state) is None

    session_state["flash"] = "bad-payload"
    assert pop_flash(session_state) is None

    session_state["flash"] = {"message": 42}
    assert pop_flash(session_state) is None

    flash(session_state, "saved", "warning")
    message = pop_flash(session_state)

    assert message is not None
    assert message.message == "saved"
    assert message.level == "warning"
    assert "flash" not in session_state

    session_state["flash"] = {"message": "fallback", "level": "unexpected"}
    normalized = pop_flash(session_state)

    assert normalized is not None
    assert normalized.level == "success"


def test_persist_wells_update_success_stores_document_and_sets_flash(documents) -> None:
    graph, wells = documents
    session_state: dict[str, object] = {}
    saved_wells = wells.model_copy(update={"version": wells.version + 1})

    result = persist_wells_update(
        session_state,
        wells,
        save=lambda updated: saved_wells,
        reload_data=lambda **_: None,
        success_message="saved",
    )

    assert result.should_rerun is True
    assert result.error_message is None
    assert session_state["wells_doc"] == saved_wells
    assert session_state["flash"] == {"message": "saved", "level": "success"}


def test_persist_wells_update_handles_version_conflict_and_reload(documents) -> None:
    graph, wells = documents
    session_state: dict[str, object] = {}
    reload_calls: list[bool] = []

    def save(_updated):
        raise VersionConflictError("stale")

    def reload_data(*, force: bool = False):
        reload_calls.append(force)
        return graph, wells

    result = persist_wells_update(
        session_state,
        wells,
        save=save,
        reload_data=reload_data,
        success_message="saved",
    )

    assert result.should_rerun is True
    assert result.error_message is None
    assert reload_calls == [True]
    assert session_state["flash"]["level"] == "warning"
    assert "Состояние перечитано" in str(session_state["flash"]["message"])


def test_persist_wells_update_handles_lock_and_unexpected_errors(documents) -> None:
    _graph, wells = documents

    locked_state: dict[str, object] = {}
    locked = persist_wells_update(
        locked_state,
        wells,
        save=lambda _updated: (_ for _ in ()).throw(FileLockTimeoutError("busy")),
        reload_data=lambda **_: None,
        success_message="saved",
    )

    assert locked.should_rerun is True
    assert locked.error_message is None
    assert locked_state["flash"]["level"] == "warning"
    assert "занят" in str(locked_state["flash"]["message"])

    failed_state: dict[str, object] = {}
    failed = persist_wells_update(
        failed_state,
        wells,
        save=lambda _updated: (_ for _ in ()).throw(RuntimeError("boom")),
        reload_data=lambda **_: None,
        success_message="saved",
    )

    assert failed.should_rerun is False
    assert failed.error_message == "boom"
    assert "flash" not in failed_state


def test_persist_graph_positions_update_success_conflict_and_failures(documents) -> None:
    graph, _wells = documents

    saved_graph = graph.model_copy(update={"version": graph.version + 1})
    success_state: dict[str, object] = {}
    reset_calls: list[str] = []
    success = persist_graph_positions_update(
        success_state,
        save=lambda: saved_graph,
        reload_data=lambda **_: None,
        reset_position_edit_state=lambda: reset_calls.append("reset"),
        success_message="positions-saved",
    )

    assert success.should_rerun is True
    assert success.error_message is None
    assert success_state["graph_doc"] == saved_graph
    assert success_state["flash"] == {"message": "positions-saved", "level": "success"}
    assert reset_calls == ["reset"]

    conflict_state: dict[str, object] = {}
    conflict = persist_graph_positions_update(
        conflict_state,
        save=lambda: (_ for _ in ()).throw(VersionConflictError("stale")),
        reload_data=lambda **_: (_ for _ in ()).throw(RuntimeError("reload failed")),
        reset_position_edit_state=lambda: None,
        success_message="positions-saved",
    )

    assert conflict.should_rerun is True
    assert conflict.error_message is None
    assert conflict_state["flash"]["level"] == "warning"
    assert "Состояние перечитано" in str(conflict_state["flash"]["message"])

    locked_state: dict[str, object] = {}
    locked = persist_graph_positions_update(
        locked_state,
        save=lambda: (_ for _ in ()).throw(FileLockTimeoutError("busy")),
        reload_data=lambda **_: None,
        reset_position_edit_state=lambda: None,
        success_message="positions-saved",
    )

    assert locked.should_rerun is True
    assert locked.error_message is None
    assert locked_state["flash"]["level"] == "warning"
    assert "занят" in str(locked_state["flash"]["message"])

    failed_state: dict[str, object] = {}
    failed = persist_graph_positions_update(
        failed_state,
        save=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        reload_data=lambda **_: None,
        reset_position_edit_state=lambda: None,
        success_message="positions-saved",
    )

    assert failed.should_rerun is False
    assert failed.error_message == "boom"
    assert "flash" not in failed_state
