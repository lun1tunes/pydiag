from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pydiag.models import FlowGraphDocument
from pydiag.storage import load_documents


def test_sample_documents_are_valid(documents) -> None:
    graph, wells = documents

    assert len(graph.nodes) == 18
    assert len(graph.edges) == 21
    assert len(wells.wells) == 4


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
