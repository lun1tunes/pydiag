from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import FlowGraphDocument, WellsDocument, validate_wells_against_graph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "flow_graph.json"
WELLS_PATH = DATA_DIR / "wells.json"
GRAPH_PATH_ENV = "PYDIAG_GRAPH_PATH"
WELLS_PATH_ENV = "PYDIAG_WELLS_PATH"


class VersionConflictError(RuntimeError):
    """Raised when a writer tries to save stale JSON state."""


def graph_path() -> Path:
    return Path(os.getenv(GRAPH_PATH_ENV) or GRAPH_PATH)


def wells_path() -> Path:
    return Path(os.getenv(WELLS_PATH_ENV) or WELLS_PATH)


def load_graph_doc(path: str | Path | None = None) -> FlowGraphDocument:
    raw = Path(path or graph_path()).read_bytes()
    return FlowGraphDocument.model_validate_json(raw, strict=True)


def load_wells_doc(path: str | Path | None = None) -> WellsDocument:
    raw = Path(path or wells_path()).read_bytes()
    return WellsDocument.model_validate_json(raw, strict=True)


def load_documents(
    graph_doc_path: str | Path | None = None,
    wells_doc_path: str | Path | None = None,
) -> tuple[FlowGraphDocument, WellsDocument]:
    graph = load_graph_doc(graph_doc_path)
    wells = load_wells_doc(wells_doc_path)
    validate_wells_against_graph(graph, wells)
    return graph, wells


def save_json_atomic(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=target.name + ".",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
        fsync_parent_dir(target)
    finally:
        if tmp_name and Path(tmp_name).exists():
            Path(tmp_name).unlink()


def fsync_parent_dir(path: Path) -> None:
    if os.name != "posix":
        return

    dir_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def save_wells_with_version_check(
    wells_doc: WellsDocument,
    expected_version: int,
    path: str | Path | None = None,
    graph: FlowGraphDocument | None = None,
) -> WellsDocument:
    target = Path(path or wells_path())
    current = load_wells_doc(target)
    if current.version != expected_version:
        raise VersionConflictError(
            f"Conflict: expected wells version {expected_version}, "
            f"actual version is {current.version}"
        )

    to_save = wells_doc.model_copy(deep=True)
    to_save.version = expected_version + 1
    if graph is not None:
        validate_wells_against_graph(graph, to_save)
    save_json_atomic(target, to_save.model_dump(mode="json"))
    return load_wells_doc(target)
