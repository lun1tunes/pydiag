from __future__ import annotations

import time
from collections.abc import MutableMapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument

FLOW_VIEW_SIGNATURE_KEY = "flow_view_signature"
FLOW_STATE_TIMESTAMP_KEY = "flow_state_timestamp"

__all__ = ["flow_state_timestamp"]


def flow_state_timestamp(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    layout_mode: str,
    position_edit_enabled: bool = False,
    edge_edit_enabled: bool = False,
    node_edit_enabled: bool = False,
) -> int:
    # Search / kind / responsible filters and live draft positions are applied
    # without bumping scene revision (client dim + incremental geometry).
    del search, responsible_filter, kind_filter
    signature = flow_view_signature(
        graph=graph,
        wells=wells,
        layout_mode=layout_mode,
        position_edit_enabled=position_edit_enabled,
        edge_edit_enabled=edge_edit_enabled,
        node_edit_enabled=node_edit_enabled,
    )
    if session_state.get(FLOW_VIEW_SIGNATURE_KEY) != signature:
        previous = int(session_state.get(FLOW_STATE_TIMESTAMP_KEY, 0))
        session_state[FLOW_VIEW_SIGNATURE_KEY] = signature
        session_state[FLOW_STATE_TIMESTAMP_KEY] = max(previous + 1, int(time.time() * 1000))
    return int(session_state[FLOW_STATE_TIMESTAMP_KEY])


def flow_view_signature(
    *,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    layout_mode: str,
    position_edit_enabled: bool,
    edge_edit_enabled: bool = False,
    node_edit_enabled: bool = False,
) -> tuple[Any, ...]:
    # Topology / versions / chrome flags only. Node positions are synced
    # incrementally via positionsVersion so drag does not clear the scene.
    return (
        graph.version,
        tuple(node.id for node in graph.nodes),
        wells.version,
        tuple((well.id, well.current_node_id, well.is_archived) for well in wells.wells),
        layout_mode,
        position_edit_enabled,
        edge_edit_enabled,
        node_edit_enabled,
    )
