from __future__ import annotations

import pytest

from pydiag.models import well_by_id
from pydiag.services import move_well_to_node
from pydiag.storage import (
    graph_path,
    load_documents,
    load_wells_doc,
    save_wells_with_version_check,
    wells_path,
)


def test_env_paths_are_resolved_at_runtime(data_paths, monkeypatch) -> None:
    graph_file, wells_file = data_paths
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_file))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_file))

    graph, wells = load_documents()

    assert graph_path() == graph_file
    assert wells_path() == wells_file
    assert len(graph.nodes) == 18
    assert len(wells.wells) == 4


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

    with pytest.raises(RuntimeError, match="Conflict"):
        save_wells_with_version_check(
            updated,
            expected_version=wells.version,
            path=wells_file,
        )

