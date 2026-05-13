from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from errno import EACCES, EAGAIN
from pathlib import Path
from typing import BinaryIO

from .models import FlowGraphDocument, WellsDocument, validate_wells_against_graph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "flow_graph.json"
WELLS_PATH = DATA_DIR / "wells.json"
GRAPH_PATH_ENV = "PYDIAG_GRAPH_PATH"
WELLS_PATH_ENV = "PYDIAG_WELLS_PATH"


class VersionConflictError(RuntimeError):
    """Raised when a writer tries to save stale JSON state."""


class FileLockTimeoutError(TimeoutError):
    """Raised when an exclusive state-file lock cannot be acquired in time."""


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


@contextmanager
def json_file_lock(
    path: str | Path,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> Iterator[None]:
    """Cross-platform advisory lock for JSON state writes."""
    target = Path(path)
    lock_path = target.with_name(target.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("a+b") as lock_file:
        ensure_lock_file_region(lock_file)
        acquire_file_lock(lock_file, lock_path, timeout, poll_interval)
        try:
            yield
        finally:
            release_file_lock(lock_file)


def ensure_lock_file_region(lock_file: BinaryIO) -> None:
    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"\0")
        lock_file.flush()
        os.fsync(lock_file.fileno())
    lock_file.seek(0)


def acquire_file_lock(
    lock_file: BinaryIO,
    lock_path: Path,
    timeout: float,
    poll_interval: float,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            try_acquire_file_lock(lock_file)
            return
        except OSError as exc:
            if exc.errno not in {EACCES, EAGAIN} and os.name != "nt":
                raise
            if time.monotonic() >= deadline:
                raise FileLockTimeoutError(
                    f"Timed out waiting for exclusive lock: {lock_path}"
                ) from exc
            time.sleep(poll_interval)


def try_acquire_file_lock(lock_file: BinaryIO) -> None:
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def release_file_lock(lock_file: BinaryIO) -> None:
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def save_wells_with_version_check(
    wells_doc: WellsDocument,
    expected_version: int,
    path: str | Path | None = None,
    graph: FlowGraphDocument | None = None,
) -> WellsDocument:
    target = Path(path or wells_path())
    with json_file_lock(target):
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
