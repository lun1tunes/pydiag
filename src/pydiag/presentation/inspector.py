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
    st_module.markdown('<div class="inspector-shell">', unsafe_allow_html=True)
    st_module.markdown("### Инспектор")
    selection_kind, selected = resolve_selection(selected_id, graph, wells)

    if selection_kind == "node" and selected is not None:
        render_node_details(st_module, graph, wells, selected)
    elif selection_kind == "well" and selected is not None:
        render_well_details(st_module, graph, selected)
    elif selection_kind == "edge" and selected is not None:
        render_edge_details(st_module, graph, selected)
    else:
        st_module.info("Выберите узел, связь или фишку скважины на схеме.")
        render_overview_tables(st_module, graph, wells)

    if actions.current_user_is_admin():
        st_module.divider()
        actions.render_admin_panel(graph, wells, selected_id)

    st_module.markdown("</div>", unsafe_allow_html=True)


def render_node_details(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    node: FlowNode,
) -> None:
    model = build_node_inspector_model(graph, wells, node)

    st_module.markdown(f"#### {model.section.title}")
    st_module.markdown(
        f'<p class="muted-line">{model.section.subtitle_html}</p>',
        unsafe_allow_html=True,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)

    if model.wells_rows:
        st_module.markdown("##### Скважины на этапе")
        st_module.dataframe(
            pd.DataFrame(model.wells_rows),
            width="stretch",
            hide_index=True,
        )

    if model.transitions_rows:
        st_module.markdown("##### Доступные переходы")
        st_module.dataframe(
            pd.DataFrame(model.transitions_rows),
            width="stretch",
            hide_index=True,
        )


def render_well_details(st_module, graph: FlowGraphDocument, well: Well) -> None:
    model = build_well_inspector_model(graph, well)

    st_module.markdown(f"#### {model.section.title}")
    st_module.markdown(
        f'<p class="muted-line">{model.section.subtitle_html}</p>',
        unsafe_allow_html=True,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)
    if model.history_rows:
        st_module.markdown("##### Журнал")
        st_module.dataframe(
            pd.DataFrame(model.history_rows),
            width="stretch",
            hide_index=True,
        )


def render_edge_details(st_module, graph: FlowGraphDocument, edge: FlowEdge) -> None:
    model = build_edge_inspector_model(graph, edge)
    st_module.markdown(f"#### {model.section.title}")
    st_module.markdown(
        f'<p class="muted-line">{model.section.subtitle_html}</p>',
        unsafe_allow_html=True,
    )
    st_module.markdown(model.section.details_html, unsafe_allow_html=True)


def render_overview_tables(st_module, graph: FlowGraphDocument, wells: WellsDocument) -> None:
    top_rows = build_overview_rows(graph, wells)
    if top_rows:
        st_module.markdown("##### Распределение")
        st_module.dataframe(pd.DataFrame(top_rows), width="stretch", hide_index=True)
