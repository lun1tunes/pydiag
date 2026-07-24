from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from pydiag.application import (
    CreateGraphSourceEdgeCommand,
    GraphSourceEdgeDraft,
    GraphSourceNodeDraft,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
    WellAdminService,
)
from pydiag.domain.models import (
    FlowEdge,
    FlowGraphDocument,
    FlowNode,
    Well,
    WellsDocument,
    node_by_id,
    well_by_id,
)
from pydiag.presentation.admin_models import (
    AdminPanelDefaults,
    active_wells,
    admin_panel_defaults,
    build_create_well_command,
    default_option_index,
    graph_source_node_delete_block_reason,
    normalized_optional_text,
    suggest_well_id,
    transition_ids_for_well,
    transition_option_label,
    validate_create_well_identity,
    validate_graph_source_node_form,
)
from pydiag.presentation.html_utils import safe_text
from pydiag.presentation.inspector_models import build_overview_rows

LOCAL_ADMIN_ACTOR = "local-admin"
EMPTY_RESPONSIBLE_OPTION = "__none__"
NODE_KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
}
EDGE_KIND_LABELS = {
    "default": "Обычная",
    "yes": "Да",
    "no": "Нет",
    "dashed": "Пунктир",
}


@dataclass(frozen=True)
class AdminActions:
    resolve_selection: Callable[
        [str | None, FlowGraphDocument, WellsDocument],
        tuple[str, FlowNode | FlowEdge | Well | None],
    ]
    persist_wells_update: Callable[..., None]
    wells_edit_available: Callable[[], bool]
    wells_edit_block_reason: Callable[[], str | None]
    load_graph_source_node: Callable[[str], GraphSourceNodeDraft]
    load_graph_source_edge: Callable[[str], GraphSourceEdgeDraft]
    persist_graph_source_node_update: Callable[
        [FlowGraphDocument, UpdateGraphSourceNodeCommand],
        None,
    ]
    persist_graph_source_edge_update: Callable[
        [FlowGraphDocument, UpdateGraphSourceEdgeCommand],
        None,
    ]
    persist_graph_source_edge_create: Callable[
        [FlowGraphDocument, CreateGraphSourceEdgeCommand],
        None,
    ]
    graph_source_edit_available: Callable[[], bool]
    graph_source_edit_block_reason: Callable[[], str | None]
    live_layout_xy_for_node: Callable[[str], tuple[float, float] | None]
    sync_card_layout_inputs: Callable[[str, float, float], None]


def _render_section_label(st_module, label: str) -> None:
    st_module.markdown(
        f'<p class="inspector-section-label">{safe_text(label)}</p>',
        unsafe_allow_html=True,
    )


def render_admin_panel(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
    *,
    actions: AdminActions,
) -> None:
    selected_kind, selected = actions.resolve_selection(selected_id, graph, wells)
    defaults = admin_panel_defaults(graph, selected_kind, selected)
    service = WellAdminService(graph=graph, wells=wells, actor=LOCAL_ADMIN_ACTOR)
    wells_editable = actions.wells_edit_available()

    _render_section_label(
        st_module,
        "Связь" if selected_kind == "edge" else "Карточка",
    )
    if not actions.graph_source_edit_available():
        reason = (
            actions.graph_source_edit_block_reason() or "Редактирование сейчас недоступно"
        )
        st_module.markdown(
            f'<p class="inspector-status">{safe_text(reason)}</p>',
            unsafe_allow_html=True,
        )
    render_graph_source_editor(
        st_module,
        graph,
        wells,
        selected_kind,
        selected,
        actions=actions,
        show_block_reason=False,
    )

    _render_section_label(st_module, "Скважины")
    if not wells_editable:
        reason = actions.wells_edit_block_reason() or "Редактирование сейчас недоступно"
        st_module.markdown(
            f'<p class="inspector-status">{safe_text(reason)}</p>',
            unsafe_allow_html=True,
        )
    render_wells_distribution(st_module, graph, wells)

    move_tab, create_tab = st_module.tabs(["Управление", "Новая"])
    with move_tab:
        render_well_move_controls(
            st_module,
            graph,
            wells,
            defaults=defaults,
            service=service,
            wells_editable=wells_editable,
            actions=actions,
        )
    with create_tab:
        render_well_create_controls(
            st_module,
            graph,
            wells,
            defaults=defaults,
            service=service,
            wells_editable=wells_editable,
            actions=actions,
        )


