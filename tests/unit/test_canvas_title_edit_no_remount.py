"""Title edits must persist without fragment remount (no camera jump / white flash)."""

from __future__ import annotations

from pathlib import Path

from pydiag.infrastructure.flow_source_graph import load_structured_payload
from pydiag.infrastructure.storage import (
    load_graph_doc,
    load_graph_source_node_draft,
    load_wells_doc,
    materialize_flow_graph_from_source,
    save_graph_source_node_with_version_check,
)
from pydiag.presentation.runtime import StreamlitAppRuntime
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.rendering.flow_canvas_component import _asset_text

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

        def save_graph_source_node(self, command, *, expected_version, graph_version_id=None):
            _ = graph_version_id
            return save_graph_source_node_with_version_check(
                command,
                expected_version=expected_version,
                path=source_path,
            )

        def load_graph_source_node(self, node_id, graph_version_id=None):
            _ = graph_version_id
            return load_graph_source_node_draft(source_path, node_id)

        def list_graph_versions(self):
            return []

        def live_graph_source_exists(self) -> bool:
            return True

    return Gateway()


def test_title_edit_consume_does_not_rerun_fragment(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    graph, wells = coordinator.load_app_data(force=True)
    node_id = "proc_initial_review"

    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_node_edit": {
            "node_id": node_id,
            "request_id": "ne-title-1",
            "title": "Stable Title Edit",
        }
    }
    runtime._consume_pending_canvas_node_edit(graph, wells)

    assert st_module.errors == []
    assert st_module.reruns == 0
    assert st_module.rerun_scopes == []

    graph_after, _ = coordinator.load_app_data(force=True)
    node = next(item for item in graph_after.nodes if item.id == node_id)
    assert node.text == "Stable Title Edit"
    saved = load_structured_payload(source_path.read_bytes())
    assert saved["nodes"][node_id]["title"] == "Stable Title Edit"


def test_canvas_js_patches_same_topology_without_fit_view() -> None:
    js = _asset_text("flow_canvas.js")
    assert "function patchGraphScene(state) {" in js
    assert "function sceneTopologySignature(payload) {" in js
    assert "if (!state.hasRenderedScene && !state.userMovedView) {" in js
    assert "Only auto-fit before the first successful paint" in js
    assert "Same node/edge ids" in js
