"""Smoke coverage for multi-select: Ctrl/Shift, bulk edit/delete, undo/redo."""

from __future__ import annotations

from pathlib import Path

from pydiag.application.edit_history import (
    can_redo,
    can_undo,
    peek_redo,
    peek_undo,
    pop_undo,
    push_batch_command,
    push_delete_node_command,
)
from pydiag.application.flow_view import (
    FLOW_CANVAS_PENDING_NODE_EDITS_REQUEST_KEY,
    consume_pending_canvas_node_edits,
)
from pydiag.infrastructure.flow_source_graph import (
    FlowSourceDocument,
    load_structured_payload,
)
from pydiag.infrastructure.storage import (
    load_graph_doc,
    load_graph_source_node_draft,
    load_wells_doc,
    materialize_flow_graph_from_source,
    save_graph_source_node_with_version_check,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.rendering.flow_canvas_component import ASSETS_DIR

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _asset_text(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


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

        def load_graph_source_node(self, node_id, *, graph_version_id=None):
            _ = graph_version_id
            return load_graph_source_node_draft(source_path, node_id)

        def save_graph_source_node(self, command, *, expected_version, graph_version_id=None):
            _ = graph_version_id
            return save_graph_source_node_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def list_graph_versions(self):
            return []

        def live_graph_source_exists(self) -> bool:
            return True

    return Gateway()


def test_multi_select_js_supports_ctrl_and_shift() -> None:
    js = _asset_text("flow_canvas.js")
    assert "function isMultiSelectModifier(event)" in js
    assert "event.shiftKey" in js
    assert "event.ctrlKey || event.metaKey || event.shiftKey" in js
    assert "function setSelectionSets(state, primaryId, nextNodeIds, nextEdgeIds)" in js
    assert "selectedProcessId = null" in js
    assert "function resolveDragNodeIds(state, nodeId)" in js
    assert "pending_node_edits" in js
    assert "pending_edge_edits" in js
    assert "requestBulkDeleteSelection" in js
    assert "openMultiNodeEditActionMenu" in js
    assert "suppressNextNodeClick" in js


def test_push_batch_command_collapses_to_single_undo_step() -> None:
    session: dict = {}
    push_batch_command(
        session,
        commands=[
            {"kind": "delete_node", "node_id": "a", "before": {"title": "A"}},
            {"kind": "delete_node", "node_id": "b", "before": {"title": "B"}},
        ],
    )
    assert can_undo(session)
    command = peek_undo(session)
    assert command is not None
    assert command["kind"] == "batch"
    assert len(command["commands"]) == 2

    push_batch_command(
        session,
        commands=[{"kind": "delete_node", "node_id": "c", "before": {"title": "C"}}],
    )
    assert peek_undo(session)["kind"] == "delete_node"


def test_bulk_node_delete_is_one_undo_step(tmp_path: Path) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    graph, wells = coordinator.load_app_data(force=True)

    # Use cards without wells so delete is allowed.
    node_a = "proc_well_design"
    node_b = "dec_design_ok"
    assert node_a in {node.id for node in graph.nodes}
    assert node_b in {node.id for node in graph.nodes}

    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_node_edits": {
            "request_id": "ne-bulk-del-1",
            "node_ids": [node_a, node_b],
            "patch": {"deleted": True},
        }
    }
    runtime._consume_pending_canvas_node_edits(graph, wells)

    assert can_undo(st_module.session_state)
    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "batch"
    assert {step["node_id"] for step in command["commands"]} == {node_a, node_b}

    payload = load_structured_payload(source_path.read_bytes())
    document = FlowSourceDocument.model_validate(payload, strict=True)
    assert document.nodes[node_a].deleted is True
    assert document.nodes[node_b].deleted is True

    graph_deleted, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph_deleted, rerun=False)

    assert can_redo(st_module.session_state)
    assert peek_redo(st_module.session_state)["kind"] == "batch"

    payload_restored = load_structured_payload(source_path.read_bytes())
    restored = FlowSourceDocument.model_validate(payload_restored, strict=True)
    assert restored.nodes[node_a].deleted is not True
    assert restored.nodes[node_b].deleted is not True

    active_ids = {node.id for node in coordinator.load_app_data(force=True)[0].nodes}
    assert node_a in active_ids
    assert node_b in active_ids


def test_bulk_kind_change_is_one_undo_step(tmp_path: Path) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    graph, wells = coordinator.load_app_data(force=True)

    node_a = "proc_well_design"
    node_b = "proc_initial_review"
    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_node_edits": {
            "request_id": "ne-bulk-kind-1",
            "node_ids": [node_a, node_b],
            "patch": {"kind": "event"},
        }
    }
    runtime._consume_pending_canvas_node_edits(graph, wells)

    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "batch"
    assert all(step["kind"] == "update_node" for step in command["commands"])

    payload = load_structured_payload(source_path.read_bytes())
    document = FlowSourceDocument.model_validate(payload, strict=True)
    assert document.nodes[node_a].kind == "event"
    assert document.nodes[node_b].kind == "event"

    graph_changed, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph_changed, rerun=False)

    payload_restored = load_structured_payload(source_path.read_bytes())
    restored = FlowSourceDocument.model_validate(payload_restored, strict=True)
    assert restored.nodes[node_a].kind == "process"
    assert restored.nodes[node_b].kind == "process"


def test_consume_pending_node_edits_dedupes_request_id(documents) -> None:
    graph, _ = documents
    session: dict = {
        "well_drilling_flow_canvas": {
            "pending_node_edits": {
                "request_id": "bulk-dup",
                "node_ids": ["proc_initial_review", "proc_well_design"],
                "patch": {"kind": "event"},
            }
        }
    }
    first = consume_pending_canvas_node_edits(session, graph=graph)
    assert first is not None
    assert first["node_ids"] == ["proc_initial_review", "proc_well_design"]
    assert session[FLOW_CANVAS_PENDING_NODE_EDITS_REQUEST_KEY] == "bulk-dup"
    assert session["well_drilling_flow_canvas"]["pending_node_edits"] is None

    session["well_drilling_flow_canvas"] = {
        "pending_node_edits": {
            "request_id": "bulk-dup",
            "node_ids": ["proc_initial_review"],
            "patch": {"kind": "database"},
        }
    }
    assert consume_pending_canvas_node_edits(session, graph=graph) is None


def test_single_delete_still_pushes_plain_command() -> None:
    session: dict = {}
    push_delete_node_command(
        session,
        node_id="only",
        before={"title": "Only"},
    )
    assert pop_undo(session)["kind"] == "delete_node"