def render_wells_distribution(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
) -> None:
    top_rows = build_overview_rows(graph, wells)
    if top_rows:
        st_module.caption("Распределение")
        st_module.dataframe(pd.DataFrame(top_rows), width="stretch", hide_index=True)
    else:
        st_module.caption("Активных скважин пока нет")


def render_well_move_controls(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    *,
    defaults: AdminPanelDefaults,
    service: WellAdminService,
    wells_editable: bool,
    actions: AdminActions,
) -> None:
    active_wells_list = active_wells(wells)
    if not active_wells_list:
        st_module.caption("Активных скважин нет")
        return

    well_ids = [well.id for well in active_wells_list]
    well_id = st_module.selectbox(
        "Скважина",
        options=well_ids,
        index=default_option_index(well_ids, defaults.default_well_id),
        format_func=lambda item: well_by_id(wells)[item].name,
        key="admin_well_id",
        disabled=not wells_editable,
        label_visibility="collapsed",
    )
    current_well = well_by_id(wells)[well_id]
    current_node = node_by_id(graph)[current_well.current_node_id]
    st_module.caption(current_node.text)

    transition_ids = transition_ids_for_well(graph, current_well)
    selected_edge_id = st_module.selectbox(
        "Переход",
        options=transition_ids,
        format_func=lambda edge_id: transition_option_label(graph, current_well, edge_id),
        disabled=not transition_ids or not wells_editable,
        key="admin_transition_id",
    )
    comment = st_module.text_input(
        "Комментарий",
        key="admin_comment",
        disabled=not wells_editable,
        placeholder="Необязательно",
    )

    col_a, col_b = st_module.columns(2)
    with col_a:
        if st_module.button(
            "Продвинуть",
            disabled=not transition_ids or not wells_editable,
            width="stretch",
        ):
            actions.persist_wells_update(
                service.advance_well(
                    well_id=well_id,
                    edge_id=selected_edge_id,
                    comment=normalized_optional_text(comment),
                ),
                graph=graph,
                expected_version=wells.version,
                success_message="Скважина переведена на следующий этап",
            )
    with col_b:
        if st_module.button(
            "Откатить",
            disabled=len(current_well.history) < 2 or not wells_editable,
            width="stretch",
        ):
            actions.persist_wells_update(
                service.rollback_well(
                    well_id=well_id,
                    comment=normalized_optional_text(comment),
                ),
                graph=graph,
                expected_version=wells.version,
                success_message="Скважина откатилась на предыдущий этап",
            )

    confirm_delete = st_module.checkbox(
        "Удалить",
        key="confirm_delete",
        disabled=not wells_editable,
    )
    if st_module.button(
        "Удалить скважину",
        disabled=not confirm_delete or not wells_editable,
        width="stretch",
    ):
        actions.persist_wells_update(
            service.delete_well(well_id=well_id),
            graph=graph,
            expected_version=wells.version,
            success_message="Скважина удалена",
        )


def render_well_create_controls(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    *,
    defaults: AdminPanelDefaults,
    service: WellAdminService,
    wells_editable: bool,
    actions: AdminActions,
) -> None:
    with st_module.form("create_well_form", clear_on_submit=False):
        suggested_id = suggest_well_id(wells)
        well_id = st_module.text_input("ID", value=suggested_id, disabled=not wells_editable)
        name = st_module.text_input(
            "Название",
            value=suggested_id.replace("well_", "Скв. "),
            disabled=not wells_editable,
        )
        node_ids = [node.id for node in graph.nodes]
        start_node_id = st_module.selectbox(
            "Этап",
            options=node_ids,
            index=default_option_index(node_ids, defaults.default_node_id),
            format_func=lambda node_id: node_by_id(graph)[node_id].text,
            disabled=not wells_editable,
        )
        field = st_module.text_input("Месторождение / куст", disabled=not wells_editable)
        rig = st_module.text_input("Буровая", disabled=not wells_editable)
        comment = st_module.text_input("Комментарий", disabled=not wells_editable)
        submitted = st_module.form_submit_button(
            "Создать",
            width="stretch",
            disabled=not wells_editable,
        )

    if submitted:
        error_message = validate_create_well_identity(well_id, name)
        if error_message is not None:
            st_module.error(error_message)
        else:
            command = build_create_well_command(
                well_id=well_id,
                name=name,
                start_node_id=start_node_id,
                field=field,
                rig=rig,
                comment=comment,
            )
            actions.persist_wells_update(
                service.create_well(command),
                graph=graph,
                expected_version=wells.version,
                success_message="Скважина создана",
            )


