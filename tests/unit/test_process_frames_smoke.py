"""Production smoke for process frames: CRUD, claim, undo/redo, consume, JS."""

from __future__ import annotations

from pathlib import Path

from pydiag.application.edit_history import can_redo, can_undo, peek_undo
from pydiag.application.flow_view import (
    FLOW_CANVAS_PENDING_PROCESS_CREATE_REQUEST_KEY,
    FLOW_CANVAS_PENDING_PROCESS_DELETE_REQUEST_KEY,
    FLOW_CANVAS_PENDING_PROCESS_EDIT_REQUEST_KEY,
    consume_pending_canvas_process_create,
    consume_pending_canvas_process_delete,
    consume_pending_canvas_process_edit,
)
from pydiag.common.graph_source_admin import (
    CreateGraphSourceProcessCommand,
    DeleteGraphSourceProcessCommand,
    UpdateGraphSourceProcessCommand,
)
from pydiag.infrastructure.flow_source_graph import (
    FlowSourceDocument,
    load_structured_payload,
)
from pydiag.infrastructure.storage import (
    create_graph_source_process_with_version_check,
    delete_graph_source_process_with_version_check,
    load_graph_doc,
    load_wells_doc,
    materialize_flow_graph_from_source,
    update_graph_source_process_with_version_check,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.rendering.flow_canvas_component import ASSETS_DIR
from pydiag.rendering.flow_canvas_state import (
    component_pending_process_create_from_state,
    component_pending_process_delete_from_state,
    component_pending_process_edit_from_state,
)

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


def _gateway(graph_path: Path, wells_path: Path, source_path: Path):
    class Gateway:
        def load_documents(self, graph_version_id=None):
            _ = graph_version_id, graph_path
            return load_graph_doc(source_path), load_wells_doc(wells_path)

        def create_graph_source_process(
            self, command, *, expected_version, graph_version_id=None
        ):
            _ = graph_version_id
            return create_graph_source_process_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def update_graph_source_process(
            self, command, *, expected_version, graph_version_id=None
        ):
            _ = graph_version_id
            return update_graph_source_process_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def delete_graph_source_process(
            self, command, *, expected_version, graph_version_id=None
        ):
            _ = graph_version_id
            return delete_graph_source_process_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def list_graph_versions(self):
            return []

        def live_graph_source_exists(self) -> bool:
            return True

    return Gateway()


def _source_doc(source_path: Path) -> FlowSourceDocument:
    payload = load_structured_payload(source_path.read_bytes())
    return FlowSourceDocument.model_validate(payload, strict=True)


def test_process_frames_js_contract() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")
    assert "function syncProcessFrames(state)" in js
    assert "function commitProcessCreate(state, title, memberIds)" in js
    assert "function commitProcessEdit(state, processId, patch)" in js
    assert "function commitProcessDelete(state, processId)" in js
    assert "pending_process_create" in js
    assert "pending_process_edit" in js
    assert "pending_process_delete" in js
    assert "flow-canvas-processes" in js
    assert ".flow-process-frame" in css
    assert "commitProcessDelete(state, current.id)" in js
    assert "syncProcessFrames(state);" in js
    assert "state.selectedProcessId = null" in js
    assert "processes.some((item) => item && item.id === state.selectedProcessId)" in js


def test_create_rename_delete_process_with_undo_redo(tmp_path: Path) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, _ = coordinator.load_app_data(force=True)
    node_a = "proc_well_design"
    node_b = "proc_initial_review"

    created_id = coordinator.create_graph_source_process(
        graph,
        CreateGraphSourceProcessCommand(
            title="Подготовка",
            node_ids=(node_a, node_b),
            process_id="block_smoke",
        ),
        quiet=True,
        rerun=False,
    )
    assert created_id == "block_smoke"
    assert can_undo(st_module.session_state)
    doc = _source_doc(source_path)
    assert doc.processes["block_smoke"].title == "Подготовка"
    assert doc.processes["block_smoke"].node_ids == [node_a, node_b]

    graph2, _ = coordinator.load_app_data(force=True)
    assert coordinator.update_graph_source_process(
        graph2,
        UpdateGraphSourceProcessCommand(process_id="block_smoke", title="Этап А"),
        quiet=True,
        rerun=False,
    )
    assert _source_doc(source_path).processes["block_smoke"].title == "Этап А"

    graph3, _ = coordinator.load_app_data(force=True)
    assert coordinator.delete_graph_source_process(
        graph3,
        DeleteGraphSourceProcessCommand(process_id="block_smoke"),
        quiet=True,
        rerun=False,
    )
    assert "block_smoke" not in _source_doc(source_path).processes

    graph4, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph4, rerun=False)
    assert "block_smoke" in _source_doc(source_path).processes
    assert can_redo(st_module.session_state)

    graph5, _ = coordinator.load_app_data(force=True)
    coordinator.redo_edit(graph5, rerun=False)
    assert "block_smoke" not in _source_doc(source_path).processes


