from __future__ import annotations

from pydiag.application.edit_history import (
    can_undo,
    pop_undo,
    push_delete_node_command,
    push_update_node_command,
)
from pydiag.application.flow_view import (
    FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY,
    FLOW_CANVAS_PENDING_NODE_EDITS_REQUEST_KEY,
    consume_pending_canvas_node_edit,
    consume_pending_canvas_node_edits,
)
from pydiag.rendering.flow_canvas_payload import build_flow_canvas_payload
from pydiag.rendering.flow_canvas_state import (
    component_pending_node_edit_from_state,
    component_pending_node_edits_from_state,
)


def test_payload_includes_node_edit_fields_when_enabled(documents) -> None:
    graph, wells = documents
    payload = build_flow_canvas_payload(
        graph,
        wells,
        node_edit_enabled=True,
    )
    assert payload["node_edit_enabled"] is True
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")
    assert node["editable"] is True
    assert node["title"] == node["text"]
    assert isinstance(node["participants"], list)
    assert isinstance(node["approvers"], list)
    assert node["kind_options"]
    assert node["responsible_options"]
    assert "responsible_id" in node


def test_payload_marks_nodes_not_editable_when_disabled(documents) -> None:
    graph, wells = documents
    payload = build_flow_canvas_payload(graph, wells, node_edit_enabled=False)
    assert payload["node_edit_enabled"] is False
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")
    assert node["editable"] is False


def test_component_pending_node_edit_from_state_validates(documents) -> None:
    graph, _ = documents
    assert component_pending_node_edit_from_state(
        graph,
        {
            "pending_node_edit": {
                "node_id": "proc_initial_review",
                "title": "Новый заголовок",
                "kind": "process",
                "responsible": "planning",
                "participants": ["geology"],
                "approvers": [],
                "duration": "2 hours",
                "note": "note",
                "request_id": "ne-1",
            }
        },
    ) == {
        "node_id": "proc_initial_review",
        "title": "Новый заголовок",
        "kind": "process",
        "responsible": "planning",
        "participants": ["geology"],
        "approvers": [],
        "duration": "2 hours",
        "note": "note",
        "request_id": "ne-1",
    }
    assert (
        component_pending_node_edit_from_state(
            graph,
            {"pending_node_edit": {"node_id": "missing", "title": "x"}},
        )
        is None
    )
    assert component_pending_node_edit_from_state(
        graph,
        {
            "pending_node_edit": {
                "node_id": "proc_initial_review",
                "deleted": True,
                "request_id": "ne-del",
            }
        },
    ) == {
        "node_id": "proc_initial_review",
        "deleted": True,
        "request_id": "ne-del",
    }


def test_consume_pending_canvas_node_edit_dedupes_request_id(documents) -> None:
    graph, _ = documents
    session_state = {
        "well_drilling_flow_canvas": {
            "pending_node_edit": {
                "node_id": "proc_initial_review",
                "title": "A",
                "request_id": "ne-dup",
            }
        }
    }
    first = consume_pending_canvas_node_edit(session_state, graph=graph)
    assert first == {"node_id": "proc_initial_review", "title": "A"}
    assert session_state[FLOW_CANVAS_PENDING_NODE_EDIT_REQUEST_KEY] == "ne-dup"
    assert session_state["well_drilling_flow_canvas"]["pending_node_edit"] is None

    session_state["well_drilling_flow_canvas"] = {
        "pending_node_edit": {
            "node_id": "proc_initial_review",
            "title": "A",
            "request_id": "ne-dup",
        }
    }
    assert consume_pending_canvas_node_edit(session_state, graph=graph) is None


def test_push_update_and_delete_node_history() -> None:
    session: dict = {}
    before = {
        "title": "Old",
        "kind": "process",
        "layout_x": 1.0,
        "layout_y": 2.0,
        "layout_w": 280,
        "layout_h": 72,
        "responsible": "planning",
        "participants": [],
        "approvers": [],
        "duration": None,
        "note": None,
    }
    after = {**before, "title": "New"}
    push_update_node_command(session, node_id="n1", before=before, after=after)
    assert can_undo(session)
    command = pop_undo(session)
    assert command is not None
    assert command["kind"] == "update_node"
    assert command["before"]["title"] == "Old"
    assert command["after"]["title"] == "New"

    push_delete_node_command(session, node_id="n1", before=before)
    deleted = pop_undo(session)
    assert deleted is not None
    assert deleted["kind"] == "delete_node"
    assert deleted["before"]["title"] == "Old"


def test_component_pending_node_edits_bulk_and_duration_context(documents) -> None:
    graph, _ = documents
    assert "seismic" in graph.responsibles
    assert "well_completion" in graph.responsibles
    assert "b" in graph.responsibles
    pending = component_pending_node_edits_from_state(
        graph,
        {
            "pending_node_edits": {
                "request_id": "ne-bulk-1",
                "node_ids": ["proc_initial_review", "proc_well_design"],
                "patch": {
                    "duration": "1-2 hours",
                    "duration_context": "после запроса",
                },
            }
        },
    )
    assert pending is not None
    assert pending["node_ids"] == ["proc_initial_review", "proc_well_design"]
    assert pending["patch"]["duration"] == "1-2 hours"
    assert pending["patch"]["duration_context"] == "после запроса"
    assert pending["request_id"] == "ne-bulk-1"

    session_state = {
        "well_drilling_flow_canvas": {
            "pending_node_edits": {
                "request_id": "ne-bulk-1",
                "node_ids": ["proc_initial_review"],
                "patch": {"duration": "2 hours"},
            }
        }
    }
    first = consume_pending_canvas_node_edits(session_state, graph=graph)
    assert first is not None
    assert first["node_ids"] == ["proc_initial_review"]
    assert session_state[FLOW_CANVAS_PENDING_NODE_EDITS_REQUEST_KEY] == "ne-bulk-1"
    session_state["well_drilling_flow_canvas"] = {
        "pending_node_edits": {
            "request_id": "ne-bulk-1",
            "node_ids": ["proc_initial_review"],
            "patch": {"duration": "2 hours"},
        }
    }
    assert consume_pending_canvas_node_edits(session_state, graph=graph) is None


def test_payload_includes_duration_context_field(documents) -> None:
    graph, wells = documents
    payload = build_flow_canvas_payload(graph, wells, node_edit_enabled=True)
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")
    assert "duration_context" in node
    assert "note" in node
    assert any(opt["id"] == "seismic" for opt in node["responsible_options"])
    assert any(opt["id"] == "b" for opt in node["responsible_options"])


def test_payload_includes_note_when_editing_disabled(documents) -> None:
    graph, wells = documents
    # Inject a note via metadata the same way runtime canvas_note works.
    target = next(node for node in graph.nodes if node.id == "proc_initial_review")
    target.metadata["canvas_note"] = "проверить комплект"
    payload = build_flow_canvas_payload(graph, wells, node_edit_enabled=False)
    node = next(item for item in payload["nodes"] if item["id"] == "proc_initial_review")
    assert node["editable"] is False
    assert node["note"] == "проверить комплект"