def render_graph_source_editor(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_kind: str,
    selected: FlowNode | FlowEdge | Well | None,
    *,
    actions: AdminActions,
    show_block_reason: bool = True,
) -> None:
    if not actions.graph_source_edit_available():
        if show_block_reason:
            st_module.caption(
                actions.graph_source_edit_block_reason()
                or "Редактирование сейчас недоступно"
            )
        return

    if selected_kind == "node" and selected is not None:
        render_graph_source_node_editor(
            st_module,
            graph,
            wells,
            selected,
            actions=actions,
        )
        return

    if selected_kind == "edge" and selected is not None:
        render_graph_source_edge_editor(
            st_module,
            graph,
            selected,
            actions=actions,
        )
        return

    st_module.caption("Выберите карточку или связь на схеме")


def render_graph_source_node_editor(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    node: FlowNode,
    *,
    actions: AdminActions,
) -> None:
    try:
        draft = actions.load_graph_source_node(node.id)
    except Exception as exc:
        st_module.error(f"Не удалось загрузить карточку из source YAML: {exc}")
        return

    live_xy = actions.live_layout_xy_for_node(node.id)
    display_x, display_y = live_xy if live_xy is not None else (draft.layout_x, draft.layout_y)
    actions.sync_card_layout_inputs(node.id, display_x, display_y)

    responsible_ids = list(graph.responsibles.keys())
    primary_options = [EMPTY_RESPONSIBLE_OPTION, *responsible_ids]
    node_kind_options = [
        "process",
        "decision_diamond",
        "database",
        "input_data",
        "event",
    ]
    current_primary = draft.responsible or EMPTY_RESPONSIBLE_OPTION
    # Streamlit keeps widget state by key; scope every field to node.id so
    # switching selection remounts with the new draft instead of stale values.
    def field_key(name: str) -> str:
        return f"graph_source_node_{name}::{node.id}"

    with st_module.form(f"graph_source_node_form::{node.id}", clear_on_submit=False):
        title = st_module.text_input(
            "Заголовок",
            value=draft.title,
            key=field_key("title"),
        )
        kind = st_module.selectbox(
            "Тип",
            options=node_kind_options,
            index=default_option_index(node_kind_options, draft.kind),
            format_func=lambda value: NODE_KIND_LABELS[value],
            key=field_key("kind"),
        )
        col_a, col_b = st_module.columns(2)
        with col_a:
            # X/Y keys are synced from live/source layout before the form.
            layout_x = st_module.number_input(
                "X",
                step=10.0,
                format="%.2f",
                key=field_key("layout_x"),
            )
            layout_w = st_module.number_input(
                "Ширина",
                min_value=80,
                max_value=1200,
                value=int(draft.layout_w),
                step=10,
                key=field_key("layout_w"),
            )
        with col_b:
            layout_y = st_module.number_input(
                "Y",
                step=10.0,
                format="%.2f",
                key=field_key("layout_y"),
            )
            layout_h = st_module.number_input(
                "Высота",
                min_value=40,
                max_value=800,
                value=int(draft.layout_h),
                step=10,
                key=field_key("layout_h"),
            )
        responsible = st_module.selectbox(
            "Ответственный",
            options=primary_options,
            index=default_option_index(primary_options, current_primary),
            format_func=lambda value: (
                "Не задан" if value == EMPTY_RESPONSIBLE_OPTION else graph.responsibles[value].label
            ),
            key=field_key("responsible"),
        )
        participants = st_module.multiselect(
            "Участники",
            options=responsible_ids,
            default=list(draft.participants),
            format_func=lambda value: graph.responsibles[value].label,
            key=field_key("participants"),
        )
        approvers = st_module.multiselect(
            "Согласующие",
            options=responsible_ids,
            default=list(draft.approvers),
            format_func=lambda value: graph.responsibles[value].label,
            key=field_key("approvers"),
        )
        duration = st_module.text_input(
            "Длительность",
            value=draft.duration or "",
            key=field_key("duration"),
        )
        note = st_module.text_area(
            "Заметка",
            value=draft.note or "",
            height=68,
            key=field_key("note"),
        )
        submitted = st_module.form_submit_button("Сохранить", width="stretch")

    delete_block_reason = graph_source_node_delete_block_reason(node.id, wells)
    if delete_block_reason is not None:
        st_module.caption(delete_block_reason)
    confirm_delete = st_module.checkbox(
        "Подтвердить удаление карточки",
        key=f"confirm_delete_graph_source_node::{node.id}",
        disabled=delete_block_reason is not None,
    )
    if st_module.button(
        "Удалить карточку",
        key=f"delete_graph_source_node::{node.id}",
        disabled=delete_block_reason is not None or not confirm_delete,
        width="stretch",
    ):
        actions.persist_graph_source_node_update(
            graph,
            UpdateGraphSourceNodeCommand(
                node_id=node.id,
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
                deleted=True,
            ),
        )

    render_related_graph_source_edges_for_node(
        st_module,
        graph,
        node,
        actions=actions,
    )

    if not submitted:
        return

    error_message = validate_graph_source_node_form(
        title=title,
        kind=kind,
        responsible=None if responsible == EMPTY_RESPONSIBLE_OPTION else responsible,
        participants=participants,
        approvers=approvers,
    )
    if error_message is not None:
        st_module.error(error_message)
        return

    # Prefer submitted widget values; fall back to live/source display values.
    # Do not read widget session keys here — they can lag behind the submit payload.
    layout_values = parse_graph_source_layout_form(
        layout_x=coalesce_layout_field(layout_x, None, display_x),
        layout_y=coalesce_layout_field(layout_y, None, display_y),
        layout_w=coalesce_layout_field(layout_w, None, draft.layout_w),
        layout_h=coalesce_layout_field(layout_h, None, draft.layout_h),
    )
    if isinstance(layout_values, str):
        st_module.error(layout_values)
        return

    actions.persist_graph_source_node_update(
        graph,
        UpdateGraphSourceNodeCommand(
            node_id=node.id,
            title=title.strip(),
            kind=kind,
            layout_x=layout_values[0],
            layout_y=layout_values[1],
            layout_w=layout_values[2],
            layout_h=layout_values[3],
            responsible=None if responsible == EMPTY_RESPONSIBLE_OPTION else responsible,
            participants=tuple(participants),
            approvers=tuple(approvers),
            duration=normalized_optional_text(duration),
            note=normalized_optional_text(note),
            deleted=None,
        ),
    )


