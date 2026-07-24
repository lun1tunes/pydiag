from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from pydiag.application import (
    CreateGraphSourceEdgeCommand,
    CreateGraphSourceNodeCommand,
    CreateGraphSourceProcessCommand,
    DeleteGraphSourceProcessCommand,
    DocumentsGateway,
    FLOW_SELECTION_RERUN_REQUEST_KEY,
    GraphSourceEdgeDraft,
    GraphSourceNodeDraft,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
    UpdateGraphSourceProcessCommand,
    ensure_position_edit_positions,
    pop_flash,
    persist_graph_document_update,
    normalize_position_pair,
    position_edit_positions_from_state,
    reset_position_edit_state,
)
from pydiag.application.edit_history import (
    can_redo,
    can_undo,
    pop_redo,
    pop_undo,
    push_batch_command,
    push_create_edge_command,
    push_create_node_command,
    push_create_process_command,
    push_delete_edge_command,
    push_delete_node_command,
    push_delete_process_command,
    push_move_nodes_command,
    push_onto_undo_from_redo,
    push_onto_undo_keep_redo,
    push_update_edge_command,
    push_update_node_command,
    push_update_process_command,
)
from pydiag.application.flow_position_edit import graph_node_positions
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
from pydiag.common.graph_versions import (
    GraphVersionInfo,
    RawImportResult,
    newest_graph_version,
)
from pydiag.domain.models import FlowGraphDocument, WellsDocument

