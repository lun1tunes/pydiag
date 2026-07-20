from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from pydiag.common.errors import FileLockTimeoutError, VersionConflictError
from pydiag.common.layout_metadata import CUSTOM_LAYOUT_X_META, CUSTOM_LAYOUT_Y_META
from pydiag.common.graph_source_admin import UpdateGraphSourceNodeCommand
from pydiag.domain import move_well_to_node, well_by_id
from pydiag.infrastructure.flow_source_graph import load_structured_payload
from pydiag.infrastructure.graph_versions import (
    can_import_raw_graph_source,
    can_materialize_graph_version,
    ensure_live_graph_source,
    import_live_graph_source_from_raw,
    materialize_new_graph_version_from_raw_source,
)
from pydiag.infrastructure.storage_io import fsync_parent_dir, json_file_lock
from pydiag.infrastructure.storage_loading import load_documents, load_graph_doc, load_wells_doc
from pydiag.infrastructure.storage_materialization import materialize_flow_graph_from_raw_source
from pydiag.infrastructure.storage_paths import (
    graph_path,
    graph_version_paths,
    latest_graph_version_path,
    next_graph_version_path,
    preferred_graph_source_path,
    raw_graph_path,
    wells_path,
)
from pydiag.infrastructure.storage_writes import (
    load_graph_source_node_draft,
    save_graph_positions_with_version_check,
    save_graph_source_node_with_version_check,
    save_wells_with_version_check,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FLOW_SOURCE_FIXTURE_PATH = FIXTURES_DIR / "flow_source.yaml"
WELLS_FIXTURE_PATH = FIXTURES_DIR / "wells.yaml"


def raw_figma_payload() -> dict[str, object]:
    return {
        "version": 3,
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=process;responsible=planning;time=1 hour",
                "type": "TEXT",
                "characters": "Start",
                "fontSize": 18,
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            },
            {
                "id": "text_end",
                "name": "id=end;kind=event",
                "type": "TEXT",
                "characters": "End",
                "fontSize": 18,
                "x": 260,
                "y": 20,
                "width": 160,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "id=edge_1;kind=usual;source=start;target=end",
                "type": "CONNECTOR",
                "x": 190,
                "y": 50,
                "width": 70,
                "height": 2,
                "rotation": 0,
            },
        ],
    }


def raw_components_payload() -> dict[str, object]:
    return {
        "selectionCount": 3,
        "timestamp": "2026-07-05T00:00:00Z",
        "components": [
            {
                "id": "shape_1",
                "name": "Start",
                "type": "SHAPE_WITH_TEXT",
                "x": 0,
                "y": 0,
                "width": 120,
                "height": 60,
            },
            {
                "id": "shape_2",
                "name": "End",
                "type": "SHAPE_WITH_TEXT",
                "x": 220,
                "y": 0,
                "width": 120,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "Connector line",
                "type": "CONNECTOR",
                "x": 120,
                "y": 29,
                "width": 100,
                "height": 2,
                "rotation": 0,
            },
        ],
    }


def raw_components_payload_with_duplicate_connectors() -> dict[str, object]:
    return {
        "selectionCount": 5,
        "components": [
            {
                "id": "shape_1",
                "name": "Start?",
                "type": "SHAPE_WITH_TEXT",
                "x": 0,
                "y": 0,
                "width": 120,
                "height": 60,
                "flowNode": {
                    "id": "start",
                    "type": "decision_diamond",
                    "responsibles": ["planning"],
                },
            },
            {
                "id": "shape_2",
                "name": "End",
                "type": "SHAPE_WITH_TEXT",
                "x": 220,
                "y": 0,
                "width": 120,
                "height": 60,
                "flowNode": {"id": "end", "type": "process", "responsibles": ["planning"]},
            },
            {
                "id": "conn_yes",
                "name": "Connector line",
                "type": "CONNECTOR",
                "x": 120,
                "y": 29,
                "width": 100,
                "height": 2,
                "rotation": 0,
                "flowEdge": {"id": "2992:1201", "kind": "yes", "source": "start", "target": "end"},
            },
            {
                "id": "conn_default_1",
                "name": "Connector line",
                "type": "CONNECTOR",
                "x": 120,
                "y": 29,
                "width": 100,
                "height": 2,
                "rotation": 0,
                "flowEdge": {"id": "3029:889", "kind": "usual", "source": "start", "target": "end"},
            },
            {
                "id": "conn_default_2",
                "name": "Connector line",
                "type": "CONNECTOR",
                "x": 120,
                "y": 29,
                "width": 100,
                "height": 2,
                "rotation": 0,
                "flowEdge": {
                    "id": "3071:1067",
                    "kind": "usual",
                    "source": "start",
                    "target": "end",
                },
            },
        ],
    }


