from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from pydiag.common.graph_versions import GraphVersionInfo
from pydiag.domain.models import FlowGraphDocument
from pydiag.rendering.flow_node_rendering import KIND_LABELS

__all__ = [
    "KIND_FILTER_LABELS",
    "SidebarActions",
    "SidebarAuthContext",
    "SidebarState",
    "render_sidebar",
]

LIVE_GRAPH_OPTION = "__live__"
KIND_FILTER_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение (ромб)",
    "decision_card": "Решение (карточка)",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
    "figma_text": "Текст Figma",
}
LAYOUT_MODE_LABELS = {
    "snake": "Змейка",
    "manual": "Координаты из source",
}


@dataclass(frozen=True)
class SidebarAuthenticatedUser:
    display_name: str
    username_caption: str | None
    show_admin_caption: bool
    show_super_admin_caption: bool


@dataclass(frozen=True)
class SidebarLoginState:
    users_configured: bool
    warning_message: str | None
    insecure_caption: str | None


@dataclass(frozen=True)
class SidebarPositionEditState:
    visible: bool
    enabled: bool
    editable: bool
    helper_caption: str | None
    save_disabled: bool


@dataclass(frozen=True)
class SidebarState:
    search: str
    responsible_filter: list[str]
    kind_filter: list[str]
    layout_mode: str
    position_edit_enabled: bool


@dataclass(frozen=True)
class SidebarActions:
    render_legend: Callable[[], None]
    save_positions: Callable[[], None]
    reset_positions: Callable[[], None]
    reload_data: Callable[[], None]
    select_graph_version: Callable[[str | None], None]
    materialize_graph_version: Callable[[], None]
    can_materialize_graph_version: bool
    save_positions_enabled: bool
    graph_versions: list[GraphVersionInfo]
    selected_graph_version_id: str | None
    layout_editable: bool
    layout_edit_block_reason: str | None


class SidebarAuthContext(Protocol):
    def current_auth_user(self) -> dict[str, str | bool] | None: ...
    def current_user_is_admin(self) -> bool: ...
    def current_user_is_super_admin(self) -> bool: ...
    def configured_auth_users(self) -> dict[str, object]: ...
    def authenticate_user(self, username: str, password: str) -> object | None: ...
    def login_user(self, user: object) -> None: ...
    def logout_user(self) -> None: ...
    def auth_config_warning(self) -> str: ...
    def insecure_admin_mode_enabled(self) -> bool: ...


def render_sidebar(
    st_module,
    graph: FlowGraphDocument,
    *,
    auth: SidebarAuthContext,
    actions: SidebarActions,
):
    with st_module.sidebar:
        render_access_section(st_module, auth=auth)

        if actions.graph_versions or auth.current_user_is_admin():
            st_module.divider()
            render_graph_version_section(
                st_module,
                versions=actions.graph_versions,
                selected_version_id=actions.selected_graph_version_id,
                select_graph_version=actions.select_graph_version,
                materialize_graph_version=actions.materialize_graph_version,
                can_materialize=(
                    auth.current_user_is_admin() and actions.can_materialize_graph_version
                ),
            )

        st_module.divider()
        search, responsible_filter, kind_filter, layout_mode = render_filter_section(
            st_module,
            graph,
        )

        position_edit_enabled = render_layout_section(
            st_module,
            auth=auth,
            save_positions_enabled=actions.save_positions_enabled,
            save_positions=actions.save_positions,
            reset_positions=actions.reset_positions,
            layout_editable=actions.layout_editable,
            layout_edit_block_reason=actions.layout_edit_block_reason,
        )

        st_module.divider()
        actions.render_legend()

        st_module.divider()
        if st_module.button("Перечитать данные", width="stretch"):
            actions.reload_data()

    return SidebarState(
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        layout_mode=layout_mode,
        position_edit_enabled=position_edit_enabled,
    )


def build_authenticated_user_state(
    user: Mapping[str, object],
    *,
    is_admin: bool,
    is_super_admin: bool,
) -> SidebarAuthenticatedUser:
    display_name = str(user.get("display_name") or "Пользователь")
    username = str(user.get("username") or "")
    return SidebarAuthenticatedUser(
        display_name=display_name,
        username_caption=f"Логин: {username}" if username and username != display_name else None,
        show_admin_caption=is_admin,
        show_super_admin_caption=is_super_admin,
    )


def build_login_state(
    *,
    users_configured: bool,
    warning_message: str,
    insecure_admin_mode_enabled: bool,
) -> SidebarLoginState:
    return SidebarLoginState(
        users_configured=users_configured,
        warning_message=None if users_configured else warning_message,
        insecure_caption=(
            "Включен локальный небезопасный пароль: admin" if insecure_admin_mode_enabled else None
        ),
    )


def build_position_edit_state(
    *,
    is_super_admin: bool,
    enabled: bool,
    editable: bool,
    save_positions_enabled: bool,
    block_reason: str | None,
) -> SidebarPositionEditState:
    helper_caption = None
    if is_super_admin and not editable:
        helper_caption = block_reason
    elif is_super_admin and enabled:
        helper_caption = (
            "Перетаскивание активно только для карточек схемы. Фишки скважин не двигаются."
        )
    return SidebarPositionEditState(
        visible=is_super_admin,
        enabled=enabled if is_super_admin and editable else False,
        editable=editable,
        helper_caption=helper_caption,
        save_disabled=not save_positions_enabled,
    )