SELECTED_GRAPH_VERSION_KEY = "selected_graph_version_id"
LOADED_GRAPH_VERSION_KEY = "loaded_graph_version_id"
POSITION_EDIT_RERUN_REQUEST_KEY = "_position_edit_rerun_requested"
POSITION_AUTOSAVE_SIG_KEY = "_flow_position_autosave_sig"


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

    def live_graph_source_exists(self) -> bool:
        return self.documents_gateway.live_graph_source_exists()

    def ensure_selected_graph_version(
        self,
        versions: list[GraphVersionInfo],
    ) -> str | None:
        selected = self.selected_graph_version_id()
        valid_ids = {version.id for version in versions}
        if selected is not None and selected not in valid_ids:
            self.session_state.pop(SELECTED_GRAPH_VERSION_KEY, None)
            selected = None
        # Without a live schema, bind to the newest archive so the app still loads.
        if selected is None and not self.live_graph_source_exists() and versions:
            newest_id = newest_graph_version(versions).id
            self._set_selected_graph_version(newest_id)
            return newest_id
        return selected

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
        quiet: bool = False,
        rerun: bool = True,
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
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )

    def save_graph_positions(
        self,
        graph: FlowGraphDocument,
        positions: dict[str, tuple[float, float]],
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> bool:
        if not self.position_edit_available():
            self.st_module.error(
                self.position_edit_block_reason()
                or "Редактирование расположения сейчас недоступно."
            )
            return False

        before = graph_node_positions(graph)
        sig = _positions_signature(positions)
        if self.session_state.get(POSITION_AUTOSAVE_SIG_KEY) == sig:
            return False

        def save() -> FlowGraphDocument:
            return self.documents_gateway.save_graph_positions(
                positions,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )

        result = persist_graph_positions(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            reset_position_edit_state=lambda: reset_position_edit_state(
                self.session_state
            ),
            success_message=None if quiet else "Расположение карточек сохранено",
        )
        if result.saved:
            self.session_state[POSITION_AUTOSAVE_SIG_KEY] = sig
            if record_history:
                push_move_nodes_command(
                    self.session_state,
                    before=before,
                    after=positions,
                )
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return result.saved

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
        *,
        quiet: bool = False,
        record_history: bool = False,
        before_snapshot: dict[str, Any] | None = None,
        rerun: bool = True,
    ) -> bool:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return False

        process_side_effects: list[dict[str, Any]] = []
        if command.deleted is True:
            process_side_effects = process_claim_side_effect_commands(
                graph,
                claimed_node_ids={command.node_id},
            )
        result = persist_graph_document_update(
            self.session_state,
            save=lambda: self.documents_gateway.save_graph_source_node(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            ),
            reload_data=self.load_app_data,
            success_message=(
                None
                if quiet
                else (
                    "Карточка схемы удалена"
                    if command.deleted is True
                    else "Карточка схемы обновлена"
                )
            ),
        )
        if record_history and result.saved and before_snapshot is not None:
            if command.deleted is True:
                delete_step = {
                    "kind": "delete_node",
                    "node_id": command.node_id,
                    "before": before_snapshot,
                }
                if process_side_effects:
                    push_batch_command(
                        self.session_state,
                        commands=[*process_side_effects, delete_step],
                    )
                else:
                    push_delete_node_command(
                        self.session_state,
                        node_id=command.node_id,
                        before=before_snapshot,
                    )
            else:
                push_update_node_command(
                    self.session_state,
                    node_id=command.node_id,
                    before=before_snapshot,
                    after=node_snapshot_from_command(command),
                )
        if command.deleted is True and self.session_state.get("selected_id") == command.node_id:
            self.session_state.pop("selected_id", None)
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return result.saved

    def apply_canvas_node_edit(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        patch: dict[str, Any],
        *,
        quiet: bool = True,
        record_history: bool = True,
        rerun: bool = True,
    ) -> bool:
        from pydiag.presentation.admin_models import (
            graph_source_node_delete_block_reason,
            normalized_optional_text,
            validate_graph_source_node_form,
        )

        node_id = patch.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            return False
        try:
            draft = self.load_graph_source_node(node_id)
        except Exception as exc:
            self.st_module.error(str(exc))
            return False

        before = node_snapshot_from_draft(draft)
        if patch.get("deleted") is True:
            block = graph_source_node_delete_block_reason(node_id, wells)
            if block is not None:
                self.st_module.error(block)
                return False
            return self.save_graph_source_node(
                graph,
                UpdateGraphSourceNodeCommand(
                    node_id=draft.node_id,
                    title=draft.title,
                    kind=draft.kind,
                    layout_x=draft.layout_x,
                    layout_y=draft.layout_y,
                    layout_w=draft.layout_w,
                    layout_h=draft.layout_h,
                    responsible=draft.responsible,
                    participants=draft.participants,
                    approvers=draft.approvers,
                    duration=draft.duration,
                    note=draft.note,
                    duration_context=draft.duration_context,
                    deleted=True,
                ),
                quiet=quiet,
                record_history=record_history,
                before_snapshot=before,
                rerun=rerun,
            )

        title = patch["title"] if "title" in patch else draft.title
        kind = patch["kind"] if "kind" in patch else draft.kind
        responsible = patch["responsible"] if "responsible" in patch else draft.responsible
        participants = (
            tuple(patch["participants"])
            if "participants" in patch
            else draft.participants
        )
        approvers = (
            tuple(patch["approvers"]) if "approvers" in patch else draft.approvers
        )
        if "duration" in patch:
            duration = normalized_optional_text(str(patch["duration"] or ""))
        else:
            duration = draft.duration
        if "duration_context" in patch:
            duration_context = normalized_optional_text(
                str(patch["duration_context"] or "")
            )
        else:
            duration_context = draft.duration_context
        if "note" in patch:
            note = normalized_optional_text(str(patch["note"] or ""))
        else:
            note = draft.note

        if not isinstance(title, str):
            return False
        if kind not in {
            "process",
            "decision_diamond",
            "database",
            "input_data",
            "event",
        }:
            return False

        # Responsible wins; participants win over approvers (same as canvas UI).
        participants = tuple(
            item for item in participants if item and item != responsible
        )
        approvers = tuple(
            item
            for item in approvers
            if item and item != responsible and item not in participants
        )

        error_message = validate_graph_source_node_form(
            title=title,
            kind=kind,
            responsible=responsible,
            participants=list(participants),
            approvers=list(approvers),
        )
        if error_message is not None:
            self.st_module.error(error_message)
            return False

        if duration is not None:
            try:
                from pydiag.domain.models import parse_node_time

                parse_node_time(duration)
            except ValueError as exc:
                self.st_module.error(str(exc))
                return False

        return self.save_graph_source_node(
            graph,
            UpdateGraphSourceNodeCommand(
                node_id=draft.node_id,
                title=title.strip(),
                kind=kind,  # type: ignore[arg-type]
                layout_x=draft.layout_x,
                layout_y=draft.layout_y,
                layout_w=draft.layout_w,
                layout_h=draft.layout_h,
                responsible=responsible,
                participants=tuple(participants),
                approvers=tuple(approvers),
                duration=duration,
                note=note,
                duration_context=duration_context,
                deleted=None,
            ),
            quiet=quiet,
            record_history=record_history,
            before_snapshot=before,
            rerun=rerun,
        )

    def save_graph_source_edge(
        self,
        graph: FlowGraphDocument,
        command: UpdateGraphSourceEdgeCommand,
        *,
        quiet: bool = False,
        record_history: bool = False,
        before_snapshot: dict[str, Any] | None = None,
        rerun: bool = True,
    ) -> bool:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return False

        result = persist_graph_document_update(
            self.session_state,
            save=lambda: self.documents_gateway.save_graph_source_edge(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            ),
            reload_data=self.load_app_data,
            success_message=(
                None
                if quiet
                else (
                    "Связь схемы удалена"
                    if command.deleted is True
                    else "Связь схемы обновлена"
                )
            ),
        )
        if record_history and result.saved and before_snapshot is not None:
            if command.deleted is True:
                push_delete_edge_command(
                    self.session_state,
                    edge_id=command.edge_id,
                    before=before_snapshot,
                )
            else:
                push_update_edge_command(
                    self.session_state,
                    edge_id=command.edge_id,
                    before=before_snapshot,
                    after=edge_snapshot_from_command(command),
                )
        if command.deleted is True and self.session_state.get("selected_id") == command.edge_id:
            self.session_state.pop("selected_id", None)
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return result.saved

    def create_graph_source_edge(
        self,
        graph: FlowGraphDocument,
        command: CreateGraphSourceEdgeCommand,
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> str | None:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return None

        before_ids = {edge.id for edge in graph.edges}
        created_edge_id: str | None = None

        def save() -> FlowGraphDocument:
            nonlocal created_edge_id
            updated = self.documents_gateway.create_graph_source_edge(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )
            new_ids = {edge.id for edge in updated.edges} - before_ids
            if command.edge_id and command.edge_id in {edge.id for edge in updated.edges}:
                created_edge_id = command.edge_id
            elif len(new_ids) == 1:
                created_edge_id = next(iter(new_ids))
            elif new_ids:
                # Prefer an edge matching source/target.
                for edge in updated.edges:
                    if edge.id in new_ids and edge.source == command.source and edge.target == command.target:
                        created_edge_id = edge.id
                        break
                if created_edge_id is None:
                    created_edge_id = sorted(new_ids)[0]
            return updated

        result = persist_graph_document_update(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            success_message=None if quiet else "Связь схемы создана",
        )
        if result.saved and record_history and created_edge_id:
            push_create_edge_command(
                self.session_state,
                edge_id=created_edge_id,
                source=command.source,
                target=command.target,
                kind=command.kind,
                label=command.label,
                condition=command.condition,
                note=command.note,
            )
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return created_edge_id if result.saved else None

    def create_graph_source_node(
        self,
        graph: FlowGraphDocument,
        command: CreateGraphSourceNodeCommand,
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> str | None:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return None

        before_ids = {node.id for node in graph.nodes}
        created_node_id: str | None = None

        def save() -> FlowGraphDocument:
            nonlocal created_node_id
            updated = self.documents_gateway.create_graph_source_node(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )
            new_ids = {node.id for node in updated.nodes} - before_ids
            if command.node_id and command.node_id in {node.id for node in updated.nodes}:
                created_node_id = command.node_id
            elif len(new_ids) == 1:
                created_node_id = next(iter(new_ids))
            elif new_ids:
                title = command.title.strip()
                for node in updated.nodes:
                    if node.id in new_ids and node.title == title:
                        created_node_id = node.id
                        break
                if created_node_id is None:
                    created_node_id = sorted(new_ids)[0]
            return updated

        result = persist_graph_document_update(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            success_message=None if quiet else "Карточка схемы создана",
        )
        if result.saved and record_history and created_node_id:
            push_create_node_command(
                self.session_state,
                node_id=created_node_id,
                after=node_snapshot_from_create_command(command),
            )
            self.session_state["selected_id"] = created_node_id
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return created_node_id if result.saved else None

    def create_graph_source_process(
        self,
        graph: FlowGraphDocument,
        command: CreateGraphSourceProcessCommand,
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> str | None:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return None

        before_ids = set(graph.processes)
        created_process_id: str | None = None

        def save() -> FlowGraphDocument:
            return self.documents_gateway.create_graph_source_process(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )

        result = persist_graph_document_update(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            success_message=None if quiet else "Процесс создан",
        )
        claimed = {str(node_id) for node_id in command.node_ids}
        side_effects = process_claim_side_effect_commands(
            graph,
            claimed_node_ids=claimed,
        )
        if result.saved:
            updated, _ = self.load_app_data()
            new_ids = set(updated.processes) - before_ids
            if command.process_id and command.process_id in updated.processes:
                created_process_id = command.process_id
            elif len(new_ids) == 1:
                created_process_id = next(iter(new_ids))
            elif new_ids:
                title = command.title.strip()
                for process_id, process in updated.processes.items():
                    if process_id in new_ids and process.title == title:
                        created_process_id = process_id
                        break
                if created_process_id is None:
                    created_process_id = sorted(new_ids)[0]
            if record_history and created_process_id:
                process = updated.processes[created_process_id]
                create_step = {
                    "kind": "create_process",
                    "process_id": created_process_id,
                    "after": process_snapshot(process),
                }
                if side_effects:
                    push_batch_command(
                        self.session_state,
                        commands=[*side_effects, create_step],
                    )
                else:
                    push_create_process_command(
                        self.session_state,
                        process_id=created_process_id,
                        after=create_step["after"],
                    )
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return created_process_id if result.saved else None

    def update_graph_source_process(
        self,
        graph: FlowGraphDocument,
        command: UpdateGraphSourceProcessCommand,
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> bool:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return False
        current = graph.processes.get(command.process_id)
        if current is None:
            self.st_module.error(f"Неизвестный процесс: {command.process_id}")
            return False
        before = process_snapshot(current)

        def save() -> FlowGraphDocument:
            return self.documents_gateway.update_graph_source_process(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )

        result = persist_graph_document_update(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            success_message=None if quiet else "Процесс обновлён",
        )
        side_effects: list[dict[str, Any]] = []
        if command.node_ids is not None:
            side_effects = process_claim_side_effect_commands(
                graph,
                claimed_node_ids={str(node_id) for node_id in command.node_ids},
                exclude_process_id=command.process_id,
            )
        if result.saved and record_history:
            updated, _ = self.load_app_data()
            after_process = updated.processes.get(command.process_id)
            steps = list(side_effects)
            if after_process is None:
                # Membership emptied → process deleted.
                steps.append(
                    {
                        "kind": "delete_process",
                        "process_id": command.process_id,
                        "before": before,
                    }
                )
            else:
                after = process_snapshot(after_process)
                if before != after:
                    steps.append(
                        {
                            "kind": "update_process",
                            "process_id": command.process_id,
                            "before": before,
                            "after": after,
                        }
                    )
            if len(steps) == 1:
                step = steps[0]
                if step["kind"] == "delete_process":
                    push_delete_process_command(
                        self.session_state,
                        process_id=str(step["process_id"]),
                        before=step["before"],
                    )
                elif step["kind"] == "update_process":
                    push_update_process_command(
                        self.session_state,
                        process_id=str(step["process_id"]),
                        before=step["before"],
                        after=step["after"],
                    )
                else:
                    push_batch_command(self.session_state, commands=steps)
            elif steps:
                push_batch_command(self.session_state, commands=steps)
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return result.saved

    def delete_graph_source_process(
        self,
        graph: FlowGraphDocument,
        command: DeleteGraphSourceProcessCommand,
        *,
        quiet: bool = False,
        record_history: bool = True,
        rerun: bool = True,
    ) -> bool:
        if not self.graph_source_edit_available():
            self.st_module.error(
                self.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return False
        current = graph.processes.get(command.process_id)
        if current is None:
            self.st_module.error(f"Неизвестный процесс: {command.process_id}")
            return False
        before = process_snapshot(current)

        def save() -> FlowGraphDocument:
            return self.documents_gateway.delete_graph_source_process(
                command,
                expected_version=graph.version,
                graph_version_id=self.editable_graph_version_id(),
            )

        result = persist_graph_document_update(
            self.session_state,
            save=save,
            reload_data=self.load_app_data,
            success_message=None if quiet else "Процесс удалён",
        )
        if result.saved and record_history:
            push_delete_process_command(
                self.session_state,
                process_id=command.process_id,
                before=before,
            )
        self.finalize_persistence(
            result.should_rerun,
            result.error_message,
            scope="fragment" if quiet else "app",
            rerun=rerun,
        )
        return result.saved

    def can_undo_edit(self) -> bool:
        return can_undo(self.session_state)

    def can_redo_edit(self) -> bool:
        return can_redo(self.session_state)

    def undo_edit(self, graph: FlowGraphDocument, *, rerun: bool = True) -> None:
        command = pop_undo(self.session_state)
        if command is None:
            return
        # Park on redo before persist+rerun so the stack survives RerunException.
        push_onto_undo_keep_redo(self.session_state, command)
        ok = self._apply_history_command(graph, command, reverse=True, rerun=rerun)
        if not ok:
            restored = pop_redo(self.session_state)
            if restored is not None:
                undo_stack = list(self.session_state.get("_flow_edit_undo") or [])
                undo_stack.append(restored)
                self.session_state["_flow_edit_undo"] = undo_stack

    def redo_edit(self, graph: FlowGraphDocument, *, rerun: bool = True) -> None:
        command = pop_redo(self.session_state)
        if command is None:
            return
        push_onto_undo_from_redo(self.session_state, command)
        ok = self._apply_history_command(graph, command, reverse=False, rerun=rerun)
        if not ok:
            restored = pop_undo(self.session_state)
            if restored is not None:
                redo_stack = list(self.session_state.get("_flow_edit_redo") or [])
                redo_stack.append(restored)
                self.session_state["_flow_edit_redo"] = redo_stack

    def _apply_history_command(
        self,
        graph: FlowGraphDocument,
        command: dict[str, Any],
        *,
        reverse: bool,
        rerun: bool = True,
    ) -> bool:
        kind = command.get("kind")
        if kind == "batch":
            steps = command.get("commands")
            if not isinstance(steps, list) or not steps:
                return False
            ordered = list(reversed(steps)) if reverse else list(steps)
            for step in ordered:
                if not isinstance(step, dict):
                    return False
                current_graph, _wells = self.load_app_data()
                if not self._apply_history_command(
                    current_graph,
                    step,
                    reverse=reverse,
                    rerun=False,
                ):
                    return False
            if rerun:
                self.finalize_persistence(True, None, scope="fragment", rerun=True)
            return True
        if kind == "move_nodes":
            payload = command.get("before" if reverse else "after")
            if not isinstance(payload, dict):
                return False
            current = graph_node_positions(graph)
            for node_id, xy in payload.items():
                if not isinstance(xy, list | tuple) or len(xy) != 2:
                    continue
                current[str(node_id)] = (float(xy[0]), float(xy[1]))
            # Clear autosave sig so undo/redo positions always write.
            self.session_state.pop(POSITION_AUTOSAVE_SIG_KEY, None)
            # Neutralize stale FE positions before persist+rerun; otherwise the
            # next fragment run re-autosaves the pre-undo layout and wipes redo.
            from pydiag.application.flow_view import (
                SKIP_POSITION_AUTOSAVE_ONCE_KEY,
                sync_component_positions,
            )

            self.session_state[SKIP_POSITION_AUTOSAVE_ONCE_KEY] = True
            sync_component_positions(self.session_state, current)
            return self.save_graph_positions(
                graph,
                current,
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "create_edge":
            edge_id = command.get("edge_id")
            source = command.get("source")
            target = command.get("target")
            edge_kind = command.get("kind_value", "default")
            if not isinstance(edge_id, str) or not isinstance(source, str) or not isinstance(target, str):
                return False
            if reverse:
                return self.save_graph_source_edge(
                    graph,
                    UpdateGraphSourceEdgeCommand(
                        edge_id=edge_id,
                        source=source,
                        target=target,
                        kind=edge_kind,  # type: ignore[arg-type]
                        label=command.get("label"),
                        condition=command.get("condition"),
                        note=command.get("note"),
                        deleted=True,
                    ),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
            created = self.create_graph_source_edge(
                graph,
                CreateGraphSourceEdgeCommand(
                    source=source,
                    target=target,
                    kind=edge_kind,  # type: ignore[arg-type]
                    label=command.get("label"),
                    condition=command.get("condition"),
                    note=command.get("note"),
                    edge_id=edge_id,
                ),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
            return created is not None
        if kind == "create_node":
            node_id = command.get("node_id")
            after = command.get("after")
            if not isinstance(node_id, str) or not isinstance(after, dict):
                return False
            if reverse:
                return self.save_graph_source_node(
                    graph,
                    update_command_from_node_snapshot(node_id, after, deleted=True),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
            created = self.create_graph_source_node(
                graph,
                create_command_from_node_snapshot(node_id, after),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
            return created is not None
        if kind == "update_node":
            payload = command.get("before" if reverse else "after")
            node_id = command.get("node_id")
            if not isinstance(node_id, str) or not isinstance(payload, dict):
                return False
            return self.save_graph_source_node(
                graph,
                update_command_from_node_snapshot(node_id, payload, deleted=None),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "delete_node":
            node_id = command.get("node_id")
            before = command.get("before")
            if not isinstance(node_id, str) or not isinstance(before, dict):
                return False
            if reverse:
                return self.save_graph_source_node(
                    graph,
                    update_command_from_node_snapshot(node_id, before, deleted=False),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
            return self.save_graph_source_node(
                graph,
                update_command_from_node_snapshot(node_id, before, deleted=True),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "update_edge":
            payload = command.get("before" if reverse else "after")
            edge_id = command.get("edge_id")
            if not isinstance(edge_id, str) or not isinstance(payload, dict):
                return False
            return self.save_graph_source_edge(
                graph,
                update_command_from_edge_snapshot(edge_id, payload, deleted=None),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "delete_edge":
            edge_id = command.get("edge_id")
            before = command.get("before")
            if not isinstance(edge_id, str) or not isinstance(before, dict):
                return False
            if reverse:
                kind_value = before.get("kind") or "default"
                if kind_value not in {"default", "yes", "no", "dashed"}:
                    kind_value = "default"
                created = self.create_graph_source_edge(
                    graph,
                    CreateGraphSourceEdgeCommand(
                        source=str(before.get("source") or ""),
                        target=str(before.get("target") or ""),
                        kind=kind_value,  # type: ignore[arg-type]
                        label=before.get("label"),
                        condition=before.get("condition"),
                        note=before.get("note"),
                        edge_id=edge_id,
                    ),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
                return created is not None
            return self.save_graph_source_edge(
                graph,
                update_command_from_edge_snapshot(edge_id, before, deleted=True),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "create_process":
            process_id = command.get("process_id")
            after = command.get("after")
            if not isinstance(process_id, str) or not isinstance(after, dict):
                return False
            if reverse:
                return self.delete_graph_source_process(
                    graph,
                    DeleteGraphSourceProcessCommand(process_id=process_id),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
            created = self.create_graph_source_process(
                graph,
                create_command_from_process_snapshot(process_id, after),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
            return created is not None
        if kind == "update_process":
            process_id = command.get("process_id")
            payload = command.get("before" if reverse else "after")
            if not isinstance(process_id, str) or not isinstance(payload, dict):
                return False
            return self.update_graph_source_process(
                graph,
                update_command_from_process_snapshot(process_id, payload),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        if kind == "delete_process":
            process_id = command.get("process_id")
            before = command.get("before")
            if not isinstance(process_id, str) or not isinstance(before, dict):
                return False
            if reverse:
                created = self.create_graph_source_process(
                    graph,
                    create_command_from_process_snapshot(process_id, before),
                    quiet=True,
                    record_history=False,
                    rerun=rerun,
                )
                return created is not None
            return self.delete_graph_source_process(
                graph,
                DeleteGraphSourceProcessCommand(process_id=process_id),
                quiet=True,
                record_history=False,
                rerun=rerun,
            )
        return False

    def working_schema_selected(self) -> bool:
        """True for any selectable schema: live «Текущая» or any archived ``v000x``.

        All versions are equally editable; edits write to the selected file.
        """
        return True

    def editable_graph_version_id(self) -> str | None:
        """Version id for writes: None = live/default path; otherwise selected archive."""
        return self.selected_graph_version_id()

    def position_edit_available(self) -> bool:
        return True

    def position_edit_block_reason(self) -> str | None:
        return None

    def wells_edit_available(self) -> bool:
        return True

    def wells_edit_block_reason(self) -> str | None:
        return None

    def graph_source_edit_available(self) -> bool:
        return True

    def graph_source_edit_block_reason(self) -> str | None:
        return None

    def finalize_persistence(
        self,
        should_rerun: bool,
        error_message: str | None,
        *,
        scope: str = "app",
        rerun: bool = True,
    ) -> None:
        if error_message is not None:
            self.st_module.error(error_message)
            return
        if should_rerun and rerun:
            # Canvas quiet edits run inside a fragment: app-scoped rerun remounts
            # the whole page and feels like the view/selection "falls apart".
            # Pre-mount consume paths pass rerun=False and continue rendering in
            # the same fragment tick (avoids jump / white flash on title edits).
            rerun_scope = "fragment" if scope == "fragment" else "app"
            try:
                self.st_module.rerun(scope=rerun_scope)
            except TypeError:
                # Older Streamlit without scope= — stay put for fragment callers.
                if scope == "fragment":
                    return
                self.st_module.rerun()
            except Exception as exc:
                # Streamlit rejects fragment scope outside a fragment rerun
                # (AppTest / first full-script pass). Persist already succeeded;
                # do not escalate to app remount (that wipes the canvas host).
                message = str(exc)
                if scope == "fragment" and "fragment" in message.lower():
                    return
                raise

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


def _positions_signature(positions: dict[str, tuple[float, float]]) -> tuple[tuple[str, float, float], ...]:
    return tuple(
        sorted(
            (node_id, round(float(xy[0]), 2), round(float(xy[1]), 2))
            for node_id, xy in positions.items()
        )
    )


def process_snapshot(process: Any) -> dict[str, Any]:
    return {
        "title": str(getattr(process, "title", "") or ""),
        "node_ids": list(getattr(process, "node_ids", []) or []),
    }


def process_claim_side_effect_commands(
    graph: FlowGraphDocument,
    *,
    claimed_node_ids: set[str],
    exclude_process_id: str | None = None,
) -> list[dict[str, Any]]:
    """History steps for processes that lose members to exclusive claim."""
    if not claimed_node_ids:
        return []
    steps: list[dict[str, Any]] = []
    for process_id, process in graph.processes.items():
        if exclude_process_id is not None and process_id == exclude_process_id:
            continue
        member_ids = list(process.node_ids)
        if not claimed_node_ids.intersection(member_ids):
            continue
        before = process_snapshot(process)
        remaining = [node_id for node_id in member_ids if node_id not in claimed_node_ids]
        if not remaining:
            steps.append(
                {
                    "kind": "delete_process",
                    "process_id": process_id,
                    "before": before,
                }
            )
        else:
            steps.append(
                {
                    "kind": "update_process",
                    "process_id": process_id,
                    "before": before,
                    "after": {
                        "title": before["title"],
                        "node_ids": remaining,
                    },
                }
            )
    return steps


def create_command_from_process_snapshot(
    process_id: str,
    snapshot: dict[str, Any],
) -> CreateGraphSourceProcessCommand:
    node_ids = snapshot.get("node_ids") or []
    return CreateGraphSourceProcessCommand(
        title=str(snapshot.get("title") or "Процесс").strip() or "Процесс",
        node_ids=tuple(str(item) for item in node_ids)
        if isinstance(node_ids, list)
        else (),
        process_id=process_id,
    )


def update_command_from_process_snapshot(
    process_id: str,
    snapshot: dict[str, Any],
) -> UpdateGraphSourceProcessCommand:
    node_ids = snapshot.get("node_ids") or []
    title = str(snapshot.get("title") or "").strip() or "Процесс"
    return UpdateGraphSourceProcessCommand(
        process_id=process_id,
        title=title,
        node_ids=tuple(str(item) for item in node_ids)
        if isinstance(node_ids, list)
        else (),
    )


def node_snapshot_from_draft(draft: GraphSourceNodeDraft) -> dict[str, Any]:
    return {
        "title": draft.title,
        "kind": draft.kind,
        "layout_x": draft.layout_x,
        "layout_y": draft.layout_y,
        "layout_w": draft.layout_w,
        "layout_h": draft.layout_h,
        "responsible": draft.responsible,
        "participants": list(draft.participants),
        "approvers": list(draft.approvers),
        "duration": draft.duration,
        "note": draft.note,
        "duration_context": draft.duration_context,
    }


def node_snapshot_from_command(command: UpdateGraphSourceNodeCommand) -> dict[str, Any]:
    return {
        "title": command.title,
        "kind": command.kind,
        "layout_x": command.layout_x,
        "layout_y": command.layout_y,
        "layout_w": command.layout_w,
        "layout_h": command.layout_h,
        "responsible": command.responsible,
        "participants": list(command.participants),
        "approvers": list(command.approvers),
        "duration": command.duration,
        "note": command.note,
        "duration_context": command.duration_context,
    }


def node_snapshot_from_create_command(command: CreateGraphSourceNodeCommand) -> dict[str, Any]:
    return {
        "title": command.title,
        "kind": command.kind,
        "layout_x": command.layout_x,
        "layout_y": command.layout_y,
        "layout_w": command.layout_w,
        "layout_h": command.layout_h,
        "responsible": command.responsible,
        "participants": list(command.participants),
        "approvers": list(command.approvers),
        "duration": command.duration,
        "note": command.note,
        "duration_context": command.duration_context,
    }


def edge_snapshot_from_draft(draft: GraphSourceEdgeDraft) -> dict[str, Any]:
    return {
        "source": draft.source,
        "target": draft.target,
        "kind": draft.kind,
        "label": draft.label,
        "condition": draft.condition,
        "note": draft.note,
    }


def edge_snapshot_from_command(command: UpdateGraphSourceEdgeCommand) -> dict[str, Any]:
    return {
        "source": command.source,
        "target": command.target,
        "kind": command.kind,
        "label": command.label,
        "condition": command.condition,
        "note": command.note,
    }


def update_command_from_node_snapshot(
    node_id: str,
    snapshot: dict[str, Any],
    *,
    deleted: bool | None,
) -> UpdateGraphSourceNodeCommand:
    participants = snapshot.get("participants") or []
    approvers = snapshot.get("approvers") or []
    return UpdateGraphSourceNodeCommand(
        node_id=node_id,
        title=str(snapshot.get("title") or ""),
        kind=snapshot.get("kind") or "process",  # type: ignore[arg-type]
        layout_x=float(snapshot.get("layout_x") or 0),
        layout_y=float(snapshot.get("layout_y") or 0),
        layout_w=int(snapshot.get("layout_w") or 280),
        layout_h=int(snapshot.get("layout_h") or 72),
        responsible=snapshot.get("responsible"),
        participants=tuple(participants) if isinstance(participants, list) else (),
        approvers=tuple(approvers) if isinstance(approvers, list) else (),
        duration=snapshot.get("duration"),
        note=snapshot.get("note"),
        duration_context=snapshot.get("duration_context"),
        deleted=deleted,
    )


def create_command_from_node_snapshot(
    node_id: str,
    snapshot: dict[str, Any],
) -> CreateGraphSourceNodeCommand:
    participants = snapshot.get("participants") or []
    approvers = snapshot.get("approvers") or []
    kind = snapshot.get("kind") or "process"
    if kind not in {
        "process",
        "decision_diamond",
        "database",
        "input_data",
        "event",
    }:
        kind = "process"
    return CreateGraphSourceNodeCommand(
        node_id=node_id,
        title=str(snapshot.get("title") or "Измени меня"),
        kind=kind,  # type: ignore[arg-type]
        layout_x=float(snapshot.get("layout_x") or 0),
        layout_y=float(snapshot.get("layout_y") or 0),
        layout_w=int(snapshot.get("layout_w") or 280),
        layout_h=int(snapshot.get("layout_h") or 72),
        responsible=snapshot.get("responsible"),
        participants=tuple(participants) if isinstance(participants, list) else (),
        approvers=tuple(approvers) if isinstance(approvers, list) else (),
        duration=snapshot.get("duration"),
        note=snapshot.get("note"),
        duration_context=snapshot.get("duration_context"),
    )


def update_command_from_edge_snapshot(
    edge_id: str,
    snapshot: dict[str, Any],
    *,
    deleted: bool | None,
) -> UpdateGraphSourceEdgeCommand:
    kind = snapshot.get("kind") or "default"
    if kind not in {"default", "yes", "no", "dashed"}:
        kind = "default"
    return UpdateGraphSourceEdgeCommand(
        edge_id=edge_id,
        source=str(snapshot.get("source") or ""),
        target=str(snapshot.get("target") or ""),
        kind=kind,  # type: ignore[arg-type]
        label=snapshot.get("label"),
        condition=snapshot.get("condition"),
        note=snapshot.get("note"),
        deleted=deleted,
    )