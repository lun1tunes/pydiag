from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FLOW_SOURCES_DIR = DATA_DIR / "flow_sources"
GRAPH_PATH = DATA_DIR / "flow_graph.json"
AUTH_SESSIONS_PATH = DATA_DIR / ".auth_sessions.json"
GRAPH_VERSIONS_DIR = FLOW_SOURCES_DIR
SOURCE_GRAPH_PATH = FLOW_SOURCES_DIR / "flow_source.yaml"
RAW_GRAPH_PATH = DATA_DIR / "real_true_data.json"
WELLS_PATH = DATA_DIR / "wells.yaml"
GRAPH_PATH_ENV = "PYDIAG_GRAPH_PATH"
AUTH_SESSIONS_PATH_ENV = "PYDIAG_AUTH_SESSIONS_PATH"
SOURCE_GRAPH_PATH_ENV = "PYDIAG_SOURCE_GRAPH_PATH"
RAW_GRAPH_PATH_ENV = "PYDIAG_RAW_GRAPH_PATH"
WELLS_PATH_ENV = "PYDIAG_WELLS_PATH"
FLOW_SOURCE_VERSION_FILENAME_RE = re.compile(r"^flow_source\.v(?P<sequence>\d{4})\.ya?ml$")
GRAPH_VERSION_FILENAME_RE = FLOW_SOURCE_VERSION_FILENAME_RE

__all__ = [
    "AUTH_SESSIONS_PATH",
    "AUTH_SESSIONS_PATH_ENV",
    "DATA_DIR",
    "FLOW_SOURCES_DIR",
    "FLOW_SOURCE_VERSION_FILENAME_RE",
    "GRAPH_PATH",
    "GRAPH_PATH_ENV",
    "GRAPH_VERSIONS_DIR",
    "GRAPH_VERSION_FILENAME_RE",
    "SOURCE_GRAPH_PATH",
    "SOURCE_GRAPH_PATH_ENV",
    "RAW_GRAPH_PATH",
    "RAW_GRAPH_PATH_ENV",
    "WELLS_PATH",
    "WELLS_PATH_ENV",
    "auth_sessions_path",
    "configured_graph_path",
    "graph_path",
    "graph_versions_dir",
    "graph_version_paths",
    "graph_version_display_label",
    "latest_graph_version_path",
    "next_graph_version_path",
    "existing_default_graph_path",
    "live_graph_source_exists",
    "preferred_graph_source_path",
    "readable_graph_source_path",
    "source_graph_path",
    "raw_graph_path",
    "wells_path",
]


def auth_sessions_path() -> Path:
    configured = os.getenv(AUTH_SESSIONS_PATH_ENV)
    if configured:
        return Path(configured)
    return AUTH_SESSIONS_PATH


def configured_graph_path() -> Path | None:
    configured = os.getenv(GRAPH_PATH_ENV)
    if configured:
        return Path(configured)
    return None


def graph_path() -> Path:
    configured = configured_graph_path()
    if configured is not None:
        return configured
    return GRAPH_PATH


def graph_versions_dir() -> Path:
    return source_graph_path().parent


def graph_version_paths() -> list[Path]:
    versions_dir = graph_versions_dir()
    if not versions_dir.exists():
        return []

    candidates: list[tuple[int, Path]] = []
    for path in versions_dir.iterdir():
        if not path.is_file():
            continue
        match = GRAPH_VERSION_FILENAME_RE.fullmatch(path.name)
        if match is None:
            continue
        candidates.append((int(match.group("sequence")), path))
    return [path for _, path in sorted(candidates)]


def graph_version_display_label(path: Path | str) -> str:
    """Short UI label for a versioned flow source file (e.g. v0002)."""
    name = Path(path).name
    match = GRAPH_VERSION_FILENAME_RE.fullmatch(name)
    if match is not None:
        return f"v{match.group('sequence')}"
    return name


def latest_graph_version_path() -> Path | None:
    candidates = graph_version_paths()
    if not candidates:
        return None
    return candidates[-1]


def next_graph_version_path() -> Path:
    candidates = graph_version_paths()
    versions_dir = graph_versions_dir()
    if candidates:
        last_name = candidates[-1].name
        match = GRAPH_VERSION_FILENAME_RE.fullmatch(last_name)
        if match is not None:
            next_sequence = int(match.group("sequence")) + 1
            return versions_dir / f"flow_source.v{next_sequence:04d}.yaml"
    return versions_dir / "flow_source.v0001.yaml"


def source_graph_path() -> Path:
    configured = os.getenv(SOURCE_GRAPH_PATH_ENV)
    if configured:
        return Path(configured)
    return SOURCE_GRAPH_PATH


def raw_graph_path() -> Path:
    configured = os.getenv(RAW_GRAPH_PATH_ENV)
    if configured:
        return Path(configured)
    return RAW_GRAPH_PATH


def live_graph_source_exists() -> bool:
    return source_graph_path().exists()


def readable_graph_source_path() -> Path | None:
    """Path used to render the app: live schema, else newest archived version.

    Raw Figma JSON is intentionally excluded — it is only an import source.
    """
    source = source_graph_path()
    if source.exists():
        return source
    return latest_graph_version_path()


def existing_default_graph_path() -> Path | None:
    """Existing file for default read/write when no version id is selected.

    Preference: live YAML → newest archive → configured/materialized JSON.
    Never returns a path that does not exist on disk.
    """
    source = readable_graph_source_path()
    if source is not None:
        return source
    configured = configured_graph_path()
    if configured is not None and configured.exists():
        return configured
    target = graph_path()
    if target.exists():
        return target
    return None


def preferred_graph_source_path() -> Path | None:
    """Best source for materialize/import helpers: live schema, else raw Figma JSON."""
    source = source_graph_path()
    if source.exists():
        return source
    raw = raw_graph_path()
    if raw.exists():
        return raw
    return None


def wells_path() -> Path:
    configured = os.getenv(WELLS_PATH_ENV)
    if configured:
        return Path(configured)
    return WELLS_PATH
