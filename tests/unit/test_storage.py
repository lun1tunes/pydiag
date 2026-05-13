from __future__ import annotations

import pytest

from pydiag.models import well_by_id
from pydiag.services import move_well_to_node
from pydiag.storage import (
    FileLockTimeoutError,
    VersionConflictError,
    fsync_parent_dir,
    graph_path,
    json_file_lock,
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

    with pytest.raises(VersionConflictError, match="Conflict"):
        save_wells_with_version_check(
            updated,
            expected_version=wells.version,
            path=wells_file,
        )


def test_json_file_lock_prevents_nested_writer(tmp_path) -> None:
    target = tmp_path / "wells.json"
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


def test_fsync_parent_dir_is_noop_on_non_posix(monkeypatch, tmp_path) -> None:
    import pydiag.storage as storage

    def fail_if_called(*args, **kwargs):
        raise AssertionError("os.open should not be called on non-posix platforms")

    monkeypatch.setattr(storage.os, "name", "nt")
    monkeypatch.setattr(storage.os, "open", fail_if_called)

    fsync_parent_dir(tmp_path / "wells.json")