def test_empty_membership_update_deletes_process_and_undo_restores(
    tmp_path: Path,
) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, _ = coordinator.load_app_data(force=True)
    coordinator.create_graph_source_process(
        graph,
        CreateGraphSourceProcessCommand(
            title="Временный",
            node_ids=("proc_well_design",),
            process_id="block_tmp",
        ),
        quiet=True,
        rerun=False,
    )
    graph2, _ = coordinator.load_app_data(force=True)
    assert coordinator.update_graph_source_process(
        graph2,
        UpdateGraphSourceProcessCommand(process_id="block_tmp", node_ids=()),
        quiet=True,
        rerun=False,
    )
    assert "block_tmp" not in _source_doc(source_path).processes
    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "delete_process"

    graph3, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph3, rerun=False)
    restored = _source_doc(source_path).processes["block_tmp"]
    assert restored.node_ids == ["proc_well_design"]
    assert restored.title == "Временный"


def test_claim_from_existing_process_batches_side_effects_for_undo(
    tmp_path: Path,
) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, _ = coordinator.load_app_data(force=True)
    coordinator.create_graph_source_process(
        graph,
        CreateGraphSourceProcessCommand(
            title="Донор",
            node_ids=("proc_well_design", "proc_initial_review"),
            process_id="block_donor",
        ),
        quiet=True,
        rerun=False,
    )
    graph2, _ = coordinator.load_app_data(force=True)
    created = coordinator.create_graph_source_process(
        graph2,
        CreateGraphSourceProcessCommand(
            title="Приёмник",
            node_ids=("proc_well_design", "proc_initial_review"),
            process_id="block_recv",
        ),
        quiet=True,
        rerun=False,
    )
    assert created == "block_recv"
    doc = _source_doc(source_path)
    assert "block_donor" not in doc.processes
    assert doc.processes["block_recv"].node_ids == [
        "proc_well_design",
        "proc_initial_review",
    ]
    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "batch"
    kinds = [step["kind"] for step in command["commands"]]
    assert kinds == ["delete_process", "create_process"]

    graph3, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph3, rerun=False)
    restored = _source_doc(source_path)
    assert "block_recv" not in restored.processes
    assert restored.processes["block_donor"].node_ids == [
        "proc_well_design",
        "proc_initial_review",
    ]


def test_consume_pending_process_create_edit_delete(tmp_path: Path) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    graph, _ = coordinator.load_app_data(force=True)

    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_process_create": {
            "request_id": "pc-1",
            "title": "Канвас",
            "member_ids": ["proc_well_design", "dec_design_ok"],
        }
    }
    runtime._consume_pending_canvas_process_create(graph)
    doc = _source_doc(source_path)
    process_ids = [
        pid for pid, proc in doc.processes.items() if proc.title == "Канвас"
    ]
    assert len(process_ids) == 1
    process_id = process_ids[0]

    graph2, _ = coordinator.load_app_data(force=True)
    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_process_edit": {
            "request_id": "pe-1",
            "process_id": process_id,
            "title": "Канвас v2",
        }
    }
    runtime._consume_pending_canvas_process_edit(graph2)
    assert _source_doc(source_path).processes[process_id].title == "Канвас v2"

    graph3, _ = coordinator.load_app_data(force=True)
    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_process_delete": {
            "request_id": "pd-1",
            "process_id": process_id,
        }
    }
    runtime._consume_pending_canvas_process_delete(graph3)
    assert process_id not in _source_doc(source_path).processes


