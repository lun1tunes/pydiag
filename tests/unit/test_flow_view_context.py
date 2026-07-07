from __future__ import annotations

from pydiag.application.flow_view_context import prepare_render_context


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_prepare_render_context_keeps_original_graph_without_edit_mode(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()

    context = prepare_render_context(
        session_state,
        graph=graph,
        wells=wells,
        layout_mode="snake",
        position_edit_enabled=False,
        component_state=None,
    )

    first_node = graph.nodes[0]

    assert context.graph is graph
    assert context.layout_mode == "snake"
    assert context.default_positions[first_node.id] == {
        "x": first_node.position.x,
        "y": first_node.position.y,
    }
    assert session_state == {}


def test_prepare_render_context_switches_to_manual_and_uses_component_positions(documents) -> None:
    graph, wells = documents
    moved_node = graph.nodes[0]
    session_state = FakeSessionState()
    component_state = {
        "positions": {
            node.id: {
                "x": node.position.x + (12.5 if node.id == moved_node.id else 0),
                "y": node.position.y + (6.25 if node.id == moved_node.id else 0),
            }
            for node in graph.nodes
        }
    }

    context = prepare_render_context(
        session_state,
        graph=graph,
        wells=wells,
        layout_mode="snake",
        position_edit_enabled=True,
        component_state=component_state,
    )

    assert context.graph is not graph
    assert context.layout_mode == "manual"
    assert context.graph.nodes[0].position.x == moved_node.position.x + 12.5
    assert context.graph.nodes[0].position.y == moved_node.position.y + 6.25
    assert context.default_positions[moved_node.id] == {
        "x": moved_node.position.x + 12.5,
        "y": moved_node.position.y + 6.25,
    }
    assert session_state["position_edit_dirty"] is True
