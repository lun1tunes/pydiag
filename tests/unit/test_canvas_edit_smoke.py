"""Smoke: every canvas edit action stays quiet (fragment rerun, no UI reset)."""

from __future__ import annotations

from pathlib import Path

from pydiag.application.flow_view import (
    FLOW_CANVAS_SESSION_EPOCH_KEY,
    bump_flow_canvas_session_epoch,
    consume_pending_canvas_edge_edit,
    consume_pending_canvas_node_edit,
)
from pydiag.common.graph_source_admin import UpdateGraphSourceEdgeCommand
from pydiag.infrastructure.flow_source_graph import load_structured_payload
from pydiag.infrastructure.storage import (
    load_graph_doc,
    load_graph_source_edge_draft,
    load_graph_source_node_draft,
    load_wells_doc,
    materialize_flow_graph_from_source,
    save_graph_source_edge_with_version_check,
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
            # Load runtime graph from the editable source so version stays in sync
            # across sequential quiet canvas edits.
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

        def editable_graph_version_id(self):
            return None

    return Gateway()


def _assert_fragment_only(st_module: FakeStreamlitModule, *, before: int) -> None:
    assert st_module.reruns == before + 1
    assert st_module.rerun_scopes[-1] == "fragment"
    assert "app" not in st_module.rerun_scopes[before:]


def test_canvas_edit_menu_js_covers_every_action() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    # Node menu actions
    for label in ("Заголовок", "Тип", "Роли", "Длительность", "Заметка", "Удалить"):
        assert f'label: "{label}"' in js or f'textContent = "{label}"' in js
    assert "function openDurationPopover(state, nodeId, anchor)" in js
    assert "function openDeleteConfirmPopover(state," in js
    assert "function openRolesPopover(state, nodeId, anchor)" in js
    assert '"Участники"' in js
    assert "Согласующие" not in js
    assert "function openKindMenu(state, nodeId, anchor)" in js
    assert "function beginTitleEdit(state, nodeId)" in js
    assert "function applyOptimisticNodeEdit(state, nodeId, payload)" in js

    # Edge menu
    assert 'textContent = "Тип связи"' in js
    assert "function openEdgeKindEditor(state, edgeId, anchor)" in js
    assert "Удалить связь?" in js

    # No native dialogs / no always-on chrome
    assert ".confirm(" not in js
    assert "flow-node-edit-panel" not in js
    assert "immersiveMode" in js
    assert "scope=\"fragment\"" not in js  # scope is Python-side
    assert ".flow-edit-hud" in css
    assert ".flow-edit-duration__unit" in css
    assert ".flow-edit-confirm__message" in css


def test_smoke_all_node_edit_buttons_use_fragment_rerun(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY] = 7
    bump_flow_canvas_session_epoch(st_module.session_state)
    epoch_before = int(st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY])

    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    node_id = "proc_initial_review"
    st_module.session_state["selected_id"] = node_id

    edits: list[tuple[str, dict]] = [
        ("title", {"title": "Smoke title"}),
        ("kind", {"kind": "decision_diamond"}),
        (
            "roles",
            {
                "responsible": "geology",
                "participants": ["planning"],
            },
        ),
        ("duration", {"duration": "45 minutes"}),
        ("note", {"note": "smoke note"}),
    ]

    for field, patch in edits:
        graph, wells = coordinator.load_app_data(force=True)
        before = st_module.reruns
        ok = coordinator.apply_canvas_node_edit(
            graph,
            wells,
            {"node_id": node_id, **patch},
            quiet=True,
            record_history=True,
        )
        assert ok is True, f"{field} failed: {st_module.errors}"
        assert st_module.errors == []
        _assert_fragment_only(st_module, before=before)
        assert st_module.session_state.get("selected_id") == node_id
        assert int(st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY]) == epoch_before

    saved = load_structured_payload(source_path.read_bytes())
    node = saved["nodes"][node_id]
    assert node["title"] == "Smoke title"
    assert node["kind"] == "decision_diamond"
    assert node["responsible"] == "geology"
    assert node["participants"] == ["planning"]
    assert node["duration"] == "45 minutes"
    assert node["note"] == "smoke note"


