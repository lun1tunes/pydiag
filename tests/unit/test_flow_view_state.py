from __future__ import annotations

from pydiag.application.flow_position_edit import graph_with_positions
from pydiag.application.flow_view_state import flow_state_timestamp


class FakeSessionState(dict):
    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value


def test_flow_state_timestamp_is_stable_for_same_view(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()

    first = flow_state_timestamp(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )
    session_state["flow_component_timestamp"] = first + 1000

    second = flow_state_timestamp(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )

    assert second == first


def test_flow_state_timestamp_changes_only_when_view_signature_changes(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()

    first = flow_state_timestamp(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )
    second = flow_state_timestamp(
        session_state,
        graph=graph,
        wells=wells,
        search="1001",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="snake",
    )

    assert second > first


def test_flow_state_timestamp_changes_when_node_position_changes(documents) -> None:
    graph, wells = documents
    session_state = FakeSessionState()

    first = flow_state_timestamp(
        session_state,
        graph=graph,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="manual",
        position_edit_enabled=True,
    )
    moved = graph_with_positions(
        graph,
        {"proc_initial_review": (graph.nodes[2].position.x + 10, graph.nodes[2].position.y)},
    )
    second = flow_state_timestamp(
        session_state,
        graph=moved,
        wells=wells,
        search="",
        responsible_filter=[],
        kind_filter=[],
        layout_mode="manual",
        position_edit_enabled=True,
    )

    assert second > first
