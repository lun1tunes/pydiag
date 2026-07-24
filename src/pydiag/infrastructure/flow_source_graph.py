from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pydiag.common.graph_source_admin import (
    CreateGraphSourceEdgeCommand,
    CreateGraphSourceNodeCommand,
    CreateGraphSourceProcessCommand,
    DeleteGraphSourceProcessCommand,
    GraphSourceEdgeDraft,
    GraphSourceNodeDraft,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
    UpdateGraphSourceProcessCommand,
)
from pydiag.common.layout_metadata import (
    CUSTOM_LAYOUT_X_META,
    CUSTOM_LAYOUT_Y_META,
)
from pydiag.domain.models import (
    HEX_COLOR_RE,
    FlowGraphDocument,
    MetaValue,
    format_node_time,
    parse_node_time,
)
from pydiag.infrastructure.editable_flow_graph import (
    EDITABLE_FLOW_GRAPH_SCHEMA_VERSION,
    EditableEdgeKind,
    EditableFlowGraphDocument,
    EditableFlowGraphNode,
    EditableNodeKind,
)

FLOW_SOURCE_SCHEMA_VERSION = "flow-source/1.0"
SHORT_DURATION_RE = re.compile(
    r"^(?:(?P<lo>\d+)\s*-\s*(?P<hi>\d+)|(?P<amount>\d+))\s*(?P<unit>[mhd])$"
)
AUTO_LAYOUT_COLUMNS = 4
AUTO_LAYOUT_HORIZONTAL_STEP = 420
AUTO_LAYOUT_VERTICAL_STEP = 240
FLOW_SOURCE_STRIPPED_METADATA_KEYS = frozenset(
    {
        "figma_source_id",
        "figma_parent_id",
        "figma_source_type",
        # Runtime-only canvas edit fields (not persisted to YAML).
        "canvas_responsible",
        "canvas_participants",
        "canvas_approvers",
        "canvas_note",
        "canvas_duration_context",
    }
)
DEFAULT_NODE_SIZES: dict[EditableNodeKind, tuple[int, int]] = {
    "process": (280, 72),
    "decision_diamond": (280, 96),
    "database": (260, 96),
    "input_data": (260, 72),
    "event": (220, 56),
}
CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

SourceResponsibleType = Literal["team", "role", "system", "external"]

__all__ = [
    "FLOW_SOURCE_SCHEMA_VERSION",
    "FlowSourceDocument",
    "FlowSourceProcess",
    "dump_structured_yaml_payload",
    "dump_flow_source_payload",
    "flow_source_payload_from_editable_payload",
    "editable_flow_graph_payload_from_source_payload",
    "flow_source_payload_from_runtime_payload",
    "graph_source_edge_draft_from_payload",
    "graph_source_node_draft_from_payload",
    "is_flow_source_payload",
    "load_structured_payload",
    "create_flow_source_payload_edge",
    "create_flow_source_payload_node",
    "create_flow_source_payload_process",
    "delete_flow_source_payload_process",
    "flow_source_has_directed_edge",
    "update_flow_source_payload_custom_layout",
    "update_flow_source_payload_edge",
    "update_flow_source_payload_layout",
    "update_flow_source_payload_node",
    "update_flow_source_payload_process",
]


class FlowSourceStrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        populate_by_name=True,
    )


@dataclass(frozen=True)
class YamlLine:
    number: int
    indent: int
    content: str


class FlowSourceResponsible(FlowSourceStrictModel):
    label: str = Field(min_length=1)
    abbr: str | None = None
    type: SourceResponsibleType = "team"
    fill: str
    border: str
    text: str = "#172033"
    aliases: list[str] = Field(default_factory=list)
    note: str | None = None
    active: bool = True
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @field_validator("fill", "border", "text")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not HEX_COLOR_RE.fullmatch(value):
            raise ValueError("color values must use 6-digit hex format, for example '#dcecff'")
        return value


class FlowSourceSection(FlowSourceStrictModel):
    title: str = Field(min_length=1)
    order: int = 0
    note: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class FlowSourceProcess(FlowSourceStrictModel):
    """Grouping frame around cards (not the card kind ``process``)."""

    title: str = Field(min_length=1)
    node_ids: list[str] = Field(default_factory=list)


class FlowSourceTransition(FlowSourceStrictModel):
    to: str = Field(min_length=1)
    kind: EditableEdgeKind = "default"
    label: str | None = None
    condition: str | None = None
    note: str | None = None
    id: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class FlowSourceNode(FlowSourceStrictModel):
    title: str = Field(min_length=1)
    kind: EditableNodeKind
    deleted: bool | None = None
    section: str | None = None
    responsible: str | None = None
    participants: list[str] = Field(default_factory=list)
    approvers: list[str] = Field(default_factory=list)
    duration: str | None = None
    duration_context: str | None = None
    note: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_ref: dict[str, MetaValue] = Field(default_factory=dict)
    transitions: list[FlowSourceTransition] = Field(default_factory=list)
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @field_validator("kind", mode="before")
    @classmethod
    def migrate_legacy_kind(cls, value: object) -> object:
        if value == "decision_card":
            return "process"
        return value

    @field_validator("duration_context")
    @classmethod
    def normalize_duration_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(str(value).split()).strip()
        return cleaned or None

    @field_validator("duration")
    @classmethod
    def normalize_duration(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().lower().split())
        shorthand = SHORT_DURATION_RE.fullmatch(normalized)
        if shorthand is not None:
            unit_key = shorthand.group("unit")
            if shorthand.group("lo") is not None:
                lo = int(shorthand.group("lo"))
                hi = int(shorthand.group("hi"))
                unit = {
                    "m": "minutes",
                    "h": "hours",
                    "d": "days",
                }[unit_key]
                if lo == hi:
                    amount = lo
                    unit = {
                        "m": "minute" if amount == 1 else "minutes",
                        "h": "hour" if amount == 1 else "hours",
                        "d": "day" if amount == 1 else "days",
                    }[unit_key]
                    normalized = f"{amount} {unit}"
                else:
                    normalized = f"{lo}-{hi} {unit}"
            else:
                amount = int(shorthand.group("amount"))
                unit = {
                    "m": "minute" if amount == 1 else "minutes",
                    "h": "hour" if amount == 1 else "hours",
                    "d": "day" if amount == 1 else "days",
                }[unit_key]
                normalized = f"{amount} {unit}"
        return format_node_time(parse_node_time(normalized))


