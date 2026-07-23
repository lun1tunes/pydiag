from __future__ import annotations

from pathlib import Path

from pydiag.application.edit_history import can_redo, can_undo, peek_undo
from pydiag.infrastructure.flow_source_graph import load_structured_payload
from pydiag.infrastructure.storage import (
    load_documents,
    load_graph_source_edge_draft,
    load_graph_source_node_draft,
    materialize_flow_graph_from_source,
    save_graph_source_edge_with_version_check,
    save_graph_source_node_with_version_check,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator

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
    def __init__(self, *, is_admin: bool = True) -> None:
        self._is_admin = is_admin

    def current_user_is_admin(self) -> bool:
        return self._is_admin


class RuntimeWithSession(StreamlitAppRuntime):
    def __init__(self, st_module, session, *, is_admin: bool = True) -> None:
        super().__init__(st_module, documents_gateway=object())  # type: ignore[arg-type]
        self._session = session
        self._auth = FakeAuth(is_admin=is_admin)

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


def test_runtime_consumes_pending_canvas_node_edit(documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()

    class FakeSession:
        def __init__(self) -> None:
            self.session_state = {
                "well_drilling_flow_canvas": {
                    "pending_node_edit": {
                        "node_id": "proc_initial_review",
                        "title": "Canvas title",
                        "request_id": "ne-rt-1",
                    }
                }
            }
            self.patches: list[dict] = []
            self.edit_available = True

        def graph_source_edit_available(self) -> bool:
            return self.edit_available

        def graph_source_edit_block_reason(self) -> str | None:
            return None if self.edit_available else "blocked"

        def apply_canvas_node_edit(self, graph, wells, patch, **kwargs):
            _ = graph, wells, kwargs
            self.patches.append(patch)
            return True

    session = FakeSession()
    runtime = RuntimeWithSession(st_module, session)
    runtime._consume_pending_canvas_node_edit(graph, wells)

    assert session.patches == [
        {"node_id": "proc_initial_review", "title": "Canvas title"}
    ]
    assert session.session_state["well_drilling_flow_canvas"]["pending_node_edit"] is None


def test_runtime_consumes_pending_canvas_edge_edit(documents) -> None:
    graph, _wells = documents
    edge = next(item for item in graph.edges if item.id == "e_completion_archive")
    st_module = FakeStreamlitModule()

    class FakeDraft:
        edge_id = edge.id
        source = edge.source
        target = edge.target
        kind = "default"
        label = None
        condition = None
        note = None

    class FakeSession:
        def __init__(self) -> None:
            self.session_state = {
                "well_drilling_flow_canvas": {
                    "pending_edge_edit": {
                        "edge_id": edge.id,
                        "kind": "dashed",
                        "request_id": "ee-rt-1",
                    }
                }
            }
            self.commands: list[object] = []
            self.kwargs: list[dict] = []
            self.edit_available = True

        def graph_source_edit_available(self) -> bool:
            return self.edit_available

        def graph_source_edit_block_reason(self) -> str | None:
            return None if self.edit_available else "blocked"

        def load_graph_source_edge(self, edge_id: str):
            assert edge_id == edge.id
            return FakeDraft()

        def save_graph_source_edge(self, graph_doc, command, **kwargs):
            _ = graph_doc
            self.commands.append(command)
            self.kwargs.append(kwargs)
            return True

    session = FakeSession()
    runtime = RuntimeWithSession(st_module, session)
    runtime._consume_pending_canvas_edge_edit(graph)

    assert len(session.commands) == 1
    command = session.commands[0]
    assert command.edge_id == edge.id
    assert command.kind == "dashed"
    assert command.deleted is None
    assert session.kwargs[0]["record_history"] is True
    assert session.kwargs[0]["before_snapshot"]["kind"] == "default"
    assert session.session_state["well_drilling_flow_canvas"]["pending_edge_edit"] is None


def test_apply_canvas_edge_edit_writes_yaml(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    graph, _wells = load_documents(graph_path, wells_path)
    st_module = FakeStreamlitModule()

    class Gateway:
        def load_documents(self, graph_version_id=None):
            _ = graph_version_id
            return load_documents(graph_path, wells_path)

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

        def list_graph_versions(self):
            return []

        def live_graph_source_exists(self) -> bool:
            return True

    from pydiag.common.graph_source_admin import UpdateGraphSourceEdgeCommand

    coordinator = StreamlitSessionCoordinator(st_module, Gateway())  # type: ignore[arg-type]
    draft = load_graph_source_edge_draft(source_path, "e_completion_archive")
    assert draft.kind == "default"
    ok = coordinator.save_graph_source_edge(
        graph,
        UpdateGraphSourceEdgeCommand(
            edge_id=draft.edge_id,
            source=draft.source,
            target=draft.target,
            kind="yes",
            label=draft.label,
            condition=draft.condition,
            note=draft.note,
        ),
        quiet=True,
    )
    assert ok is True
    assert st_module.errors == []
    assert st_module.rerun_scopes == ["fragment"]
    saved = load_structured_payload(source_path.read_bytes())
    transition = next(
        item
        for item in saved["nodes"]["proc_completion"]["transitions"]
        if item["id"] == "e_completion_archive"
    )
    assert transition["kind"] == "yes"


def test_apply_canvas_node_edit_writes_yaml_and_undo_restores(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    graph, wells = load_documents(graph_path, wells_path)
    st_module = FakeStreamlitModule()

    class Gateway:
        def load_documents(self, graph_version_id=None):
            _ = graph_version_id
            return load_documents(graph_path, wells_path)

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

    coordinator = StreamlitSessionCoordinator(st_module, Gateway())  # type: ignore[arg-type]
    original = load_graph_source_node_draft(source_path, "proc_initial_review")
    ok = coordinator.apply_canvas_node_edit(
        graph,
        wells,
        {
            "node_id": "proc_initial_review",
            "title": "Inline renamed",
            "kind": "decision_diamond",
            "responsible": "geology",
            "participants": [],
            "approvers": [],
        },
        quiet=True,
        record_history=True,
    )
    assert ok is True
    assert st_module.errors == []
    assert st_module.rerun_scopes == ["fragment"]
    saved = load_structured_payload(source_path.read_bytes())
    assert saved["nodes"]["proc_initial_review"]["title"] == "Inline renamed"
    assert saved["nodes"]["proc_initial_review"]["kind"] == "decision_diamond"
    assert saved["nodes"]["proc_initial_review"]["responsible"] == "geology"
    assert can_undo(st_module.session_state)
    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "update_node"
    assert command["before"]["title"] == original.title

    graph_after = st_module.session_state["graph_doc"]
    coordinator.undo_edit(graph_after)

    restored = load_structured_payload(source_path.read_bytes())
    assert restored["nodes"]["proc_initial_review"]["title"] == original.title
    assert restored["nodes"]["proc_initial_review"]["kind"] == original.kind
    assert restored["nodes"]["proc_initial_review"]["responsible"] == original.responsible
    assert can_redo(st_module.session_state)
