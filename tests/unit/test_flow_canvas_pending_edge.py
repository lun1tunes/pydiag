from __future__ import annotations

from pydiag.application.flow_view import consume_pending_canvas_edge
from pydiag.rendering.flow_canvas_payload import build_flow_canvas_payload
from pydiag.rendering.flow_canvas_state import component_pending_edge_from_state


def test_payload_includes_edge_edit_enabled_flag(documents) -> None:
    graph, wells = documents
    payload = build_flow_canvas_payload(
        graph,
        wells,
        edge_edit_enabled=True,
    )
    assert payload["edge_edit_enabled"] is True


def test_component_pending_edge_from_state_validates_nodes(documents) -> None:
    graph, _ = documents
    assert component_pending_edge_from_state(
        graph,
        {
            "pending_edge": {
                "source": "proc_initial_review",
                "target": "card_mitigation",
                "kind": "dashed",
            }
        },
    ) == {
        "source": "proc_initial_review",
        "target": "card_mitigation",
        "kind": "dashed",
    }
    assert (
        component_pending_edge_from_state(
            graph,
            {"pending_edge": {"source": "missing", "target": "card_mitigation"}},
        )
        is None
    )
    assert (
        component_pending_edge_from_state(
            graph,
            {
                "pending_edge": {
                    "source": "proc_initial_review",
                    "target": "proc_initial_review",
                }
            },
        )
        is None
    )


def test_consume_pending_canvas_edge_clears_component_state(documents) -> None:
    graph, _ = documents
    session_state = {
        "well_drilling_flow_canvas": {
            "selected_id": "proc_initial_review",
            "pending_edge": {
                "source": "proc_initial_review",
                "target": "card_mitigation",
                "kind": "default",
            },
        }
    }

    pending = consume_pending_canvas_edge(session_state, graph=graph)

    assert pending == {
        "source": "proc_initial_review",
        "target": "card_mitigation",
        "kind": "default",
    }
    assert session_state["well_drilling_flow_canvas"]["pending_edge"] is None