class FlowSourceLayoutEntry(FlowSourceStrictModel):
    x: float
    y: float
    w: int = Field(ge=80, le=1200)
    h: int = Field(ge=40, le=800)


class FlowSourceDocument(FlowSourceStrictModel):
    schema_version: Literal["flow-source/1.0"] = FLOW_SOURCE_SCHEMA_VERSION
    graph_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str | None = None
    responsibles: dict[str, FlowSourceResponsible]
    sections: dict[str, FlowSourceSection] = Field(default_factory=dict)
    processes: dict[str, FlowSourceProcess] = Field(default_factory=dict)
    nodes: dict[str, FlowSourceNode]
    layout: dict[str, FlowSourceLayoutEntry] = Field(default_factory=dict)
    custom_layout: dict[str, FlowSourceLayoutEntry] = Field(default_factory=dict)
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> FlowSourceDocument:
        if not self.responsibles:
            raise ValueError("At least one responsible must be defined")

        responsible_ids = set(self.responsibles)
        node_ids = set(self.nodes)
        section_ids = set(self.sections)
        explicit_transition_ids: list[str] = []

        unknown_layout_ids = sorted(set(self.layout) - node_ids)
        if unknown_layout_ids:
            raise ValueError(f"Unknown layout node ids: {', '.join(unknown_layout_ids)}")
        unknown_custom_layout_ids = sorted(set(self.custom_layout) - node_ids)
        if unknown_custom_layout_ids:
            raise ValueError(
                f"Unknown custom layout node ids: {', '.join(unknown_custom_layout_ids)}"
            )

        for node_id, node in self.nodes.items():
            if node.section is not None and node.section not in section_ids:
                raise ValueError(f"Node {node_id}: unknown section {node.section}")

            combined = [
                responsible
                for responsible in [node.responsible, *node.participants, *node.approvers]
                if responsible is not None
            ]
            if len(combined) != len(set(combined)):
                raise ValueError(f"Node {node_id}: duplicate responsibles are not allowed")
            for responsible in combined:
                if responsible not in responsible_ids:
                    raise ValueError(f"Node {node_id}: unknown responsible {responsible}")

            for transition in node.transitions:
                if transition.to not in node_ids:
                    raise ValueError(f"Node {node_id}: unknown transition target {transition.to}")
                if transition.id is not None:
                    explicit_transition_ids.append(transition.id)

        if len(explicit_transition_ids) != len(set(explicit_transition_ids)):
            raise ValueError("Duplicate transition ids are not allowed")

        membership: dict[str, str] = {}
        for process_id, process in self.processes.items():
            seen_in_process: set[str] = set()
            for member_id in process.node_ids:
                if member_id not in node_ids:
                    raise ValueError(
                        f"Process {process_id}: unknown node id {member_id}"
                    )
                if flow_source_node_deleted(self.nodes[member_id]):
                    raise ValueError(
                        f"Process {process_id}: node {member_id} is deleted"
                    )
                if member_id in seen_in_process:
                    raise ValueError(
                        f"Process {process_id}: duplicate node id {member_id}"
                    )
                seen_in_process.add(member_id)
                owner = membership.get(member_id)
                if owner is not None:
                    raise ValueError(
                        f"Node {member_id} belongs to multiple processes: "
                        f"{owner} and {process_id}"
                    )
                membership[member_id] = process_id
        return self


def load_structured_payload(raw: bytes | str) -> object:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    stripped = text.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return parse_yaml_subset(stripped)


def is_flow_source_payload(payload: object) -> bool:
    return isinstance(payload, dict) and payload.get("schema_version") == FLOW_SOURCE_SCHEMA_VERSION


def editable_flow_graph_payload_from_source_payload(payload: object) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)

    nodes_payload: list[dict[str, Any]] = []
    edges_payload: list[dict[str, Any]] = []
    used_edge_ids: set[str] = set()
    active_node_ids = [
        node_id
        for node_id, node in document.nodes.items()
        if not flow_source_node_deleted(node)
    ]
    active_node_id_set = set(active_node_ids)

    for node_index, node_id in enumerate(active_node_ids):
        node = document.nodes[node_id]
        layout = document.layout.get(node_id) or auto_layout_entry(node.kind, node_index)
        custom_layout = document.custom_layout.get(node_id)
        nodes_payload.append(
            {
                "id": node_id,
                "kind": node.kind,
                "title": node.title,
                "position": {
                    "x": round(float(layout.x), 2),
                    "y": round(float(layout.y), 2),
                },
                "size": {
                    "w": int(layout.w),
                    "h": int(layout.h),
                },
                "responsible": node.responsible,
                "participants": node.participants,
                "approvers": node.approvers,
                "note": node.note,
                "duration": node.duration,
                "duration_context": node.duration_context,
                "metadata": editable_node_metadata(
                    node,
                    custom_layout=custom_layout,
                ),
            }
        )
        for transition_index, transition in enumerate(node.transitions):
            if transition.to not in active_node_id_set:
                continue
            edge_id = unique_edge_id(
                transition.id,
                source=node_id,
                target=transition.to,
                kind=transition.kind,
                label=transition.label,
                index=transition_index,
                used_ids=used_edge_ids,
            )
            used_edge_ids.add(edge_id)
            edges_payload.append(
                {
                    "id": edge_id,
                    "kind": transition.kind,
                    "source": node_id,
                    "target": transition.to,
                    "label": effective_transition_label(transition.kind, transition.label),
                    "metadata": editable_transition_metadata(transition),
                }
            )

    editable_payload = {
        "schema_version": EDITABLE_FLOW_GRAPH_SCHEMA_VERSION,
        "version": document.version,
        "responsibles": {
            responsible_id: {
                "label": responsible.label,
                "fill": responsible.fill,
                "border": responsible.border,
                "text": responsible.text,
                **({"abbr": responsible.abbr} if responsible.abbr else {}),
            }
            for responsible_id, responsible in document.responsibles.items()
        },
        "processes": {
            process_id: {
                "title": process.title,
                "node_ids": [
                    node_id
                    for node_id in process.node_ids
                    if node_id in active_node_id_set
                ],
            }
            for process_id, process in document.processes.items()
        },
        "nodes": nodes_payload,
        "edges": edges_payload,
    }
    EditableFlowGraphDocument.model_validate(editable_payload, strict=True)
    return editable_payload