def render_graph_source_edge_editor(
    st_module,
    graph: FlowGraphDocument,
    edge: FlowEdge,
    *,
    actions: AdminActions,
    form_key_prefix: str = "graph_source_edge",
    submit_label: str = "Сохранить связь",
) -> None:
    try:
        draft = actions.load_graph_source_edge(edge.id)
    except Exception as exc:
        st_module.error(f"Не удалось загрузить связь из source YAML: {exc}")
        return

    edge_kind_options = list(EDGE_KIND_LABELS.keys())
    def field_key(name: str) -> str:
        return f"{form_key_prefix}_{name}::{edge.id}"

    with st_module.form(f"{form_key_prefix}_form::{edge.id}", clear_on_submit=False):
        kind = st_module.selectbox(
            "Тип связи",
            options=edge_kind_options,
            index=default_option_index(edge_kind_options, draft.kind),
            format_func=lambda value: EDGE_KIND_LABELS[value],
            key=field_key("kind"),
        )
        submitted = st_module.form_submit_button(submit_label, width="stretch")

    confirm_delete = st_module.checkbox(
        "Подтвердить удаление связи",
        key=f"confirm_delete_{form_key_prefix}::{edge.id}",
    )
    if st_module.button(
        "Удалить связь",
        key=f"delete_{form_key_prefix}::{edge.id}",
        disabled=not confirm_delete,
        width="stretch",
    ):
        actions.persist_graph_source_edge_update(
            graph,
            UpdateGraphSourceEdgeCommand(
                edge_id=edge.id,
                source=draft.source,
                target=draft.target,
                kind=draft.kind,
                label=draft.label,
                condition=draft.condition,
                note=draft.note,
                deleted=True,
            ),
        )
        return

    if not submitted:
        return

    actions.persist_graph_source_edge_update(
        graph,
        UpdateGraphSourceEdgeCommand(
            edge_id=edge.id,
            source=draft.source,
            target=draft.target,
            kind=kind,
            label=draft.label,
            condition=draft.condition,
            note=draft.note,
        ),
    )


def render_related_graph_source_edges_for_node(
    st_module,
    graph: FlowGraphDocument,
    node: FlowNode,
    *,
    actions: AdminActions,
) -> None:
    _render_section_label(st_module, "Связи")
    related_edges = [
        edge
        for edge in graph.edges
        if edge.source == node.id or edge.target == node.id
    ]
    if not related_edges:
        st_module.caption("У карточки пока нет связей.")
    else:
        node_map = node_by_id(graph)
        for edge in related_edges:
            edge_kind = "default" if edge.kind == "usual" else edge.kind
            edge_title = (
                f"{node_map[edge.source].text} -> {node_map[edge.target].text}"
                f" · {EDGE_KIND_LABELS[edge_kind]}"
            )
            with st_module.expander(edge_title, expanded=False):
                render_graph_source_edge_editor(
                    st_module,
                    graph,
                    edge,
                    actions=actions,
                    form_key_prefix=f"graph_source_edge_{edge.id}",
                    submit_label="Сохранить эту связь",
                )

    render_create_graph_source_edge_form(
        st_module,
        graph,
        source_node=node,
        actions=actions,
    )


