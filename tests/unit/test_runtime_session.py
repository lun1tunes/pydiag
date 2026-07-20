from __future__ import annotations

from pathlib import Path

from pydiag.application.session_state import PersistenceResult
from pydiag.application.flow_view import FLOW_SELECTION_RERUN_REQUEST_KEY
from pydiag.common.graph_versions import GraphVersionInfo, RawImportResult
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator


class FakeDocumentsGateway:
    def __init__(self, *, graph=None, wells=None, live_exists: bool = True):
        self.graph = graph
        self.wells = wells
        self.live_exists = live_exists
        self.calls: list[tuple[object, ...]] = []
        self.versions = [
            GraphVersionInfo(
                id="flow_source.v0001.yaml",
                label="v0001",
                path=Path("/tmp/flow_source.v0001.yaml"),
                is_versioned=True,
            )
        ]

    def load_documents(self, graph_version_id: str | None = None):
        self.calls.append(("load_documents", graph_version_id))
        return self.graph, self.wells

    def live_graph_source_exists(self) -> bool:
        self.calls.append(("live_graph_source_exists", self.live_exists))
        return self.live_exists

    def ensure_live_graph_source(self):
        path = Path("/tmp/flow_source.yaml")
        self.calls.append(("ensure_live_graph_source", path))
        return path

    def save_wells(self, document, *, graph, expected_version: int):
        self.calls.append(
            ("save_wells", document.version, expected_version, graph.version),
        )
        return document

    def save_graph_positions(
        self,
        positions,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ):
        self.calls.append(
            (
                "save_graph_positions",
                positions,
                expected_version,
                graph_version_id,
            ),
        )
        return self.graph

    def list_graph_versions(self):
        self.calls.append(("list_graph_versions",))
        return self.versions

    def can_materialize_graph_version(self):
        self.calls.append(("can_materialize_graph_version",))
        return True

    def materialize_graph_version(self):
        version = GraphVersionInfo(
            id="flow_source.v0002.yaml",
            label="flow_source.v0002.yaml",
            path=Path("/tmp/flow_source.v0002.yaml"),
            is_versioned=True,
        )
        self.calls.append(("materialize_graph_version", version.id))
        self.versions = [version, *self.versions]
        return version

    def can_import_raw_graph_source(self):
        self.calls.append(("can_import_raw_graph_source",))
        return True

    def import_live_graph_source_from_raw(self):
        result = RawImportResult(
            live_path=Path("/tmp/flow_source.yaml"),
            changed=True,
            backup_version=GraphVersionInfo(
                id="flow_source.v0002.yaml",
                label="flow_source.v0002.yaml",
                path=Path("/tmp/flow_source.v0002.yaml"),
                is_versioned=True,
            ),
        )
        self.calls.append(("import_live_graph_source_from_raw", result.backup_version.id))
        return result


class FakeStreamlitModule:
    def __init__(self):
        self.session_state: dict[str, object] = {}
        self.messages: list[tuple[str, str]] = []
        self.reruns = 0

    def success(self, message: str) -> None:
        self.messages.append(("success", message))

    def warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def error(self, message: str) -> None:
        self.messages.append(("error", message))

    def rerun(self) -> None:
        self.reruns += 1


def test_session_coordinator_render_flash_emits_streamlit_messages() -> None:
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(st_module, FakeDocumentsGateway())

    coordinator.flash("saved")
    coordinator.render_flash()
    coordinator.flash("watch out", "warning")
    coordinator.render_flash()
    coordinator.flash("boom", "error")
    coordinator.render_flash()

    assert st_module.messages == [
        ("success", "saved"),
        ("warning", "watch out"),
        ("error", "boom"),
    ]


def test_session_coordinator_consumes_flow_selection_rerun_request() -> None:
    st_module = FakeStreamlitModule()
    st_module.session_state[FLOW_SELECTION_RERUN_REQUEST_KEY] = True
    coordinator = StreamlitSessionCoordinator(st_module, FakeDocumentsGateway())

    assert coordinator.consume_flow_selection_rerun_request() is True
    assert coordinator.consume_flow_selection_rerun_request() is False


