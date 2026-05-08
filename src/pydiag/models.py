from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MetaValue = str | int | float | bool | None

NodeKind = Literal[
    "process",
    "decision_diamond",
    "decision_card",
    "database",
    "input_data",
]

EdgeKind = Literal["default", "yes", "no", "dashed"]


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


class ApproverBadge(StrictModel):
    responsible: str
    label: str | None = None


class NodeBase(StrictModel):
    id: str = Field(min_length=1)
    kind: NodeKind
    title: str = Field(min_length=1)
    position: Position
    size: Size
    note: str | None = None
    approvers: list[ApproverBadge] = Field(default_factory=list)
    duration_hours: int | None = Field(default=None, ge=0)
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class ProcessNode(NodeBase):
    kind: Literal["process"]
    responsible: str


class DecisionDiamondNode(NodeBase):
    kind: Literal["decision_diamond"]


class DecisionCardNode(NodeBase):
    kind: Literal["decision_card"]


class DatabaseNode(NodeBase):
    kind: Literal["database"]


class InputDataNode(NodeBase):
    kind: Literal["input_data"]


FlowNode = Annotated[
    ProcessNode | DecisionDiamondNode | DecisionCardNode | DatabaseNode | InputDataNode,
    Field(discriminator="kind"),
]


class EdgeBase(StrictModel):
    id: str = Field(min_length=1)
    kind: EdgeKind
    source: str
    target: str
    label: str | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)


class DefaultEdge(EdgeBase):
    kind: Literal["default"]


class YesEdge(EdgeBase):
    kind: Literal["yes"]
    label: str = "Да"


class NoEdge(EdgeBase):
    kind: Literal["no"]
    label: str = "Нет"


class DashedEdge(EdgeBase):
    kind: Literal["dashed"]


FlowEdge = Annotated[
    DefaultEdge | YesEdge | NoEdge | DashedEdge,
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

        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Duplicate edge ids are not allowed")

        node_set = set(node_ids)
        responsible_set = set(self.responsibles)

        for node in self.nodes:
            if node.kind == "process" and node.responsible not in responsible_set:
                raise ValueError(f"Node {node.id}: unknown responsible {node.responsible}")
            for approver in node.approvers:
                if approver.responsible not in responsible_set:
                    raise ValueError(f"Node {node.id}: unknown approver {approver.responsible}")

        for edge in self.edges:
            if edge.source not in node_set:
                raise ValueError(f"Edge {edge.id}: unknown source node {edge.source}")
            if edge.target not in node_set:
                raise ValueError(f"Edge {edge.id}: unknown target node {edge.target}")
        return self


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
