from __future__ import annotations

from pydiag.rendering.flow_canvas_state import (
    component_positions_from_state,
    component_responsible_filter_from_state,
    component_selected_id_from_state,
    component_view_state_from_state,
)


def test_component_positions_from_state_extracts_known_canvas_positions(documents) -> None:
    graph, _ = documents

    positions = component_positions_from_state(
        graph,
        {
            "positions": {
                "proc_initial_review": {"x": 321.25, "y": 654.5},
                "unknown": {"x": 1, "y": 2},
            }
        },
    )

    assert positions == {"proc_initial_review": (321.25, 654.5)}


def test_component_selected_id_from_state_accepts_domain_edge_and_well(documents) -> None:
    graph, wells = documents

    assert (
        component_selected_id_from_state(
            graph,
            wells,
            {"selected_id": "e_review_decision"},
        )
        == "e_review_decision"
    )
    assert (
        component_selected_id_from_state(
            graph,
            wells,
            {"selected_id": "well::well_1001"},
        )
        == "well::well_1001"
    )
    assert component_selected_id_from_state(graph, wells, {"selected_id": "unknown"}) is None


def test_component_responsible_filter_from_state_keeps_known_keys(documents) -> None:
    graph, _ = documents

    assert component_responsible_filter_from_state(graph, None) is None
    assert component_responsible_filter_from_state(graph, {}) is None
    assert component_responsible_filter_from_state(
        graph,
        {"responsible_filter": ["planning", "unknown", "geology"]},
    ) == ["planning", "geology"]
    assert component_responsible_filter_from_state(
        graph,
        {"responsible_filter": []},
    ) == []


def test_component_view_state_from_state_extracts_viewport() -> None:
    assert component_view_state_from_state(
        {
            "view": {"x": 12.34567, "y": -45.67891, "scale": 0.87543},
            "user_moved_view": True,
        }
    ) == {
        "x": 12.3457,
        "y": -45.6789,
        "scale": 0.8754,
        "user_moved_view": True,
    }


def test_component_view_state_from_state_rejects_invalid_payload() -> None:
    assert component_view_state_from_state({"view": {"x": "12", "y": 3, "scale": 1}}) is None
    assert component_view_state_from_state({"view": {"x": 1, "y": 3, "scale": 0}}) is None
