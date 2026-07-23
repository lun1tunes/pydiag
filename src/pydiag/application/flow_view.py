from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.rendering import (
    build_flow_canvas_payload,
    component_pending_edge_from_state,
    component_responsible_filter_from_state,
)
from pydiag.rendering.flow_canvas_state import (
    component_history_action_from_state,
    component_pending_edge_edit_from_state,
    component_pending_node_edit_from_state,
    component_positions_from_state,
)

from .edit_history import HISTORY_ACTION_REQUEST_KEY
from .flow_position_edit import graph_node_positions
from .flow_view_context import prepare_render_context
from .flow_view_selection import (
    component_state_from_session,
    resolve_selected_id,
    sync_returned_selected_id,
)
from .flow_view_state import flow_state_timestamp

FLOW_CANVAS_COMPONENT_KEY = "well_drilling_flow_canvas"
FLOW_CANVAS_PENDING_EDGE_REQUEST_KEY = "_flow_canvas_pending_edge_request_id"
FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY = "_flow_canvas_pending_node_edit_request_id"
FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY = "_flow_canvas_pending_edge_edit_request_id"
FLOW_SELECTION_RERUN_REQUEST_KEY = "_flow_selection_rerun_requested"
FLOW_RESPONSIBLE_FILTER_RERUN_REQUEST_KEY = "_flow_responsible_filter_rerun_requested"
FLOW_RENDER_SNAPSHOT_CACHE_KEY = "_flow_render_snapshot_cache"
FLOW_CANVAS_SESSION_EPOCH_KEY = "_flow_canvas_session_epoch"
# Sidebar multiselect widget key — must not collide with canvas component state
# field "responsible_filter" nested under FLOW_CANVAS_COMPONENT_KEY.
RESPONSIBLE_FILTER_SESSION_KEY = "sidebar_responsible_filter"
RESPONSIBLE_FILTER_LAST_KEY = "_responsible_filter_last"