def test_session_coordinator_reload_and_reset_position_draft(monkeypatch, documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[bool] = []

    def fake_load(session_state, loader, *, force: bool = False):
        _ = session_state
        loaded_graph, loaded_wells = loader()
        load_calls.append(force)
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )
    st_module.session_state["position_edit_signature"] = ("sig",)
    st_module.session_state["position_edit_positions"] = {"node": (1.0, 2.0)}

    coordinator.reload_data()
    coordinator.reset_position_draft()

    assert load_calls == [True]
    assert gateway.calls == [
        ("list_graph_versions",),
        ("live_graph_source_exists", True),
        ("load_documents", None),
    ]
    assert st_module.reruns == 2
    assert "position_edit_signature" not in st_module.session_state
    assert "position_edit_positions" not in st_module.session_state
    assert st_module.session_state["position_edit_dirty"] is False
    assert st_module.session_state["flash"] == {
        "message": "Черновик расположения сброшен",
        "level": "success",
    }


def test_session_coordinator_reload_does_not_materialize_live_source_for_archived_view(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[tuple[bool, str | None]] = []

    def fake_load(session_state, loader, *, force: bool = False):
        loaded_graph, loaded_wells = loader()
        load_calls.append((force, session_state.get("selected_graph_version_id")))
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"

    coordinator.reload_data()

    assert load_calls == [(True, "flow_source.v0001.yaml")]
    assert gateway.calls == [
        ("list_graph_versions",),
        ("load_documents", "flow_source.v0001.yaml"),
    ]
    assert st_module.reruns == 1


def test_session_coordinator_reload_reports_error_when_live_source_bootstrap_fails(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    def fail_load(graph_version_id: str | None = None):
        gateway.calls.append(("load_documents", graph_version_id))
        raise FileNotFoundError("Graph source not found")

    monkeypatch.setattr(gateway, "load_documents", fail_load)

    coordinator.reload_data()

    assert gateway.calls == [
        ("list_graph_versions",),
        ("live_graph_source_exists", True),
        ("load_documents", None),
    ]
    assert st_module.messages == [
        ("error", "Не удалось обновить данные: Graph source not found"),
    ]
    assert st_module.reruns == 0
    assert "flash" not in st_module.session_state


def test_session_coordinator_reload_reports_error_when_load_fails_after_bootstrap(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    def fail_load(graph_version_id: str | None = None):
        gateway.calls.append(("load_documents", graph_version_id))
        raise ValueError("broken source")

    monkeypatch.setattr(gateway, "load_documents", fail_load)

    coordinator.reload_data()

    assert gateway.calls == [
        ("list_graph_versions",),
        ("live_graph_source_exists", True),
        ("load_documents", None),
    ]
    assert st_module.messages == [
        ("error", "Не удалось обновить данные: broken source"),
    ]
    assert st_module.reruns == 0
    assert "flash" not in st_module.session_state


def test_session_coordinator_position_edit_helpers(documents) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(st_module, FakeDocumentsGateway())

    assert coordinator.has_position_edit_positions() is False
    positions = coordinator.position_edit_positions(graph)
    assert positions["proc_initial_review"] == (
        graph.nodes[2].position.x,
        graph.nodes[2].position.y,
    )

    st_module.session_state["position_edit_positions"] = {"proc_initial_review": (10.0, 20.0)}
    assert coordinator.has_position_edit_positions() is True
    assert coordinator.position_edit_positions(graph)["proc_initial_review"] == (10.0, 20.0)


def test_session_coordinator_updates_position_edit_draft(documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    coordinator = StreamlitSessionCoordinator(st_module, FakeDocumentsGateway())

    draft = coordinator.ensure_position_edit_draft(graph, wells, "custom")
    assert "proc_initial_review" in draft

    updated = coordinator.update_position_edit_draft(
        graph,
        node_id="proc_initial_review",
        x=733.5,
        y=412.25,
    )

    assert updated["proc_initial_review"] == (733.5, 412.25)
    assert st_module.session_state["position_edit_positions"]["proc_initial_review"] == (
        733.5,
        412.25,
    )
    assert st_module.session_state["position_edit_dirty"] is True
    assert st_module.session_state["_position_edit_rerun_requested"] is True


def test_session_coordinator_exposes_materialization_capability() -> None:
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway()
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    assert coordinator.can_materialize_graph_version() is True
    assert gateway.calls == [("can_materialize_graph_version",)]


def test_session_coordinator_exposes_raw_import_capability() -> None:
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway()
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    assert coordinator.can_import_raw_graph_source() is True
    assert gateway.calls == [("can_import_raw_graph_source",)]


def test_session_coordinator_save_wells_runs_storage_workflow(monkeypatch, documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway()
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    calls: list[tuple[str, object]] = []

    def fake_persist_wells(session_state, updated, *, save, reload_data, success_message):
        _ = session_state
        _ = reload_data
        calls.append(("persist", updated.version, success_message))
        save(updated)
        return PersistenceResult(should_rerun=True)

    monkeypatch.setattr("pydiag.presentation.runtime_session.persist_wells", fake_persist_wells)

    coordinator.save_wells(
        wells,
        graph=graph,
        expected_version=wells.version,
        success_message="saved",
    )

    assert ("persist", wells.version, "saved") in calls
    assert gateway.calls == [("save_wells", wells.version, wells.version, graph.version)]
    assert st_module.reruns == 1


def test_session_coordinator_blocks_wells_update_for_archived_schema_version(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"
    calls: list[tuple[str, object]] = []

    def fake_persist_wells(session_state, updated, *, save, reload_data, success_message):
        _ = session_state
        _ = reload_data
        calls.append(("persist", updated.version, success_message))
        save(updated)
        return PersistenceResult(should_rerun=True)

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.persist_wells",
        fake_persist_wells,
    )

    coordinator.save_wells(
        wells,
        graph=graph,
        expected_version=wells.version,
        success_message="saved",
    )

    assert calls == []
    assert not any(call[0] == "save_wells" for call in gateway.calls)
    assert st_module.reruns == 0
    assert st_module.messages == [
        (
            "error",
            "Изменение скважин доступно только в текущей схеме. "
            "Переключитесь на текущую схему.",
        )
    ]


def test_session_coordinator_blocks_position_save_for_archived_schema_version(
    monkeypatch,
    documents,
) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"
    calls: list[tuple[str, object]] = []

    def fake_persist_graph_positions(
        session_state,
        *,
        save,
        reload_data,
        reset_position_edit_state,
        success_message,
    ):
        _ = session_state
        _ = reload_data
        calls.append(("persist", success_message))
        save()
        reset_position_edit_state()
        return PersistenceResult(should_rerun=True, error_message=None)

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.persist_graph_positions",
        fake_persist_graph_positions,
    )

    coordinator.save_graph_positions(
        graph,
        {"proc_initial_review": (5.0, 6.0)},
    )

    assert calls == []
    assert not any(call[0] == "save_graph_positions" for call in gateway.calls)
    assert st_module.reruns == 0
    assert st_module.messages == [
        (
            "error",
            "Версии схемы доступны только для просмотра. "
            "Переключитесь на текущую схему.",
        )
    ]


def test_session_coordinator_allows_position_save_for_newest_archive_without_live(
    monkeypatch,
    documents,
) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, live_exists=False)
    gateway.versions = [
        GraphVersionInfo(
            id="flow_source.v0002.yaml",
            label="v0002",
            path=Path("/tmp/flow_source.v0002.yaml"),
            is_versioned=True,
        ),
        GraphVersionInfo(
            id="flow_source.v0001.yaml",
            label="v0001",
            path=Path("/tmp/flow_source.v0001.yaml"),
            is_versioned=True,
        ),
    ]
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0002.yaml"
    calls: list[tuple[str, object]] = []

    def fake_persist_graph_positions(
        session_state,
        *,
        save,
        reload_data,
        reset_position_edit_state,
        success_message,
    ):
        _ = session_state
        _ = reload_data
        calls.append(("persist", success_message))
        save()
        reset_position_edit_state()
        return PersistenceResult(should_rerun=True, error_message=None)

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.persist_graph_positions",
        fake_persist_graph_positions,
    )

    coordinator.save_graph_positions(
        graph,
        {"proc_initial_review": (5.0, 6.0)},
    )

    assert ("persist", "Расположение карточек сохранено") in calls
    assert (
        "save_graph_positions",
        {"proc_initial_review": (5.0, 6.0)},
        graph.version,
        "flow_source.v0002.yaml",
    ) in gateway.calls
    assert st_module.reruns == 1


def test_session_coordinator_blocks_position_save_for_older_archive_without_live(
    monkeypatch,
    documents,
) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, live_exists=False)
    gateway.versions = [
        GraphVersionInfo(
            id="flow_source.v0002.yaml",
            label="v0002",
            path=Path("/tmp/flow_source.v0002.yaml"),
            is_versioned=True,
        ),
        GraphVersionInfo(
            id="flow_source.v0001.yaml",
            label="v0001",
            path=Path("/tmp/flow_source.v0001.yaml"),
            is_versioned=True,
        ),
    ]
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"

    coordinator.save_graph_positions(
        graph,
        {"proc_initial_review": (5.0, 6.0)},
    )

    assert not any(call[0] == "save_graph_positions" for call in gateway.calls)
    assert st_module.messages == [
        (
            "error",
            "Версии схемы доступны только для просмотра. "
            "Переключитесь на текущую схему.",
        )
    ]


def test_session_coordinator_save_graph_positions_runs_storage_workflow(
    monkeypatch,
    documents,
) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    calls: list[tuple[str, object]] = []

    def fake_persist_graph_positions(
        session_state,
        *,
        save,
        reload_data,
        reset_position_edit_state,
        success_message,
    ):
        _ = session_state
        _ = reload_data
        calls.append(("persist", success_message))
        save()
        reset_position_edit_state()
        return PersistenceResult(should_rerun=False, error_message="cannot-save")

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.persist_graph_positions",
        fake_persist_graph_positions,
    )
    st_module.session_state["position_edit_signature"] = ("sig",)
    st_module.session_state["position_edit_positions"] = {"proc_initial_review": (1.0, 2.0)}

    coordinator.save_graph_positions(
        graph,
        {"proc_initial_review": (5.0, 6.0)},
    )

    assert ("persist", "Расположение карточек сохранено") in calls
    assert gateway.calls == [
        (
            "save_graph_positions",
            {"proc_initial_review": (5.0, 6.0)},
            graph.version,
            None,
        ),
    ]
    assert "position_edit_signature" not in st_module.session_state
    assert st_module.messages == [("error", "cannot-save")]

