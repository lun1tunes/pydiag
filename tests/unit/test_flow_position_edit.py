from __future__ import annotations

from pydiag.common.layout_metadata import CUSTOM_LAYOUT_X_META, CUSTOM_LAYOUT_Y_META
from pydiag.application.flow_position_edit import (
    custom_layout_positions_for_graph,
    ensure_position_edit_positions,
    graph_with_positions,
    initial_position_edit_positions,
    position_edit_positions_from_state,
    update_position_edit_positions_from_component,
)


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_position_edit_positions_from_state_falls_back_to_graph_positions(documents) -> None:
    graph, _ = documents
    first_node = graph.nodes[0]
    session_state = FakeSessionState(
        {
            "position_edit_positions": {
                first_node.id: "bad-value",
                "unknown": (1, 2),
            }
        }
    )

    positions = position_edit_positions_from_state(session_state, graph)

    assert positions[first_node.id] == (first_node.position.x, first_node.position.y)
    assert set(positions) == {node.id for node in graph.nodes}


def test_ensure_position_edit_positions_resets_when_signature_changes(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()

    ensure_position_edit_positions(session_state, graph, wells, "snake")
    session_state["position_edit_positions"] = {node.id: (999.0, 999.0) for node in graph.nodes}

    positions = ensure_position_edit_positions(session_state, graph, wells, "manual")

    assert positions == initial_position_edit_positions(graph, wells, "manual")
    assert session_state["position_edit_dirty"] is False


def test_update_position_edit_positions_from_component_marks_state_dirty(documents) -> None:
    graph, _ = documents
    session_state = FakeSessionState(
        {
            "position_edit_positions": {
                node.id: (node.position.x, node.position.y) for node in graph.nodes
            }
        }
    )
    moved_node = graph.nodes[0]
    component_state = {
        "positions": {
            node.id: {
                "x": node.position.x + (4.25 if node.id == moved_node.id else 0),
                "y": node.position.y + (3.5 if node.id == moved_node.id else 0),
            }
            for node in graph.nodes
        }
    }

    changed = update_position_edit_positions_from_component(session_state, graph, component_state)

    assert changed is True
    assert session_state["position_edit_dirty"] is True
    assert session_state["position_edit_positions"][moved_node.id] == (
        round(moved_node.position.x + 4.25, 2),
        round(moved_node.position.y + 3.5, 2),
    )


def test_graph_with_positions_returns_new_graph_with_overridden_coordinates(documents) -> None:
    graph, _ = documents
    node = graph.nodes[0]

    moved = graph_with_positions(graph, {node.id: (node.position.x + 12.0, node.position.y + 8.0)})

    assert moved is not graph
    assert moved.nodes[0].position.x == node.position.x + 12.0
    assert moved.nodes[0].position.y == node.position.y + 8.0
    assert graph.nodes[0].position.x == node.position.x
    assert graph.nodes[0].position.y == node.position.y


def test_custom_layout_positions_for_graph_prefers_metadata_when_available(
    documents,
) -> None:
    graph, _ = documents
    first_node = graph.nodes[0]
    graph.nodes[0].metadata[CUSTOM_LAYOUT_X_META] = 901.25
    graph.nodes[0].metadata[CUSTOM_LAYOUT_Y_META] = 444.5

    positions = custom_layout_positions_for_graph(graph)

    assert positions[first_node.id] == (901.25, 444.5)
