from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.rendering import build_flow_canvas_payload, component_view_state_from_state

from .flow_view_context import prepare_render_context
from .flow_view_selection import (
    component_state_from_session,
    resolve_selected_id,
    sync_returned_selected_id,
)
from .flow_view_state import flow_state_timestamp

FLOW_CANVAS_COMPONENT_KEY = "well_drilling_flow_canvas"
FLOW_SELECTION_RERUN_REQUEST_KEY = "_flow_selection_rerun_requested"

__all__ = [
    "FLOW_CANVAS_COMPONENT_KEY",
    "FLOW_SELECTION_RERUN_REQUEST_KEY",
    "flow_state_timestamp",
    "render_flow",
]


def render_flow(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    layout_mode: str,
    position_edit_enabled: bool,
    render_canvas,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> str | None:
    previous_selected_id = normalized_selected_id(session_state.get("selected_id"))
    component_state = component_state_from_session(session_state, component_key)
    selected_id = resolve_selected_id(session_state, graph, wells, component_state)
    render_context = prepare_render_context(
        session_state,
        graph=graph,
        wells=wells,
        layout_mode=layout_mode,
        position_edit_enabled=position_edit_enabled,
        component_state=component_state,
    )

    payload = build_flow_canvas_payload(
        render_context.graph,
        wells,
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        selected_id=selected_id,
        layout_mode=render_context.layout_mode,
        domain_nodes_draggable=position_edit_enabled,
        revision=flow_state_timestamp(
            session_state,
            graph=render_context.graph,
            wells=wells,
            search=search,
            responsible_filter=responsible_filter,
            kind_filter=kind_filter,
            layout_mode=render_context.layout_mode,
            position_edit_enabled=position_edit_enabled,
        ),
    )
    returned = render_canvas(
        payload,
        key=component_key,
        default_selected_id=selected_id,
        default_positions=render_context.default_positions,
        persisted_view_state=component_view_state_from_state(component_state),
    )
    selected_id = sync_returned_selected_id(session_state, graph, wells, selected_id, returned)
    if selected_id != previous_selected_id:
        session_state[FLOW_SELECTION_RERUN_REQUEST_KEY] = True
    return selected_id


def normalized_selected_id(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