def valid_internal_graph_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "version": 1,
        "responsibles": {
            "planning": {
                "label": "Planning",
                "fill": "#DCECFF",
                "border": "#5B8DEF",
                "text": "#172033",
            }
        },
        "nodes": [],
        "edges": [],
    }


def flow_source_yaml() -> str:
    return dedent(
        """
        schema_version: flow-source/1.0
        graph_id: pilot-drilling
        title: Pilot drilling flow
        version: 7
        responsibles:
          planning:
            label: Planning
            type: team
            fill: "#dcecff"
            border: "#356ca8"
            text: "#17314f"
          geology:
            label: Geology
            type: team
            fill: "#e3f7ea"
            border: "#3f8a55"
            text: "#17311e"
          hse:
            label: HSE
            type: team
            fill: "#ffe3e3"
            border: "#b84c4c"
            text: "#4e1717"
        sections:
          intake:
            title: Intake
        nodes:
          intake_data:
            title: Исходные данные
            kind: input_data
            section: intake
            transitions:
              - to: review_data
          review_data:
            title: Проверка комплекта данных
            kind: process
            section: intake
            responsible: planning
            participants: [geology]
            approvers: [hse]
            duration: 40m
            tags: [critical, intake]
            source_ref:
              figma_text_id: text_review
            transitions:
              - to: data_complete
          data_complete:
            title: Данные полные?
            kind: decision_diamond
            responsible: planning
            participants: [geology]
            transitions:
              - to: well_design
                kind: yes
                condition: dataset complete
              - to: review_data
                kind: no
                note: вернуть на доработку
          well_design:
            title: Проект скважины
            kind: process
            responsible: geology
            duration: 2d
        layout:
          intake_data:
            x: 40
            y: 60
            w: 280
            h: 96
          review_data:
            x: 380
            y: 60
            w: 320
            h: 120
        metadata:
          owner: pydiag
        """
    ).strip()


def wells_yaml() -> str:
    return dedent(
        """
        schema_version: "1.0"
        version: 1
        wells:
          - id: well_1
            name: Скв. 1
            current_node_id: intake_data
            history:
              - ts: "2026-05-08T08:00:00Z"
                node_id: intake_data
                action: create
                to_node_id: intake_data
                by: system
        """
    ).strip()


def test_env_paths_are_resolved_at_runtime(data_paths, monkeypatch) -> None:
    graph_file, wells_file = data_paths
    source_file = graph_file.with_name("flow_source.yaml")
    source_file.write_text(flow_source_yaml(), encoding="utf-8")
    wells_file.write_text(wells_yaml(), encoding="utf-8")
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_file))
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_file))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_file))

    graph, wells = load_documents()

    assert graph_path() == graph_file
    assert wells_path() == wells_file
    assert len(graph.nodes) == 4
    assert len(wells.wells) == 1


def test_load_documents_returns_empty_runtime_when_only_raw_figma_exists(
    monkeypatch,
    tmp_path,
) -> None:
    """Raw Figma JSON is import-only; runtime must not treat it as a live schema."""
    import pydiag.infrastructure.storage_paths as storage_paths

    raw_file = tmp_path / "real_true_data.json"
    graph_file = tmp_path / "flow_graph.json"
    wells_file = tmp_path / "wells.yaml"
    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    raw_file.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")
    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source_dir / "flow_source.yaml")
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_file))
    monkeypatch.setenv("PYDIAG_RAW_GRAPH_PATH", str(raw_file))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_file))
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_dir / "flow_source.yaml"))

    graph, wells = load_documents()

    assert graph.nodes == []
    assert wells.wells == []
    assert wells_file.exists() is False
    assert preferred_graph_source_path() == raw_file
    assert can_import_raw_graph_source() is True


