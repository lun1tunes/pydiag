"""Undo/redo for canvas moves, node edits, and edge edits."""

from __future__ import annotations

from pathlib import Path

from pydiag.application.edit_history import can_redo, can_undo, peek_redo, peek_undo
from pydiag.application.flow_position_edit import graph_node_positions
from pydiag.application.flow_view import (
    SKIP_POSITION_AUTOSAVE_ONCE_KEY,
    detect_canvas_position_autosave,
    sync_component_positions,
    take_skip_position_autosave_once,
)
from pydiag.common.graph_source_admin import UpdateGraphSourceEdgeCommand
from pydiag.infrastructure.flow_source_graph import load_structured_payload
from pydiag.infrastructure.storage import (
    load_graph_doc,
    load_graph_source_edge_draft,
    load_wells_doc,
    materialize_flow_graph_from_source,
    save_graph_positions_with_version_check,
    save_graph_source_edge_with_version_check,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import (
    StreamlitSessionCoordinator,
    edge_snapshot_from_draft,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeStreamlitModule:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []
        self.reruns = 0
        self.rerun_scopes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def rerun(self, *, scope: str = "app") -> None:
        self.reruns += 1
        self.rerun_scopes.append(scope)


class FakeAuth:
    def current_user_is_admin(self) -> bool:
        return True


class RuntimeWithSession(StreamlitAppRuntime):
    def __init__(self, st_module, session) -> None:
        super().__init__(st_module, documents_gateway=object())  # type: ignore[arg-type]
        self._session = session
        self._auth = FakeAuth()

    @property
    def session(self):  # type: ignore[override]
        return self._session

    def auth_context(self):  # type: ignore[override]
        return self._auth


def _prepare_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    graph_path = tmp_path / "flow_graph.json"
    wells_path = tmp_path / "wells.yaml"
    source_path = tmp_path / "flow_source.yaml"
    source_path.write_bytes((FIXTURES / "flow_source.yaml").read_bytes())
    wells_path.write_bytes((FIXTURES / "wells.yaml").read_bytes())
    materialize_flow_graph_from_source(source_path=source_path, target_path=graph_path)
    return graph_path, wells_path, source_path


def _gateway(graph_path: Path, wells_path: Path, source_path: Path):
    class Gateway:
        def load_documents(self, graph_version_id=None):
            _ = graph_version_id, graph_path
            return load_graph_doc(source_path), load_wells_doc(wells_path)

        def save_graph_positions(
            self, positions, *, expected_version, graph_version_id=None
        ):
            _ = graph_version_id
            return save_graph_positions_with_version_check(
                positions,
                expected_version=expected_version,
                path=source_path,
            )

        def load_graph_source_edge(self, edge_id, *, graph_version_id=None):
            _ = graph_version_id
            return load_graph_source_edge_draft(source_path, edge_id)

        def save_graph_source_edge(self, command, *, expected_version, graph_version_id=None):
            _ = graph_version_id
            return save_graph_source_edge_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def create_graph_source_edge(self, command, *, expected_version, graph_version_id=None):
            from pydiag.infrastructure.storage import create_graph_source_edge_with_version_check

            _ = graph_version_id
            return create_graph_source_edge_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def list_graph_versions(self):
            return []

        def live_graph_source_exists(self) -> bool:
            return True

    return Gateway()


def test_sync_component_positions_and_skip_flag() -> None:
    session: dict = {}
    sync_component_positions(session, {"a": (1.5, 2.5)})
    assert session["well_drilling_flow_canvas"]["positions"] == {
        "a": {"x": 1.5, "y": 2.5}
    }
    session[SKIP_POSITION_AUTOSAVE_ONCE_KEY] = True
    assert take_skip_position_autosave_once(session) is True
    assert take_skip_position_autosave_once(session) is False


def test_position_undo_redo_survives_stale_component_positions(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)

    graph, _wells = coordinator.load_app_data(force=True)
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")
    original = (node.position.x, node.position.y)
    moved = (original[0] + 40.0, original[1] - 15.0)
    positions = graph_node_positions(graph)
    positions[node.id] = moved

    assert coordinator.save_graph_positions(
        graph, positions, quiet=True, record_history=True
    )
    assert can_undo(st_module.session_state)
    assert peek_undo(st_module.session_state)["kind"] == "move_nodes"

    # Simulate FE still holding the moved layout after undo persist.
    graph_after_move, _ = coordinator.load_app_data(force=True)
    st_module.session_state["well_drilling_flow_canvas"] = {
        "positions": {node.id: {"x": moved[0], "y": moved[1]}},
    }
    coordinator.undo_edit(graph_after_move)

    assert can_redo(st_module.session_state)
    assert peek_redo(st_module.session_state)["kind"] == "move_nodes"
    assert st_module.session_state.get(SKIP_POSITION_AUTOSAVE_ONCE_KEY) is True

    graph_undone, _ = coordinator.load_app_data(force=True)
    assert graph_node_positions(graph_undone)[node.id] == (
        round(original[0], 2),
        round(original[1], 2),
    )

    # Stale FE positions would otherwise re-autosave and wipe redo.
    st_module.session_state["well_drilling_flow_canvas"] = {
        "positions": {node.id: {"x": moved[0], "y": moved[1]}},
    }
    runtime._autosave_canvas_positions(graph_undone, position_edit_enabled=True)

    assert can_redo(st_module.session_state)
    assert detect_canvas_position_autosave(
        st_module.session_state, graph=graph_undone
    ) is None

    graph_for_redo, _ = coordinator.load_app_data(force=True)
    coordinator.redo_edit(graph_for_redo)
    graph_redone, _ = coordinator.load_app_data(force=True)
    assert graph_node_positions(graph_redone)[node.id] == (
        round(moved[0], 2),
        round(moved[1], 2),
    )
    assert can_undo(st_module.session_state)
    assert not can_redo(st_module.session_state)


def test_edge_kind_edit_undo_redo(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, _ = coordinator.load_app_data(force=True)
    draft = load_graph_source_edge_draft(source_path, "e_completion_archive")
    before = edge_snapshot_from_draft(draft)

    ok = coordinator.save_graph_source_edge(
        graph,
        UpdateGraphSourceEdgeCommand(
            edge_id=draft.edge_id,
            source=draft.source,
            target=draft.target,
            kind="dashed",
            label=draft.label,
            condition=draft.condition,
            note=draft.note,
        ),
        quiet=True,
        record_history=True,
        before_snapshot=before,
    )
    assert ok is True
    assert can_undo(st_module.session_state)
    assert peek_undo(st_module.session_state)["kind"] == "update_edge"

    graph_after, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph_after)
    restored = load_graph_source_edge_draft(source_path, "e_completion_archive")
    assert restored.kind == "default"
    assert can_redo(st_module.session_state)

    graph_undone, _ = coordinator.load_app_data(force=True)
    coordinator.redo_edit(graph_undone)
    redone = load_graph_source_edge_draft(source_path, "e_completion_archive")
    assert redone.kind == "dashed"


def test_edge_delete_undo_restores(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, _ = coordinator.load_app_data(force=True)
    draft = load_graph_source_edge_draft(source_path, "e_completion_archive")
    before = edge_snapshot_from_draft(draft)

    ok = coordinator.save_graph_source_edge(
        graph,
        UpdateGraphSourceEdgeCommand(
            edge_id=draft.edge_id,
            source=draft.source,
            target=draft.target,
            kind=draft.kind,
            label=draft.label,
            condition=draft.condition,
            note=draft.note,
            deleted=True,
        ),
        quiet=True,
        record_history=True,
        before_snapshot=before,
    )
    assert ok is True
    saved = load_structured_payload(source_path.read_bytes())
    assert not any(
        item["id"] == "e_completion_archive"
        for item in saved["nodes"]["proc_completion"]["transitions"]
    )
    assert peek_undo(st_module.session_state)["kind"] == "delete_edge"

    graph_after, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph_after)
    restored = load_graph_source_edge_draft(source_path, "e_completion_archive")
    assert restored.source == draft.source
    assert restored.target == draft.target
    assert can_redo(st_module.session_state)
