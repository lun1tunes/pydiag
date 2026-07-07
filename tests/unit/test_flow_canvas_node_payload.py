from __future__ import annotations

from pydiag.rendering.flow_canvas_payload import build_flow_canvas_nodes_from_snapshot
from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot


def test_build_flow_canvas_nodes_from_snapshot_embeds_overlays_in_domain_node(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")

    nodes, active_node_ids = build_flow_canvas_nodes_from_snapshot(
        snapshot,
        selected_id="well::well_1001",
    )

    node = next(item for item in nodes if item["id"] == "proc_initial_review")

    assert "proc_initial_review" in active_node_ids
    assert node["time_badge"] is not None
    assert node["time_badge"]["text"] == "16 ч"
    assert [badge["abbr"] for badge in node["responsible_badges"]] == ["ГЕО", "ПБОТОС"]
    assert node["well_tokens"][0]["id"] == "well::well_1001"
    assert node["well_tokens"][0]["selected"] is True
    assert node["well_tokens"][0]["style"]["pointerEvents"] == "auto"
