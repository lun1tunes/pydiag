from __future__ import annotations

from pydiag.application.flow_view import (
    FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY,
    consume_pending_canvas_edge_edit,
)
from pydiag.rendering.flow_canvas_state import component_pending_edge_edit_from_state


def test_component_pending_edge_edit_from_state_validates(documents) -> None:
    graph, _ = documents
    edge = graph.edges[0]
    assert component_pending_edge_edit_from_state(
        graph,
        {
            "pending_edge_edit": {
                "edge_id": edge.id,
                "kind": "yes",
                "request_id": "ee-1",
            }
        },
    ) == {
        "edge_id": edge.id,
        "kind": "yes",
        "request_id": "ee-1",
    }
    assert (
        component_pending_edge_edit_from_state(
            graph,
            {"pending_edge_edit": {"edge_id": "missing", "kind": "yes"}},
        )
        is None
    )
    assert (
        component_pending_edge_edit_from_state(
            graph,
            {"pending_edge_edit": {"edge_id": edge.id, "kind": "usual"}},
        )
        is None
    )
    assert component_pending_edge_edit_from_state(
        graph,
        {
            "pending_edge_edit": {
                "edge_id": edge.id,
                "deleted": True,
                "request_id": "ee-del",
            }
        },
    ) == {
        "edge_id": edge.id,
        "deleted": True,
        "request_id": "ee-del",
    }


def test_consume_pending_canvas_edge_edit_dedupes_request_id(documents) -> None:
    graph, _ = documents
    edge = graph.edges[0]
    session_state = {
        "well_drilling_flow_canvas": {
            "pending_edge_edit": {
                "edge_id": edge.id,
                "kind": "dashed",
                "request_id": "ee-dup",
            }
        }
    }
    first = consume_pending_canvas_edge_edit(session_state, graph=graph)
    assert first == {"edge_id": edge.id, "kind": "dashed"}
    assert session_state[FLOW_CANVAS_PENDING_EDGE_EDIT_REQUEST_KEY] == "ee-dup"
    assert session_state["well_drilling_flow_canvas"]["pending_edge_edit"] is None

    session_state["well_drilling_flow_canvas"] = {
        "pending_edge_edit": {
            "edge_id": edge.id,
            "kind": "dashed",
            "request_id": "ee-dup",
        }
    }
    assert consume_pending_canvas_edge_edit(session_state, graph=graph) is None