def flow_source_payload_from_runtime_payload(
    payload: object,
    *,
    graph_id: str,
    title: str,
    description: str | None = None,
) -> dict[str, Any]:
    document = FlowGraphDocument.model_validate(payload, strict=True)
    transitions_by_source: dict[str, list[dict[str, Any]]] = {
        node.id: [] for node in document.nodes
    }
    for edge in document.edges:
        metadata = sanitize_flow_source_metadata(dict(edge.metadata))
        transitions_by_source[edge.source].append(
            {
                "to": edge.target,
                "kind": "default" if edge.kind == "usual" else edge.kind,
                "label": (
                    None
                    if edge.label
                    == effective_transition_label(
                        "default" if edge.kind == "usual" else edge.kind,
                        None,
                    )
                    else edge.label
                ),
                "id": edge.id,
                "metadata": metadata,
            }
        )

    nodes_payload: dict[str, dict[str, Any]] = {}
    custom_layout: dict[str, dict[str, Any]] = {}
    for node in document.nodes:
        metadata = sanitize_flow_source_metadata(dict(node.metadata))
        custom_layout_entry = extract_custom_layout_entry(
            metadata,
            width=int(node.size.w),
            height=int(node.size.h),
        )
        if custom_layout_entry is not None:
            custom_layout[node.id] = custom_layout_entry
        duration_context = _metadata_optional_text(
            node.metadata, "canvas_duration_context"
        )
        nodes_payload[node.id] = {
            "title": node.text,
            "kind": node.kind,
            "responsible": node.primary_responsible,
            "participants": node.secondary_responsibles,
            "duration": node.time,
            "duration_context": duration_context,
            "transitions": transitions_by_source[node.id],
            "metadata": metadata,
        }

    source_payload = {
        "schema_version": FLOW_SOURCE_SCHEMA_VERSION,
        "graph_id": graph_id,
        "title": title,
        "version": document.version,
        "description": description,
        "responsibles": {
            responsible_id: {
                "label": style.label,
                "fill": style.fill,
                "border": style.border,
                "text": style.text,
                **({"abbr": style.abbr} if getattr(style, "abbr", None) else {}),
            }
            for responsible_id, style in document.responsibles.items()
        },
        "processes": {
            process_id: {
                "title": process.title,
                "node_ids": list(process.node_ids),
            }
            for process_id, process in document.processes.items()
        },
        "nodes": nodes_payload,
        "layout": {
            node.id: {
                "x": round(float(node.position.x), 2),
                "y": round(float(node.position.y), 2),
                "w": int(node.size.w),
                "h": int(node.size.h),
            }
            for node in document.nodes
        },
        "custom_layout": custom_layout,
    }
    FlowSourceDocument.model_validate(source_payload, strict=True)
    return source_payload


def flow_source_payload_from_editable_payload(
    payload: object,
    *,
    graph_id: str,
    title: str,
    description: str | None = None,
) -> dict[str, Any]:
    document = EditableFlowGraphDocument.model_validate(payload, strict=True)
    transitions_by_source: dict[str, list[dict[str, Any]]] = {
        node.id: [] for node in document.nodes
    }
    for edge in document.edges:
        metadata = sanitize_flow_source_metadata(dict(edge.metadata))
        condition = metadata.pop("condition", None)
        note = metadata.pop("note", None)
        transitions_by_source[edge.source].append(
            {
                "to": edge.target,
                "kind": edge.kind,
                "label": transition_source_label(edge.kind, edge.label),
                "condition": condition if isinstance(condition, str) else None,
                "note": note if isinstance(note, str) else None,
                "id": edge.id,
                "metadata": metadata,
            }
        )

    sections = editable_sections_payload(document.nodes)
    custom_layout: dict[str, dict[str, Any]] = {}
    nodes_payload: dict[str, dict[str, Any]] = {}
    for node in document.nodes:
        node_payload, custom_layout_entry = editable_node_source_payload(
            node,
            transitions_by_source[node.id],
        )
        nodes_payload[node.id] = node_payload
        if custom_layout_entry is not None:
            custom_layout[node.id] = custom_layout_entry

    source_payload = {
        "schema_version": FLOW_SOURCE_SCHEMA_VERSION,
        "graph_id": graph_id,
        "title": title,
        "version": document.version,
        "description": description,
        "responsibles": {
            responsible_id: {
                "label": style.label,
                "type": "team",
                "fill": style.fill,
                "border": style.border,
                "text": style.text,
                **({"abbr": style.abbr} if getattr(style, "abbr", None) else {}),
            }
            for responsible_id, style in document.responsibles.items()
        },
        "sections": sections,
        "processes": {
            process_id: {
                "title": process.title,
                "node_ids": list(process.node_ids),
            }
            for process_id, process in document.processes.items()
        },
        "nodes": nodes_payload,
        "layout": {
            node.id: {
                "x": round(float(node.position.x), 2),
                "y": round(float(node.position.y), 2),
                "w": int(node.size.w),
                "h": int(node.size.h),
            }
            for node in document.nodes
        },
        "custom_layout": custom_layout,
    }
    FlowSourceDocument.model_validate(source_payload, strict=True)
    return source_payload


def update_flow_source_payload_layout(
    payload: object,
    *,
    positions: dict[str, tuple[float, float]],
    expected_version: int,
) -> dict[str, Any]:
    return update_flow_source_payload_layout_bucket(
        payload,
        positions=positions,
        expected_version=expected_version,
        use_custom_layout=False,
    )


def update_flow_source_payload_custom_layout(
    payload: object,
    *,
    positions: dict[str, tuple[float, float]],
    expected_version: int,
) -> dict[str, Any]:
    return update_flow_source_payload_layout_bucket(
        payload,
        positions=positions,
        expected_version=expected_version,
        use_custom_layout=True,
    )


