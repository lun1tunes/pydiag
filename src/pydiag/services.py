from __future__ import annotations

from datetime import UTC, datetime

from .models import (
    FlowEdge,
    FlowGraphDocument,
    Well,
    WellHistoryEntry,
    WellsDocument,
    node_by_id,
)


def outgoing_edges(graph: FlowGraphDocument, node_id: str) -> list[FlowEdge]:
    return [edge for edge in graph.edges if edge.source == node_id]


def create_well(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    well_id: str,
    name: str,
    start_node_id: str,
    actor: str,
    metadata: dict[str, str | int | float | bool | None] | None = None,
    comment: str | None = None,
) -> WellsDocument:
    nodes = node_by_id(graph)
    if start_node_id not in nodes:
        raise ValueError(f"Unknown start node: {start_node_id}")
    if any(well.id == well_id for well in wells_doc.wells):
        raise ValueError(f"Well id already exists: {well_id}")

    created = Well(
        id=well_id,
        name=name,
        current_node_id=start_node_id,
        metadata=metadata or {},
        history=[
            WellHistoryEntry(
                ts=datetime.now(UTC),
                node_id=start_node_id,
                action="create",
                from_node_id=None,
                to_node_id=start_node_id,
                by=actor,
                comment=comment or "Created from admin panel",
            )
        ],
    )

    updated = wells_doc.model_copy(deep=True)
    updated.wells.append(created)
    return updated


def delete_well(wells_doc: WellsDocument, well_id: str) -> WellsDocument:
    updated = wells_doc.model_copy(deep=True)
    before = len(updated.wells)
    updated.wells = [well for well in updated.wells if well.id != well_id]
    if len(updated.wells) == before:
        raise ValueError(f"Unknown well: {well_id}")
    return updated


def move_well_to_node(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    well_id: str,
    target_node_id: str,
    actor: str,
    comment: str | None = None,
) -> WellsDocument:
    nodes = node_by_id(graph)
    if target_node_id not in nodes:
        raise ValueError(f"Unknown target node: {target_node_id}")

    updated = wells_doc.model_copy(deep=True)
    well = next((item for item in updated.wells if item.id == well_id), None)
    if well is None:
        raise ValueError(f"Unknown well: {well_id}")

    if well.current_node_id == target_node_id:
        raise ValueError("Well is already on this node")

    allowed_targets = {
        edge.target for edge in graph.edges if edge.source == well.current_node_id
    }
    if target_node_id not in allowed_targets:
        raise ValueError(
            f"Illegal transition: {well.current_node_id} -> {target_node_id}"
        )

    previous = well.current_node_id
    well.current_node_id = target_node_id
    well.history.append(
        WellHistoryEntry(
            ts=datetime.now(UTC),
            node_id=target_node_id,
            action="move",
            from_node_id=previous,
            to_node_id=target_node_id,
            by=actor,
            comment=comment,
        )
    )
    return updated


def rollback_well(
    wells_doc: WellsDocument,
    well_id: str,
    actor: str,
    comment: str | None = None,
) -> WellsDocument:
    updated = wells_doc.model_copy(deep=True)
    well = next((item for item in updated.wells if item.id == well_id), None)
    if well is None:
        raise ValueError(f"Unknown well: {well_id}")
    if len(well.history) < 2:
        raise ValueError("No previous node in well history")

    current = well.current_node_id
    previous_node = well.history[-2].node_id
    if previous_node == current:
        raise ValueError("Previous history entry points to the current node")

    well.current_node_id = previous_node
    well.history.append(
        WellHistoryEntry(
            ts=datetime.now(UTC),
            node_id=previous_node,
            action="rollback",
            from_node_id=current,
            to_node_id=previous_node,
            by=actor,
            comment=comment,
        )
    )
    return updated


def transition_label(edge: FlowEdge, graph: FlowGraphDocument) -> str:
    nodes = node_by_id(graph)
    target_title = nodes[edge.target].title if edge.target in nodes else edge.target
    prefix = edge.label or {
        "default": "Далее",
        "yes": "Да",
        "no": "Нет",
        "dashed": "Возврат",
    }[edge.kind]
    return f"{prefix}: {target_title}"

