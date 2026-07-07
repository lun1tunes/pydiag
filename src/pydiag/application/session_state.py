from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any, Literal

from pydiag.common.errors import FileLockTimeoutError, VersionConflictError
from pydiag.domain.models import FlowGraphDocument, WellsDocument

FlashLevel = Literal["success", "warning", "error"]


@dataclass(frozen=True)
class AppDocuments:
    graph: FlowGraphDocument
    wells: WellsDocument


@dataclass(frozen=True)
class FlashMessage:
    message: str
    level: FlashLevel = "success"


@dataclass(frozen=True)
class PersistenceResult:
    should_rerun: bool = False
    error_message: str | None = None


def load_app_data(
    session_state: MutableMapping[str, Any],
    loader: Callable[[], tuple[FlowGraphDocument, WellsDocument]],
    *,
    force: bool = False,
) -> AppDocuments:
    if force or "graph_doc" not in session_state or "wells_doc" not in session_state:
        graph, wells = loader()
        session_state["graph_doc"] = graph
        session_state["wells_doc"] = wells
    return AppDocuments(
        graph=session_state["graph_doc"],
        wells=session_state["wells_doc"],
    )


def flash(
    session_state: MutableMapping[str, Any],
    message: str,
    level: FlashLevel = "success",
) -> None:
    session_state["flash"] = {"message": message, "level": level}


def pop_flash(session_state: MutableMapping[str, Any]) -> FlashMessage | None:
    payload = session_state.pop("flash", None)
    if not isinstance(payload, Mapping):
        return None

    message = payload.get("message")
    if not isinstance(message, str) or not message:
        return None

    raw_level = payload.get("level", "success")
    level = raw_level if raw_level in {"success", "warning", "error"} else "success"
    return FlashMessage(message=message, level=level)


def persist_wells_update(
    session_state: MutableMapping[str, Any],
    updated: WellsDocument,
    *,
    save: Callable[[WellsDocument], WellsDocument],
    reload_data: Callable[..., object],
    success_message: str,
) -> PersistenceResult:
    try:
        session_state["wells_doc"] = save(updated)
        flash(session_state, success_message)
        return PersistenceResult(should_rerun=True)
    except VersionConflictError as exc:
        _try_reload(reload_data)
        flash(
            session_state,
            f"Данные уже изменились другим пользователем. Состояние перечитано: {exc}",
            "warning",
        )
        return PersistenceResult(should_rerun=True)
    except FileLockTimeoutError as exc:
        flash(
            session_state,
            f"Файл состояния сейчас занят другой операцией. Повторите действие: {exc}",
            "warning",
        )
        return PersistenceResult(should_rerun=True)
    except Exception as exc:
        return PersistenceResult(error_message=str(exc))


def persist_graph_positions_update(
    session_state: MutableMapping[str, Any],
    *,
    save: Callable[[], FlowGraphDocument],
    reload_data: Callable[..., object],
    reset_position_edit_state: Callable[[], None],
    success_message: str,
) -> PersistenceResult:
    try:
        session_state["graph_doc"] = save()
        reset_position_edit_state()
        flash(session_state, success_message)
        return PersistenceResult(should_rerun=True)
    except VersionConflictError as exc:
        _try_reload(reload_data)
        flash(
            session_state,
            f"Схема уже изменилась другим пользователем. Состояние перечитано: {exc}",
            "warning",
        )
        return PersistenceResult(should_rerun=True)
    except FileLockTimeoutError as exc:
        flash(
            session_state,
            f"Файл схемы сейчас занят другой операцией. Повторите действие: {exc}",
            "warning",
        )
        return PersistenceResult(should_rerun=True)
    except Exception as exc:
        return PersistenceResult(error_message=str(exc))


def _try_reload(reload_data: Callable[..., object]) -> None:
    try:
        reload_data(force=True)
    except Exception:
        pass