def update_flow_source_payload_layout_bucket(
    payload: object,
    *,
    positions: dict[str, tuple[float, float]],
    expected_version: int,
    use_custom_layout: bool,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )

    unknown_ids = sorted(set(positions) - set(document.nodes))
    if unknown_ids:
        raise ValueError(f"Unknown graph node positions: {', '.join(unknown_ids)}")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    node_indexes = {node_id: index for index, node_id in enumerate(document.nodes)}
    bucket = updated.custom_layout if use_custom_layout else updated.layout
    for node_id, position in positions.items():
        existing = updated.layout.get(node_id) if use_custom_layout else bucket.get(node_id)
        if existing is None and use_custom_layout:
            existing = bucket.get(node_id)
        if existing is None:
            existing = auto_layout_entry(updated.nodes[node_id].kind, node_indexes[node_id])
        normalized_x = round(float(position[0]), 2)
        normalized_y = round(float(position[1]), 2)
        if not math.isfinite(normalized_x) or not math.isfinite(normalized_y):
            raise ValueError("Layout coordinates must be finite numbers")
        bucket[node_id] = FlowSourceLayoutEntry(
            x=normalized_x,
            y=normalized_y,
            w=int(existing.w),
            h=int(existing.h),
        )
    return updated.model_dump(mode="json")


def graph_source_node_draft_from_payload(payload: object, node_id: str) -> GraphSourceNodeDraft:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if node_id not in document.nodes:
        raise ValueError(f"Unknown graph node: {node_id}")
    node = document.nodes[node_id]
    node_index = list(document.nodes).index(node_id)
    layout = document.layout.get(node_id) or auto_layout_entry(node.kind, node_index)
    return GraphSourceNodeDraft(
        node_id=node_id,
        title=node.title,
        kind=node.kind,
        layout_x=round(float(layout.x), 2),
        layout_y=round(float(layout.y), 2),
        layout_w=int(layout.w),
        layout_h=int(layout.h),
        responsible=node.responsible,
        participants=tuple(node.participants),
        approvers=tuple(node.approvers),
        duration=node.duration,
        note=node.note,
        duration_context=node.duration_context,
    )


def graph_source_edge_draft_from_payload(payload: object, edge_id: str) -> GraphSourceEdgeDraft:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    source_node_id, transition_index = find_transition_location(document, edge_id)
    transition = document.nodes[source_node_id].transitions[transition_index]
    return GraphSourceEdgeDraft(
        edge_id=edge_id,
        source=source_node_id,
        target=transition.to,
        kind=transition.kind,
        label=transition.label,
        condition=transition.condition,
        note=transition.note,
    )


