from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument


def component_positions_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, tuple[float, float]] | None:
    if component_state is None:
        return None
    raw_positions = component_state.get("positions")
    if not isinstance(raw_positions, Mapping):
        return None

    result: dict[str, tuple[float, float]] = {}
    known_ids = {node.id for node in graph.nodes}
    for node_id, value in raw_positions.items():
        if node_id not in known_ids or not isinstance(value, Mapping):
            continue
        x = value.get("x")
        y = value.get("y")
        if not isinstance(x, int | float) or not isinstance(y, int | float):
            continue
        result[node_id] = (round(float(x), 2), round(float(y), 2))
    return result or None


def component_selected_id_from_state(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    component_state: Mapping[str, Any] | None,
) -> str | None:
    if component_state is None:
        return None
    selected_id = component_state.get("selected_id")
    if not isinstance(selected_id, str) or not selected_id:
        return None

    node_ids = {node.id for node in graph.nodes}
    edge_ids = {edge.id for edge in graph.edges}
    well_ids = {f"well::{well.id}" for well in wells_doc.wells}
    if (
        selected_id in node_ids
        or selected_id in edge_ids
        or selected_id in well_ids
        or selected_id.startswith("well-extra::")
    ):
        return selected_id
    return None