def render_create_graph_source_edge_form(
    st_module,
    graph: FlowGraphDocument,
    *,
    source_node: FlowNode,
    actions: AdminActions,
) -> None:
    editable = actions.graph_source_edit_available()
    node_ids = [item.id for item in graph.nodes]
    existing_targets = {
        edge.target for edge in graph.edges if edge.source == source_node.id
    }
    target_options = [
        node_id
        for node_id in node_ids
        if node_id != source_node.id and node_id not in existing_targets
    ]
    if not target_options:
        st_module.caption(
            "Нет других карточек для новой связи "
            "(ко всем доступным уже есть связь из этой карточки)."
            if existing_targets
            else "Нет других карточек для новой связи."
        )
        return

    node_map = node_by_id(graph)
    edge_kind_options = list(EDGE_KIND_LABELS.keys())
    form_key = f"graph_source_edge_create::{source_node.id}"

    def field_key(name: str) -> str:
        return f"{form_key}_{name}"

    with st_module.expander("Новая связь", expanded=False):
        st_module.caption(f"Откуда: {source_node.text}")
        with st_module.form(f"{form_key}_form", clear_on_submit=True):
            target = st_module.selectbox(
                "Куда",
                options=target_options,
                index=0,
                format_func=lambda value: node_map[value].text,
                key=field_key("target"),
                disabled=not editable,
            )
            kind = st_module.selectbox(
                "Тип связи",
                options=edge_kind_options,
                index=0,
                format_func=lambda value: EDGE_KIND_LABELS[value],
                key=field_key("kind"),
                disabled=not editable,
            )
            label = st_module.text_input(
                "Метка связи",
                value="",
                key=field_key("label"),
                disabled=not editable,
            )
            condition = st_module.text_input(
                "Условие",
                value="",
                key=field_key("condition"),
                disabled=not editable,
            )
            note = st_module.text_area(
                "Заметка",
                value="",
                height=68,
                key=field_key("note"),
                disabled=not editable,
            )
            submitted = st_module.form_submit_button(
                "Добавить связь",
                width="stretch",
                disabled=not editable,
            )

    if not submitted:
        return

    if not editable:
        st_module.error(
            actions.graph_source_edit_block_reason()
            or "Редактирование схемы сейчас недоступно."
        )
        return

    actions.persist_graph_source_edge_create(
        graph,
        CreateGraphSourceEdgeCommand(
            source=source_node.id,
            target=target,
            kind=kind,
            label=normalized_optional_text(label),
            condition=normalized_optional_text(condition),
            note=normalized_optional_text(note),
        ),
    )


def coalesce_layout_field(
    primary: object,
    secondary: object,
    fallback: float | int,
) -> str:
    for candidate in (primary, secondary):
        text = layout_field_text(candidate)
        if text:
            return text
    return layout_field_text(fallback) or str(fallback)


def layout_field_text(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return format_layout_float(value)
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_graph_source_layout_form(
    *,
    layout_x: object,
    layout_y: object,
    layout_w: object,
    layout_h: object,
) -> tuple[float, float, int, int] | str:
    x_text = layout_field_text(layout_x)
    y_text = layout_field_text(layout_y)
    w_text = layout_field_text(layout_w)
    h_text = layout_field_text(layout_h)
    try:
        parsed_x = round(float(x_text), 2)
        parsed_y = round(float(y_text), 2)
    except ValueError:
        return "Координаты source layout должны быть числами."
    if (
        parsed_x != parsed_x
        or parsed_y != parsed_y
        or parsed_x in (float("inf"), float("-inf"))
        or parsed_y in (float("inf"), float("-inf"))
    ):
        return "Координаты source layout должны быть конечными числами."

    try:
        parsed_w = int(float(w_text))
        parsed_h = int(float(h_text))
    except ValueError:
        return "Размер карточки должен задаваться целыми числами."

    if parsed_w < 80 or parsed_w > 1200:
        return "Ширина карточки должна быть в диапазоне 80-1200."
    if parsed_h < 40 or parsed_h > 800:
        return "Высота карточки должна быть в диапазоне 40-800."
    return parsed_x, parsed_y, parsed_w, parsed_h


def format_layout_float(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