def test_smoke_pending_node_edit_consume_path_for_each_field(documents, tmp_path: Path) -> None:
    """Runtime consume mirrors ⋯ menu commits (title/kind/roles/duration/note)."""
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY] = 3
    epoch_before = 3

    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    runtime = RuntimeWithSession(st_module, coordinator)
    node_id = "proc_initial_review"

    patches = [
        {"title": "Via pending title"},
        {"kind": "event"},
        {"responsible": "hse", "participants": [], "approvers": ["planning"]},
        {"duration": "2 days"},
        {"note": "via pending"},
    ]
    for index, patch in enumerate(patches):
        graph, wells = coordinator.load_app_data(force=True)
        request_id = f"ne-smoke-{index}"
        st_module.session_state["well_drilling_flow_canvas"] = {
            "pending_node_edit": {
                "node_id": node_id,
                "request_id": request_id,
                **patch,
            }
        }
        before = st_module.reruns
        # Parse/dedupe then apply like the fragment does.
        pending = consume_pending_canvas_node_edit(st_module.session_state, graph=graph)
        assert pending is not None
        ok = coordinator.apply_canvas_node_edit(
            graph, wells, pending, quiet=True, record_history=True
        )
        assert ok is True
        _assert_fragment_only(st_module, before=before)
        assert int(st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY]) == epoch_before
        _ = runtime  # keep wiring import used for parity with production runtime class

    saved = load_structured_payload(source_path.read_bytes())
    node = saved["nodes"][node_id]
    assert node["title"] == "Via pending title"
    assert node["kind"] == "event"
    assert node["responsible"] == "hse"
    assert node["approvers"] == ["planning"]
    assert node["duration"] == "2 days"
    assert node["note"] == "via pending"


def test_smoke_edge_kind_and_delete_use_fragment_rerun(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY] = 11
    epoch_before = 11

    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    edge_id = "e_completion_archive"
    st_module.session_state["selected_id"] = edge_id

    graph, _ = coordinator.load_app_data(force=True)
    draft = load_graph_source_edge_draft(source_path, edge_id)
    before = st_module.reruns
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
    )
    assert ok is True
    _assert_fragment_only(st_module, before=before)
    assert int(st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY]) == epoch_before

    # pending_edge_edit consume path (kind)
    graph, _ = coordinator.load_app_data(force=True)
    st_module.session_state["well_drilling_flow_canvas"] = {
        "pending_edge_edit": {
            "edge_id": edge_id,
            "kind": "yes",
            "request_id": "ee-smoke-kind",
        }
    }
    pending = consume_pending_canvas_edge_edit(st_module.session_state, graph=graph)
    assert pending == {"edge_id": edge_id, "kind": "yes"}
    draft = coordinator.load_graph_source_edge(edge_id)
    before = st_module.reruns
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
    _assert_fragment_only(st_module, before=before)

    saved = load_structured_payload(source_path.read_bytes())
    transition = next(
        item
        for item in saved["nodes"]["proc_completion"]["transitions"]
        if item["id"] == edge_id
    )
    assert transition["kind"] == "yes"

    # Soft-delete via quiet edge update
    graph, _ = coordinator.load_app_data(force=True)
    draft = coordinator.load_graph_source_edge(edge_id)
    before = st_module.reruns
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
    )
    assert ok is True
    _assert_fragment_only(st_module, before=before)
    assert st_module.session_state.get("selected_id") is None
    assert int(st_module.session_state[FLOW_CANVAS_SESSION_EPOCH_KEY]) == epoch_before


def test_smoke_quiet_vs_loud_rerun_scope(tmp_path: Path) -> None:
    graph_path, wells_path, source_path = _prepare_workspace(tmp_path)
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(
        st_module,
        _gateway(graph_path, wells_path, source_path),  # type: ignore[arg-type]
    )
    graph, wells = coordinator.load_app_data(force=True)
    ok = coordinator.apply_canvas_node_edit(
        graph,
        wells,
        {"node_id": "proc_initial_review", "title": "Quiet"},
        quiet=True,
    )
    assert ok is True
    assert st_module.rerun_scopes == ["fragment"]

    graph, wells = coordinator.load_app_data(force=True)
    ok = coordinator.apply_canvas_node_edit(
        graph,
        wells,
        {"node_id": "proc_initial_review", "title": "Loud"},
        quiet=False,
    )
    assert ok is True
    assert st_module.rerun_scopes[-1] == "app"
