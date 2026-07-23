from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

GraphSourceNodeKind = Literal[
    "process",
    "decision_diamond",
    "database",
    "input_data",
    "event",
]
GraphSourceEdgeKind = Literal["default", "yes", "no", "dashed"]

__all__ = [
    "CreateGraphSourceEdgeCommand",
    "CreateGraphSourceNodeCommand",
    "GraphSourceEdgeDraft",
    "GraphSourceEdgeKind",
    "GraphSourceNodeDraft",
    "GraphSourceNodeKind",
    "UpdateGraphSourceEdgeCommand",
    "UpdateGraphSourceNodeCommand",
]


@dataclass(frozen=True)
class GraphSourceNodeDraft:
    node_id: str
    title: str
    kind: GraphSourceNodeKind
    layout_x: float
    layout_y: float
    layout_w: int
    layout_h: int
    responsible: str | None
    participants: tuple[str, ...]
    approvers: tuple[str, ...]
    duration: str | None
    note: str | None


@dataclass(frozen=True)
class UpdateGraphSourceNodeCommand:
    node_id: str
    title: str
    kind: GraphSourceNodeKind
    layout_x: float
    layout_y: float
    layout_w: int
    layout_h: int
    responsible: str | None
    participants: tuple[str, ...]
    approvers: tuple[str, ...]
    duration: str | None
    note: str | None
    deleted: bool | None = None


@dataclass(frozen=True)
class GraphSourceEdgeDraft:
    edge_id: str
    source: str
    target: str
    kind: GraphSourceEdgeKind
    label: str | None
    condition: str | None
    note: str | None


@dataclass(frozen=True)
class UpdateGraphSourceEdgeCommand:
    edge_id: str
    source: str
    target: str
    kind: GraphSourceEdgeKind
    label: str | None
    condition: str | None
    note: str | None
    deleted: bool | None = None


@dataclass(frozen=True)
class CreateGraphSourceEdgeCommand:
    source: str
    target: str
    kind: GraphSourceEdgeKind
    label: str | None
    condition: str | None
    note: str | None
    edge_id: str | None = None


@dataclass(frozen=True)
class CreateGraphSourceNodeCommand:
    title: str
    kind: GraphSourceNodeKind
    layout_x: float
    layout_y: float
    layout_w: int
    layout_h: int
    responsible: str | None = None
    participants: tuple[str, ...] = ()
    approvers: tuple[str, ...] = ()
    duration: str | None = None
    note: str | None = None
    node_id: str | None = None
