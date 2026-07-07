from __future__ import annotations

from pydiag.rendering.flow_render_snapshot import build_flow_render_snapshot
from pydiag.rendering.flow_streamlit_nodes import overlay_nodes_for_domain_node


def test_overlay_nodes_for_domain_node_builds_duration_responsibles_and_wells(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    overlay_nodes = overlay_nodes_for_domain_node(
        graph=graph,
        node=node,
        wells_here=snapshot.wells_by_node[node.id],
        node_position=snapshot.positions[node.id],
        node_height=snapshot.render_specs[node.id].height,
        selected_id="well::well_1001",
        search="",
        active=True,
    )

    assert {item.id for item in overlay_nodes} == {
        "duration::proc_initial_review",
        "responsible::proc_initial_review::geology",
        "responsible::proc_initial_review::hse",
        "well::well_1001",
    }
    token = next(item for item in overlay_nodes if item.id == "well::well_1001")
    assert token.selectable is True
    assert token.style["opacity"] == 1.0


def test_overlay_nodes_for_domain_node_adds_overflow_token_after_four_wells(documents) -> None:
    graph, wells = documents
    snapshot = build_flow_render_snapshot(graph, wells, "snake")
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")
    template_well = next(item for item in wells.wells if not item.is_archived)
    many_wells = [
        template_well.model_copy(
            update={
                "id": f"well_extra_{index}",
                "name": f"Скв. Тест {index}",
                "current_node_id": node.id,
            }
        )
        for index in range(5)
    ]

    overlay_nodes = overlay_nodes_for_domain_node(
        graph=graph,
        node=node,
        wells_here=many_wells,
        node_position=snapshot.positions[node.id],
        node_height=snapshot.render_specs[node.id].height,
        selected_id=None,
        search="",
        active=False,
    )

    extra = next(item for item in overlay_nodes if item.id == "well-extra::proc_initial_review")
    assert len([item for item in overlay_nodes if item.id.startswith("well::")]) == 4
    assert "Скв. **+1**" in extra.data["content"]
    assert extra.style["opacity"] == 0.24
