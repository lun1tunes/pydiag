from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "GraphVersionInfo",
    "RawImportResult",
    "graph_version_sequence",
    "newest_graph_version",
]

_GRAPH_VERSION_ID_RE = re.compile(r"^flow_source\.v(?P<sequence>\d{4})\.ya?ml$")


@dataclass(frozen=True)
class GraphVersionInfo:
    id: str
    label: str
    path: Path
    is_versioned: bool = False


@dataclass(frozen=True)
class RawImportResult:
    live_path: Path
    changed: bool
    backup_version: GraphVersionInfo | None = None


def graph_version_sequence(version_id: str) -> int:
    match = _GRAPH_VERSION_ID_RE.fullmatch(version_id)
    if match is None:
        return -1
    return int(match.group("sequence"))


def newest_graph_version(versions: list[GraphVersionInfo]) -> GraphVersionInfo:
    """Return the archive with the highest version sequence, independent of list order."""
    if not versions:
        raise ValueError("versions must not be empty")
    return max(versions, key=lambda version: (graph_version_sequence(version.id), version.id))
