from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["GraphVersionInfo"]


@dataclass(frozen=True)
class GraphVersionInfo:
    id: str
    label: str
    path: Path
    is_versioned: bool = False
