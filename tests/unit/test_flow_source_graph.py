from __future__ import annotations

import pytest
from pydantic import ValidationError

from pydiag.infrastructure.flow_source_graph import (
    FlowSourceDocument,
    editable_flow_graph_payload_from_source_payload,
    flow_source_payload_from_editable_payload,
)


def valid_flow_source_payload() -> dict[str, object]:
    return {
        "schema_version": "flow-source/1.0",
        "graph_id": "pilot-drilling",
        "title": "Pilot drilling flow",
        "version": 7,
        "responsibles": {
            "planning": {
                "label": "Planning",
                "type": "team",
                "fill": "#dcecff",
                "border": "#356ca8",
                "text": "#17314f",
            },
            "geology": {
                "label": "Geology",
                "type": "team",
                "fill": "#e3f7ea",
                "border": "#3f8a55",
                "text": "#17311e",
            },
            "hse": {
                "label": "HSE",
                "type": "team",
                "fill": "#ffe3e3",
                "border": "#b84c4c",
                "text": "#4e1717",
            },
        },
        "sections": {
            "intake": {
                "title": "Intake",
                "order": 10,
            }
        },
        "nodes": {
            "review_data": {
                "title": "Проверка комплекта данных",
                "kind": "process",
                "section": "intake",
                "responsible": "planning",
                "participants": ["geology"],
                "approvers": ["hse"],
                "duration": "40m",
                "tags": ["critical", "intake"],
                "source_ref": {"figma_text_id": "text_review"},
                "transitions": [
                    {"to": "data_complete"},
                ],
            },
            "data_complete": {
                "title": "Данные полные?",
                "kind": "decision_diamond",
                "responsible": "planning",
                "participants": ["geology"],
                "transitions": [
                    {
                        "to": "well_design",
                        "kind": "yes",
                        "condition": "dataset complete",
                    },
                    {
                        "to": "review_data",
                        "kind": "no",
                        "note": "вернуть на доработку",
                    },
                ],
            },
            "well_design": {
                "title": "Проект скважины",
                "kind": "process",
                "responsible": "geology",
                "duration": "2d",
            },
        },
        "layout": {
            "review_data": {
                "x": 380.0,
                "y": 60.0,
                "w": 320,
                "h": 120,
            }
        },
    }


def test_flow_source_payload_materializes_rich_editable_graph() -> None:
    editable_payload = editable_flow_graph_payload_from_source_payload(
        valid_flow_source_payload()
    )

    review_node = next(
        node for node in editable_payload["nodes"] if node["id"] == "review_data"
    )
    decision_node = next(
        node for node in editable_payload["nodes"] if node["id"] == "data_complete"
    )
    yes_edge = next(edge for edge in editable_payload["edges"] if edge["kind"] == "yes")
    no_edge = next(edge for edge in editable_payload["edges"] if edge["kind"] == "no")

    assert editable_payload["schema_version"] == "editable-flow-graph/1.0"
    assert review_node["participants"] == ["geology"]
    assert review_node["approvers"] == ["hse"]
    assert review_node["duration"] == "40 minutes"
    assert review_node["metadata"]["source_section"] == "intake"
    assert review_node["metadata"]["source_tags"] == "critical, intake"
    assert review_node["metadata"]["source_ref:figma_text_id"] == "text_review"
    assert decision_node["size"] == {"w": 360, "h": 220}
    assert yes_edge["label"] == "Да"
    assert yes_edge["metadata"]["condition"] == "dataset complete"
    assert no_edge["label"] == "Нет"
    assert no_edge["metadata"]["note"] == "вернуть на доработку"


def test_editable_flow_graph_payload_converts_back_to_flow_source_payload() -> None:
    editable_payload = editable_flow_graph_payload_from_source_payload(
        valid_flow_source_payload()
    )

    source_payload = flow_source_payload_from_editable_payload(
        editable_payload,
        graph_id="pilot-drilling",
        title="Pilot drilling flow",
    )

    review_node = source_payload["nodes"]["review_data"]
    decision_node = source_payload["nodes"]["data_complete"]
    no_transition = next(
        transition
        for transition in decision_node["transitions"]
        if transition["to"] == "review_data"
    )

    assert source_payload["schema_version"] == "flow-source/1.0"
    assert review_node["responsible"] == "planning"
    assert review_node["participants"] == ["geology"]
    assert review_node["approvers"] == ["hse"]
    assert review_node["duration"] == "40 minutes"
    assert review_node["section"] == "intake"
    assert review_node["tags"] == ["critical", "intake"]
    assert review_node["source_ref"]["figma_text_id"] == "text_review"
    assert source_payload["layout"]["review_data"] == {
        "x": 380.0,
        "y": 60.0,
        "w": 320,
        "h": 120,
    }
    assert no_transition["kind"] == "no"
    assert no_transition["label"] is None
    assert no_transition["note"] == "вернуть на доработку"


def test_flow_source_document_rejects_unknown_transition_target() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["transitions"] = [{"to": "missing_node"}]

    with pytest.raises(ValidationError, match="unknown transition target missing_node"):
        FlowSourceDocument.model_validate(payload, strict=True)


def test_flow_source_document_rejects_duplicate_responsibles_within_node() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["participants"] = ["planning"]

    with pytest.raises(ValidationError, match="duplicate responsibles are not allowed"):
        FlowSourceDocument.model_validate(payload, strict=True)
