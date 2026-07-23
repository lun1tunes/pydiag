from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydiag.application import (
    CreateGraphSourceEdgeCommand,
    CreateGraphSourceNodeCommand,
    FLOW_CANVAS_COMPONENT_KEY,
    DocumentsGateway,
    UpdateGraphSourceEdgeCommand,
    consume_history_action,
    consume_pending_canvas_edge,
    consume_pending_canvas_edge_edit,
    consume_pending_canvas_node_create,
    consume_pending_canvas_node_edit,
    detect_canvas_position_autosave,
)
from pydiag.application import (
    render_flow as render_flow_view,
)
from pydiag.application.edit_history import can_redo, can_undo
from pydiag.application.flow_position_edit import graph_node_positions
from pydiag.application.flow_view import (
    sync_component_positions,
    take_skip_position_autosave_once,
    resolve_inspector_collapsed,
)
from pydiag.common.auth_sessions import AuthSessionStore
from pydiag.domain.models import FlowGraphDocument, FlowNode, WellsDocument
from pydiag.presentation.admin import (
    AdminActions,
    render_admin_panel,
)
from pydiag.presentation.auth import StreamlitAuthContext
from pydiag.presentation.auth_session import DEFAULT_AUTH_SESSION_TTL_SECONDS
from pydiag.presentation.chrome import inject_css, render_legend
from pydiag.presentation.inspector import InspectorActions, render_inspector
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.presentation.selection import resolve_selection
from pydiag.presentation.sidebar import (
    SOURCE_LAYOUT_MODE,
    SidebarActions,
    render_sidebar,
)
from pydiag.rendering.flow_canvas_component import render_flow_canvas

# Streamlit requires a fixed px height; chrome CSS overrides this to
# --pydiag-workspace-height so the panel tracks the viewport on any monitor.
WORKSPACE_PANEL_HEIGHT = 1600
CARD_LAYOUT_SYNC_TOKEN_KEY = "_card_layout_sync_token"


def card_layout_x_key(node_id: str) -> str:
    return f"graph_source_node_layout_x::{node_id}"


def card_layout_y_key(node_id: str) -> str:
    return f"graph_source_node_layout_y::{node_id}"


