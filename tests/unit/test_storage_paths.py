from __future__ import annotations

from pathlib import Path

from pydiag.infrastructure.storage_paths import (
    auth_sessions_path,
    existing_default_graph_path,
    graph_version_display_label,
    graph_version_paths,
    live_graph_source_exists,
    next_graph_version_path,
    preferred_graph_source_path,
    readable_graph_source_path,
)


def test_graph_version_paths_follow_configured_source_directory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "custom_sources"
    source_dir.mkdir()
    source_path = source_dir / "flow_source.yaml"
    source_path.write_text("schema_version: \"flow-source/1.0\"\n", encoding="utf-8")
    (source_dir / "flow_source.v0002.yaml").write_text("version: 2\n", encoding="utf-8")
    (source_dir / "flow_source.v0001.yaml").write_text("version: 1\n", encoding="utf-8")

    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_path))

    assert graph_version_paths() == [
        source_dir / "flow_source.v0001.yaml",
        source_dir / "flow_source.v0002.yaml",
    ]
    assert next_graph_version_path() == source_dir / "flow_source.v0003.yaml"


def test_auth_sessions_path_uses_explicit_environment_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "sessions.json"
    monkeypatch.setenv("PYDIAG_AUTH_SESSIONS_PATH", str(configured))

    assert auth_sessions_path() == configured


def test_graph_version_display_label_uses_short_version_tag() -> None:
    assert graph_version_display_label("flow_source.v0002.yaml") == "v0002"
    assert graph_version_display_label(Path("/tmp/flow_source.v0001.yaml")) == "v0001"
    assert graph_version_display_label("flow_source.yaml") == "flow_source.yaml"


def test_readable_graph_source_prefers_live_then_newest_archive_not_raw(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    live = source_dir / "flow_source.yaml"
    raw = tmp_path / "real_true_data.json"
    raw.write_text("{}", encoding="utf-8")
    archive = source_dir / "flow_source.v0002.yaml"
    archive.write_text("version: 2\n", encoding="utf-8")
    (source_dir / "flow_source.v0001.yaml").write_text("version: 1\n", encoding="utf-8")

    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(live))
    monkeypatch.setenv("PYDIAG_RAW_GRAPH_PATH", str(raw))

    assert live_graph_source_exists() is False
    assert readable_graph_source_path() == archive
    assert preferred_graph_source_path() == raw

    assert existing_default_graph_path() == archive

    live.write_text("schema_version: \"flow-source/1.0\"\n", encoding="utf-8")
    assert live_graph_source_exists() is True
    assert readable_graph_source_path() == live
    assert preferred_graph_source_path() == live
    assert existing_default_graph_path() == live


def test_existing_default_graph_path_falls_back_to_materialized_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    live = source_dir / "flow_source.yaml"
    graph_json = tmp_path / "flow_graph.json"
    graph_json.write_text('{"version": 1, "responsibles": {}, "nodes": [], "edges": []}', encoding="utf-8")

    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(live))
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_json))

    assert existing_default_graph_path() == graph_json
