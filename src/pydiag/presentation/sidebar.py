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
SOURCE_LAYOUT_MODE = "manual"
DATA_CONTROLS_TITLE = "### Схема и данные"
GRAPH_VERSION_LABEL = "Версия схемы"
LIVE_GRAPH_LABEL = "Текущая"
REFRESH_DATA_BUTTON_LABEL = "Обновить данные"
CREATE_VERSION_BUTTON_LABEL = "Создать версию"
IMPORT_ACTUAL_DATA_BUTTON_LABEL = "Импорт json figma"
KIND_FILTER_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
    "figma_text": "Текст Figma",
}


@dataclass(frozen=True)
class SidebarAuthenticatedUser:
    display_name: str
    rights_caption: str


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
    import_live_graph_source_from_raw: Callable[[], None]
    can_materialize_graph_version: bool
    can_import_raw_graph_source: bool
    save_positions_enabled: bool
    graph_versions: list[GraphVersionInfo]
    selected_graph_version_id: str | None
    live_graph_available: bool
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

        st_module.divider()
        render_data_controls_section(
            st_module,
            auth=auth,
            versions=actions.graph_versions,
            selected_version_id=actions.selected_graph_version_id,
            live_available=actions.live_graph_available,
            select_graph_version=actions.select_graph_version,
            materialize_graph_version=actions.materialize_graph_version,
            reload_data=actions.reload_data,
            can_materialize=auth.current_user_is_admin() and actions.can_materialize_graph_version,
            import_live_graph_source_from_raw=actions.import_live_graph_source_from_raw,
            can_import_raw_graph_source=actions.can_import_raw_graph_source,
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
        search, responsible_filter, kind_filter = render_filter_section(
            st_module,
            graph,
        )

        st_module.divider()
        actions.render_legend()

    return SidebarState(
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        layout_mode=SOURCE_LAYOUT_MODE,
        position_edit_enabled=position_edit_enabled,
    )


def build_authenticated_user_state(
    user: Mapping[str, object],
    *,
    is_admin: bool,
    is_super_admin: bool,
) -> SidebarAuthenticatedUser:
    display_name = str(user.get("display_name") or "Пользователь")
    if is_super_admin:
        rights = "Super Admin"
    elif is_admin:
        rights = "Админ"
    else:
        rights = "Пользователь"
    return SidebarAuthenticatedUser(
        display_name=display_name,
        rights_caption=f"Права: {rights}",
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
    is_admin: bool,
    enabled: bool,
    editable: bool,
    save_positions_enabled: bool,
) -> SidebarPositionEditState:
    drag_enabled = editable
    return SidebarPositionEditState(
        visible=is_admin,
        enabled=enabled if is_admin and drag_enabled else False,
        editable=drag_enabled,
        save_disabled=not save_positions_enabled or not drag_enabled,
    )


def render_data_controls_section(
    st_module,
    *,
    auth: SidebarAuthContext,
    versions: list[GraphVersionInfo],
    selected_version_id: str | None,
    live_available: bool,
    select_graph_version: Callable[[str | None], None],
    materialize_graph_version: Callable[[], None],
    reload_data: Callable[[], None],
    import_live_graph_source_from_raw: Callable[[], None],
    can_materialize: bool,
    can_import_raw_graph_source: bool,
) -> None:
    can_import_raw = can_import_raw_graph_source and (
        auth.current_user_is_admin() or not auth.configured_auth_users()
    )
    st_module.markdown(DATA_CONTROLS_TITLE)

    if not live_available and not versions:
        st_module.caption("Схема ещё не загружена. Импортируйте json figma.")
    elif versions or live_available:
        options: list[str] = []
        labels: dict[str, str] = {}
        if live_available:
            options.append(LIVE_GRAPH_OPTION)
            labels[LIVE_GRAPH_OPTION] = LIVE_GRAPH_LABEL
        options.extend(version.id for version in versions)
        labels.update({version.id: version.label for version in versions})
        if selected_version_id and selected_version_id in options:
            selected_option = selected_version_id
        elif live_available:
            selected_option = LIVE_GRAPH_OPTION
        else:
            selected_option = options[0]
        index = options.index(selected_option)
        selected = st_module.selectbox(
            GRAPH_VERSION_LABEL,
            options=options,
            index=index,
            format_func=lambda version_id: labels[version_id],
            key="graph_version_mode",
        )
        next_version_id = None if selected == LIVE_GRAPH_OPTION else selected
        if next_version_id != selected_version_id:
            select_graph_version(next_version_id)

    if st_module.button(REFRESH_DATA_BUTTON_LABEL, width="stretch"):
        reload_data()
    if can_materialize and st_module.button(
        CREATE_VERSION_BUTTON_LABEL,
        width="stretch",
    ):
        materialize_graph_version()
    if can_import_raw and st_module.button(
        IMPORT_ACTUAL_DATA_BUTTON_LABEL,
        width="stretch",
    ):
        import_live_graph_source_from_raw()


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
        st_module.caption(user_state.rights_caption)
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
) -> tuple[str, list[str], list[str]]:
    st_module.markdown("### Фильтры")
    search = st_module.text_input("Поиск", placeholder="узел, скважина, ответственный")
    responsible_filter = st_module.multiselect(
        "Ответственные",
        options=list(graph.responsibles.keys()),
        format_func=lambda key: graph.responsibles[key].label,
        # Distinct from canvas component state field "responsible_filter".
        key="sidebar_responsible_filter",
    )
    kind_filter = st_module.multiselect(
        "Тип узла",
        options=list(KIND_LABELS.keys()),
        format_func=lambda key: KIND_FILTER_LABELS[key],
    )
    return search, responsible_filter, kind_filter


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
        is_admin=auth.current_user_is_admin(),
        enabled=False,
        editable=layout_editable,
        save_positions_enabled=save_positions_enabled,
    )
    if not position_edit_state.visible:
        return False

    if not position_edit_state.editable:
        st_module.session_state["position_edit_enabled"] = False

    st_module.divider()
    st_module.markdown("### Положение")
    if not position_edit_state.editable and layout_edit_block_reason:
        st_module.caption(layout_edit_block_reason)
    position_edit_enabled = st_module.toggle(
        "Редактировать положение",
        key="position_edit_enabled",
        disabled=not position_edit_state.editable,
    )
    position_edit_state = build_position_edit_state(
        is_admin=auth.current_user_is_admin(),
        enabled=position_edit_enabled,
        editable=layout_editable,
        save_positions_enabled=save_positions_enabled,
    )
    if position_edit_state.enabled:
        st_module.caption("Перетащите карточки на схеме — положение сохраняется сразу.")
    return position_edit_state.enabled
