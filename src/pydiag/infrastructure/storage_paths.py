from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FLOW_SOURCES_DIR = DATA_DIR / "flow_sources"
GRAPH_PATH = DATA_DIR / "flow_graph.json"
GRAPH_VERSIONS_DIR = FLOW_SOURCES_DIR
SOURCE_GRAPH_PATH = FLOW_SOURCES_DIR / "flow_source.yaml"
RAW_GRAPH_PATH = DATA_DIR / "real_true_data.json"
WELLS_PATH = DATA_DIR / "wells.yaml"
GRAPH_PATH_ENV = "PYDIAG_GRAPH_PATH"
SOURCE_GRAPH_PATH_ENV = "PYDIAG_SOURCE_GRAPH_PATH"
RAW_GRAPH_PATH_ENV = "PYDIAG_RAW_GRAPH_PATH"
WELLS_PATH_ENV = "PYDIAG_WELLS_PATH"
FLOW_SOURCE_VERSION_FILENAME_RE = re.compile(r"^flow_source\.v(?P<sequence>\d{4})\.ya?ml$")
GRAPH_VERSION_FILENAME_RE = FLOW_SOURCE_VERSION_FILENAME_RE

__all__ = [
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
    "configured_graph_path",
    "graph_path",
    "graph_versions_dir",
    "graph_version_paths",
    "latest_graph_version_path",
    "next_graph_version_path",
    "preferred_graph_source_path",
    "source_graph_path",
    "raw_graph_path",
    "wells_path",
]


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


def preferred_graph_source_path() -> Path | None:
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
