from __future__ import annotations

from pathlib import Path

from pydiag.common.graph_source_admin import (
    CreateGraphSourceEdgeCommand,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
)
from pydiag.infrastructure.flow_source_graph import (
    create_flow_source_payload_edge,
    graph_source_edge_draft_from_payload,
    graph_source_node_draft_from_payload,
    load_structured_payload,
    update_flow_source_payload_custom_layout,
    update_flow_source_payload_edge,
    update_flow_source_payload_node,
)

FIXTURE_SOURCE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "flow_source.yaml"
)


def load_fixture_payload() -> object:
    return load_structured_payload(FIXTURE_SOURCE_PATH.read_bytes())


def test_graph_source_node_draft_and_update_roundtrip() -> None:
    payload = load_fixture_payload()

    draft = graph_source_node_draft_from_payload(payload, "proc_initial_review")
    updated = update_flow_source_payload_node(
        payload,
        command=UpdateGraphSourceNodeCommand(
            node_id="proc_initial_review",
            title="Обновленный анализ",
            kind="process",
            layout_x=410.25,
            layout_y=520.5,
            layout_w=360,
            layout_h=140,
            responsible="geology",
            participants=("planning",),
            approvers=("hse",),
            duration="20 hours",
            note="important",
        ),
        expected_version=1,
    )

    assert draft.title == "Первичный анализ и паспорт скважины"
    assert draft.participants == ("geology", "hse")
    assert draft.layout_w == 300
    assert updated["version"] == 2
    assert updated["nodes"]["proc_initial_review"]["title"] == "Обновленный анализ"
    assert updated["nodes"]["proc_initial_review"]["responsible"] == "geology"
    assert updated["nodes"]["proc_initial_review"]["participants"] == ["planning"]
    assert updated["nodes"]["proc_initial_review"]["approvers"] == ["hse"]
    assert updated["nodes"]["proc_initial_review"]["note"] == "important"
    assert updated["layout"]["proc_initial_review"] == {
        "x": 410.25,
        "y": 520.5,
        "w": 360,
        "h": 140,
    }


def test_graph_source_edge_draft_and_update_can_move_transition() -> None:
    payload = load_fixture_payload()

    draft = graph_source_edge_draft_from_payload(payload, "e_review_decision")
    updated = update_flow_source_payload_edge(
        payload,
        command=UpdateGraphSourceEdgeCommand(
            edge_id="e_review_decision",
            source="proc_well_design",
            target="card_data_rework",
            kind="dashed",
            label="обход",
            condition="manual",
            note="rerouted",
        ),
        expected_version=1,
    )

    assert draft.source == "proc_initial_review"
    assert draft.target == "dec_data_complete"
    assert updated["version"] == 2
    assert updated["nodes"]["proc_initial_review"].get("transitions") == []
    moved = updated["nodes"]["proc_well_design"]["transitions"][-1]
    assert moved["to"] == "card_data_rework"
    assert moved["kind"] == "dashed"
    assert moved["label"] == "обход"
    assert moved["condition"] == "manual"
    assert moved["note"] == "rerouted"
    assert moved["id"] == "e_review_decision"


def test_graph_source_edge_update_can_delete_transition() -> None:
    payload = load_fixture_payload()
    before = graph_source_edge_draft_from_payload(payload, "e_review_decision")

    updated = update_flow_source_payload_edge(
        payload,
        command=UpdateGraphSourceEdgeCommand(
            edge_id="e_review_decision",
            source=before.source,
            target=before.target,
            kind=before.kind,
            label=before.label,
            condition=before.condition,
            note=before.note,
            deleted=True,
        ),
        expected_version=1,
    )

    assert updated["version"] == 2
    transition_ids = [
        item.get("id")
        for item in updated["nodes"]["proc_initial_review"].get("transitions", [])
    ]
    assert "e_review_decision" not in transition_ids


def test_graph_source_edge_create_appends_transition_with_stable_id() -> None:
    payload = load_fixture_payload()
    before_count = len(payload["nodes"]["proc_initial_review"].get("transitions", []))

    updated = create_flow_source_payload_edge(
        payload,
        command=CreateGraphSourceEdgeCommand(
            source="proc_initial_review",
            target="card_mitigation",
            kind="dashed",
            label="новая",
            condition="manual",
            note="created",
        ),
        expected_version=1,
    )

    transitions = updated["nodes"]["proc_initial_review"]["transitions"]
    assert updated["version"] == 2
    assert len(transitions) == before_count + 1
    created = transitions[-1]
    assert created["to"] == "card_mitigation"
    assert created["kind"] == "dashed"
    assert created["label"] == "новая"
    assert created["condition"] == "manual"
    assert created["note"] == "created"
    assert isinstance(created["id"], str) and created["id"]
    draft = graph_source_edge_draft_from_payload(updated, created["id"])
    assert draft.source == "proc_initial_review"
    assert draft.target == "card_mitigation"


def test_graph_source_custom_layout_update_keeps_source_layout_intact() -> None:
    payload = load_fixture_payload()

    updated = update_flow_source_payload_custom_layout(
        payload,
        positions={"proc_initial_review": (901.5, 410.25)},
        expected_version=1,
    )

    assert updated["layout"]["proc_initial_review"] == {
        "x": 420,
        "y": 260,
        "w": 300,
        "h": 116,
    }
    assert updated["custom_layout"]["proc_initial_review"] == {
        "x": 901.5,
        "y": 410.25,
        "w": 300,
        "h": 116,
    }


def test_graph_source_custom_layout_update_tracks_latest_source_size() -> None:
    payload = load_fixture_payload()
    payload["custom_layout"] = {
        "proc_initial_review": {
            "x": 901.5,
            "y": 410.25,
            "w": 300,
            "h": 116,
        }
    }
    resized = update_flow_source_payload_node(
        payload,
        command=UpdateGraphSourceNodeCommand(
            node_id="proc_initial_review",
            title="Первичный анализ и паспорт скважины",
            kind="process",
            layout_x=420,
            layout_y=260,
            layout_w=420,
            layout_h=180,
            responsible="planning",
            participants=("geology", "hse"),
            approvers=(),
            duration="40 minutes",
            note=None,
        ),
        expected_version=1,
    )

    updated = update_flow_source_payload_custom_layout(
        resized,
        positions={"proc_initial_review": (933.0, 512.25)},
        expected_version=2,
    )

    assert updated["custom_layout"]["proc_initial_review"] == {
        "x": 933.0,
        "y": 512.25,
        "w": 420,
        "h": 180,
    }