def test_consume_process_ops_dedupe_request_ids(documents) -> None:
    from pydiag.domain.models import FlowProcess

    graph, _ = documents
    graph_with = graph.model_copy(
        update={
            "processes": {
                "block_x": FlowProcess(
                    title="X",
                    node_ids=["proc_initial_review"],
                )
            }
        }
    )
    session: dict = {
        "well_drilling_flow_canvas": {
            "pending_process_create": {
                "request_id": "dup-pc",
                "title": "X",
                "member_ids": ["proc_initial_review"],
            }
        }
    }
    first = consume_pending_canvas_process_create(session, graph=graph)
    assert first is not None
    session["well_drilling_flow_canvas"] = {
        "pending_process_create": {
            "request_id": "dup-pc",
            "title": "X",
            "member_ids": ["proc_initial_review"],
        }
    }
    assert consume_pending_canvas_process_create(session, graph=graph) is None
    assert session[FLOW_CANVAS_PENDING_PROCESS_CREATE_REQUEST_KEY] == "dup-pc"

    session["well_drilling_flow_canvas"] = {
        "pending_process_edit": {
            "request_id": "dup-pe",
            "process_id": "block_x",
            "title": "Y",
        }
    }
    assert consume_pending_canvas_process_edit(session, graph=graph_with) is not None
    session["well_drilling_flow_canvas"] = {
        "pending_process_edit": {
            "request_id": "dup-pe",
            "process_id": "block_x",
            "title": "Y",
        }
    }
    assert consume_pending_canvas_process_edit(session, graph=graph_with) is None
    assert session[FLOW_CANVAS_PENDING_PROCESS_EDIT_REQUEST_KEY] == "dup-pe"

    session["well_drilling_flow_canvas"] = {
        "pending_process_delete": {
            "request_id": "dup-pd",
            "process_id": "block_x",
        }
    }
    assert consume_pending_canvas_process_delete(session, graph=graph_with) is not None
    session["well_drilling_flow_canvas"] = {
        "pending_process_delete": {
            "request_id": "dup-pd",
            "process_id": "block_x",
        }
    }
    assert consume_pending_canvas_process_delete(session, graph=graph_with) is None
    assert session[FLOW_CANVAS_PENDING_PROCESS_DELETE_REQUEST_KEY] == "dup-pd"


def test_process_pending_validators(documents) -> None:
    graph, _ = documents
    from pydiag.domain.models import FlowProcess

    graph = graph.model_copy(
        update={
            "processes": {
                "block_x": FlowProcess(
                    title="X",
                    node_ids=["proc_initial_review"],
                )
            }
        }
    )
    assert (
        component_pending_process_create_from_state(
            graph,
            {"pending_process_create": {"title": "", "member_ids": ["proc_initial_review"]}},
        )
        is None
    )
    assert component_pending_process_create_from_state(
        graph,
        {
            "pending_process_create": {
                "title": "Ok",
                "member_ids": ["proc_initial_review", "missing"],
            }
        },
    ) == {"title": "Ok", "member_ids": ["proc_initial_review"]}
    assert (
        component_pending_process_edit_from_state(
            graph,
            {"pending_process_edit": {"process_id": "missing", "title": "Z"}},
        )
        is None
    )
    assert component_pending_process_edit_from_state(
        graph,
        {
            "pending_process_edit": {
                "process_id": "block_x",
                "member_ids": [],
            }
        },
    ) == {"process_id": "block_x", "member_ids": []}
    assert (
        component_pending_process_delete_from_state(
            graph,
            {"pending_process_delete": {"process_id": "missing"}},
        )
        is None
    )


def test_non_admin_cannot_consume_process_ops(tmp_path: Path) -> None:
    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(_graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator, is_admin=False)
    graph, _ = coordinator.load_app_data(force=True)
    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_process_create": {
            "request_id": "pc-admin",
            "title": "Нет",
            "member_ids": ["proc_well_design"],
        }
    }
    runtime._consume_pending_canvas_process_create(graph)
    assert st_module.errors
    assert "администратору" in st_module.errors[0]
    assert _source_doc(source_path).processes == {}


def test_soft_delete_last_member_restores_process_on_undo(tmp_path: Path) -> None:
    from pydiag.infrastructure.storage import (
        load_graph_source_node_draft,
        save_graph_source_node_with_version_check,
    )

    _graph_path, wells_path, source_path = _prepare_workspace(tmp_path)

    class GatewayWithNodes:
        def load_documents(self, graph_version_id=None):
            _ = graph_version_id, _graph_path
            return load_graph_doc(source_path), load_wells_doc(wells_path)

        def create_graph_source_process(
            self, command, *, expected_version, graph_version_id=None
        ):
            _ = graph_version_id
            return create_graph_source_process_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

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

    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        GatewayWithNodes(),  # type: ignore[arg-type]
    )
    graph, wells = coordinator.load_app_data(force=True)
    node_id = "proc_well_design"
    coordinator.create_graph_source_process(
        graph,
        CreateGraphSourceProcessCommand(
            title="Один",
            node_ids=(node_id,),
            process_id="block_solo",
        ),
        quiet=True,
        rerun=False,
    )
    graph2, wells2 = coordinator.load_app_data(force=True)
    assert coordinator.apply_canvas_node_edit(
        graph2,
        wells2,
        {"node_id": node_id, "deleted": True},
        quiet=True,
        record_history=True,
        rerun=False,
    )
    assert "block_solo" not in _source_doc(source_path).processes
    command = peek_undo(st_module.session_state)
    assert command is not None
    assert command["kind"] == "batch"

    graph3, _ = coordinator.load_app_data(force=True)
    coordinator.undo_edit(graph3, rerun=False)
    restored = _source_doc(source_path)
    assert restored.nodes[node_id].deleted is not True
    assert restored.processes["block_solo"].node_ids == [node_id]