def _is_layout_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class StreamlitAppRuntime:
    st_module: Any
    documents_gateway: DocumentsGateway
    auth_session_store: AuthSessionStore | None = None
    auth_session_ttl_seconds: int = DEFAULT_AUTH_SESSION_TTL_SECONDS
    render_canvas: Callable[..., object] = render_flow_canvas

    @property
    def session(self) -> StreamlitSessionCoordinator:
        return StreamlitSessionCoordinator(self.st_module, self.documents_gateway)

    def auth_context(self) -> StreamlitAuthContext:
        return StreamlitAuthContext(
            self.st_module,
            session_store=self.auth_session_store,
            session_ttl_seconds=self.auth_session_ttl_seconds,
        )

    def _sync_card_layout_inputs(
        self,
        *,
        node_id: str,
        current_x: float,
        current_y: float,
    ) -> None:
        values = {
            "x": round(float(current_x), 2),
            "y": round(float(current_y), 2),
        }
        x_key = card_layout_x_key(node_id)
        y_key = card_layout_y_key(node_id)
        token = f"{node_id}|{values['x']}|{values['y']}"
        current_x_value = self.st_module.session_state.get(x_key)
        current_y_value = self.st_module.session_state.get(y_key)
        missing_values = not (
            _is_layout_number(current_x_value) and _is_layout_number(current_y_value)
        )
        if (
            self.st_module.session_state.get(CARD_LAYOUT_SYNC_TOKEN_KEY) == token
            and not missing_values
        ):
            return
        self.st_module.session_state[x_key] = values["x"]
        self.st_module.session_state[y_key] = values["y"]
        self.st_module.session_state[CARD_LAYOUT_SYNC_TOKEN_KEY] = token

    def _live_node_layout_xy(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        node: FlowNode,
        *,
        layout_mode: str,
        position_edit_enabled: bool,
    ) -> tuple[float, float] | None:
        session = self.session
        if not position_edit_enabled or not session.position_edit_available():
            return None
        positions = session.ensure_position_edit_draft(graph, wells, layout_mode)
        return positions.get(node.id, (node.position.x, node.position.y))

    def _render_sidebar(
        self, graph: FlowGraphDocument
    ) -> tuple[str, list[str], list[str], str, bool]:
        session = self.session
        graph_versions = session.list_graph_versions()

        def save_positions() -> None:
            session.save_graph_positions(
                graph,
                session.position_edit_positions(graph),
            )

        state = render_sidebar(
            self.st_module,
            graph,
            auth=self.auth_context(),
            actions=SidebarActions(
                render_legend=lambda: render_legend(self.st_module, graph),
                save_positions=save_positions,
                reset_positions=session.reset_position_draft,
                reload_data=session.reload_data,
                select_graph_version=session.select_graph_version,
                materialize_graph_version=session.materialize_graph_version,
                import_live_graph_source_from_raw=session.import_live_graph_source_from_raw,
                can_materialize_graph_version=session.can_materialize_graph_version(),
                can_import_raw_graph_source=session.can_import_raw_graph_source(),
                save_positions_enabled=session.has_position_edit_positions(),
                graph_versions=graph_versions,
                selected_graph_version_id=session.selected_graph_version_id(),
                live_graph_available=session.live_graph_source_exists(),
                layout_editable=session.position_edit_available(),
                layout_edit_block_reason=session.position_edit_block_reason(),
            ),
        )
        return (
            state.search,
            state.responsible_filter,
            state.kind_filter,
            state.layout_mode,
            state.position_edit_enabled,
        )

    def _render_inspector(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        selected_id: str | None,
        *,
        layout_mode: str,
        position_edit_enabled: bool,
    ) -> None:
        render_inspector(
            self.st_module,
            graph,
            wells,
            selected_id,
            actions=InspectorActions(
                current_user_is_admin=lambda: self.auth_context().current_user_is_admin(),
                render_admin_panel=lambda admin_graph, admin_wells, admin_selected_id: (
                    self._render_admin_panel(
                        admin_graph,
                        admin_wells,
                        admin_selected_id,
                        layout_mode=layout_mode,
                        position_edit_enabled=position_edit_enabled,
                    )
                ),
            ),
        )

    def _render_admin_panel(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        selected_id: str | None,
        *,
        layout_mode: str,
        position_edit_enabled: bool,
    ) -> None:
        session = self.session

        def live_layout_xy_for_node(node_id: str) -> tuple[float, float] | None:
            node = next((item for item in graph.nodes if item.id == node_id), None)
            if node is None:
                return None
            return self._live_node_layout_xy(
                graph,
                wells,
                node,
                layout_mode=layout_mode,
                position_edit_enabled=position_edit_enabled,
            )

        render_admin_panel(
            self.st_module,
            graph,
            wells,
            selected_id,
            actions=AdminActions(
                resolve_selection=resolve_selection,
                persist_wells_update=self._persist_wells_update,
                wells_edit_available=session.wells_edit_available,
                wells_edit_block_reason=session.wells_edit_block_reason,
                load_graph_source_node=session.load_graph_source_node,
                load_graph_source_edge=session.load_graph_source_edge,
                persist_graph_source_node_update=session.save_graph_source_node,
                persist_graph_source_edge_update=session.save_graph_source_edge,
                persist_graph_source_edge_create=session.create_graph_source_edge,
                graph_source_edit_available=session.graph_source_edit_available,
                graph_source_edit_block_reason=session.graph_source_edit_block_reason,
                live_layout_xy_for_node=live_layout_xy_for_node,
                sync_card_layout_inputs=lambda node_id, current_x, current_y: (
                    self._sync_card_layout_inputs(
                        node_id=node_id,
                        current_x=current_x,
                        current_y=current_y,
                    )
                ),
            ),
        )

    def _persist_wells_update(
        self,
        updated: WellsDocument,
        *,
        graph: FlowGraphDocument,
        expected_version: int,
        success_message: str,
    ) -> None:
        self.session.save_wells(
            updated,
            graph=graph,
            expected_version=expected_version,
            success_message=success_message,
        )

    def _render_flow(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        search: str,
        responsible_filter: list[str],
        kind_filter: list[str],
        layout_mode: str,
        *,
        position_edit_enabled: bool = False,
        edge_edit_enabled: bool = False,
        node_edit_enabled: bool = False,
        render_canvas: Callable[..., object] | None = None,
    ) -> str | None:
        return render_flow_view(
            self.session.session_state,
            graph=graph,
            wells=wells,
            search=search,
            responsible_filter=responsible_filter,
            kind_filter=kind_filter,
            layout_mode=layout_mode,
            position_edit_enabled=position_edit_enabled,
            edge_edit_enabled=edge_edit_enabled,
            node_edit_enabled=node_edit_enabled,
            can_undo=can_undo(self.session.session_state),
            can_redo=can_redo(self.session.session_state),
            render_canvas=render_canvas or self.render_canvas,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )

    def _consume_pending_canvas_edge(self, graph: FlowGraphDocument) -> None:
        session = self.session
        pending = consume_pending_canvas_edge(
            session.session_state,
            graph=graph,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if pending is None:
            return
        if not session.graph_source_edit_available():
            self.st_module.error(
                session.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return
        kind = pending["kind"]
        if kind not in {"default", "yes", "no", "dashed"}:
            kind = "default"
        session.create_graph_source_edge(
            graph,
            CreateGraphSourceEdgeCommand(
                source=pending["source"],
                target=pending["target"],
                kind=kind,  # type: ignore[arg-type]
                label=None,
                condition=None,
                note=None,
            ),
            quiet=True,
            record_history=True,
        )

    def _consume_pending_canvas_node_edit(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
    ) -> None:
        session = self.session
        pending = consume_pending_canvas_node_edit(
            session.session_state,
            graph=graph,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if pending is None:
            return
        if not session.graph_source_edit_available():
            self.st_module.error(
                session.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return
        if not self.auth_context().current_user_is_admin():
            self.st_module.error("Редактирование карточек доступно только администратору.")
            return
        session.apply_canvas_node_edit(graph, wells, pending, quiet=True, record_history=True)

    def _consume_pending_canvas_node_create(self, graph: FlowGraphDocument) -> None:
        session = self.session
        pending = consume_pending_canvas_node_create(
            session.session_state,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if pending is None:
            return
        if not session.graph_source_edit_available():
            self.st_module.error(
                session.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return
        if not self.auth_context().current_user_is_admin():
            self.st_module.error("Добавление карточек доступно только администратору.")
            return
        # process/decision require ≥1 responsible in the runtime graph model.
        default_responsible = None
        if pending["kind"] in {"process", "decision_diamond"} and graph.responsibles:
            preferred = [
                key
                for key in graph.responsibles
                if key not in {"unassigned", "none", ""}
            ]
            default_responsible = preferred[0] if preferred else next(iter(graph.responsibles))
        session.create_graph_source_node(
            graph,
            CreateGraphSourceNodeCommand(
                title=pending["title"],
                kind=pending["kind"],  # type: ignore[arg-type]
                layout_x=pending["layout_x"],
                layout_y=pending["layout_y"],
                layout_w=pending["layout_w"],
                layout_h=pending["layout_h"],
                responsible=default_responsible,
            ),
            quiet=True,
            record_history=True,
        )

    def _consume_pending_canvas_edge_edit(self, graph: FlowGraphDocument) -> None:
        session = self.session
        pending = consume_pending_canvas_edge_edit(
            session.session_state,
            graph=graph,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if pending is None:
            return
        if not session.graph_source_edit_available():
            self.st_module.error(
                session.graph_source_edit_block_reason()
                or "Редактирование схемы сейчас недоступно."
            )
            return
        if not self.auth_context().current_user_is_admin():
            self.st_module.error("Редактирование связей доступно только администратору.")
            return
        try:
            draft = session.load_graph_source_edge(pending["edge_id"])
        except Exception as exc:
            self.st_module.error(f"Не удалось загрузить связь: {exc}")
            return
        kind = pending.get("kind", draft.kind)
        if kind not in {"default", "yes", "no", "dashed"}:
            kind = draft.kind
        from pydiag.presentation.runtime_session import edge_snapshot_from_draft

        before = edge_snapshot_from_draft(draft)
        session.save_graph_source_edge(
            graph,
            UpdateGraphSourceEdgeCommand(
                edge_id=draft.edge_id,
                source=draft.source,
                target=draft.target,
                kind=kind,  # type: ignore[arg-type]
                label=draft.label,
                condition=draft.condition,
                note=draft.note,
                deleted=True if pending.get("deleted") is True else None,
            ),
            quiet=True,
            record_history=True,
            before_snapshot=before,
        )

    def _consume_history_action(self, graph: FlowGraphDocument) -> None:
        action = consume_history_action(
            self.session.session_state,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if action == "undo":
            self.session.undo_edit(graph)
        elif action == "redo":
            self.session.redo_edit(graph)

    def _autosave_canvas_positions(
        self,
        graph: FlowGraphDocument,
        *,
        position_edit_enabled: bool,
    ) -> None:
        if not position_edit_enabled or not self.session.position_edit_available():
            return
        if not self.auth_context().current_user_is_admin():
            return
        # After undo/redo of moves, FE may still hold pre-undo positions in
        # component state. Skip one autosave and resync so redo stack survives.
        if take_skip_position_autosave_once(self.session.session_state):
            sync_component_positions(
                self.session.session_state,
                graph_node_positions(graph),
                component_key=FLOW_CANVAS_COMPONENT_KEY,
            )
            return
        positions = detect_canvas_position_autosave(
            self.session.session_state,
            graph=graph,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
        )
        if positions is None:
            return
        self.session.save_graph_positions(
            graph,
            positions,
            quiet=True,
            record_history=True,
        )

    def run(self) -> None:
        session = self.session
        inject_css(self.st_module)
        self.auth_context().sync_persistent_auth()
        session.render_flash()
        try:
            graph, wells = session.load_app_data()
        except Exception as exc:
            self.st_module.error(f"Ошибка загрузки JSON: {exc}")
            self.st_module.stop()
            return

        search, responsible_filter, kind_filter, layout_mode, position_edit_enabled = (
            self._render_sidebar(graph)
        )
        layout_mode = SOURCE_LAYOUT_MODE

        # Canvas + inspector share one fragment so selection/drag callbacks update
        # the inspector without a full-app st.rerun() that remounts the graph host.
        # Columns MUST be created inside the fragment: Streamlit forbids writing
        # fragment widgets into containers owned by the outer script run.
        @self.st_module.fragment
        def render_workspace_fragment() -> None:
            # Re-load inside the fragment so quiet fragment-scoped reruns after
            # canvas edits see the persisted graph without a full-app remount.
            graph, wells = session.load_app_data()
            inspector_collapsed = resolve_inspector_collapsed(session.session_state)
            if inspector_collapsed:
                diagram_col = self.st_module.container()
                side_col = None
            else:
                diagram_col, side_col = self.st_module.columns((2.3, 1.1), gap="large")
            try:
                with diagram_col:
                    edge_edit_enabled = (
                        self.auth_context().current_user_is_admin()
                        and session.graph_source_edit_available()
                    )
                    node_edit_enabled = edge_edit_enabled
                    # Mutate widget session_state BEFORE the canvas is mounted.
                    self._consume_history_action(graph)
                    self._consume_pending_canvas_edge(graph)
                    self._consume_pending_canvas_node_create(graph)
                    self._consume_pending_canvas_node_edit(graph, wells)
                    self._consume_pending_canvas_edge_edit(graph)
                    self._autosave_canvas_positions(
                        graph,
                        position_edit_enabled=position_edit_enabled,
                    )
                    # Persist may have refreshed session docs; use the latest.
                    graph, wells = session.load_app_data()
                    selected_id = self._render_flow(
                        graph,
                        wells,
                        search=search,
                        responsible_filter=responsible_filter,
                        kind_filter=kind_filter,
                        layout_mode=layout_mode,
                        position_edit_enabled=position_edit_enabled,
                        edge_edit_enabled=edge_edit_enabled,
                        node_edit_enabled=node_edit_enabled,
                    )
            except Exception as exc:
                self.st_module.error(f"Ошибка отрисовки схемы: {exc}")
                selected_id = None

            if not isinstance(selected_id, str) or not selected_id:
                selected_id = self.st_module.session_state.get("selected_id")
            if not isinstance(selected_id, str) or not selected_id:
                selected_id = None

            if side_col is not None:
                try:
                    with side_col:
                        with self.st_module.container(height=WORKSPACE_PANEL_HEIGHT, border=True):
                            self._render_inspector(
                                graph,
                                wells,
                                selected_id,
                                layout_mode=layout_mode,
                                position_edit_enabled=position_edit_enabled,
                            )
                except Exception as exc:
                    self.st_module.error(f"Ошибка панели инспектора: {exc}")

            # Sidebar save/enable flags live outside this fragment.
            if session.consume_position_edit_rerun_request():
                self.st_module.rerun()

        render_workspace_fragment()
