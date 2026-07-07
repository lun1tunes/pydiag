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
) -> int:
    signature = flow_view_signature(
        graph=graph,
        wells=wells,
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        layout_mode=layout_mode,
        position_edit_enabled=position_edit_enabled,
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
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    layout_mode: str,
    position_edit_enabled: bool,
) -> tuple[Any, ...]:
    return (
        graph.version,
        tuple((node.id, node.position.x, node.position.y) for node in graph.nodes),
        wells.version,
        tuple((well.id, well.current_node_id, well.is_archived) for well in wells.wells),
        search.strip().casefold(),
        tuple(responsible_filter),
        tuple(kind_filter),
        layout_mode,
        position_edit_enabled,
    )
