from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydiag.application import FLOW_CANVAS_COMPONENT_KEY, DocumentsGateway
from pydiag.application import render_flow as render_flow_view
from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.presentation.admin import AdminActions, render_admin_panel
from pydiag.presentation.auth import StreamlitAuthContext
from pydiag.presentation.chrome import inject_css, render_legend
from pydiag.presentation.inspector import InspectorActions, render_inspector
from pydiag.presentation.runtime_session import StreamlitSessionCoordinator
from pydiag.presentation.selection import resolve_selection
from pydiag.presentation.sidebar import SidebarActions, render_sidebar
from pydiag.rendering.flow_canvas_component import render_flow_canvas


@dataclass(frozen=True)
class StreamlitAppRuntime:
    st_module: Any
    documents_gateway: DocumentsGateway
    render_canvas: Callable[..., object] = render_flow_canvas

    @property
    def session(self) -> StreamlitSessionCoordinator:
        return StreamlitSessionCoordinator(self.st_module, self.documents_gateway)

    def auth_context(self) -> StreamlitAuthContext:
        return StreamlitAuthContext(self.st_module)

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
                can_materialize_graph_version=session.can_materialize_graph_version(),
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

    def _render_admin_panel(
        self,
        graph: FlowGraphDocument,
        wells: WellsDocument,
        selected_id: str | None,
    ) -> None:
        render_admin_panel(
            self.st_module,
            graph,
            wells,
            selected_id,
            actions=AdminActions(
                resolve_selection=resolve_selection,
                persist_wells_update=self._persist_wells_update,
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

        selected_id = self._render_flow(
            graph,
            wells,
            search=search,
            responsible_filter=responsible_filter,
            kind_filter=kind_filter,
            layout_mode=layout_mode,
            position_edit_enabled=position_edit_enabled,
        )
        with self.st_module.expander(
            "Инспектор и управление",
            expanded=bool(selected_id) or self.auth_context().current_user_is_admin(),
        ):
            self._render_inspector(graph, wells, selected_id)
