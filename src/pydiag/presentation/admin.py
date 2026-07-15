from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydiag.application import (
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
    active_wells,
    admin_panel_defaults,
    build_create_well_command,
    default_option_index,
    normalized_optional_text,
    suggest_well_id,
    transition_ids_for_well,
    transition_option_label,
    validate_create_well_identity,
)

LOCAL_ADMIN_ACTOR = "local-admin"
EMPTY_RESPONSIBLE_OPTION = "__none__"
NODE_KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение (ромб)",
    "decision_card": "Решение (карточка)",
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
    graph_source_edit_available: Callable[[], bool]
    graph_source_edit_block_reason: Callable[[], str | None]


def render_admin_panel(
    st_module,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
    *,
    actions: AdminActions,
) -> None:
    st_module.markdown("### Панель управления")
    selected_kind, selected = actions.resolve_selection(selected_id, graph, wells)
    defaults = admin_panel_defaults(graph, selected_kind, selected)
    service = WellAdminService(graph=graph, wells=wells, actor=LOCAL_ADMIN_ACTOR)
    wells_editable = actions.wells_edit_available()
    wells_edit_block_reason = actions.wells_edit_block_reason()

    with st_module.expander("Переместить или откатить скважину", expanded=True):
        if not wells_editable and wells_edit_block_reason is not None:
            st_module.caption(wells_edit_block_reason)
        active_wells_list = active_wells(wells)
        if not active_wells_list:
            st_module.caption("Активных скважин пока нет.")
        else:
            well_ids = [well.id for well in active_wells_list]
            well_id = st_module.selectbox(
                "Скважина",
                options=well_ids,
                index=default_option_index(well_ids, defaults.default_well_id),
                format_func=lambda item: well_by_id(wells)[item].name,
                key="admin_well_id",
                disabled=not wells_editable,
            )
            current_well = well_by_id(wells)[well_id]
            current_node = node_by_id(graph)[current_well.current_node_id]
            st_module.caption(f"Сейчас: {current_node.text}")

            transition_ids = transition_ids_for_well(graph, current_well)
            selected_edge_id = st_module.selectbox(
                "Переход",
                options=transition_ids,
                format_func=lambda edge_id: transition_option_label(graph, current_well, edge_id),
                disabled=not transition_ids or not wells_editable,
                key="admin_transition_id",
            )
            comment = st_module.text_area(
                "Комментарий",
                height=68,
                key="admin_comment",
                disabled=not wells_editable,
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
                "Подтвердить удаление",
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

    with st_module.expander("Добавить скважину", expanded=False):
        if not wells_editable and wells_edit_block_reason is not None:
            st_module.caption(wells_edit_block_reason)
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
                "Начальный этап",
                options=node_ids,
                index=default_option_index(node_ids, defaults.default_node_id),
                format_func=lambda node_id: node_by_id(graph)[node_id].text,
                disabled=not wells_editable,
            )
            field = st_module.text_input("Месторождение / куст", disabled=not wells_editable)
            rig = st_module.text_input("Буровая", disabled=not wells_editable)
            comment = st_module.text_area("Комментарий", height=68, disabled=not wells_editable)
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

    render_graph_source_editor(
        st_module,
        graph,
        selected_kind,
        selected,
        actions=actions,
    )