def test_load_documents_bootstraps_empty_wells_yaml_after_live_import(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    raw_file = tmp_path / "real_true_data.json"
    graph_file = tmp_path / "flow_graph.json"
    wells_file = tmp_path / "wells.yaml"
    live_source = tmp_path / "flow_source.yaml"
    raw_file.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")
    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", live_source)
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_file))
    monkeypatch.setenv("PYDIAG_RAW_GRAPH_PATH", str(raw_file))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_file))
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(live_source))

    result = import_live_graph_source_from_raw()
    graph, wells = load_documents()
    template = wells_file.read_text(encoding="utf-8")

    assert result.changed is True
    assert live_source.exists() is True
    assert graph.version == 3
    assert [node.id for node in graph.nodes] == ["start", "end"]
    assert wells.version == 1
    assert wells.wells == []
    assert wells_file.exists() is True
    assert 'schema_version: "1.0"' in template
    assert "wells: []" in template
    assert "#   - id: well_1" in template
    assert "#     current_node_id: intake_data" in template


def test_graph_version_path_helpers_track_latest_and_next_version(
    monkeypatch,
    tmp_path,
) -> None:
    versions_dir = tmp_path / "flow_sources"
    versions_dir.mkdir()
    (versions_dir / "flow_source.v0002.yaml").write_text("{}", encoding="utf-8")
    (versions_dir / "flow_source.v0001.yaml").write_text("{}", encoding="utf-8")
    (versions_dir / "ignore-me.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv(
        "PYDIAG_SOURCE_GRAPH_PATH",
        str(versions_dir / "flow_source.yaml"),
    )

    assert graph_version_paths() == [
        versions_dir / "flow_source.v0001.yaml",
        versions_dir / "flow_source.v0002.yaml",
    ]
    assert latest_graph_version_path() == versions_dir / "flow_source.v0002.yaml"
    assert next_graph_version_path() == versions_dir / "flow_source.v0003.yaml"


