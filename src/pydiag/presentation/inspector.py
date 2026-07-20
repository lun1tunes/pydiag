from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from pydiag.domain.models import (
    FlowEdge,
    FlowGraphDocument,
    FlowNode,
    Well,
    WellsDocument,
)
from pydiag.presentation.html_utils import safe_text
from pydiag.presentation.inspector_models import (
    build_edge_inspector_model,
    build_node_inspector_model,
    build_overview_rows,
    build_well_inspector_model,
)
from pydiag.presentation.selection import resolve_selection


@dataclass(frozen=True)
class InspectorActions:
    current_user_is_admin: Callable[[], bool]
    render_admin_panel: Callable[[FlowGraphDocument, WellsDocument, str | None], None]


def render_inspector(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
    *,
    actions: InspectorActions,
) -> None:
    selection_kind, selected = resolve_selection(selected_id, graph, wells)
    is_admin = actions.current_user_is_admin()

    if selection_kind == "node" and selected is not None:
        render_node_details(st_module, graph, wells, selected)
    elif selection_kind == "well" and selected is not None:
        render_well_details(st_module, graph, selected)
    elif selection_kind == "edge" and selected is not None:
        render_edge_details(st_module, graph, selected)
    elif not is_admin:
        # Для админа распределение живёт в блоке «Скважины».
        render_overview_tables(st_module, graph, wells)

    if is_admin:
        actions.render_admin_panel(graph, wells, selected_id)


def _render_entity_header(st_module, *, title: str, subtitle_html: str) -> None:
    st_module.markdown(
        f'<p class="inspector-entity">{safe_text(title)}</p>'
        f'<p class="inspector-sub">{subtitle_html}</p>',
        unsafe_allow_html=True,
    )


def _render_section_label(st_module, label: str) -> None:
    st_module.markdown(
        f'<p class="inspector-section-label">{safe_text(label)}</p>',
        unsafe_allow_html=True,
    )


def render_node_details(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    node: FlowNode,
) -> None:
    model = build_node_inspector_model(graph, wells, node)
    _render_entity_header(
        st_module,
        title=model.section.title,
        subtitle_html=model.section.subtitle_html,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)

    if model.wells_rows:
        _render_section_label(st_module, "Скважины на этапе")
        st_module.dataframe(
            pd.DataFrame(model.wells_rows),
            width="stretch",
            hide_index=True,
        )

    if model.transitions_rows:
        _render_section_label(st_module, "Связи")
        st_module.dataframe(
            pd.DataFrame(model.transitions_rows),
            width="stretch",
            hide_index=True,
        )


def render_well_details(st_module, graph: FlowGraphDocument, well: Well) -> None:
    model = build_well_inspector_model(graph, well)
    _render_entity_header(
        st_module,
        title=model.section.title,
        subtitle_html=model.section.subtitle_html,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)
    if model.history_rows:
        _render_section_label(st_module, "Журнал")
        st_module.dataframe(
            pd.DataFrame(model.history_rows),
            width="stretch",
            hide_index=True,
        )


def render_edge_details(st_module, graph: FlowGraphDocument, edge: FlowEdge) -> None:
    model = build_edge_inspector_model(graph, edge)
    _render_entity_header(
        st_module,
        title=model.section.title,
        subtitle_html=model.section.subtitle_html,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)


def render_overview_tables(st_module, graph: FlowGraphDocument, wells: WellsDocument) -> None:
    top_rows = build_overview_rows(graph, wells)
    if top_rows:
        _render_section_label(st_module, "Распределение")
        st_module.dataframe(pd.DataFrame(top_rows), width="stretch", hide_index=True)
    else:
        st_module.markdown(
            '<p class="inspector-sub">Выберите элемент на схеме</p>',
            unsafe_allow_html=True,
        )