__all__ = [
    "FLOW_CANVAS_COMPONENT_KEY",
    "FLOW_CANVAS_PENDING_EDGE_REQUEST_KEY",
    "FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY",
    "FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY",
    "FLOW_CANVAS_SESSION_EPOCH_KEY",
    "FLOW_RENDER_SNAPSHOT_CACHE_KEY",
    "FLOW_RESPONSIBLE_FILTER_RERUN_REQUEST_KEY",
    "FLOW_SELECTION_RERUN_REQUEST_KEY",
    "HISTORY_ACTION_REQUEST_KEY",
    "RESPONSIBLE_FILTER_LAST_KEY",
    "RESPONSIBLE_FILTER_SESSION_KEY",
    "bump_flow_canvas_session_epoch",
    "consume_history_action",
    "consume_pending_canvas_edge",
    "consume_pending_canvas_edge_edit",
    "consume_pending_canvas_node_edit",
    "consume_responsible_filter_rerun_request",
    "detect_canvas_position_autosave",
    "flow_state_timestamp",
    "render_flow",
    "resolve_responsible_filter",
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
    edge_edit_enabled: bool = False,
    node_edit_enabled: bool = False,
    can_undo: bool = False,
    can_redo: bool = False,
    render_canvas,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> str | None:
    component_state = component_state_from_session(session_state, component_key)
    selected_id = resolve_selected_id(session_state, graph, wells, component_state)
    effective_responsible_filter = resolve_responsible_filter(
        session_state,
        graph=graph,
        component_state=component_state,
        sidebar_filter=responsible_filter,
        component_key=component_key,
    )
    render_context = prepare_render_context(
        session_state,
        graph=graph,
        wells=wells,
        layout_mode=layout_mode,
        position_edit_enabled=position_edit_enabled,
        component_state=component_state,
    )

    revision = flow_state_timestamp(
        session_state,
        graph=render_context.graph,
        wells=wells,
        search=search,
        responsible_filter=effective_responsible_filter,
        kind_filter=kind_filter,
        layout_mode=render_context.layout_mode,
        position_edit_enabled=position_edit_enabled,
        edge_edit_enabled=edge_edit_enabled,
        node_edit_enabled=node_edit_enabled,
    )
    snapshot_cache = session_state.setdefault(FLOW_RENDER_SNAPSHOT_CACHE_KEY, {})
    if not isinstance(snapshot_cache, dict):
        snapshot_cache = {}
        session_state[FLOW_RENDER_SNAPSHOT_CACHE_KEY] = snapshot_cache
    payload = build_flow_canvas_payload(
        render_context.graph,
        wells,
        search=search,
        responsible_filter=effective_responsible_filter,
        kind_filter=kind_filter,
        selected_id=selected_id,
        layout_mode=render_context.layout_mode,
        domain_nodes_draggable=position_edit_enabled,
        edge_edit_enabled=edge_edit_enabled,
        node_edit_enabled=node_edit_enabled,
        can_undo=can_undo,
        can_redo=can_redo,
        revision=revision,
        snapshot_cache=snapshot_cache,
        session_epoch=int(session_state.get(FLOW_CANVAS_SESSION_EPOCH_KEY, 0) or 0),
    )
    returned = render_canvas(
        payload,
        key=component_key,
        default_selected_id=selected_id,
        default_positions=render_context.default_positions,
        default_responsible_filter=effective_responsible_filter,
    )
    # Selection stays local in canvas JS; session_state is only mirrored for the
    # inspector in the same fragment. Never request a full-app selection rerun.
    return sync_returned_selected_id(session_state, graph, wells, selected_id, returned)


def detect_canvas_position_autosave(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> dict[str, tuple[float, float]] | None:
    """Return full node positions to persist when canvas drag changed layout."""
    component_state = component_state_from_session(session_state, component_key)
    incoming = component_positions_from_state(graph, component_state)
    if incoming is None:
        return None
    persisted = graph_node_positions(graph)
    changed = False
    merged = dict(persisted)
    for node_id, xy in incoming.items():
        if persisted.get(node_id) != xy:
            changed = True
        merged[node_id] = xy
    return merged if changed else None


def consume_history_action(
    session_state: MutableMapping[str, Any],
    *,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> str | None:
    """Take a pending undo/redo action once. Returns ``\"undo\"`` / ``\"redo\"``."""
    component_state = component_state_from_session(session_state, component_key)
    pending = component_history_action_from_state(component_state)
    if pending is None:
        return None
    request_id = pending["request_id"]
    if session_state.get(HISTORY_ACTION_REQUEST_KEY) == request_id:
        _clear_history_action_component_state(session_state, component_key)
        return None
    session_state[HISTORY_ACTION_REQUEST_KEY] = request_id
    _clear_history_action_component_state(session_state, component_key)
    return pending["action"]


def _clear_history_action_component_state(
    session_state: MutableMapping[str, Any],
    component_key: str,
) -> None:
    current = session_state.get(component_key)
    if isinstance(current, dict):
        updated = dict(current)
        updated["history_action"] = None
        session_state[component_key] = updated


def consume_pending_canvas_edge(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> dict[str, str] | None:
    """Take a pending canvas edge once, clearing component state to avoid repeats.

    Must run before the canvas widget with ``component_key`` is instantiated in
    the same script/fragment run. Streamlit rejects writes to
    ``session_state[component_key]`` after that widget exists.

    Streamlit bidi may re-surface the same ``pending_edge`` after rerun because
    the frontend state is not cleared. Deduplicate by ``request_id`` when present.
    """
    component_state = component_state_from_session(session_state, component_key)
    pending = component_pending_edge_from_state(graph, component_state)
    if pending is None:
        return None

    request_id = pending.get("request_id")
    if isinstance(request_id, str) and request_id:
        if session_state.get(FLOW_CANVAS_PENDING_EDGE_REQUEST_KEY) == request_id:
            _clear_pending_edge_component_state(session_state, component_key)
            return None
        session_state[FLOW_CANVAS_PENDING_EDGE_REQUEST_KEY] = request_id

    _clear_pending_edge_component_state(session_state, component_key)
    return {
        "source": pending["source"],
        "target": pending["target"],
        "kind": pending["kind"],
    }


def _clear_pending_edge_component_state(
    session_state: MutableMapping[str, Any],
    component_key: str,
) -> None:
    current = session_state.get(component_key)
    if isinstance(current, dict):
        updated = dict(current)
        updated["pending_edge"] = None
        session_state[component_key] = updated


def consume_pending_canvas_node_edit(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> dict[str, Any] | None:
    """Take a pending canvas node edit once. Must run before canvas mount."""
    component_state = component_state_from_session(session_state, component_key)
    pending = component_pending_node_edit_from_state(graph, component_state)
    if pending is None:
        return None

    request_id = pending.get("request_id")
    if isinstance(request_id, str) and request_id:
        if session_state.get(FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY) == request_id:
            _clear_pending_node_edit_component_state(session_state, component_key)
            return None
        session_state[FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY] = request_id

    _clear_pending_node_edit_component_state(session_state, component_key)
    result = dict(pending)
    result.pop("request_id", None)
    return result


def _clear_pending_node_edit_component_state(
    session_state: MutableMapping[str, Any],
    component_key: str,
) -> None:
    current = session_state.get(component_key)
    if isinstance(current, dict):
        updated = dict(current)
        updated["pending_node_edit"] = None
        session_state[component_key] = updated


def consume_pending_canvas_edge_edit(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> dict[str, Any] | None:
    """Take a pending canvas edge edit once. Must run before canvas mount."""
    component_state = component_state_from_session(session_state, component_key)
    pending = component_pending_edge_edit_from_state(graph, component_state)
    if pending is None:
        return None

    request_id = pending.get("request_id")
    if isinstance(request_id, str) and request_id:
        if session_state.get(FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY) == request_id:
            _clear_pending_edge_edit_component_state(session_state, component_key)
            return None
        session_state[FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY] = request_id

    _clear_pending_edge_edit_component_state(session_state, component_key)
    result = dict(pending)
    result.pop("request_id", None)
    return result


def _clear_pending_edge_edit_component_state(
    session_state: MutableMapping[str, Any],
    component_key: str,
) -> None:
    current = session_state.get(component_key)
    if isinstance(current, dict):
        updated = dict(current)
        updated["pending_edge_edit"] = None
        session_state[component_key] = updated


def resolve_responsible_filter(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    component_state: Any,
    sidebar_filter: list[str],
    component_key: str = FLOW_CANVAS_COMPONENT_KEY,
) -> list[str]:
    sidebar_values = list(sidebar_filter)
    from_component = component_responsible_filter_from_state(graph, component_state)
    last_raw = session_state.get(RESPONSIBLE_FILTER_LAST_KEY)
    last_values = list(last_raw) if isinstance(last_raw, list) else None

    if from_component is None:
        chosen = sidebar_values
    elif last_values is None:
        # First sync: prefer a non-empty legend/component opinion, else sidebar.
        if from_component and from_component != sidebar_values:
            chosen = list(from_component)
            session_state[RESPONSIBLE_FILTER_SESSION_KEY] = list(chosen)
        else:
            chosen = sidebar_values
    else:
        sidebar_changed = sidebar_values != last_values
        component_changed = from_component != last_values
        if sidebar_changed and not component_changed:
            chosen = sidebar_values
            _write_component_responsible_filter(session_state, component_key, chosen)
        elif component_changed and not sidebar_changed:
            chosen = list(from_component)
            # Mirror legend → sidebar widget for the next full script run.
            session_state[RESPONSIBLE_FILTER_SESSION_KEY] = list(chosen)
        elif sidebar_changed and component_changed:
            # Prefer the Streamlit sidebar control when both moved.
            chosen = sidebar_values
            _write_component_responsible_filter(session_state, component_key, chosen)
        else:
            chosen = sidebar_values

    session_state[RESPONSIBLE_FILTER_LAST_KEY] = list(chosen)
    return list(chosen)


def _write_component_responsible_filter(
    session_state: MutableMapping[str, Any],
    component_key: str,
    values: list[str],
) -> None:
    current = session_state.get(component_key)
    if isinstance(current, dict):
        updated = dict(current)
        updated["responsible_filter"] = list(values)
        session_state[component_key] = updated
    else:
        session_state[component_key] = {"responsible_filter": list(values)}


def consume_responsible_filter_rerun_request(
    session_state: MutableMapping[str, Any],
) -> bool:
    return bool(session_state.pop(FLOW_RESPONSIBLE_FILTER_RERUN_REQUEST_KEY, False))


def normalized_selected_id(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def bump_flow_canvas_session_epoch(session_state: MutableMapping[str, Any]) -> int:
    next_epoch = int(session_state.get(FLOW_CANVAS_SESSION_EPOCH_KEY, 0) or 0) + 1
    session_state[FLOW_CANVAS_SESSION_EPOCH_KEY] = next_epoch
    session_state.pop(FLOW_RENDER_SNAPSHOT_CACHE_KEY, None)
    return next_epoch
