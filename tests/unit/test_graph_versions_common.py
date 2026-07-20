from __future__ import annotations

from pathlib import Path

from pydiag.common.graph_versions import (
    GraphVersionInfo,
    graph_version_sequence,
    newest_graph_version,
)


def test_graph_version_sequence_parses_versioned_ids() -> None:
    assert graph_version_sequence("flow_source.v0003.yaml") == 3
    assert graph_version_sequence("flow_source.v0012.yml") == 12
    assert graph_version_sequence("flow_source.yaml") == -1


def test_newest_graph_version_ignores_list_order() -> None:
    older = GraphVersionInfo(
        id="flow_source.v0001.yaml",
        label="v0001",
        path=Path("/tmp/flow_source.v0001.yaml"),
        is_versioned=True,
    )
    newer = GraphVersionInfo(
        id="flow_source.v0004.yaml",
        label="v0004",
        path=Path("/tmp/flow_source.v0004.yaml"),
        is_versioned=True,
    )

    assert newest_graph_version([older, newer]) is newer
    assert newest_graph_version([newer, older]) is newer