def render_graph_version_section(
    st_module,
    *,
    versions: list[GraphVersionInfo],
    selected_version_id: str | None,
    select_graph_version: Callable[[str | None], None],
    materialize_graph_version: Callable[[], None],
    can_materialize: bool,
) -> None:
    if not versions and not can_materialize:
        return

    st_module.markdown("### Версия source")
    options = [LIVE_GRAPH_OPTION, *(version.id for version in versions)]
    labels = {
        LIVE_GRAPH_OPTION: "Текущий source YAML",
        **{version.id: version.label for version in versions},
    }
    selected_option = selected_version_id or LIVE_GRAPH_OPTION
    index = options.index(selected_option) if selected_option in options else 0
    selected = st_module.selectbox(
        "Режим просмотра",
        options=options,
        index=index,
        format_func=lambda version_id: labels[version_id],
    )
    next_version_id = None if selected == LIVE_GRAPH_OPTION else selected
    if next_version_id != selected_version_id:
        select_graph_version(next_version_id)

    if next_version_id is None:
        st_module.caption("Live режим: layout сохраняется обратно в source YAML.")
    else:
        st_module.caption("Архивная версия source YAML доступна только для просмотра.")

    if can_materialize and st_module.button(
        "Сохранить версию source YAML",
        width="stretch",
    ):
        materialize_graph_version()


def render_access_section(st_module, *, auth: SidebarAuthContext) -> None:
    st_module.markdown("### Доступ")
    authenticated_user = auth.current_auth_user()
    if authenticated_user is not None:
        user_state = build_authenticated_user_state(
            authenticated_user,
            is_admin=auth.current_user_is_admin(),
            is_super_admin=auth.current_user_is_super_admin(),
        )
        st_module.success(f"Пользователь: {user_state.display_name}")
        if user_state.username_caption is not None:
            st_module.caption(user_state.username_caption)
        if user_state.show_admin_caption:
            st_module.caption("Режим управления активен")
        if user_state.show_super_admin_caption:
            st_module.caption("Роль: super_admin")
        if st_module.button("Выйти", width="stretch"):
            auth.logout_user()
            st_module.rerun()
        return

    users = auth.configured_auth_users()
    login_state = build_login_state(
        users_configured=bool(users),
        warning_message=auth.auth_config_warning(),
        insecure_admin_mode_enabled=auth.insecure_admin_mode_enabled(),
    )
    username = st_module.text_input(
        "Пользователь",
        disabled=not login_state.users_configured,
    )
    password = st_module.text_input(
        "Пароль",
        type="password",
        disabled=not login_state.users_configured,
    )
    if login_state.warning_message is not None:
        st_module.warning(login_state.warning_message)
    if login_state.insecure_caption is not None:
        st_module.caption(login_state.insecure_caption)
    if st_module.button("Войти", width="stretch", disabled=not login_state.users_configured):
        user = auth.authenticate_user(username, password)
        if user is not None:
            auth.login_user(user)
            st_module.rerun()
        else:
            st_module.error("Неверный пользователь или пароль")


def render_filter_section(
    st_module,
    graph: FlowGraphDocument,
) -> tuple[str, list[str], list[str], str]:
    st_module.markdown("### Фильтры")
    search = st_module.text_input("Поиск", placeholder="узел, скважина, ответственный")
    responsible_filter = st_module.multiselect(
        "Ответственные",
        options=list(graph.responsibles.keys()),
        format_func=lambda key: graph.responsibles[key].label,
    )
    kind_filter = st_module.multiselect(
        "Тип узла",
        options=list(KIND_LABELS.keys()),
        format_func=lambda key: KIND_FILTER_LABELS[key],
    )
    layout_mode = st_module.selectbox(
        "Расположение",
        options=list(LAYOUT_MODE_LABELS.keys()),
        format_func=lambda key: LAYOUT_MODE_LABELS[key],
    )
    return search, responsible_filter, kind_filter, layout_mode


def render_layout_section(
    st_module,
    *,
    auth: SidebarAuthContext,
    save_positions_enabled: bool,
    save_positions: Callable[[], None],
    reset_positions: Callable[[], None],
    layout_editable: bool,
    layout_edit_block_reason: str | None,
) -> bool:
    position_edit_state = build_position_edit_state(
        is_super_admin=auth.current_user_is_super_admin(),
        enabled=False,
        editable=layout_editable,
        save_positions_enabled=save_positions_enabled,
        block_reason=layout_edit_block_reason,
    )
    if not position_edit_state.visible:
        return False

    if not layout_editable:
        st_module.session_state["position_edit_enabled"] = False

    st_module.divider()
    st_module.markdown("### Layout")
    position_edit_enabled = st_module.toggle(
        "Редактировать положение",
        key="position_edit_enabled",
        disabled=not layout_editable,
        help="Перетаскивайте карточки на схеме; связи перестраиваются после отпускания блока.",
    )
    position_edit_state = build_position_edit_state(
        is_super_admin=True,
        enabled=position_edit_enabled,
        editable=layout_editable,
        save_positions_enabled=save_positions_enabled,
        block_reason=layout_edit_block_reason,
    )
    if position_edit_state.helper_caption is not None:
        st_module.caption(position_edit_state.helper_caption)
    if position_edit_state.enabled:
        col_a, col_b = st_module.columns(2)
        with col_a:
            if st_module.button(
                "Сохранить",
                width="stretch",
                disabled=position_edit_state.save_disabled,
            ):
                save_positions()
        with col_b:
            if st_module.button("Сбросить", width="stretch"):
                reset_positions()
    return position_edit_state.enabled
