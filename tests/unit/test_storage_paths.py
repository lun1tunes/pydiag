from __future__ import annotations

from pathlib import Path

from pydiag.infrastructure.storage_paths import graph_version_paths, next_graph_version_path


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
