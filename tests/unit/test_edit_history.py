from __future__ import annotations

from pydiag.application.edit_history import (
    can_redo,
    can_undo,
    pop_redo,
    pop_undo,
    push_create_edge_command,
    push_move_nodes_command,
    push_onto_undo_from_redo,
    push_onto_undo_keep_redo,
)
from pydiag.application.flow_view import (
    HISTORY_ACTION_REQUEST_KEY,
    consume_history_action,
    detect_canvas_position_autosave,
)
from pydiag.rendering.flow_canvas_state import component_history_action_from_state


def test_push_move_nodes_records_only_changed_ids() -> None:
    session: dict = {}
    push_move_nodes_command(
        session,
        before={"a": (0.0, 0.0), "b": (10.0, 10.0)},
        after={"a": (5.0, 0.0), "b": (10.0, 10.0)},
    )
    assert can_undo(session)
    assert not can_redo(session)
    command = pop_undo(session)
    assert command is not None
    assert command["kind"] == "move_nodes"
    assert command["before"] == {"a": [0.0, 0.0]}
    assert command["after"] == {"a": [5.0, 0.0]}


def test_push_create_edge_and_undo_redo_stacks() -> None:
    session: dict = {}
    push_create_edge_command(
        session,
        edge_id="e1",
        source="a",
        target="b",
        kind="default",
    )
    command = pop_undo(session)
    assert command is not None
    push_onto_undo_keep_redo(session, command)
    assert can_redo(session)
    assert not can_undo(session)
    redone = pop_redo(session)
    assert redone == command
    push_onto_undo_from_redo(session, redone)
    assert can_undo(session)


def test_component_history_action_from_state_validates() -> None:
    assert component_history_action_from_state(
        {"history_action": {"action": "undo", "request_id": "ha-1"}}
    ) == {"action": "undo", "request_id": "ha-1"}
    assert component_history_action_from_state({"history_action": {"action": "nope"}}) is None


def test_consume_history_action_dedupes_request_id() -> None:
    session: dict = {
        "well_drilling_flow_canvas": {
            "history_action": {"action": "redo", "request_id": "ha-dup"},
        }
    }
    assert consume_history_action(session) == "redo"
    assert session[HISTORY_ACTION_REQUEST_KEY] == "ha-dup"
    assert session["well_drilling_flow_canvas"]["history_action"] is None

    session["well_drilling_flow_canvas"] = {
        "history_action": {"action": "redo", "request_id": "ha-dup"},
    }
    assert consume_history_action(session) is None


def test_detect_canvas_position_autosave(documents) -> None:
    graph, _ = documents
    node = graph.nodes[0]
    session = {
        "well_drilling_flow_canvas": {
            "positions": {
                node.id: {"x": node.position.x + 12.5, "y": node.position.y - 3.0},
            }
        }
    }
    merged = detect_canvas_position_autosave(session, graph=graph)
    assert merged is not None
    assert merged[node.id] == (node.position.x + 12.5, node.position.y - 3.0)

    session["well_drilling_flow_canvas"] = {
        "positions": {
            node.id: {"x": node.position.x, "y": node.position.y},
        }
    }
    assert detect_canvas_position_autosave(session, graph=graph) is None
