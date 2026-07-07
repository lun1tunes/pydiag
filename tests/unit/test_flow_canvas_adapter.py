from __future__ import annotations

from pydiag.rendering import (
    build_flow_canvas_payload,
    component_positions_from_state,
    component_selected_id_from_state,
)


def test_rendering_package_exposes_payload_and_state_helpers(documents) -> None:
    graph, wells = documents

    payload = build_flow_canvas_payload(graph, wells, selected_id="well::well_1001")
    positions = component_positions_from_state(
        graph,
        {"positions": {"proc_initial_review": {"x": 321.25, "y": 654.5}}},
    )
    selected_id = component_selected_id_from_state(graph, wells, {"selected_id": "well::well_1001"})

    assert any(node["id"] == "proc_initial_review" for node in payload["nodes"])
    assert positions == {"proc_initial_review": (321.25, 654.5)}
    assert selected_id == "well::well_1001"
