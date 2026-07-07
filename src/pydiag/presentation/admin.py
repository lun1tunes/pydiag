from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydiag.application import WellAdminService
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


@dataclass(frozen=True)
class AdminActions:
    resolve_selection: Callable[
        [str | None, FlowGraphDocument, WellsDocument],
        tuple[str, FlowNode | FlowEdge | Well | None],
    ]
    persist_wells_update: Callable[..., None]


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

    with st_module.expander("Переместить или откатить скважину", expanded=True):
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
            )
            current_well = well_by_id(wells)[well_id]
            current_node = node_by_id(graph)[current_well.current_node_id]
            st_module.caption(f"Сейчас: {current_node.text}")

            transition_ids = transition_ids_for_well(graph, current_well)
            selected_edge_id = st_module.selectbox(
                "Переход",
                options=transition_ids,
                format_func=lambda edge_id: transition_option_label(graph, current_well, edge_id),
                disabled=not transition_ids,
                key="admin_transition_id",
            )
            comment = st_module.text_area("Комментарий", height=68, key="admin_comment")

            col_a, col_b = st_module.columns(2)
            with col_a:
                if st_module.button(
                    "Продвинуть",
                    disabled=not transition_ids,
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
                    disabled=len(current_well.history) < 2,
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

            confirm_delete = st_module.checkbox("Подтвердить удаление", key="confirm_delete")
            if st_module.button(
                "Удалить скважину",
                disabled=not confirm_delete,
                width="stretch",
            ):
                actions.persist_wells_update(
                    service.delete_well(well_id=well_id),
                    graph=graph,
                    expected_version=wells.version,
                    success_message="Скважина удалена",
                )

    with st_module.expander("Добавить скважину", expanded=False):
        with st_module.form("create_well_form", clear_on_submit=False):
            suggested_id = suggest_well_id(wells)
            well_id = st_module.text_input("ID", value=suggested_id)
            name = st_module.text_input("Название", value=suggested_id.replace("well_", "Скв. "))
            node_ids = [node.id for node in graph.nodes]
            start_node_id = st_module.selectbox(
                "Начальный этап",
                options=node_ids,
                index=default_option_index(node_ids, defaults.default_node_id),
                format_func=lambda node_id: node_by_id(graph)[node_id].text,
            )
            field = st_module.text_input("Месторождение / куст")
            rig = st_module.text_input("Буровая")
            comment = st_module.text_area("Комментарий", height=68)
            submitted = st_module.form_submit_button("Создать", width="stretch")

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
