from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pydiag.models import FlowGraphDocument
from pydiag.storage import load_documents


def test_sample_documents_are_valid(documents) -> None:
    graph, wells = documents

    assert len(graph.nodes) == 19
    assert len(graph.edges) == 22
    assert len(wells.wells) == 4
    assert graph.nodes[0].type == "input_data"
    assert graph.nodes[0].text == "Лицензия и исходные геоданные"
    assert graph.nodes[2].responsible == ["planning", "geology", "hse"]
    assert graph.nodes[3].responsible == ["planning", "geology"]
    assert graph.nodes[3].time == "40 minutes"
    assert graph.nodes[-1].type == "event"
    assert graph.nodes[-1].text == "Скважина передана в эксплуатацию"
    assert {edge.kind for edge in graph.edges} == {"usual", "dashed", "yes", "no"}


def test_sample_decision_diamonds_have_yes_and_no_branches(documents) -> None:
    graph, _ = documents

    outgoing_by_source = {
        node.id: [edge.kind for edge in graph.edges if edge.source == node.id]
        for node in graph.nodes
    }

    for node in graph.nodes:
        if node.type == "decision_diamond":
            assert {"yes", "no"} <= set(outgoing_by_source[node.id])


def test_strict_graph_validation_rejects_wrong_position_type(
    data_paths,
) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][0]["position"]["x"] = "80"

    with pytest.raises(ValidationError):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_duplicate_node_ids(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][1]["id"] = payload["nodes"][0]["id"]

    with pytest.raises(ValidationError, match="Duplicate node ids"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_legacy_node_fields(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][0]["title"] = payload["nodes"][0]["text"]

    with pytest.raises(ValidationError):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_invalid_time_value(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][0]["time"] = "2 weeks"

    with pytest.raises(ValidationError, match="time must use"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_process_without_responsible(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][2]["responsible"] = []

    with pytest.raises(ValidationError):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_decision_without_responsible(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][3]["responsible"] = []

    with pytest.raises(ValidationError):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_unknown_responsible(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][2]["responsible"].append("unknown_team")

    with pytest.raises(ValidationError, match="unknown responsible unknown_team"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_invalid_responsible_color(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["responsibles"]["planning"]["fill"] = "red"

    with pytest.raises(ValidationError, match="6-digit hex"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_accepts_event_node_type(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"].append(
        {
            "id": "event_kickoff",
            "type": "event",
            "text": "Старт работ",
            "position": {"x": 40.0, "y": 40.0},
            "size": {"w": 220, "h": 72},
            "time": "10 minutes",
            "metadata": {},
        }
    )

    graph = FlowGraphDocument.model_validate(payload, strict=True)

    assert graph.nodes[-1].kind == "event"
    assert graph.nodes[-1].responsible == []


def test_graph_validation_rejects_legacy_default_edge_kind(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["edges"][0]["kind"] = "default"

    with pytest.raises(ValidationError):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_reserved_ui_node_prefix(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][0]["id"] = "route-anchor::shadow"

    with pytest.raises(ValidationError, match="reserved for UI internals"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_reserved_ui_edge_prefix(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["edges"][0]["id"] = "route::shadow"

    with pytest.raises(ValidationError, match="reserved for UI internals"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_graph_validation_rejects_reserved_responsible_badge_prefix(data_paths) -> None:
    graph_path, _ = data_paths
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    payload["nodes"][0]["id"] = "responsible::shadow"

    with pytest.raises(ValidationError, match="reserved for UI internals"):
        FlowGraphDocument.model_validate(payload, strict=True)


def test_cross_document_validation_rejects_unknown_well_node(
    data_paths,
) -> None:
    graph_path, wells_path = data_paths
    payload = json.loads(wells_path.read_text(encoding="utf-8"))
    payload["wells"][0]["current_node_id"] = "missing_node"
    wells_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not exist in graph"):
        load_documents(graph_path, wells_path)
