from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pydiag.domain.models import FlowGraphDocument, MetaValue, parse_node_time

EditableNodeKind = Literal[
    "process",
    "decision_diamond",
    "decision_card",
    "database",
    "input_data",
    "event",
]
EditableEdgeKind = Literal["default", "yes", "no", "dashed"]
EDITABLE_FLOW_GRAPH_SCHEMA_VERSION = "editable-flow-graph/1.0"

__all__ = [
    "EDITABLE_FLOW_GRAPH_SCHEMA_VERSION",
    "EditableEdgeKind",
    "EditableFlowGraphDocument",
    "EditableFlowGraphEdge",
    "EditableFlowGraphNode",
    "EditableNodeKind",
    "editable_flow_graph_to_runtime",
    "is_editable_flow_graph_payload",
    "update_editable_graph_payload_positions",
]


class EditableStrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        populate_by_name=True,
    )


class EditablePosition(EditableStrictModel):
    x: float
    y: float


class EditableSize(EditableStrictModel):
    w: int = Field(ge=80, le=1200)
    h: int = Field(ge=40, le=800)


class EditableResponsibleStyle(EditableStrictModel):
    label: str
    fill: str
    border: str
    text: str = "#172033"


class EditableFlowGraphNode(EditableStrictModel):
    id: str = Field(min_length=1)
    kind: EditableNodeKind
    title: str = Field(min_length=1)
    position: EditablePosition
    size: EditableSize
    responsible: str | None = None
    participants: list[str] = Field(default_factory=list)
    approvers: list[str] = Field(default_factory=list)
    note: str | None = None
    duration: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if "participants" not in normalized:
            normalized["participants"] = []

        if "duration" not in normalized:
            legacy_duration = normalized.pop(
                "duration_hours", normalized.pop("durationHours", None)
            )
            if legacy_duration is not None:
                if isinstance(legacy_duration, int):
                    normalized["duration"] = f"{legacy_duration} hours"
                else:
                    normalized["duration"] = legacy_duration
        return normalized

    @model_validator(mode="after")
    def validate_duration(self) -> EditableFlowGraphNode:
        if self.duration is not None:
            parse_node_time(self.duration)
        return self


class EditableFlowGraphEdge(EditableStrictModel):
    id: str = Field(min_length=1)
    kind: EditableEdgeKind = "default"
    source: str
    target: str
    label: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class EditableFlowGraphDocument(EditableStrictModel):
    schema_version: Literal["editable-flow-graph/1.0"] = (
        EDITABLE_FLOW_GRAPH_SCHEMA_VERSION
    )
    version: int = Field(ge=1)
    responsibles: dict[str, EditableResponsibleStyle]
    nodes: list[EditableFlowGraphNode]
    edges: list[EditableFlowGraphEdge]

    @model_validator(mode="after")
    def validate_graph(self) -> EditableFlowGraphDocument:
        if not self.responsibles:
            raise ValueError("At least one responsible must be defined")

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Duplicate node ids are not allowed")

        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Duplicate edge ids are not allowed")

        node_set = set(node_ids)
        responsible_set = set(self.responsibles)
        for node in self.nodes:
            combined = [
                responsible
                for responsible in [
                    node.responsible,
                    *node.participants,
                    *node.approvers,
                ]
                if responsible is not None
            ]
            if len(combined) != len(set(combined)):
                raise ValueError(
                    f"Node {node.id}: duplicate responsibles are not allowed"
                )
            for responsible in combined:
                if responsible not in responsible_set:
                    raise ValueError(
                        f"Node {node.id}: unknown responsible {responsible}"
                    )

        for edge in self.edges:
            if edge.source not in node_set:
                raise ValueError(f"Edge {edge.id}: unknown source node {edge.source}")
            if edge.target not in node_set:
                raise ValueError(f"Edge {edge.id}: unknown target node {edge.target}")
        return self


def is_editable_flow_graph_payload(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == EDITABLE_FLOW_GRAPH_SCHEMA_VERSION
    )


def editable_flow_graph_to_runtime(
    document: EditableFlowGraphDocument,
) -> FlowGraphDocument:
    available_responsibles = set(document.responsibles)
    runtime_payload = {
        "schema_version": "1.0",
        "version": document.version,
        "responsibles": {
            responsible_id: style.model_dump(mode="json")
            for responsible_id, style in document.responsibles.items()
        },
        "nodes": [
            {
                "id": node.id,
                "type": node.kind,
                "text": node.title,
                "position": node.position.model_dump(mode="json"),
                "size": node.size.model_dump(mode="json"),
                "responsible": runtime_node_responsibles(
                    node,
                    available_responsibles=available_responsibles,
                ),
                "time": node.duration,
                "metadata": node.metadata,
            }
            for node in document.nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "kind": "usual" if edge.kind == "default" else edge.kind,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "metadata": edge.metadata,
            }
            for edge in document.edges
        ],
    }
    return FlowGraphDocument.model_validate(runtime_payload, strict=True)


def runtime_node_responsibles(
    node: EditableFlowGraphNode,
    *,
    available_responsibles: set[str],
) -> list[str]:
    ordered = [
        responsible
        for responsible in [node.responsible, *node.participants, *node.approvers]
        if responsible
    ]
    deduplicated = list(dict.fromkeys(ordered))
    if deduplicated:
        return deduplicated
    if (
        node.kind in {"process", "decision_diamond", "decision_card"}
        and "unassigned" in available_responsibles
    ):
        return ["unassigned"]
    return []


def update_editable_graph_payload_positions(
    payload: object,
    positions: dict[str, tuple[float, float]],
    expected_version: int,
) -> object:
    document = EditableFlowGraphDocument.model_validate(payload, strict=True)
    if document.version != expected_version:
        raise RuntimeError(
            f"Conflict: expected graph version {expected_version}, actual version is {document.version}"
        )

    node_payloads = {node.id: node for node in document.nodes}
    unknown_ids = sorted(set(positions) - set(node_payloads))
    if unknown_ids:
        raise ValueError(f"Unknown graph node positions: {', '.join(unknown_ids)}")

    updated_payload = document.model_dump(mode="json")
    updated_payload["version"] = expected_version + 1
    for node_payload in updated_payload["nodes"]:
        position = positions.get(node_payload["id"])
        if position is None:
            continue
        node_payload["position"] = {
            "x": round(float(position[0]), 2),
            "y": round(float(position[1]), 2),
        }
    return updated_payload
