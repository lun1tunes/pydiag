from __future__ import annotations

from dataclasses import dataclass

from pydiag.domain import (
    FlowEdge,
    FlowGraphDocument,
    WellsDocument,
    create_well,
    delete_well,
    move_well_to_node,
    rollback_well,
)

__all__ = [
    "CreateWellCommand",
    "WellAdminService",
]


@dataclass(frozen=True)
class CreateWellCommand:
    well_id: str
    name: str
    start_node_id: str
    metadata: dict[str, str]
    comment: str | None


@dataclass(frozen=True)
class WellAdminService:
    graph: FlowGraphDocument
    wells: WellsDocument
    actor: str

    def advance_well(
        self,
        *,
        well_id: str,
        edge_id: str,
        comment: str | None = None,
    ) -> WellsDocument:
        return move_well_to_node(
            self.graph,
            self.wells,
            well_id=well_id,
            target_node_id=self._edge(edge_id).target,
            actor=self.actor,
            comment=comment,
        )

    def rollback_well(
        self,
        *,
        well_id: str,
        comment: str | None = None,
    ) -> WellsDocument:
        return rollback_well(
            self.wells,
            well_id=well_id,
            actor=self.actor,
            comment=comment,
        )

    def delete_well(self, *, well_id: str) -> WellsDocument:
        return delete_well(self.wells, well_id)

    def create_well(self, command: CreateWellCommand) -> WellsDocument:
        return create_well(
            self.graph,
            self.wells,
            well_id=command.well_id,
            name=command.name,
            start_node_id=command.start_node_id,
            actor=self.actor,
            metadata=command.metadata,
            comment=command.comment,
        )

    def _edge(self, edge_id: str) -> FlowEdge:
        edge = next((item for item in self.graph.edges if item.id == edge_id), None)
        if edge is None:
            raise ValueError(f"Unknown edge: {edge_id}")
        return edge