def render_graph_source_editor(
    st_module,
    graph: FlowGraphDocument,
    selected_kind: str,
    selected: FlowNode | FlowEdge | Well | None,
    *,
    actions: AdminActions,
) -> None:
    with st_module.expander(
        "Редактирование active flow source",
        expanded=selected_kind in {"node", "edge"},
    ):
        if not actions.graph_source_edit_available():
            st_module.caption(
                actions.graph_source_edit_block_reason()
                or "Редактирование source YAML сейчас недоступно."
            )
            return

        if selected_kind == "node" and selected is not None:
            render_graph_source_node_editor(
                st_module,
                graph,
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

        st_module.caption("Выберите карточку или связь на схеме, чтобы изменить source YAML.")


def render_graph_source_node_editor(
    st_module,
    graph: FlowGraphDocument,
    node: FlowNode,
    *,
    actions: AdminActions,
) -> None:
    try:
        draft = actions.load_graph_source_node(node.id)
    except Exception as exc:
        st_module.error(f"Не удалось загрузить карточку из source YAML: {exc}")
        return

    responsible_ids = list(graph.responsibles.keys())
    primary_options = [EMPTY_RESPONSIBLE_OPTION, *responsible_ids]
    node_kind_options = [
        "process",
        "decision_diamond",
        "decision_card",
        "database",
        "input_data",
        "event",
    ]
    current_primary = draft.responsible or EMPTY_RESPONSIBLE_OPTION

    with st_module.form("graph_source_node_form", clear_on_submit=False):
        title = st_module.text_input(
            "Заголовок карточки",
            value=draft.title,
            key="graph_source_node_title",
        )
        kind = st_module.selectbox(
            "Тип карточки",
            options=node_kind_options,
            index=default_option_index(node_kind_options, draft.kind),
            format_func=lambda value: NODE_KIND_LABELS[value],
            key="graph_source_node_kind",
        )
        col_a, col_b = st_module.columns(2)
        with col_a:
            layout_x = st_module.text_input(
                "X в source layout",
                value=format_layout_float(draft.layout_x),
                key="graph_source_node_layout_x",
            )
            layout_w = st_module.text_input(
                "Ширина карточки",
                value=str(draft.layout_w),
                key="graph_source_node_layout_w",
            )
        with col_b:
            layout_y = st_module.text_input(
                "Y в source layout",
                value=format_layout_float(draft.layout_y),
                key="graph_source_node_layout_y",
            )
            layout_h = st_module.text_input(
                "Высота карточки",
                value=str(draft.layout_h),
                key="graph_source_node_layout_h",
            )
        responsible = st_module.selectbox(
            "Основной ответственный",
            options=primary_options,
            index=default_option_index(primary_options, current_primary),
            format_func=lambda value: (
                "Не задан" if value == EMPTY_RESPONSIBLE_OPTION else graph.responsibles[value].label
            ),
            key="graph_source_node_responsible",
        )
        participants = st_module.multiselect(
            "Участники",
            options=responsible_ids,
            default=list(draft.participants),
            format_func=lambda value: graph.responsibles[value].label,
            key="graph_source_node_participants",
        )
        approvers = st_module.multiselect(
            "Согласующие",
            options=responsible_ids,
            default=list(draft.approvers),
            format_func=lambda value: graph.responsibles[value].label,
            key="graph_source_node_approvers",
        )
        duration = st_module.text_input(
            "Длительность карточки",
            value=draft.duration or "",
            key="graph_source_node_duration",
        )
        note = st_module.text_area(
            "Заметка карточки",
            value=draft.note or "",
            height=80,
            key="graph_source_node_note",
        )
        submitted = st_module.form_submit_button("Сохранить карточку", width="stretch")

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
    layout_values = parse_graph_source_layout_form(
        layout_x=layout_x,
        layout_y=layout_y,
        layout_w=layout_w,
        layout_h=layout_h,
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

    node_ids = [item.id for item in graph.nodes]
    node_map = node_by_id(graph)
    edge_kind_options = list(EDGE_KIND_LABELS.keys())

    with st_module.form(f"{form_key_prefix}_form", clear_on_submit=False):
        source = st_module.selectbox(
            "Откуда",
            options=node_ids,
            index=default_option_index(node_ids, draft.source),
            format_func=lambda value: node_map[value].text,
            key=f"{form_key_prefix}_source",
        )
        target = st_module.selectbox(
            "Куда",
            options=node_ids,
            index=default_option_index(node_ids, draft.target),
            format_func=lambda value: node_map[value].text,
            key=f"{form_key_prefix}_target",
        )
        kind = st_module.selectbox(
            "Тип связи",
            options=edge_kind_options,
            index=default_option_index(edge_kind_options, draft.kind),
            format_func=lambda value: EDGE_KIND_LABELS[value],
            key=f"{form_key_prefix}_kind",
        )
        label = st_module.text_input(
            "Метка связи",
            value=draft.label or "",
            key=f"{form_key_prefix}_label",
        )
        condition = st_module.text_input(
            "Условие",
            value=draft.condition or "",
            key=f"{form_key_prefix}_condition",
        )
        note = st_module.text_area(
            "Заметка связи",
            value=draft.note or "",
            height=80,
            key=f"{form_key_prefix}_note",
        )
        submitted = st_module.form_submit_button(submit_label, width="stretch")

    if not submitted:
        return

    actions.persist_graph_source_edge_update(
        graph,
        UpdateGraphSourceEdgeCommand(
            edge_id=edge.id,
            source=source,
            target=target,
            kind=kind,
            label=normalized_optional_text(label),
            condition=normalized_optional_text(condition),
            note=normalized_optional_text(note),
        ),
    )


def render_related_graph_source_edges_for_node(
    st_module,
    graph: FlowGraphDocument,
    node: FlowNode,
    *,
    actions: AdminActions,
) -> None:
    related_edges = [
        edge
        for edge in graph.edges
        if edge.source == node.id or edge.target == node.id
    ]
    if not related_edges:
        st_module.caption("У карточки пока нет связанных переходов.")
        return

    st_module.caption(
        "Связи этой карточки можно править прямо отсюда, не переключаясь на отдельную линию."
    )
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


def validate_graph_source_node_form(
    *,
    title: str,
    kind: str,
    responsible: str | None,
    participants: list[str],
    approvers: list[str],
) -> str | None:
    if not title.strip():
        return "Заголовок карточки обязателен."

    combined = [
        value
        for value in [responsible, *participants, *approvers]
        if value is not None
    ]
    if len(combined) != len(set(combined)):
        return "Один и тот же ответственный не должен повторяться в карточке."

    if kind in {"process", "decision_diamond", "decision_card"} and not combined:
        return "Для process/decision карточек нужно назначить хотя бы одного ответственного."

    return None


def parse_graph_source_layout_form(
    *,
    layout_x: str,
    layout_y: str,
    layout_w: str,
    layout_h: str,
) -> tuple[float, float, int, int] | str:
    try:
        parsed_x = round(float(layout_x.strip()), 2)
        parsed_y = round(float(layout_y.strip()), 2)
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
        parsed_w = int(layout_w.strip())
        parsed_h = int(layout_h.strip())
    except ValueError:
        return "Размер карточки должен задаваться целыми числами."

    if parsed_w < 80 or parsed_w > 1200:
        return "Ширина карточки должна быть в диапазоне 80-1200."
    if parsed_h < 40 or parsed_h > 800:
        return "Высота карточки должна быть в диапазоне 40-800."
    return parsed_x, parsed_y, parsed_w, parsed_h


def format_layout_float(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
