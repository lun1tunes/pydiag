"""Canvas add-node (+ Карточка) create path."""

from __future__ import annotations

from pathlib import Path

from pydiag.application.edit_history import can_redo, can_undo, peek_undo
from pydiag.common.graph_source_admin import CreateGraphSourceNodeCommand
from pydiag.infrastructure.flow_source_graph import (
    create_flow_source_payload_node,
    load_structured_payload,
)
from pydiag.infrastructure.storage import (
    create_graph_source_node_with_version_check,
    load_graph_doc,
    load_wells_doc,
    materialize_flow_graph_from_source,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.rendering.flow_canvas_component import _asset_text
from pydiag.rendering.flow_canvas_state import component_pending_node_create_from_state

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

        def create_graph_source_node(self, command, *, expected_version, graph_version_id=None):
            _ = graph_version_id
            return create_graph_source_node_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def save_graph_source_node(self, command, *, expected_version, graph_version_id=None):
            from pydiag.infrastructure.storage import save_graph_source_node_with_version_check

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


def test_add_node_button_assets() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")
    assert "flow-canvas-add-node" in js
    assert 'textContent = "+ Карточка"' in js
    assert 'title: "Измени меня"' in js
    assert 'setStateValue("pending_node_create"' in js
    assert ".flow-canvas-add-node" in css
    assert "left: 14px" in css
    assert "bottom: 14px" in css


def test_component_pending_node_create_from_state() -> None:
    pending = component_pending_node_create_from_state(
        {
            "pending_node_create": {
                "request_id": "nc-1",
                "title": "Измени меня",
                "kind": "process",
                "layout_x": 120.5,
                "layout_y": 80,
                "layout_w": 280,
                "layout_h": 72,
            }
        }
    )
    assert pending == {
        "request_id": "nc-1",
        "title": "Измени меня",
        "kind": "process",
        "layout_x": 120.5,
        "layout_y": 80.0,
        "layout_w": 280,
        "layout_h": 72,
    }


def test_create_flow_source_payload_node_defaults(tmp_path: Path) -> None:
    source_path = tmp_path / "flow_source.yaml"
    source_path.write_bytes((FIXTURES / "flow_source.yaml").read_bytes())
    payload = load_structured_payload(source_path.read_bytes())
    updated = create_flow_source_payload_node(
        payload,
        command=CreateGraphSourceNodeCommand(
            title="Измени меня",
            kind="process",
            layout_x=10,
            layout_y=20,
            layout_w=280,
            layout_h=72,
        ),
        expected_version=payload["version"],
    )
    assert "proc_izmeni_menya" in updated["nodes"]
    node = updated["nodes"]["proc_izmeni_menya"]
    assert node["title"] == "Измени меня"
    assert node["kind"] == "process"
    assert node["responsible"] == "unassigned"
    assert "unassigned" in updated["responsibles"]
    assert updated["responsibles"]["unassigned"]["label"] == "Не назначено"
    assert updated["layout"]["proc_izmeni_menya"]["x"] == 10.0


def test_create_node_from_canvas_with_undo(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    graph, _ = coordinator.load_app_data(force=True)
    before_ids = {node.id for node in graph.nodes}

    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_node_create": {
            "request_id": "nc-create-1",
            "title": "Измени меня",
            "kind": "process",
            "layout_x": 400,
            "layout_y": 300,
            "layout_w": 280,
            "layout_h": 72,
        }
    }
    runtime._consume_pending_canvas_node_create(graph)
    assert st_module.errors == []
    assert st_module.rerun_scopes == ["fragment"]

    graph_after, _ = coordinator.load_app_data(force=True)
    created_ids = {node.id for node in graph_after.nodes} - before_ids
    assert len(created_ids) == 1
    created = next(iter(created_ids))
    created_node = next(node for node in graph_after.nodes if node.id == created)
    assert created_node.text == "Измени меня"
    assert created_node.type == "process"
    assert created_node.responsible == ["unassigned"]
    assert created_node.primary_responsible == "unassigned"
    assert can_undo(st_module.session_state)
    assert peek_undo(st_module.session_state)["kind"] == "create_node"
    assert st_module.session_state.get("selected_id") == created

    coordinator.undo_edit(graph_after)
    graph_undone, _ = coordinator.load_app_data(force=True)
    assert created not in {node.id for node in graph_undone.nodes}
    assert can_redo(st_module.session_state)

    coordinator.redo_edit(graph_undone)
    graph_redone, _ = coordinator.load_app_data(force=True)
    assert created in {node.id for node in graph_redone.nodes}
    redone = next(node for node in graph_redone.nodes if node.id == created)
    assert redone.text == "Измени меня"
    assert can_undo(st_module.session_state)
    assert not can_redo(st_module.session_state)