def test_can_materialize_graph_version_requires_available_source_payload(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source = tmp_path / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    assert can_materialize_graph_version() is False

    source.write_text(flow_source_yaml(), encoding="utf-8")
    assert can_materialize_graph_version() is True

    source.unlink()
    raw.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")
    assert raw_graph_path() == raw
    assert can_materialize_graph_version() is True

    raw.unlink()
    assert can_materialize_graph_version() is False


def test_preferred_graph_source_path_prefers_raw_source_when_no_yaml_source_exists(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source = tmp_path / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"

    raw.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    assert preferred_graph_source_path() == raw
    assert source.exists() is False


def test_materialize_new_graph_version_from_live_source_writes_versioned_yaml(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    versions_dir = tmp_path / "flow_sources"
    source = versions_dir / "flow_source.yaml"
    source.parent.mkdir(parents=True)
    source.write_text(flow_source_yaml(), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.setattr(storage_paths, "GRAPH_VERSIONS_DIR", versions_dir)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)

    version = materialize_new_graph_version_from_raw_source()
    payload = load_structured_payload(version.path.read_bytes())

    assert version.id == "flow_source.v0001.yaml"
    assert version.label == "v0001"
    assert payload["schema_version"] == "flow-source/1.0"
    assert payload["graph_id"] == "pilot-drilling"
    assert payload["nodes"]["review_data"]["title"] == "Проверка комплекта данных"


def test_materialize_new_graph_version_from_raw_source_writes_versioned_yaml(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    versions_dir = tmp_path / "flow_sources"
    raw = tmp_path / "real_true_data.json"
    raw.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", versions_dir / "flow_source.yaml")
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.setattr(storage_paths, "GRAPH_VERSIONS_DIR", versions_dir)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    version = materialize_new_graph_version_from_raw_source()
    payload = load_structured_payload(version.path.read_bytes())

    assert version.id == "flow_source.v0001.yaml"
    assert version.label == "v0001"
    assert payload["schema_version"] == "flow-source/1.0"
    assert payload["version"] == 3
    assert payload["nodes"]["start"]["title"] == "Start"
    assert payload["nodes"]["end"]["title"] == "End"


def test_ensure_live_graph_source_materializes_live_yaml_from_raw_source(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    flow_sources_dir = tmp_path / "flow_sources"
    target = flow_sources_dir / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"
    raw.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", target)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    created = ensure_live_graph_source()
    payload = load_structured_payload(created.read_bytes())

    assert created == target
    assert created.exists() is True
    assert payload["schema_version"] == "flow-source/1.0"
    assert payload["version"] == 3
    assert payload["nodes"]["start"]["title"] == "Start"
    assert payload["nodes"]["end"]["title"] == "End"


def test_ensure_live_graph_source_preserves_existing_live_yaml(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    flow_sources_dir = tmp_path / "flow_sources"
    target = flow_sources_dir / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    original = flow_source_yaml()
    target.write_text(original, encoding="utf-8")
    raw.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", target)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    created = ensure_live_graph_source()

    assert created == target
    assert target.read_text(encoding="utf-8") == original


def test_ensure_live_graph_source_raises_when_no_source_payload_is_available(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    target = tmp_path / "flow_sources" / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", target)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    with pytest.raises(FileNotFoundError, match="Graph source not found"):
        ensure_live_graph_source()


def test_materialize_flow_graph_from_raw_source_creates_editable_graph(tmp_path) -> None:
    source = tmp_path / "real_true_data.json"
    target = tmp_path / "flow_graph.json"
    source.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    graph = materialize_flow_graph_from_raw_source(source_path=source, target_path=target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert graph.version == 3
    assert [node.id for node in graph.nodes] == ["start", "end"]
    assert payload["schema_version"] == "editable-flow-graph/1.0"
    assert payload["nodes"][0]["id"] == "start"
    assert payload["edges"][0]["source"] == "start"
    assert payload["edges"][0]["target"] == "end"


def test_materialize_flow_graph_from_raw_source_deduplicates_duplicate_connectors(
    tmp_path,
) -> None:
    source = tmp_path / "real_true_data.json"
    target = tmp_path / "flow_graph.json"
    source.write_text(
        json.dumps(raw_components_payload_with_duplicate_connectors()), encoding="utf-8"
    )

    graph = materialize_flow_graph_from_raw_source(source_path=source, target_path=target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert graph.version == 1
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["kind"] == "yes"
    assert payload["edges"][0]["label"] == "Да"
    assert payload["edges"][0]["source"] == "start"
    assert payload["edges"][0]["target"] == "end"


def test_materialize_flow_graph_from_components_source_creates_editable_graph(tmp_path) -> None:
    source = tmp_path / "real_true_data.json"
    target = tmp_path / "flow_graph.json"
    source.write_text(json.dumps(raw_components_payload()), encoding="utf-8")

    graph = materialize_flow_graph_from_raw_source(source_path=source, target_path=target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert graph.version == 1
    assert [node.id for node in graph.nodes] == ["start", "end"]
    assert payload["schema_version"] == "editable-flow-graph/1.0"
    assert payload["nodes"][0]["kind"] == "process"
    assert payload["edges"][0]["source"] == "start"
    assert payload["edges"][0]["target"] == "end"


def test_materialize_flow_graph_from_yaml_source_creates_editable_graph(tmp_path) -> None:
    source = tmp_path / "flow_source.yaml"
    target = tmp_path / "flow_graph.json"
    source.write_text(flow_source_yaml(), encoding="utf-8")

    graph = materialize_flow_graph_from_raw_source(source_path=source, target_path=target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    review_node = next(node for node in payload["nodes"] if node["id"] == "review_data")
    design_node = next(node for node in payload["nodes"] if node["id"] == "well_design")
    no_edge = next(
        edge
        for edge in payload["edges"]
        if edge["source"] == "data_complete" and edge["target"] == "review_data"
    )

    assert graph.version == 7
    assert [node.id for node in graph.nodes] == [
        "intake_data",
        "review_data",
        "data_complete",
        "well_design",
    ]
    assert payload["schema_version"] == "editable-flow-graph/1.0"
    assert review_node["participants"] == ["geology"]
    assert review_node["approvers"] == ["hse"]
    assert review_node["duration"] == "40 minutes"
    assert review_node["metadata"]["source_ref:figma_text_id"] == "text_review"
    assert review_node["metadata"]["source_tags"] == "critical, intake"
    assert design_node["duration"] == "2 days"
    assert no_edge["kind"] == "no"
    assert no_edge["label"] == "Нет"
    assert no_edge["metadata"]["note"] == "вернуть на доработку"


def test_load_graph_doc_reads_yaml_source_document(tmp_path) -> None:
    source = tmp_path / "flow_source.yaml"
    source.write_text(flow_source_yaml(), encoding="utf-8")

    graph = load_graph_doc(source)

    review_node = next(node for node in graph.nodes if node.id == "review_data")
    design_node = next(node for node in graph.nodes if node.id == "well_design")

    assert review_node.time == "40 minutes"
    assert review_node.responsible == ["planning", "geology", "hse"]
    assert design_node.time == "2 days"


def test_load_graph_doc_reads_raw_source_document(tmp_path) -> None:
    source = tmp_path / "real_true_data.json"
    source.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    graph = load_graph_doc(source)

    assert [node.id for node in graph.nodes] == ["start", "end"]


def test_load_graph_doc_reads_default_graph_directly_from_yaml_source(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_loading as storage_loading
    import pydiag.infrastructure.storage_paths as storage_paths

    flow_graph = tmp_path / "flow_graph.json"
    source = tmp_path / "flow_source.yaml"
    source.write_text(flow_source_yaml(), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "GRAPH_PATH", flow_graph)
    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.delenv("PYDIAG_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    graph = storage_loading.load_graph_doc()

    review_node = next(node for node in graph.nodes if node.id == "review_data")
    assert storage_paths.graph_path() == flow_graph
    assert not flow_graph.exists()
    assert review_node.time == "40 minutes"


def test_load_graph_doc_uses_existing_materialized_graph_when_no_source_available(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_loading as storage_loading
    import pydiag.infrastructure.storage_paths as storage_paths

    flow_graph = tmp_path / "flow_graph.json"
    missing_source = tmp_path / "missing_flow_source.yaml"
    missing_raw = tmp_path / "missing_real_true_data.json"
    flow_graph.write_text(json.dumps(valid_internal_graph_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "GRAPH_PATH", flow_graph)
    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", missing_source)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", missing_raw)
    monkeypatch.delenv("PYDIAG_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    graph = storage_loading.load_graph_doc()
    payload = json.loads(flow_graph.read_text(encoding="utf-8"))

    assert graph.version == 1
    assert payload["version"] == 1
    assert payload["responsibles"]["planning"]["label"] == "Planning"
    assert payload["nodes"] == []


def test_load_graph_doc_prefers_live_source_over_existing_materialized_graph(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_loading as storage_loading
    import pydiag.infrastructure.storage_paths as storage_paths

    flow_graph = tmp_path / "flow_graph.json"
    source = tmp_path / "flow_source.yaml"
    flow_graph.write_text(json.dumps(valid_internal_graph_payload()), encoding="utf-8")
    source.write_text(flow_source_yaml(), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "GRAPH_PATH", flow_graph)
    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.delenv("PYDIAG_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)

    graph = storage_loading.load_graph_doc()
    review_node = next(node for node in graph.nodes if node.id == "review_data")

    assert storage_paths.graph_path() == flow_graph
    assert json.loads(flow_graph.read_text(encoding="utf-8")) == valid_internal_graph_payload()
    assert graph.version == 7
    assert review_node.time == "40 minutes"


def test_save_wells_with_version_check_is_atomic_and_increments_version(
    data_paths,
) -> None:
    graph_file, wells_file = data_paths
    graph, wells = load_documents(graph_file, wells_file)
    updated = move_well_to_node(
        graph,
        wells,
        well_id="well_1001",
        target_node_id="dec_data_complete",
        actor="pytest",
    )

    saved = save_wells_with_version_check(
        updated,
        expected_version=wells.version,
        path=wells_file,
    )

    reloaded = load_wells_doc(wells_file)
    assert saved.version == wells.version + 1
    assert reloaded.version == saved.version
    assert well_by_id(reloaded)["well_1001"].current_node_id == "dec_data_complete"
    assert wells_file.read_text(encoding="utf-8").startswith('schema_version: "1.0"')


def test_save_graph_positions_with_version_check_updates_only_positions(
    data_paths,
) -> None:
    graph_file, wells_file = data_paths
    graph, _ = load_documents(graph_file, wells_file)

    saved = save_graph_positions_with_version_check(
        {"proc_initial_review": (512.345, 261.234)},
        expected_version=graph.version,
        path=graph_file,
    )

    moved = next(node for node in saved.nodes if node.id == "proc_initial_review")
    original = next(node for node in graph.nodes if node.id == "proc_initial_review")
    assert saved.version == graph.version + 1
    assert moved.position.x == 512.35
    assert moved.position.y == 261.23
    assert moved.text == original.text


def test_save_graph_positions_with_version_check_updates_editable_graph_payload(
    tmp_path,
) -> None:
    source = tmp_path / "real_true_data.json"
    target = tmp_path / "flow_graph.v0001.json"
    source.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    graph = materialize_flow_graph_from_raw_source(source_path=source, target_path=target)
    saved = save_graph_positions_with_version_check(
        {"start": (111.126, 222.224)},
        expected_version=graph.version,
        path=target,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    moved = next(node for node in payload["nodes"] if node["id"] == "start")

    assert payload["schema_version"] == "editable-flow-graph/1.0"
    assert payload["version"] == graph.version + 1
    assert moved["position"] == {"x": 111.13, "y": 222.22}
    assert next(node for node in saved.nodes if node.id == "start").position.x == 111.13


def test_save_graph_positions_with_version_check_updates_live_source_only(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source = tmp_path / "flow_source.yaml"
    target = tmp_path / "flow_graph.json"
    source.write_text(flow_source_yaml(), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.setattr(storage_paths, "GRAPH_PATH", target)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_GRAPH_PATH", raising=False)

    graph = load_graph_doc()
    saved = save_graph_positions_with_version_check(
        {"review_data": (111.126, 222.224)},
        expected_version=graph.version,
        path=source,
    )

    source_graph = load_graph_doc(source)
    moved = next(node for node in source_graph.nodes if node.id == "review_data")

    assert saved.version == graph.version + 1
    assert source_graph.version == graph.version + 1
    assert not target.exists()
    assert moved.position.x == 111.13
    assert moved.position.y == 222.22


def test_save_graph_positions_with_version_check_updates_custom_layout_in_live_source(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source = tmp_path / "flow_source.yaml"
    target = tmp_path / "flow_graph.json"
    source.write_text(flow_source_yaml(), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", source)
    monkeypatch.setattr(storage_paths, "GRAPH_PATH", target)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_GRAPH_PATH", raising=False)

    graph = load_graph_doc()
    saved = save_graph_positions_with_version_check(
        {"review_data": (611.5, 333.25)},
        expected_version=graph.version,
        path=source,
        layout_mode="custom",
    )

    payload = load_structured_payload(source.read_bytes())
    review_node = next(node for node in load_graph_doc(source).nodes if node.id == "review_data")

    assert saved.version == graph.version + 1
    assert payload["layout"]["review_data"] == {
        "x": 380,
        "y": 60,
        "w": 320,
        "h": 120,
    }
    assert payload["custom_layout"]["review_data"] == {
        "x": 611.5,
        "y": 333.25,
        "w": 320,
        "h": 120,
    }
    assert not target.exists()
    assert review_node.position.x == 380
    assert review_node.position.y == 60
    assert review_node.metadata[CUSTOM_LAYOUT_X_META] == 611.5
    assert review_node.metadata[CUSTOM_LAYOUT_Y_META] == 333.25


def test_import_live_graph_source_from_raw_creates_backup_before_replacing_live_source(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    live_source = source_dir / "flow_source.yaml"
    raw_source = tmp_path / "real_true_data.json"
    live_source.write_text(flow_source_yaml(), encoding="utf-8")
    raw_source.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", live_source)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw_source)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)

    assert can_import_raw_graph_source() is True

    result = import_live_graph_source_from_raw()
    backup_path = source_dir / "flow_source.v0001.yaml"
    live_payload = load_structured_payload(live_source.read_bytes())
    backup_payload = load_structured_payload(backup_path.read_bytes())

    assert result.changed is True
    assert result.backup_version is not None
    assert result.backup_version.path == backup_path
    assert result.backup_version.label == "v0001"
    assert backup_payload["nodes"]["review_data"]["title"] == "Проверка комплекта данных"
    assert live_payload["nodes"]["start"]["title"] == "Start"
    assert live_payload["version"] == 8


def test_import_live_graph_source_from_raw_is_noop_when_live_source_already_matches_raw(
    monkeypatch,
    tmp_path,
) -> None:
    import pydiag.infrastructure.storage_paths as storage_paths

    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    live_source = source_dir / "flow_source.yaml"
    raw_source = tmp_path / "real_true_data.json"
    raw_source.write_text(json.dumps(raw_figma_payload()), encoding="utf-8")

    monkeypatch.setattr(storage_paths, "SOURCE_GRAPH_PATH", live_source)
    monkeypatch.setattr(storage_paths, "RAW_GRAPH_PATH", raw_source)
    monkeypatch.delenv("PYDIAG_SOURCE_GRAPH_PATH", raising=False)
    monkeypatch.delenv("PYDIAG_RAW_GRAPH_PATH", raising=False)
    ensure_live_graph_source(source_path=raw_source, target_path=live_source)

    result = import_live_graph_source_from_raw()

    assert result.changed is False
    assert result.backup_version is None
    assert graph_version_paths() == []


def test_save_graph_positions_with_version_check_rejects_unsupported_layout_mode(
    data_paths,
) -> None:
    graph_path, _ = data_paths
    graph = load_graph_doc(graph_path)

    with pytest.raises(
        ValueError,
        match="Graph positions can only be saved for 'manual' or 'custom' layout modes",
    ):
        save_graph_positions_with_version_check(
            {"proc_initial_review": (11.0, 22.0)},
            expected_version=graph.version,
            path=graph_path,
            layout_mode="snake",
        )


def test_save_graph_positions_with_version_check_rejects_unknown_node(
    data_paths,
) -> None:
    graph_file, wells_file = data_paths
    graph, _ = load_documents(graph_file, wells_file)

    with pytest.raises(ValueError, match="missing_node"):
        save_graph_positions_with_version_check(
            {"missing_node": (1.0, 2.0)},
            expected_version=graph.version,
            path=graph_file,
        )


def test_save_wells_with_version_check_rejects_stale_writer(data_paths) -> None:
    graph_file, wells_file = data_paths
    graph, wells = load_documents(graph_file, wells_file)
    updated = move_well_to_node(
        graph,
        wells,
        well_id="well_1001",
        target_node_id="dec_data_complete",
        actor="pytest",
    )
    save_wells_with_version_check(updated, expected_version=wells.version, path=wells_file)

    with pytest.raises(VersionConflictError, match="Conflict"):
        save_wells_with_version_check(
            updated,
            expected_version=wells.version,
            path=wells_file,
        )


def test_json_file_lock_prevents_nested_writer(tmp_path) -> None:
    target = tmp_path / "wells.yaml"
    target.write_text("{}", encoding="utf-8")

    with json_file_lock(target, timeout=0.2, poll_interval=0.01):
        with pytest.raises(FileLockTimeoutError):
            with json_file_lock(target, timeout=0.05, poll_interval=0.01):
                pass


def test_save_wells_with_version_check_rejects_graph_integrity_violation(
    data_paths,
) -> None:
    graph_file, wells_file = data_paths
    graph, wells = load_documents(graph_file, wells_file)
    updated = wells.model_copy(deep=True)
    updated.wells[0].current_node_id = "missing_node"

    with pytest.raises(ValueError, match="does not exist in graph"):
        save_wells_with_version_check(
            updated,
            expected_version=wells.version,
            path=wells_file,
            graph=graph,
        )


def test_save_graph_source_node_with_version_check_rejects_soft_delete_for_referenced_node(
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "flow_source.yaml"
    wells_file = tmp_path / "wells.yaml"
    source_path.write_bytes(FLOW_SOURCE_FIXTURE_PATH.read_bytes())
    wells_file.write_bytes(WELLS_FIXTURE_PATH.read_bytes())
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_path))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_file))

    draft = load_graph_source_node_draft(source_path, "proc_initial_review")

    with pytest.raises(ValueError, match="current_node_id=proc_initial_review"):
        save_graph_source_node_with_version_check(
            UpdateGraphSourceNodeCommand(
                node_id=draft.node_id,
                title=draft.title,
                kind=draft.kind,
                layout_x=draft.layout_x,
                layout_y=draft.layout_y,
                layout_w=draft.layout_w,
                layout_h=draft.layout_h,
                responsible=draft.responsible,
                participants=draft.participants,
                approvers=draft.approvers,
                duration=draft.duration,
                note=draft.note,
                deleted=True,
            ),
            expected_version=1,
            path=source_path,
        )

    payload = load_structured_payload(source_path.read_bytes())
    assert "deleted" not in payload["nodes"]["proc_initial_review"]


def test_load_wells_doc_accepts_legacy_json_payload(tmp_path) -> None:
    target = tmp_path / "wells.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "version": 1,
                "wells": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    wells = load_wells_doc(target)

    assert wells.version == 1
    assert wells.wells == []


def test_fsync_parent_dir_is_noop_on_non_posix(monkeypatch, tmp_path) -> None:
    import pydiag.infrastructure.storage_io as storage_io

    def fail_if_called(*args, **kwargs):
        raise AssertionError("os.open should not be called on non-posix platforms")

    monkeypatch.setattr(storage_io.os, "name", "nt")
    monkeypatch.setattr(storage_io.os, "open", fail_if_called)

    fsync_parent_dir(tmp_path / "wells.yaml")
