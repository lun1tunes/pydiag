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

from pydiag.common.errors import FileLockTimeoutError

__all__ = [
    "acquire_file_lock",
    "ensure_lock_file_region",
    "fsync_parent_dir",
    "json_file_lock",
    "release_file_lock",
    "save_json_atomic",
    "save_text_atomic",
    "try_acquire_file_lock",
]


def save_json_atomic(path: str | Path, payload: dict) -> None:
    save_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def save_text_atomic(path: str | Path, payload: str) -> None:
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
            tmp.write(payload)
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
    """Cross-platform advisory lock for runtime state writes."""
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
