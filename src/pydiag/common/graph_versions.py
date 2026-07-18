from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["GraphVersionInfo", "RawImportResult"]


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
