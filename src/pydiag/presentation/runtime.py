from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import Any

from pydiag.application import FLOW_CANVAS_COMPONENT_KEY, DocumentsGateway
from pydiag.common.auth_sessions import AuthSessionStore
from pydiag.application import render_flow as render_flow_view
from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.presentation.admin import (
    AdminActions,
    format_layout_float,
    render_admin_panel,
)
from pydiag.presentation.auth import StreamlitAuthContext
from pydiag.presentation.auth_session import DEFAULT_AUTH_SESSION_TTL_SECONDS
from pydiag.presentation.chrome import inject_css, render_legend
from pydiag.presentation.inspector import InspectorActions, render_inspector
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.presentation.selection import resolve_selection
from pydiag.presentation.sidebar import SOURCE_LAYOUT_MODE, SidebarActions, render_sidebar
from pydiag.rendering.flow_canvas_component import render_flow_canvas

WORKSPACE_PANEL_HEIGHT = 828
LAYOUT_DRAFT_ERROR_KEY = "_layout_draft_error"


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

    def _layout_draft_input_key(
        self,
        *,
        axis: str,
        layout_mode: str,
        node_id: str,
    ) -> str:
        return f"layout_draft_{axis}::{layout_mode}::{node_id}"

    def _layout_draft_synced_value_key(
        self,
        *,
        axis: str,
        layout_mode: str,
        node_id: str,
    ) -> str:
        return f"_layout_draft_sync_{axis}::{layout_mode}::{node_id}"

    def _sync_layout_draft_inputs(
        self,
        *,
        layout_mode: str,
        node_id: str,
        current_x: float,
        current_y: float,
    ) -> None:
        values = {
            "x": format_layout_float(current_x),
            "y": format_layout_float(current_y),
        }
        for axis, value in values.items():
            synced_value_key = self._layout_draft_synced_value_key(
                axis=axis,
                layout_mode=layout_mode,
                node_id=node_id,
            )
            if self.st_module.session_state.get(synced_value_key) == value:
                continue
            self.st_module.session_state[
                self._layout_draft_input_key(
                    axis=axis,
                    layout_mode=layout_mode,
                    node_id=node_id,
                )
            ] = value
            self.st_module.session_state[synced_value_key] = value

    def _apply_layout_draft(
        self,
        graph: FlowGraphDocument,
        *,
        node_id: str,
        layout_mode: str,
    ) -> None:
        layout_x = self.st_module.session_state.get(
            self._layout_draft_input_key(axis="x", layout_mode=layout_mode, node_id=node_id),
            "",
        )
        layout_y = self.st_module.session_state.get(
            self._layout_draft_input_key(axis="y", layout_mode=layout_mode, node_id=node_id),
            "",
        )
        parsed = parse_layout_draft_xy(layout_x=str(layout_x), layout_y=str(layout_y))
        if isinstance(parsed, str):
            self.st_module.session_state[LAYOUT_DRAFT_ERROR_KEY] = {
                "layout_mode": layout_mode,
                "node_id": node_id,
                "message": parsed,
            }
            return

        self.st_module.session_state.pop(LAYOUT_DRAFT_ERROR_KEY, None)
        self.session.update_position_edit_draft(
            graph,
            node_id=node_id,
            x=parsed[0],
            y=parsed[1],
        )

    def _render_layout_draft_error(
        self,
        *,
        layout_mode: str,
        node_id: str,
    ) -> None:
        error_state = self.st_module.session_state.get(LAYOUT_DRAFT_ERROR_KEY)
        if not isinstance(error_state, dict):
            return
        if error_state.get("layout_mode") != layout_mode or error_state.get("node_id") != node_id:
            return
        message = error_state.get("message")
        if isinstance(message, str) and message:
            self.st_module.error(message)

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
    ) -> None:
        render_inspector(
            self.st_module,
            graph,
            wells,
            selected_id,
            actions=InspectorActions(
                current_user_is_admin=lambda: self.auth_context().current_user_is_admin(),
                render_admin_panel=self._render_admin_panel,
            ),
        )

    def _render_layout_draft_panel(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        selected_id: str | None,
        *,
        layout_mode: str,
        position_edit_enabled: bool,
    ) -> None:
        if not self.auth_context().current_user_is_admin():
            return

        session = self.session
        selected_kind, selected = resolve_selection(selected_id, graph, wells)
        with self.st_module.expander(
            "Положение на схеме",
            expanded=selected_kind == "node",
        ):
            if not session.position_edit_available():
                self.st_module.caption(
                    session.position_edit_block_reason()
                    or "Редактирование layout сейчас недоступно."
                )
                return

            if selected_kind != "node" or selected is None:
                return

            if not position_edit_enabled:
                self.st_module.caption(
                    "Включите «Редактировать положение» в боковой панели, чтобы менять layout."
                )
                return

            positions = session.ensure_position_edit_draft(graph, wells, layout_mode)
            current_x, current_y = positions.get(
                selected.id,
                (selected.position.x, selected.position.y),
            )
            self._sync_layout_draft_inputs(
                layout_mode=layout_mode,
                node_id=selected.id,
                current_x=current_x,
                current_y=current_y,
            )
            col_a, col_b = self.st_module.columns(2)
            with col_a:
                self.st_module.text_input(
                    "X в текущем layout",
                    value=format_layout_float(current_x),
                    key=self._layout_draft_input_key(
                        axis="x",
                        layout_mode=layout_mode,
                        node_id=selected.id,
                    ),
                )
            with col_b:
                self.st_module.text_input(
                    "Y в текущем layout",
                    value=format_layout_float(current_y),
                    key=self._layout_draft_input_key(
                        axis="y",
                        layout_mode=layout_mode,
                        node_id=selected.id,
                    ),
                )
            self.st_module.button(
                "Применить положение",
                key=f"apply_layout_draft::{layout_mode}::{selected.id}",
                width="stretch",
                on_click=self._apply_layout_draft,
                args=(graph,),
                kwargs={"node_id": selected.id, "layout_mode": layout_mode},
            )
            self._render_layout_draft_error(layout_mode=layout_mode, node_id=selected.id)

    def _render_admin_panel(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        selected_id: str | None,
    ) -> None:
        session = self.session
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
                graph_source_edit_available=session.graph_source_edit_available,
                graph_source_edit_block_reason=session.graph_source_edit_block_reason,
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
            render_canvas=render_canvas or self.render_canvas,
            component_key=FLOW_CANVAS_COMPONENT_KEY,
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
        diagram_col, side_col = self.st_module.columns((2.3, 1.1), gap="large")

        @self.st_module.fragment
        def render_canvas_fragment() -> None:
            self._render_flow(
                graph,
                wells,
                search=search,
                responsible_filter=responsible_filter,
                kind_filter=kind_filter,
                layout_mode=layout_mode,
                position_edit_enabled=position_edit_enabled,
            )
            if session.consume_flow_selection_rerun_request():
                self.st_module.rerun()

        @self.st_module.fragment
        def render_inspector_fragment() -> None:
            selected_id = self.st_module.session_state.get("selected_id")
            if not isinstance(selected_id, str) or not selected_id:
                selected_id = None

            with self.st_module.container(height=WORKSPACE_PANEL_HEIGHT, border=True):
                self._render_layout_draft_panel(
                    graph,
                    wells,
                    selected_id,
                    layout_mode=layout_mode,
                    position_edit_enabled=position_edit_enabled,
                )
                self._render_inspector(graph, wells, selected_id)
            if session.consume_position_edit_rerun_request():
                self.st_module.rerun()

        with diagram_col:
            render_canvas_fragment()
        with side_col:
            render_inspector_fragment()


def parse_layout_draft_xy(
    *,
    layout_x: str,
    layout_y: str,
) -> tuple[float, float] | str:
    try:
        parsed_x = round(float(layout_x.strip()), 2)
        parsed_y = round(float(layout_y.strip()), 2)
    except ValueError:
        return "Координаты текущего layout должны быть числами."

    if not isfinite(parsed_x) or not isfinite(parsed_y):
        return "Координаты текущего layout должны быть конечными числами."
    return parsed_x, parsed_y