def update_flow_source_payload_node(
    payload: object,
    *,
    command: UpdateGraphSourceNodeCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    if command.node_id not in document.nodes:
        raise ValueError(f"Unknown graph node: {command.node_id}")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    current = updated.nodes[command.node_id]
    previous_layout = updated.layout.get(command.node_id)
    size_changed = previous_layout is None or (
        int(previous_layout.w) != int(command.layout_w)
        or int(previous_layout.h) != int(command.layout_h)
    )
    metadata = dict(current.metadata)
    if size_changed:
        metadata["manual_layout_size"] = True
    updated.nodes[command.node_id] = current.model_copy(
        update={
            "title": command.title,
            "kind": command.kind,
            "responsible": command.responsible,
            "participants": list(command.participants),
            "approvers": list(command.approvers),
            "duration": command.duration,
            "note": command.note,
            "duration_context": command.duration_context,
            "deleted": current.deleted if command.deleted is None else command.deleted,
            "metadata": metadata,
        }
    )
    updated.layout[command.node_id] = FlowSourceLayoutEntry(
        x=round(float(command.layout_x), 2),
        y=round(float(command.layout_y), 2),
        w=int(command.layout_w),
        h=int(command.layout_h),
    )
    if updated.nodes[command.node_id].deleted is True:
        remove_nodes_from_processes(updated, {command.node_id})
    return updated.model_dump(mode="json")


def flow_source_node_deleted(node: FlowSourceNode) -> bool:
    return node.deleted is True


def update_flow_source_payload_edge(
    payload: object,
    *,
    command: UpdateGraphSourceEdgeCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )

    source_node_id, transition_index = find_transition_location(document, command.edge_id)
    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1

    if command.deleted is True:
        del updated.nodes[source_node_id].transitions[transition_index]
        return updated.model_dump(mode="json")

    if command.source not in document.nodes:
        raise ValueError(f"Unknown edge source node: {command.source}")
    if command.target not in document.nodes:
        raise ValueError(f"Unknown edge target node: {command.target}")

    if flow_source_has_directed_edge(
        document,
        source=command.source,
        target=command.target,
        ignore_edge_id=command.edge_id,
    ):
        raise ValueError("Между этими карточками уже есть связь.")

    current_transition = updated.nodes[source_node_id].transitions[transition_index]
    replacement = current_transition.model_copy(
        update={
            "to": command.target,
            "kind": command.kind,
            "label": command.label,
            "condition": command.condition,
            "note": command.note,
            "id": command.edge_id,
        }
    )
    if source_node_id == command.source:
        updated.nodes[source_node_id].transitions[transition_index] = replacement
        return updated.model_dump(mode="json")

    del updated.nodes[source_node_id].transitions[transition_index]
    updated.nodes[command.source].transitions.append(replacement)
    return updated.model_dump(mode="json")


def create_flow_source_payload_edge(
    payload: object,
    *,
    command: CreateGraphSourceEdgeCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    if command.source not in document.nodes:
        raise ValueError(f"Unknown edge source node: {command.source}")
    if command.target not in document.nodes:
        raise ValueError(f"Unknown edge target node: {command.target}")
    if flow_source_node_deleted(document.nodes[command.source]):
        raise ValueError(f"Edge source node is deleted: {command.source}")
    if flow_source_node_deleted(document.nodes[command.target]):
        raise ValueError(f"Edge target node is deleted: {command.target}")
    if flow_source_has_directed_edge(document, source=command.source, target=command.target):
        raise ValueError("Между этими карточками уже есть связь.")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    used_edge_ids = collect_used_edge_ids(updated)
    transition_index = len(updated.nodes[command.source].transitions)
    preferred_id = command.edge_id if isinstance(command.edge_id, str) and command.edge_id else None
    if preferred_id and preferred_id not in used_edge_ids:
        edge_id = preferred_id
    else:
        edge_id = unique_edge_id(
            None,
            source=command.source,
            target=command.target,
            kind=command.kind,
            label=command.label,
            index=transition_index,
            used_ids=used_edge_ids,
        )
    updated.nodes[command.source].transitions.append(
        FlowSourceTransition(
            to=command.target,
            kind=command.kind,
            label=command.label,
            condition=command.condition,
            note=command.note,
            id=edge_id,
        )
    )
    return updated.model_dump(mode="json")


def create_flow_source_payload_node(
    payload: object,
    *,
    command: CreateGraphSourceNodeCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    title = " ".join(str(command.title or "").split()).strip()
    if not title:
        raise ValueError("Заголовок карточки обязателен.")
    kind = command.kind
    if kind not in DEFAULT_NODE_SIZES:
        raise ValueError(f"Unsupported node kind: {kind}")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    used_ids = set(updated.nodes)
    preferred_id = command.node_id if isinstance(command.node_id, str) and command.node_id.strip() else None
    if preferred_id and preferred_id not in used_ids:
        node_id = preferred_id.strip()
    elif preferred_id and preferred_id in used_ids and flow_source_node_deleted(updated.nodes[preferred_id]):
        node_id = preferred_id.strip()
    else:
        node_id = unique_node_id(kind=kind, title=title, used_ids=used_ids)

    layout_w = int(command.layout_w) if command.layout_w else DEFAULT_NODE_SIZES[kind][0]
    layout_h = int(command.layout_h) if command.layout_h else DEFAULT_NODE_SIZES[kind][1]
    layout_entry = FlowSourceLayoutEntry(
        x=round(float(command.layout_x), 2),
        y=round(float(command.layout_y), 2),
        w=max(80, min(1200, layout_w)),
        h=max(40, min(800, layout_h)),
    )

    responsible = resolve_create_node_responsible(
        updated,
        kind=kind,
        responsible=command.responsible,
    )

    if node_id in updated.nodes:
        current = updated.nodes[node_id]
        if not flow_source_node_deleted(current):
            raise ValueError(f"Node already exists: {node_id}")
        updated.nodes[node_id] = current.model_copy(
            update={
                "title": title,
                "kind": kind,
                "responsible": responsible,
                "participants": list(command.participants),
                "approvers": list(command.approvers),
                "duration": command.duration,
                "note": command.note,
                "duration_context": command.duration_context,
                "deleted": False,
                "transitions": [],
                "metadata": {"manual_layout_size": True},
            }
        )
    else:
        updated.nodes[node_id] = FlowSourceNode(
            title=title,
            kind=kind,
            responsible=responsible,
            participants=list(command.participants),
            approvers=list(command.approvers),
            duration=command.duration,
            note=command.note,
            duration_context=command.duration_context,
            deleted=False,
            transitions=[],
            metadata={"manual_layout_size": True},
        )
    updated.layout[node_id] = layout_entry
    return updated.model_dump(mode="json")


def remove_nodes_from_processes(
    document: FlowSourceDocument,
    node_ids: set[str],
) -> None:
    if not node_ids or not document.processes:
        return
    for process_id, process in list(document.processes.items()):
        filtered = [node_id for node_id in process.node_ids if node_id not in node_ids]
        if filtered == process.node_ids:
            continue
        if not filtered:
            del document.processes[process_id]
        else:
            document.processes[process_id] = process.model_copy(
                update={"node_ids": filtered}
            )


def claim_nodes_for_process(
    document: FlowSourceDocument,
    *,
    process_id: str,
    node_ids: list[str],
) -> list[str]:
    """Assign exclusive membership; returns deduplicated ordered node ids."""
    unique_ids: list[str] = []
    seen: set[str] = set()
    for node_id in node_ids:
        if not node_id or node_id in seen:
            continue
        if node_id not in document.nodes:
            raise ValueError(f"Unknown graph node: {node_id}")
        if flow_source_node_deleted(document.nodes[node_id]):
            raise ValueError(f"Node is deleted: {node_id}")
        seen.add(node_id)
        unique_ids.append(node_id)
    remove_nodes_from_processes(document, set(unique_ids))
    return unique_ids


def unique_process_id(*, title: str, used_ids: set[str]) -> str:
    slug = slugify(title) or "process"
    base = f"block_{slug}"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def create_flow_source_payload_process(
    payload: object,
    *,
    command: CreateGraphSourceProcessCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    title = " ".join(str(command.title or "").split()).strip()
    if not title:
        raise ValueError("Название процесса обязательно.")
    if not command.node_ids:
        raise ValueError("Выберите хотя бы одну карточку для процесса.")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    used_ids = set(updated.processes)
    preferred_id = (
        command.process_id.strip()
        if isinstance(command.process_id, str) and command.process_id.strip()
        else None
    )
    if preferred_id and preferred_id not in used_ids:
        process_id = preferred_id
    else:
        process_id = unique_process_id(title=title, used_ids=used_ids)

    node_ids = claim_nodes_for_process(
        updated,
        process_id=process_id,
        node_ids=list(command.node_ids),
    )
    updated.processes[process_id] = FlowSourceProcess(title=title, node_ids=node_ids)
    return updated.model_dump(mode="json")


def update_flow_source_payload_process(
    payload: object,
    *,
    command: UpdateGraphSourceProcessCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    if command.process_id not in document.processes:
        raise ValueError(f"Unknown process: {command.process_id}")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    current = updated.processes[command.process_id]
    title = current.title
    if command.title is not None:
        title = " ".join(str(command.title or "").split()).strip()
        if not title:
            raise ValueError("Название процесса обязательно.")
    node_ids = list(current.node_ids)
    if command.node_ids is not None:
        node_ids = claim_nodes_for_process(
            updated,
            process_id=command.process_id,
            node_ids=list(command.node_ids),
        )
        if not node_ids:
            # Empty membership deletes the process frame (cards remain).
            del updated.processes[command.process_id]
            return updated.model_dump(mode="json")
    updated.processes[command.process_id] = FlowSourceProcess(
        title=title,
        node_ids=node_ids,
    )
    return updated.model_dump(mode="json")


def delete_flow_source_payload_process(
    payload: object,
    *,
    command: DeleteGraphSourceProcessCommand,
    expected_version: int,
) -> dict[str, Any]:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )
    if command.process_id not in document.processes:
        raise ValueError(f"Unknown process: {command.process_id}")

    updated = document.model_copy(deep=True)
    updated.version = expected_version + 1
    del updated.processes[command.process_id]
    return updated.model_dump(mode="json")


def resolve_create_node_responsible(
    document: FlowSourceDocument,
    *,
    kind: EditableNodeKind,
    responsible: str | None,
) -> str | None:
    """Normalize create-node responsible; ensure «Не назначено» exists in catalog."""
    raw = (responsible or "").strip()
    if raw in {"", "none"}:
        raw = ""
    needs_unassigned = kind in {"process", "decision_diamond"} and (
        not raw or raw == "unassigned"
    )
    if needs_unassigned:
        ensure_unassigned_responsible(document)
        return "unassigned"
    if raw == "unassigned":
        ensure_unassigned_responsible(document)
        return "unassigned"
    return responsible


def ensure_unassigned_responsible(document: FlowSourceDocument) -> None:
    if "unassigned" in document.responsibles:
        return
    document.responsibles["unassigned"] = FlowSourceResponsible(
        label="Не назначено",
        fill="#eef2f6",
        border="#94a3b8",
        text="#172033",
    )


def unique_node_id(*, kind: EditableNodeKind, title: str, used_ids: set[str]) -> str:
    prefix = {
        "process": "proc",
        "decision_diamond": "dec",
        "database": "db",
        "input_data": "input",
        "event": "event",
    }.get(kind, "node")
    slug = slugify(title) or "new"
    base = f"{prefix}_{slug}"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def flow_source_has_directed_edge(
    document: FlowSourceDocument,
    *,
    source: str,
    target: str,
    ignore_edge_id: str | None = None,
) -> bool:
    """True if a non-deleted source node already has a transition to target."""
    node = document.nodes.get(source)
    if node is None or flow_source_node_deleted(node):
        return False
    for transition in node.transitions:
        if transition.to != target:
            continue
        if ignore_edge_id is not None and transition.id == ignore_edge_id:
            continue
        return True
    return False


def dump_flow_source_payload(payload: object) -> str:
    document = FlowSourceDocument.model_validate(payload, strict=True)
    normalized = sanitize_flow_source_document_payload(document.model_dump(mode="json"))
    normalized = prune_empty_yaml_value(normalized)
    return dump_structured_yaml_payload(normalized)


def dump_structured_yaml_payload(payload: object) -> str:
    if isinstance(payload, dict):
        rendered = render_yaml_mapping(payload, indent=0)
    elif isinstance(payload, list):
        rendered = render_yaml_sequence(payload, indent=0)
    else:
        rendered = render_yaml_scalar(payload)
    return rendered.rstrip() + "\n"


def editable_node_metadata(
    node: FlowSourceNode,
    *,
    custom_layout: FlowSourceLayoutEntry | None = None,
) -> dict[str, MetaValue]:
    metadata = dict(node.metadata)
    if node.section is not None:
        metadata.setdefault("source_section", node.section)
    if node.tags:
        metadata.setdefault("source_tags", ", ".join(node.tags))
    for key, value in node.source_ref.items():
        metadata.setdefault(f"source_ref:{key}", value)
    if custom_layout is not None:
        metadata.setdefault(CUSTOM_LAYOUT_X_META, round(float(custom_layout.x), 2))
        metadata.setdefault(CUSTOM_LAYOUT_Y_META, round(float(custom_layout.y), 2))
    return metadata


def editable_transition_metadata(transition: FlowSourceTransition) -> dict[str, MetaValue]:
    metadata = dict(transition.metadata)
    if transition.condition is not None:
        metadata.setdefault("condition", transition.condition)
    if transition.note is not None:
        metadata.setdefault("note", transition.note)
    return metadata


def effective_transition_label(kind: EditableEdgeKind, label: str | None) -> str | None:
    if label is not None:
        return label
    if kind == "yes":
        return "Да"
    if kind == "no":
        return "Нет"
    return None


def transition_source_label(kind: EditableEdgeKind, label: str | None) -> str | None:
    if label is None:
        return None
    if label == effective_transition_label(kind, None):
        return None
    return label


def auto_layout_entry(kind: EditableNodeKind, index: int) -> FlowSourceLayoutEntry:
    width, height = DEFAULT_NODE_SIZES[kind]
    row = index // AUTO_LAYOUT_COLUMNS
    col = index % AUTO_LAYOUT_COLUMNS
    return FlowSourceLayoutEntry(
        x=float(120 + col * AUTO_LAYOUT_HORIZONTAL_STEP),
        y=float(140 + row * AUTO_LAYOUT_VERTICAL_STEP),
        w=width,
        h=height,
    )


def collect_used_edge_ids(document: FlowSourceDocument) -> set[str]:
    used_edge_ids: set[str] = set()
    for node_id, node in document.nodes.items():
        for transition_index, transition in enumerate(node.transitions):
            runtime_edge_id = unique_edge_id(
                transition.id,
                source=node_id,
                target=transition.to,
                kind=transition.kind,
                label=transition.label,
                index=transition_index,
                used_ids=used_edge_ids,
            )
            used_edge_ids.add(runtime_edge_id)
    return used_edge_ids


def find_transition_location(
    document: FlowSourceDocument,
    edge_id: str,
) -> tuple[str, int]:
    used_edge_ids: set[str] = set()
    for node_id, node in document.nodes.items():
        for transition_index, transition in enumerate(node.transitions):
            runtime_edge_id = unique_edge_id(
                transition.id,
                source=node_id,
                target=transition.to,
                kind=transition.kind,
                label=transition.label,
                index=transition_index,
                used_ids=used_edge_ids,
            )
            used_edge_ids.add(runtime_edge_id)
            if runtime_edge_id == edge_id:
                return node_id, transition_index
    raise ValueError(f"Unknown graph edge: {edge_id}")


def unique_edge_id(
    explicit_id: str | None,
    *,
    source: str,
    target: str,
    kind: EditableEdgeKind,
    label: str | None,
    index: int,
    used_ids: set[str],
) -> str:
    if explicit_id is not None:
        base = explicit_id
    else:
        parts = ["edge", source, target]
        if kind != "default":
            parts.append(kind)
        if label:
            parts.append(label)
        parts.append(str(index + 1))
        base = slugify(" ".join(parts)) or f"edge_{len(used_ids) + 1}"

    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def slugify(value: str) -> str:
    transliterated = "".join(CYRILLIC_TO_LATIN.get(char, char) for char in value.lower())
    normalized = re.sub(r"[^a-z0-9]+", "_", transliterated).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized[:96]


def prune_empty_yaml_value(value: object) -> object:
    if isinstance(value, dict):
        pruned: dict[str, object] = {}
        for key, item in value.items():
            normalized = prune_empty_yaml_value(item)
            if normalized in (None, [], {}):
                continue
            pruned[key] = normalized
        return pruned
    if isinstance(value, list):
        pruned_items = [prune_empty_yaml_value(item) for item in value]
        return [item for item in pruned_items if item not in (None, [], {})]
    return value


def editable_node_source_payload(
    node: EditableFlowGraphNode,
    transitions: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    metadata = sanitize_flow_source_metadata(dict(node.metadata))
    source_ref = extract_prefixed_metadata(metadata, "source_ref:")
    section = metadata.pop("source_section", None)
    tags = source_tags_from_metadata(metadata.pop("source_tags", None))
    custom_layout = extract_custom_layout_entry(
        metadata,
        width=int(node.size.w),
        height=int(node.size.h),
    )
    return (
        {
            "title": node.title,
            "kind": node.kind,
            "section": section if isinstance(section, str) else None,
            "responsible": node.responsible,
            "participants": list(node.participants),
            "approvers": list(node.approvers),
            "duration": node.duration,
            "duration_context": node.duration_context,
            "note": node.note,
            "tags": tags,
            "source_ref": source_ref,
            "transitions": transitions,
            "metadata": metadata,
        },
        custom_layout,
    )


def editable_sections_payload(
    nodes: list[EditableFlowGraphNode],
) -> dict[str, dict[str, Any]]:
    sections: dict[str, dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        section_id = node.metadata.get("source_section")
        if not isinstance(section_id, str) or not section_id or section_id in sections:
            continue
        sections[section_id] = {
            "title": section_id.replace("_", " ").strip().title() or section_id,
            "order": index,
        }
    return sections


def extract_prefixed_metadata(
    metadata: dict[str, MetaValue],
    prefix: str,
) -> dict[str, MetaValue]:
    extracted: dict[str, MetaValue] = {}
    for key in list(metadata):
        if not key.startswith(prefix):
            continue
        extracted[key.removeprefix(prefix)] = metadata.pop(key)
    return extracted


def source_tags_from_metadata(value: MetaValue) -> list[str]:
    if not isinstance(value, str):
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _metadata_optional_text(
    metadata: dict[str, MetaValue],
    key: str,
) -> str | None:
    raw = metadata.get(key)
    if not isinstance(raw, str):
        return None
    cleaned = " ".join(raw.split()).strip()
    return cleaned or None


def sanitize_flow_source_metadata(
    metadata: dict[str, MetaValue],
) -> dict[str, MetaValue]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in FLOW_SOURCE_STRIPPED_METADATA_KEYS
    }


def sanitize_flow_source_document_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    nodes = payload.get("nodes")
    if not isinstance(nodes, dict):
        return payload

    for node_payload in nodes.values():
        if not isinstance(node_payload, dict):
            continue
        metadata = node_payload.get("metadata")
        if isinstance(metadata, dict):
            node_payload["metadata"] = sanitize_flow_source_metadata(metadata)

        transitions = node_payload.get("transitions")
        if not isinstance(transitions, list):
            continue
        for transition_payload in transitions:
            if not isinstance(transition_payload, dict):
                continue
            transition_metadata = transition_payload.get("metadata")
            if isinstance(transition_metadata, dict):
                transition_payload["metadata"] = sanitize_flow_source_metadata(
                    transition_metadata
                )
    return payload


def extract_custom_layout_entry(
    metadata: dict[str, MetaValue],
    *,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    raw_x = metadata.get(CUSTOM_LAYOUT_X_META)
    raw_y = metadata.get(CUSTOM_LAYOUT_Y_META)
    if not isinstance(raw_x, int | float) or not isinstance(raw_y, int | float):
        return None

    x = round(float(raw_x), 2)
    y = round(float(raw_y), 2)
    if not math.isfinite(x) or not math.isfinite(y):
        return None

    metadata.pop(CUSTOM_LAYOUT_X_META, None)
    metadata.pop(CUSTOM_LAYOUT_Y_META, None)
    return {
        "x": x,
        "y": y,
        "w": int(width),
        "h": int(height),
    }


def render_yaml_mapping(mapping: dict[str, object], *, indent: int) -> str:
    lines: list[str] = []
    for key, value in mapping.items():
        prefix = " " * indent + f"{key}:"
        if isinstance(value, dict) and not value:
            # Inline empty mapping — a bare "key:" is parsed as null.
            lines.append(f"{prefix} {{}}")
            continue
        if isinstance(value, list) and not value:
            lines.append(f"{prefix} []")
            continue
        if is_yaml_scalar(value):
            lines.append(f"{prefix} {render_yaml_scalar(value)}")
            continue
        lines.append(prefix)
        lines.extend(render_yaml_lines(value, indent=indent + 2))
    return "\n".join(lines)


def render_yaml_sequence(items: list[object], *, indent: int) -> str:
    lines: list[str] = []
    for item in items:
        prefix = " " * indent + "-"
        if is_yaml_scalar(item):
            lines.append(f"{prefix} {render_yaml_scalar(item)}")
            continue
        lines.append(prefix)
        lines.extend(render_yaml_lines(item, indent=indent + 2))
    return "\n".join(lines)


def render_yaml_lines(value: object, *, indent: int) -> list[str]:
    if isinstance(value, dict):
        return render_yaml_mapping(value, indent=indent).splitlines()
    if isinstance(value, list):
        return render_yaml_sequence(value, indent=indent).splitlines()
    return [(" " * indent) + render_yaml_scalar(value)]


def is_yaml_scalar(value: object) -> bool:
    return not isinstance(value, (dict, list))


def render_yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_yaml_subset(text: str) -> object:
    lines = tokenize_yaml_lines(text)
    if not lines:
        return None
    if lines[0].indent != 0:
        raise ValueError(
            f"Top-level YAML indentation must start at column 0 (line {lines[0].number})"
        )

    value, next_index = parse_yaml_block(lines, index=0, indent=0)
    if next_index != len(lines):
        trailing = lines[next_index]
        raise ValueError(f"Unexpected trailing YAML content at line {trailing.number}")
    return value


def tokenize_yaml_lines(text: str) -> list[YamlLine]:
    lines: list[YamlLine] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        if "\t" in raw_line:
            raise ValueError(f"Tabs are not supported in YAML indentation (line {number})")
        without_comment = strip_yaml_comment(raw_line).rstrip()
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip(" "))
        lines.append(
            YamlLine(
                number=number,
                indent=indent,
                content=without_comment[indent:],
            )
        )
    return lines


def strip_yaml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in {"'", '"'} and not escaped:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        if char == "#" and quote is None:
            return line[:index]
        escaped = False
    return line


def parse_yaml_block(lines: list[YamlLine], *, index: int, indent: int) -> tuple[object, int]:
    line = lines[index]
    if line.indent != indent:
        raise ValueError(f"Invalid YAML indentation at line {line.number}")
    if is_yaml_sequence_line(line.content):
        return parse_yaml_sequence(lines, index=index, indent=indent)
    return parse_yaml_mapping(lines, index=index, indent=indent)


def parse_yaml_mapping(
    lines: list[YamlLine], *, index: int, indent: int
) -> tuple[dict[str, object], int]:
    mapping: dict[str, object] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent != indent or is_yaml_sequence_line(line.content):
            break

        key, rest = split_yaml_mapping_entry(line.content, line.number)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key '{key}' at line {line.number}")
        index += 1
        if rest:
            mapping[key] = parse_yaml_scalar(rest)
            continue

        if index < len(lines) and lines[index].indent > indent:
            value, index = parse_yaml_block(lines, index=index, indent=lines[index].indent)
            mapping[key] = value
            continue
        mapping[key] = None

    return mapping, index


def parse_yaml_sequence(
    lines: list[YamlLine], *, index: int, indent: int
) -> tuple[list[object], int]:
    items: list[object] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent != indent or not is_yaml_sequence_line(line.content):
            break

        item_text = line.content[1:].strip()
        index += 1
        if not item_text:
            if index < len(lines) and lines[index].indent > indent:
                item, index = parse_yaml_block(lines, index=index, indent=lines[index].indent)
            else:
                item = None
            items.append(item)
            continue

        if looks_like_yaml_mapping_entry(item_text):
            item, index = parse_yaml_sequence_mapping_item(
                lines,
                index=index,
                indent=indent,
                first_entry=item_text,
                line_number=line.number,
            )
            items.append(item)
            continue

        items.append(parse_yaml_scalar(item_text))
    return items, index


def parse_yaml_sequence_mapping_item(
    lines: list[YamlLine],
    *,
    index: int,
    indent: int,
    first_entry: str,
    line_number: int,
) -> tuple[dict[str, object], int]:
    item: dict[str, object] = {}
    key, rest = split_yaml_mapping_entry(first_entry, line_number)
    if rest:
        item[key] = parse_yaml_scalar(rest)
    elif index < len(lines) and lines[index].indent > indent + 1:
        value, index = parse_yaml_block(lines, index=index, indent=lines[index].indent)
        item[key] = value
    else:
        item[key] = None

    item_indent = indent + 2
    while index < len(lines):
        line = lines[index]
        if line.indent <= indent:
            break
        if line.indent != item_indent or is_yaml_sequence_line(line.content):
            break

        key, rest = split_yaml_mapping_entry(line.content, line.number)
        if key in item:
            raise ValueError(f"Duplicate YAML key '{key}' at line {line.number}")
        index += 1
        if rest:
            item[key] = parse_yaml_scalar(rest)
            continue

        if index < len(lines) and lines[index].indent > item_indent:
            value, index = parse_yaml_block(lines, index=index, indent=lines[index].indent)
            item[key] = value
            continue
        item[key] = None
    return item, index


def split_yaml_mapping_entry(content: str, line_number: int) -> tuple[str, str]:
    separator_index = find_unquoted(content, ":")
    if separator_index <= 0:
        raise ValueError(f"Invalid YAML mapping entry at line {line_number}")
    key = content[:separator_index].strip()
    if not key:
        raise ValueError(f"Empty YAML key at line {line_number}")
    rest = content[separator_index + 1 :].strip()
    return key, rest


def looks_like_yaml_mapping_entry(value: str) -> bool:
    return find_unquoted(value, ":") > 0


def is_yaml_sequence_line(value: str) -> bool:
    return value == "-" or value.startswith("- ")


def parse_yaml_scalar(value: str) -> object:
    if value == "{}":
        return {}
    if value.startswith("[") and value.endswith("]"):
        return parse_yaml_inline_list(value[1:-1])
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?\d+\.\d+", value):
        return float(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return unquote_yaml_string(value)
    return value


def parse_yaml_inline_list(value: str) -> list[object]:
    content = value.strip()
    if not content:
        return []
    return [parse_yaml_scalar(part.strip()) for part in split_unquoted(content, ",")]


def split_unquoted(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    depth = 0

    for index, char in enumerate(value):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in {"'", '"'} and not escaped:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif quote is None:
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
            elif char == separator and depth == 0:
                parts.append(value[start:index])
                start = index + 1
        escaped = False
    parts.append(value[start:])
    return parts


def find_unquoted(value: str, target: str) -> int:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in {"'", '"'} and not escaped:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == target and quote is None:
            return index
        escaped = False
    return -1


def unquote_yaml_string(value: str) -> str:
    quote = value[0]
    body = value[1:-1]
    if quote == "'":
        return body.replace("''", "'")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return body
