from __future__ import annotations

from pydiag.rendering.flow_canvas_state import (
    component_positions_from_state,
    component_selected_id_from_state,
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
