from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Literal

HistoryAction = Literal["undo", "redo"]
CommandKind = Literal[
    "move_nodes",
    "create_edge",
    "create_node",
    "update_node",
    "delete_node",
    "update_edge",
    "delete_edge",
]

EDIT_UNDO_KEY = "_flow_edit_undo"
EDIT_REDO_KEY = "_flow_edit_redo"
HISTORY_ACTION_REQUEST_KEY = "_flow_history_action_request_id"
HISTORY_STACK_LIMIT = 50

__all__ = [
    "EDIT_REDO_KEY",
    "EDIT_UNDO_KEY",
    "HISTORY_ACTION_REQUEST_KEY",
    "HISTORY_STACK_LIMIT",
    "can_redo",
    "can_undo",
    "clear_edit_history",
    "peek_redo",
    "peek_undo",
    "pop_redo",
    "pop_undo",
    "push_create_edge_command",
    "push_create_node_command",
    "push_delete_edge_command",
    "push_delete_node_command",
    "push_move_nodes_command",
    "push_update_edge_command",
    "push_update_node_command",
]


def clear_edit_history(session_state: MutableMapping[str, Any]) -> None:
    session_state[EDIT_UNDO_KEY] = []
    session_state[EDIT_REDO_KEY] = []


def can_undo(session_state: MutableMapping[str, Any]) -> bool:
    return bool(_stack(session_state, EDIT_UNDO_KEY))


def can_redo(session_state: MutableMapping[str, Any]) -> bool:
    return bool(_stack(session_state, EDIT_REDO_KEY))


def peek_undo(session_state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    stack = _stack(session_state, EDIT_UNDO_KEY)
    return dict(stack[-1]) if stack else None


def peek_redo(session_state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    stack = _stack(session_state, EDIT_REDO_KEY)
    return dict(stack[-1]) if stack else None


def pop_undo(session_state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    stack = _stack(session_state, EDIT_UNDO_KEY)
    if not stack:
        return None
    command = dict(stack.pop())
    session_state[EDIT_UNDO_KEY] = stack
    return command


def pop_redo(session_state: MutableMapping[str, Any]) -> dict[str, Any] | None:
    stack = _stack(session_state, EDIT_REDO_KEY)
    if not stack:
        return None
    command = dict(stack.pop())
    session_state[EDIT_REDO_KEY] = stack
    return command


def push_move_nodes_command(
    session_state: MutableMapping[str, Any],
    *,
    before: dict[str, tuple[float, float]],
    after: dict[str, tuple[float, float]],
) -> None:
    moved_before = {
        node_id: [float(xy[0]), float(xy[1])]
        for node_id, xy in before.items()
        if node_id in after and after[node_id] != xy
    }
    moved_after = {
        node_id: [float(after[node_id][0]), float(after[node_id][1])]
        for node_id in moved_before
    }
    if not moved_before:
        return
    _push(
        session_state,
        {
            "kind": "move_nodes",
            "before": moved_before,
            "after": moved_after,
        },
    )


def push_create_edge_command(
    session_state: MutableMapping[str, Any],
    *,
    edge_id: str,
    source: str,
    target: str,
    kind: str,
    label: str | None = None,
    condition: str | None = None,
    note: str | None = None,
) -> None:
    _push(
        session_state,
        {
            "kind": "create_edge",
            "edge_id": edge_id,
            "source": source,
            "target": target,
            "kind_value": kind,
            "label": label,
            "condition": condition,
            "note": note,
        },
    )


def push_create_node_command(
    session_state: MutableMapping[str, Any],
    *,
    node_id: str,
    after: Mapping[str, Any],
) -> None:
    _push(
        session_state,
        {
            "kind": "create_node",
            "node_id": node_id,
            "after": dict(after),
        },
    )


def push_update_node_command(
    session_state: MutableMapping[str, Any],
    *,
    node_id: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    if before == after:
        return
    _push(
        session_state,
        {
            "kind": "update_node",
            "node_id": node_id,
            "before": dict(before),
            "after": dict(after),
        },
    )


def push_delete_node_command(
    session_state: MutableMapping[str, Any],
    *,
    node_id: str,
    before: Mapping[str, Any],
) -> None:
    _push(
        session_state,
        {
            "kind": "delete_node",
            "node_id": node_id,
            "before": dict(before),
        },
    )


def push_update_edge_command(
    session_state: MutableMapping[str, Any],
    *,
    edge_id: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    if before == after:
        return
    _push(
        session_state,
        {
            "kind": "update_edge",
            "edge_id": edge_id,
            "before": dict(before),
            "after": dict(after),
        },
    )


def push_delete_edge_command(
    session_state: MutableMapping[str, Any],
    *,
    edge_id: str,
    before: Mapping[str, Any],
) -> None:
    _push(
        session_state,
        {
            "kind": "delete_edge",
            "edge_id": edge_id,
            "before": dict(before),
        },
    )


def _push(session_state: MutableMapping[str, Any], command: dict[str, Any]) -> None:
    undo = _stack(session_state, EDIT_UNDO_KEY)
    undo.append(command)
    if len(undo) > HISTORY_STACK_LIMIT:
        undo = undo[-HISTORY_STACK_LIMIT:]
    session_state[EDIT_UNDO_KEY] = undo
    session_state[EDIT_REDO_KEY] = []


def _stack(session_state: MutableMapping[str, Any], key: str) -> list[dict[str, Any]]:
    raw = session_state.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def push_onto_redo(session_state: MutableMapping[str, Any], command: dict[str, Any]) -> None:
    redo = _stack(session_state, EDIT_REDO_KEY)
    redo.append(command)
    if len(redo) > HISTORY_STACK_LIMIT:
        redo = redo[-HISTORY_STACK_LIMIT:]
    session_state[EDIT_REDO_KEY] = redo


def push_onto_undo_keep_redo(
    session_state: MutableMapping[str, Any],
    command: dict[str, Any],
) -> None:
    """After a successful undo, park the command on the redo stack."""
    push_onto_redo(session_state, command)


def push_onto_undo_from_redo(
    session_state: MutableMapping[str, Any],
    command: dict[str, Any],
) -> None:
    """After a successful redo, put the command back on the undo stack."""
    undo = _stack(session_state, EDIT_UNDO_KEY)
    undo.append(command)
    if len(undo) > HISTORY_STACK_LIMIT:
        undo = undo[-HISTORY_STACK_LIMIT:]
    session_state[EDIT_UNDO_KEY] = undo
