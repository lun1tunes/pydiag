from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MetaValue = str | int | float | bool | None

NodeKind = Literal[
    "process",
    "decision_diamond",
    "decision_card",
    "database",
    "input_data",
    "event",
    "figma_text",
]

EdgeKind = Literal["usual", "yes", "no", "dashed"]
TimeUnit = Literal["minute", "hour", "day"]
TIME_VALUE_RE = re.compile(r"^(?P<amount>\d+)\s+(?P<unit>minutes?|hours?|days?)$")
TIME_UNIT_ALIASES: dict[str, TimeUnit] = {
    "minute": "minute",
    "minutes": "minute",
    "hour": "hour",
    "hours": "hour",
    "day": "day",
    "days": "day",
}
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
RESERVED_UI_ID_PREFIXES = (
    "well::",
    "well-extra::",
    "duration::",
    "responsible::",
    "edge-label::",
    "route-anchor::",
    "route::",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        populate_by_name=True,
    )


class Position(StrictModel):
    x: float
    y: float


class Size(StrictModel):
    w: int = Field(ge=80, le=1200)
    h: int = Field(ge=40, le=800)


class ResponsibleStyle(StrictModel):
    label: str
    fill: str
    border: str
    text: str = "#172033"

    @field_validator("fill", "border", "text")
    @classmethod
    def validate_color(cls, value: str) -> str:
        if not HEX_COLOR_RE.fullmatch(value):
            raise ValueError(
                "color values must use 6-digit hex format, for example '#dcecff'"
            )
        return value


class NodeBase(StrictModel):
    id: str = Field(min_length=1)
    type: NodeKind
    text: str = Field(min_length=1)
    position: Position
    size: Size
    responsible: list[str] = Field(default_factory=list)
    time: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().lower().split())
        if not TIME_VALUE_RE.fullmatch(normalized):
            raise ValueError(
                "time must use '<number> minutes|hours|days', "
                "for example '40 minutes', '10 hours' or '2 days'"
            )
        return normalized

    @property
    def kind(self) -> NodeKind:
        """Compatibility name used by the rendering layer."""
        return self.type

    @property
    def primary_responsible(self) -> str | None:
        return self.responsible[0] if self.responsible else None

    @property
    def secondary_responsibles(self) -> list[str]:
        return self.responsible[1:]


class ProcessNode(NodeBase):
    type: Literal["process"]


class DecisionDiamondNode(NodeBase):
    type: Literal["decision_diamond"]


class DecisionCardNode(NodeBase):
    type: Literal["decision_card"]


class DatabaseNode(NodeBase):
    type: Literal["database"]


class InputDataNode(NodeBase):
    type: Literal["input_data"]


class EventNode(NodeBase):
    type: Literal["event"]


class FigmaTextSkeletonNode(NodeBase):
    type: Literal["figma_text"]


FlowNode = Annotated[
    ProcessNode
    | DecisionDiamondNode
    | DecisionCardNode
    | DatabaseNode
    | InputDataNode
    | EventNode
    | FigmaTextSkeletonNode,
    Field(discriminator="type"),
]


class EdgeBase(StrictModel):
    id: str = Field(min_length=1)
    kind: EdgeKind
    source: str
    target: str
    label: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class UsualEdge(EdgeBase):
    kind: Literal["usual"]


class YesEdge(EdgeBase):
    kind: Literal["yes"]
    label: str = "Да"


class NoEdge(EdgeBase):
    kind: Literal["no"]
    label: str = "Нет"


class DashedEdge(EdgeBase):
    kind: Literal["dashed"]


FlowEdge = Annotated[
    UsualEdge | YesEdge | NoEdge | DashedEdge,
    Field(discriminator="kind"),
]


class FlowGraphDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    version: int = Field(ge=1)
    responsibles: dict[str, ResponsibleStyle]
    nodes: list[FlowNode]
    edges: list[FlowEdge]

    @model_validator(mode="after")
    def validate_graph(self) -> FlowGraphDocument:
        if not self.responsibles:
            raise ValueError("At least one responsible must be defined")

        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Duplicate node ids are not allowed")
        for node_id in node_ids:
            validate_not_reserved_ui_id("Node", node_id)

        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Duplicate edge ids are not allowed")
        for edge_id in edge_ids:
            validate_not_reserved_ui_id("Edge", edge_id)

        node_set = set(node_ids)
        responsible_set = set(self.responsibles)

        for node in self.nodes:
            if (
                node.type in {"process", "decision_diamond", "decision_card"}
                and not node.responsible
            ):
                raise ValueError(
                    f"Node {node.id}: type {node.type} requires at least one responsible"
                )
            if len(node.responsible) != len(set(node.responsible)):
                raise ValueError(
                    f"Node {node.id}: duplicate responsible values are not allowed"
                )
            for responsible in node.responsible:
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


def validate_not_reserved_ui_id(entity: str, value: str) -> None:
    for prefix in RESERVED_UI_ID_PREFIXES:
        if value.startswith(prefix):
            raise ValueError(
                f"{entity} id {value}: prefix {prefix} is reserved for UI internals"
            )


def parse_node_time(value: str) -> tuple[int, TimeUnit]:
    normalized = " ".join(value.strip().lower().split())
    match = TIME_VALUE_RE.fullmatch(normalized)
    if not match:
        raise ValueError(
            "time must use '<number> minutes|hours|days', "
            "for example '40 minutes', '10 hours' or '2 days'"
        )
    return int(match.group("amount")), TIME_UNIT_ALIASES[match.group("unit")]


class WellHistoryEntry(StrictModel):
    ts: datetime
    node_id: str
    action: Literal["create", "move", "rollback"]
    from_node_id: str | None = None
    to_node_id: str | None = None
    by: str | None = None
    comment: str | None = None


class Well(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    current_node_id: str
    history: list[WellHistoryEntry] = Field(default_factory=list)
    metadata: dict[str, MetaValue] = Field(default_factory=dict)
    is_archived: bool = False


class WellsDocument(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    version: int = Field(ge=1)
    wells: list[Well]

    @model_validator(mode="after")
    def validate_wells(self) -> WellsDocument:
        ids = [well.id for well in self.wells]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate well ids are not allowed")
        return self


def node_by_id(graph: FlowGraphDocument) -> dict[str, FlowNode]:
    return {node.id: node for node in graph.nodes}


def well_by_id(wells_doc: WellsDocument) -> dict[str, Well]:
    return {well.id: well for well in wells_doc.wells}


def validate_wells_against_graph(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
) -> None:
    node_ids = {node.id for node in graph.nodes}
    for well in wells_doc.wells:
        if well.current_node_id not in node_ids:
            raise ValueError(
                f"Well {well.id}: current_node_id={well.current_node_id} does not exist in graph"
            )
        for item in well.history:
            if item.node_id not in node_ids:
                raise ValueError(
                    f"Well {well.id}: history node {item.node_id} does not exist in graph"
                )
            if item.from_node_id is not None and item.from_node_id not in node_ids:
                raise ValueError(
                    f"Well {well.id}: history from_node_id={item.from_node_id} "
                    "does not exist in graph"
                )
            if item.to_node_id is not None and item.to_node_id not in node_ids:
                raise ValueError(
                    f"Well {well.id}: history to_node_id={item.to_node_id} does not exist in graph"
                )
