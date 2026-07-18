from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from pydiag.application import (
    DocumentsGateway,
    FLOW_SELECTION_RERUN_REQUEST_KEY,
    GraphSourceEdgeDraft,
    GraphSourceNodeDraft,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
    ensure_position_edit_positions,
    pop_flash,
    persist_graph_document_update,
    normalize_position_pair,
    position_edit_positions_from_state,
    reset_position_edit_state,
)
from pydiag.application import (
    flash as store_flash,
)
from pydiag.application import (
    load_app_data as load_session_documents,
)
from pydiag.application import (
    persist_graph_positions_update as persist_graph_positions,
)
from pydiag.application import (
    persist_wells_update as persist_wells,
)
from pydiag.common.graph_versions import GraphVersionInfo, RawImportResult
from pydiag.domain.models import FlowGraphDocument, WellsDocument

SELECTED_GRAPH_VERSION_KEY = "selected_graph_version_id"
LOADED_GRAPH_VERSION_KEY = "loaded_graph_version_id"
POSITION_EDIT_RERUN_REQUEST_KEY = "_position_edit_rerun_requested"


@dataclass(frozen=True)
class StreamlitSessionCoordinator:
    st_module: Any
    documents_gateway: DocumentsGateway

    @property
    def session_state(self) -> MutableMapping[str, Any]:
        return self.st_module.session_state

    def load_app_data(
        self, *, force: bool = False
    ) -> tuple[FlowGraphDocument, WellsDocument]:
        selected_version_id = self.selected_graph_version_id()
        if selected_version_id is not None:
            selected_version_id = self.ensure_selected_graph_version(
                self.documents_gateway.list_graph_versions()
            )
        if self.session_state.get(LOADED_GRAPH_VERSION_KEY) != selected_version_id:
            force = True
        documents = load_session_documents(
            self.session_state,
            lambda: (
                self.documents_gateway.load_documents(selected_version_id)
                if selected_version_id is not None
                else self.documents_gateway.load_documents()
            ),
            force=force,
        )
        self.session_state[LOADED_GRAPH_VERSION_KEY] = selected_version_id
        return documents.graph, documents.wells

    def list_graph_versions(self) -> list[GraphVersionInfo]:
        versions = self.documents_gateway.list_graph_versions()
        self.ensure_selected_graph_version(versions)
        return versions

    def can_materialize_graph_version(self) -> bool:
        return self.documents_gateway.can_materialize_graph_version()

    def can_import_raw_graph_source(self) -> bool:
        return self.documents_gateway.can_import_raw_graph_source()

    def selected_graph_version_id(self) -> str | None:
        value = self.session_state.get(SELECTED_GRAPH_VERSION_KEY)
        return value if isinstance(value, str) and value else None

    def ensure_selected_graph_version(
        self,
        versions: list[GraphVersionInfo],
    ) -> str | None:
        selected = self.selected_graph_version_id()
        valid_ids = {version.id for version in versions}
        if selected is None or selected in valid_ids:
            return selected
        self.session_state.pop(SELECTED_GRAPH_VERSION_KEY, None)
        return None

    def select_graph_version(self, version_id: str | None) -> None:
        previous_version_id = self.selected_graph_version_id()
        if version_id == previous_version_id:
            return
        self._set_selected_graph_version(version_id)
        try:
            self.load_app_data(force=True)
        except Exception as exc:
            self._set_selected_graph_version(previous_version_id)
            self.st_module.error(f"Не удалось переключить версию схемы: {exc}")
            return
        self.flash("Версия схемы переключена")
        self.st_module.rerun()

    def materialize_graph_version(self) -> None:
        previous_version_id = self.selected_graph_version_id()
        try:
            version = self.documents_gateway.materialize_graph_version()
            self._set_selected_graph_version(version.id)
            self.load_app_data(force=True)
        except Exception as exc:
            self._set_selected_graph_version(previous_version_id)
            self.st_module.error(f"Не удалось создать версию схемы: {exc}")
            return
        self.flash(f"Создана версия схемы: {version.label}")
        self.st_module.rerun()

    def import_live_graph_source_from_raw(self) -> None:
        previous_version_id = self.selected_graph_version_id()
        try:
            result = self.documents_gateway.import_live_graph_source_from_raw()
            self._set_selected_graph_version(None)
            self.load_app_data(force=True)
        except Exception as exc:
            self._set_selected_graph_version(previous_version_id)
            self.st_module.error(f"Не удалось импортировать фактические данные: {exc}")
            return
        self.flash(self._raw_import_success_message(result))
        self.st_module.rerun()

    def flash(self, message: str, level: str = "success") -> None:
        store_flash(self.session_state, message, level)

    def render_flash(self) -> None:
        data = pop_flash(self.session_state)
        if data is None:
            return
        if data.level == "error":
            self.st_module.error(data.message)
        elif data.level == "warning":
            self.st_module.warning(data.message)
        else:
            self.st_module.success(data.message)

    def reload_data(self) -> None:
        try:
            self.load_app_data(force=True)
        except Exception as exc:
            self.st_module.error(f"Не удалось обновить данные: {exc}")
            return
        self.flash("Данные обновлены")
        self.st_module.rerun()

    def reset_position_draft(self) -> None:
        reset_position_edit_state(self.session_state)
        self.flash("Черновик расположения сброшен")
        self.st_module.rerun()

    def has_position_edit_positions(self) -> bool:
        return bool(self.session_state.get("position_edit_positions"))

    def position_edit_positions(
        self,
        graph: FlowGraphDocument,
    ) -> dict[str, tuple[float, float]]:
        return position_edit_positions_from_state(self.session_state, graph)

    def ensure_position_edit_draft(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        layout_mode: str,
    ) -> dict[str, tuple[float, float]]:
        return ensure_position_edit_positions(
            self.session_state,
            graph,
            wells,
            layout_mode,
        )

    def update_position_edit_draft(
        self,
        graph: FlowGraphDocument,
        *,
        node_id: str,
        x: float,
        y: float,
    ) -> dict[str, tuple[float, float]]:
        positions = dict(position_edit_positions_from_state(self.session_state, graph))
        positions[node_id] = normalize_position_pair((x, y))
        self.session_state["position_edit_positions"] = positions
        self.session_state["position_edit_dirty"] = True
        self.session_state[POSITION_EDIT_RERUN_REQUEST_KEY] = True
        return positions

    def consume_position_edit_rerun_request(self) -> bool:
        return bool(self.session_state.pop(POSITION_EDIT_RERUN_REQUEST_KEY, False))

    def consume_flow_selection_rerun_request(self) -> bool:
        return bool(self.session_state.pop(FLOW_SELECTION_RERUN_REQUEST_KEY, False))

    def save_wells(
        self,
        updated: WellsDocument,
        *,
        graph: FlowGraphDocument,
        expected_version: int,
        success_message: str,
    ) -> None:
        if not self.wells_edit_available():
            self.st_module.error(
                self.wells_edit_block_reason()
                or "Изменение скважин сейчас недоступно."
            )
            return

        result = persist_wells(
            self.session_state,
            updated,
            save=lambda document: self.documents_gateway.save_wells(
                document,
                graph=graph,
                expected_version=expected_version,
            ),
            reload_data=self.load_app_data,
            success_message=success_message,
        )
        self.finalize_persistence(result.should_rerun, result.error_message)

    def save_graph_positions(
        self,
        graph: FlowGraphDocument,
        positions: dict[str, tuple[float, float]],
    ) -> None:
        selected_version_id = self.selected_graph_version_id()
        if selected_version_id is not None:
            self.st_module.error(
                "Версии source YAML доступны только для просмотра. Переключитесь на текущий source YAML."
            )
            return

        def save() -> FlowGraphDocument:
            return self.documents_gateway.save_graph_positions(
                positions,
                expected_version=graph.version,
            )

        result = persist_graph_positions(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            reset_position_edit_state=lambda: reset_position_edit_state(
                self.session_state
            ),
            success_message="Расположение карточек сохранено",
        )
        self.finalize_persistence(result.should_rerun, result.error_message)

    def load_graph_source_node(self, node_id: str) -> GraphSourceNodeDraft:
        return self.documents_gateway.load_graph_source_node(
            node_id,
            graph_version_id=self.selected_graph_version_id(),
        )

    def load_graph_source_edge(self, edge_id: str) -> GraphSourceEdgeDraft:
        return self.documents_gateway.load_graph_source_edge(
            edge_id,
            graph_version_id=self.selected_graph_version_id(),
        )

    def save_graph_source_node(
        self,
        graph: FlowGraphDocument,
        command: UpdateGraphSourceNodeCommand,
    ) -> None:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование source YAML сейчас недоступно."
            )
            return

        result = persist_graph_document_update(
            self.session_state,
            save=lambda: self.documents_gateway.save_graph_source_node(
                command,
                expected_version=graph.version,
            ),
            reload_data=self.load_app_data,
            success_message=(
                "Карточка схемы удалена"
                if command.deleted is True
                else "Карточка схемы обновлена"
            ),
        )
        self.finalize_persistence(result.should_rerun, result.error_message)

    def save_graph_source_edge(
        self,
        graph: FlowGraphDocument,
        command: UpdateGraphSourceEdgeCommand,
    ) -> None:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование source YAML сейчас недоступно."
            )
            return

        result = persist_graph_document_update(
            self.session_state,
            save=lambda: self.documents_gateway.save_graph_source_edge(
                command,
                expected_version=graph.version,
            ),
            reload_data=self.load_app_data,
            success_message="Связь схемы обновлена",
        )
        self.finalize_persistence(result.should_rerun, result.error_message)

    def position_edit_available(self) -> bool:
        return self.selected_graph_version_id() is None

    def position_edit_block_reason(self) -> str | None:
        if self.position_edit_available():
            return None
        return "Редактирование layout доступно только для текущего source YAML."

    def wells_edit_available(self) -> bool:
        return self.selected_graph_version_id() is None

    def wells_edit_block_reason(self) -> str | None:
        if self.wells_edit_available():
            return None
        return "Изменение скважин доступно только для текущего source YAML."

    def graph_source_edit_available(self) -> bool:
        return self.selected_graph_version_id() is None

    def graph_source_edit_block_reason(self) -> str | None:
        if self.graph_source_edit_available():
            return None
        return "Редактирование карточек и связей доступно только для текущего source YAML."

    def finalize_persistence(
        self, should_rerun: bool, error_message: str | None
    ) -> None:
        if error_message is not None:
            self.st_module.error(error_message)
            return
        if should_rerun:
            self.st_module.rerun()

    def _set_selected_graph_version(self, version_id: str | None) -> None:
        if version_id is None:
            self.session_state.pop(SELECTED_GRAPH_VERSION_KEY, None)
            return
        self.session_state[SELECTED_GRAPH_VERSION_KEY] = version_id

    def _raw_import_success_message(self, result: RawImportResult) -> str:
        if not result.changed:
            return "Фактические данные уже совпадают с текущей схемой"
        if result.backup_version is None:
            return "Фактические данные импортированы в текущую схему"
        return (
            "Фактические данные импортированы в текущую схему. "
            f"Предыдущая версия сохранена как {result.backup_version.label}"
        )
