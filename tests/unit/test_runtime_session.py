from __future__ import annotations

from pathlib import Path

from pydiag.application.session_state import PersistenceResult
from pydiag.common.graph_versions import GraphVersionInfo
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator


class FakeDocumentsGateway:
    def __init__(self, *, graph=None, wells=None):
        self.graph = graph
        self.wells = wells
        self.calls: list[tuple[object, ...]] = []
        self.versions = [
            GraphVersionInfo(
                id="flow_source.v0001.yaml",
                label="flow_source.v0001.yaml",
                path=Path("/tmp/flow_source.v0001.yaml"),
                is_versioned=True,
            )
        ]

    def load_documents(self, graph_version_id: str | None = None):
        self.calls.append(("load_documents", graph_version_id))
        return self.graph, self.wells

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
        layout_mode: str = "manual",
        graph_version_id: str | None = None,
    ):
        self.calls.append(
            (
                "save_graph_positions",
                positions,
                expected_version,
                layout_mode,
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
        ("ensure_live_graph_source", Path("/tmp/flow_source.yaml")),
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

    def fail_bootstrap():
        raise FileNotFoundError("Graph source not found")

    monkeypatch.setattr(gateway, "ensure_live_graph_source", fail_bootstrap)

    coordinator.reload_data()

    assert gateway.calls == []
    assert st_module.messages == [
        ("error", "Не удалось перечитать данные: Graph source not found"),
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
        ("ensure_live_graph_source", Path("/tmp/flow_source.yaml")),
        ("load_documents", None),
    ]
    assert st_module.messages == [
        ("error", "Не удалось перечитать данные: broken source"),
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


def test_session_coordinator_exposes_materialization_capability() -> None:
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway()
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    assert coordinator.can_materialize_graph_version() is True
    assert gateway.calls == [("can_materialize_graph_version",)]


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


def test_session_coordinator_rejects_wells_update_for_archived_source_version(
    documents,
) -> None:
    graph, wells = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway()
    coordinator = StreamlitSessionCoordinator(st_module, gateway)
    st_module.session_state["selected_graph_version_id"] = "flow_source.v0001.yaml"

    coordinator.save_wells(
        wells,
        graph=graph,
        expected_version=wells.version,
        success_message="saved",
    )

    assert gateway.calls == []
    assert st_module.messages == [
        ("error", "Изменение скважин доступно только для текущего source YAML."),
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
        layout_mode="manual",
    )

    assert ("persist", "Расположение карточек сохранено") in calls
    assert gateway.calls == [
        (
            "save_graph_positions",
            {"proc_initial_review": (5.0, 6.0)},
            graph.version,
            "manual",
            None,
        ),
    ]
    assert "position_edit_signature" not in st_module.session_state
    assert st_module.messages == [("error", "cannot-save")]


def test_session_coordinator_rejects_saving_drag_positions_for_snake_layout(documents) -> None:
    graph, _ = documents
    st_module = FakeStreamlitModule()
    gateway = FakeDocumentsGateway(graph=graph)
    coordinator = StreamlitSessionCoordinator(st_module, gateway)

    coordinator.save_graph_positions(
        graph,
        {"proc_initial_review": (5.0, 6.0)},
        layout_mode="snake",
    )

    assert gateway.calls == []
    assert st_module.messages == [
        ("error", "Перетаскивание можно сохранять только для layout source или custom."),
    ]


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
        "message": "Создана новая версия source YAML: flow_source.v0002.yaml",
        "level": "success",
    }
    assert st_module.reruns == 1


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
            "Не удалось сохранить версию source YAML: materialized version is invalid",
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
        ("load_documents", None),
    ]
    assert load_calls == [(False, None)]
    assert "selected_graph_version_id" not in st_module.session_state
    assert st_module.session_state["loaded_graph_version_id"] is None