def test_session_coordinator_switches_selected_graph_version(monkeypatch, documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[tuple[bool, str | None]] = []

    def fake_load(session_state, loader, *, force: bool = False):
        loaded_graph, loaded_wells = loader()
        load_calls.append((force, session_state.get("selected_graph_version_id")))
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )

    coordinator.select_graph_version("flow_source.v0001.yaml")

    assert load_calls == [(True, "flow_source.v0001.yaml")]
    assert gateway.calls == [
        ("list_graph_versions",),
        ("load_documents", "flow_source.v0001.yaml"),
    ]
    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0001.yaml"
    assert st_module.session_state["loaded_graph_version_id"] == "flow_source.v0001.yaml"
    assert st_module.reruns == 1


def test_session_coordinator_restores_previous_selection_when_version_switch_fails(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    def fail_load(graph_version_id: str | None = None):
        gateway.calls.append(("load_documents", graph_version_id))
        raise ValueError("invalid version payload")

    monkeypatch.setattr(gateway, "load_documents", fail_load)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0000.yaml"

    coordinator.select_graph_version("flow_source.v0001.yaml")

    assert gateway.calls == [
        ("list_graph_versions",),
        ("load_documents", "flow_source.v0001.yaml"),
    ]
    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0000.yaml"
    assert "loaded_graph_version_id" not in st_module.session_state
    assert st_module.messages == [
        ("error", "Не удалось переключить версию схемы: invalid version payload"),
    ]
    assert st_module.reruns == 0


def test_session_coordinator_materializes_and_selects_new_graph_version(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[bool] = []

    def fake_load(session_state, loader, *, force: bool = False):
        _ = session_state
        loaded_graph, loaded_wells = loader()
        load_calls.append(force)
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )

    coordinator.materialize_graph_version()

    assert load_calls == [True]
    assert gateway.calls == [
        ("materialize_graph_version", "flow_source.v0002.yaml"),
        ("list_graph_versions",),
        ("load_documents", "flow_source.v0002.yaml"),
    ]
    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0002.yaml"
    assert st_module.session_state["loaded_graph_version_id"] == "flow_source.v0002.yaml"
    assert st_module.session_state["flash"] == {
        "message": "Создана версия схемы: flow_source.v0002.yaml",
        "level": "success",
    }
    assert st_module.reruns == 1


def test_session_coordinator_imports_live_source_from_raw_and_switches_to_live(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[tuple[bool, str | None]] = []

    def fake_load(session_state, loader, *, force: bool = False):
        loaded_graph, loaded_wells = loader()
        load_calls.append((force, session_state.get("selected_graph_version_id")))
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"

    coordinator.import_live_graph_source_from_raw()

    assert load_calls == [(True, None)]
    assert gateway.calls == [
        ("import_live_graph_source_from_raw", "flow_source.v0002.yaml"),
        ("list_graph_versions",),
        ("live_graph_source_exists", True),
        ("load_documents", None),
    ]
    assert "selected_graph_version_id" not in st_module.session_state
    assert st_module.session_state["loaded_graph_version_id"] is None
    assert st_module.session_state["flash"] == {
        "message": (
            "Фактические данные импортированы в текущую схему. "
            "Предыдущая версия сохранена как flow_source.v0002.yaml"
        ),
        "level": "success",
    }
    assert st_module.reruns == 1


def test_session_coordinator_import_reports_error_and_restores_selection(documents) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    def fail_import():
        raise ValueError("broken raw payload")

    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"
    gateway.import_live_graph_source_from_raw = fail_import

    coordinator.import_live_graph_source_from_raw()

    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0001.yaml"
    assert st_module.messages == [
        ("error", "Не удалось импортировать фактические данные: broken raw payload"),
    ]
    assert st_module.reruns == 0


def test_session_coordinator_restores_previous_selection_when_materialized_version_load_fails(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    def fail_load(graph_version_id: str | None = None):
        gateway.calls.append(("load_documents", graph_version_id))
        raise ValueError("materialized version is invalid")

    monkeypatch.setattr(gateway, "load_documents", fail_load)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"

    coordinator.materialize_graph_version()

    assert gateway.calls == [
        ("materialize_graph_version", "flow_source.v0002.yaml"),
        ("list_graph_versions",),
        ("load_documents", "flow_source.v0002.yaml"),
    ]
    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0001.yaml"
    assert "loaded_graph_version_id" not in st_module.session_state
    assert st_module.messages == [
        (
            "error",
            "Не удалось создать версию схемы: materialized version is invalid",
        ),
    ]
    assert st_module.reruns == 0


def test_session_coordinator_falls_back_to_live_when_selected_graph_version_disappears(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells)
    gateway.versions = []
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[tuple[bool, str | None]] = []

    def fake_load(session_state, loader, *, force: bool = False):
        loaded_graph, loaded_wells = loader()
        load_calls.append((force, session_state.get("selected_graph_version_id")))
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )
    st_module.session_state["selected_graph_version_id"] = "flow_source.v9999.yaml"

    assert coordinator.load_app_data() == (graph, wells)

    assert gateway.calls == [
        ("list_graph_versions",),
        ("live_graph_source_exists", True),
        ("load_documents", None),
    ]
    assert load_calls == [(False, None)]
    assert "selected_graph_version_id" not in st_module.session_state
    assert st_module.session_state["loaded_graph_version_id"] is None


def test_session_coordinator_auto_selects_newest_archive_when_live_missing(
    monkeypatch,
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph, wells=wells, live_exists=False)
    # Ascending order on purpose: selection must use sequence, not list[0].
    gateway.versions = [
        GraphVersionInfo(
            id="flow_source.v0001.yaml",
            label="v0001",
            path=Path("/tmp/flow_source.v0001.yaml"),
            is_versioned=True,
        ),
        GraphVersionInfo(
            id="flow_source.v0003.yaml",
            label="v0003",
            path=Path("/tmp/flow_source.v0003.yaml"),
            is_versioned=True,
        ),
    ]
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    load_calls: list[tuple[bool, str | None]] = []

    def fake_load(session_state, loader, *, force: bool = False):
        loaded_graph, loaded_wells = loader()
        load_calls.append((force, session_state.get("selected_graph_version_id")))
        return type("Documents", (), {"graph": loaded_graph, "wells": loaded_wells})()

    monkeypatch.setattr(
        "pydiag.presentation.runtime_session.load_session_documents",
        fake_load,
    )

    assert coordinator.load_app_data() == (graph, wells)
    assert st_module.session_state["selected_graph_version_id"] == "flow_source.v0003.yaml"
    assert load_calls == [(True, "flow_source.v0003.yaml")]
    assert ("load_documents", "flow_source.v0003.yaml") in gateway.calls
