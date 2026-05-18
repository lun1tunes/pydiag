from __future__ import annotations

import hmac
import json
import os
import re
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from html import escape as html_escape
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.layouts import ManualLayout
from streamlit_flow.state import StreamlitFlowState

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
MIN_ADMIN_PASSWORD_LENGTH = 8
AUTH_USERS_ENV = "PYDIAG_AUTH_USERS_JSON"
LEGACY_ADMIN_USERNAME = "admin"
KIND_FILTER_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение (ромб)",
    "decision_card": "Решение (карточка)",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
}


@dataclass(frozen=True)
class AuthUser:
    username: str
    display_name: str
    password: str
    is_admin: bool = True


from pydiag.flow_adapter import (  # noqa: E402
    KIND_LABELS,
    build_streamlit_edges,
    build_streamlit_nodes,
    duration_label,
    flow_canvas_height,
    wells_grouped_by_node,
)
from pydiag.models import (  # noqa: E402
    FlowEdge,
    FlowGraphDocument,
    FlowNode,
    Well,
    WellsDocument,
    node_by_id,
    well_by_id,
)
from pydiag.services import (  # noqa: E402
    create_well,
    delete_well,
    move_well_to_node,
    outgoing_edges,
    rollback_well,
    transition_label,
)
from pydiag.storage import (  # noqa: E402
    FileLockTimeoutError,
    VersionConflictError,
    load_documents,
    save_wells_with_version_check,
    wells_path,
)

st.set_page_config(
    page_title="Планирование и бурение скважин",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                linear-gradient(180deg, rgba(246, 247, 249, 0.98), rgba(246, 247, 249, 1));
        }
        [data-testid="stHeader"],
        .stAppHeader {
            background: transparent !important;
            box-shadow: none !important;
            height: 2.25rem !important;
            min-height: 2.25rem !important;
            pointer-events: none;
        }
        [data-testid="stHeader"] button,
        [data-testid="stHeader"] [role="button"],
        [data-testid="collapsedControl"],
        .stAppHeader button,
        .stAppHeader [role="button"] {
            pointer-events: auto !important;
            visibility: visible !important;
        }
        [data-testid="collapsedControl"] {
            z-index: 1000000 !important;
        }
        [data-testid="stToolbar"] {
            background: transparent !important;
            box-shadow: none !important;
            pointer-events: none;
        }
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapseButton"] {
            display: inline-flex !important;
            pointer-events: auto !important;
            visibility: visible !important;
        }
        [data-testid="stHeaderActionElements"],
        [data-testid="stToolbarActions"],
        [data-testid="stMainMenu"],
        [data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"],
        [data-testid="stDecoration"],
        .stDeployButton {
            display: none !important;
        }
        .block-container {
            max-width: none;
            padding: 2.25rem 1.55rem 2rem;
        }
        [data-testid="stSidebar"] {
            background: #eef2f6;
            border-right: 1px solid rgba(100, 116, 139, 0.18);
        }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
            color: #263244;
        }
        .app-title {
            font-size: 1.65rem;
            line-height: 1.05;
            font-weight: 780;
            letter-spacing: 0;
            color: #0f172a;
            margin: 0 0 0.15rem;
        }
        .app-subtitle {
            color: #526173;
            font-size: 0.94rem;
            margin: 0 0 0.9rem;
        }
        .status-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(120px, 1fr));
            gap: 10px;
            margin: 0.25rem 0 0.85rem;
        }
        .status-cell {
            border-top: 1px solid rgba(100, 116, 139, 0.22);
            padding-top: 9px;
        }
        .status-cell span {
            display: block;
            color: #667085;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .status-cell strong {
            display: block;
            color: #111827;
            font-size: 1.08rem;
            margin-top: 2px;
        }
        .inspector-shell {
            border-top: 1px solid rgba(100, 116, 139, 0.20);
            padding-top: 1rem;
            margin-top: 1rem;
            min-height: auto;
        }
        .muted-line {
            color: #64748b;
            font-size: 0.86rem;
            margin: 0.1rem 0 0.55rem;
        }
        .mini-kv {
            display: grid;
            grid-template-columns: 112px minmax(0, 1fr);
            gap: 7px 10px;
            font-size: 0.88rem;
            margin: 0.65rem 0 0.9rem;
        }
        .mini-kv span:nth-child(odd) {
            color: #64748b;
        }
        .mini-kv span:nth-child(even) {
            color: #111827;
            font-weight: 620;
        }
        .legend-shell {
            display: grid;
            gap: 12px;
            margin: 0.2rem 0 0.8rem;
        }
        .legend-title {
            color: #526173;
            font-size: 0.74rem;
            font-weight: 760;
            letter-spacing: 0.04em;
            margin: 0.1rem 0 0.25rem;
            text-transform: uppercase;
        }
        .legend-list,
        .legend-dept-list {
            display: grid;
            gap: 7px;
        }
        .legend-item,
        .legend-dept {
            display: flex;
            align-items: center;
            gap: 9px;
            min-width: 0;
            color: #263244;
            font-size: 0.84rem;
            line-height: 1.2;
        }
        .legend-item span:last-child,
        .legend-dept-label {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .legend-symbol {
            flex: 0 0 auto;
            width: 38px;
            height: 30px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }
        .legend-symbol-svg {
            width: 38px;
            height: 30px;
            display: block;
            overflow: visible;
        }
        .legend-swatch {
            flex: 0 0 auto;
            width: 20px;
            height: 20px;
            border: 1.6px solid;
            border-radius: 5px;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.55);
        }
        .legend-dept-code {
            margin-left: auto;
            color: #64748b;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.68rem;
        }
        div[data-testid="stButton"] button {
            border-radius: 7px;
            min-height: 2.35rem;
        }
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 7px;
            min-height: 2.35rem;
        }
        div[data-testid="stAlert"] {
            border-radius: 8px;
        }
        @media (max-width: 900px) {
            .status-row {
                grid-template-columns: repeat(2, minmax(120px, 1fr));
            }
            .inspector-shell {
                border-top: 1px solid rgba(100, 116, 139, 0.20);
                padding-top: 1rem;
                min-height: auto;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_app_data(force: bool = False) -> tuple[FlowGraphDocument, WellsDocument]:
    if force or "graph_doc" not in st.session_state or "wells_doc" not in st.session_state:
        graph, wells = load_documents()
        st.session_state.graph_doc = graph
        st.session_state.wells_doc = wells
    return st.session_state.graph_doc, st.session_state.wells_doc


def flash(message: str, level: str = "success") -> None:
    st.session_state.flash = {"message": message, "level": level}


def render_flash() -> None:
    data = st.session_state.pop("flash", None)
    if not data:
        return
    if data["level"] == "error":
        st.error(data["message"])
    elif data["level"] == "warning":
        st.warning(data["message"])
    else:
        st.success(data["message"])


def streamlit_secrets_enabled() -> bool:
    return os.getenv("PYDIAG_DISABLE_STREAMLIT_SECRETS") != "1"


def configured_auth_users() -> dict[str, AuthUser]:
    users: dict[str, AuthUser] = {}
    users.update(auth_users_from_env_json())
    if streamlit_secrets_enabled():
        users.update(auth_users_from_streamlit_secrets())

    legacy_password = configured_admin_password()
    if legacy_password:
        users.setdefault(
            LEGACY_ADMIN_USERNAME,
            AuthUser(
                username=LEGACY_ADMIN_USERNAME,
                display_name=LEGACY_ADMIN_USERNAME,
                password=legacy_password,
            ),
        )
    if insecure_admin_mode_enabled() and not users:
        users[LEGACY_ADMIN_USERNAME] = AuthUser(
            username=LEGACY_ADMIN_USERNAME,
            display_name=LEGACY_ADMIN_USERNAME,
            password="admin",
        )
    return {
        username: user for username, user in users.items() if password_is_allowed(user.password)
    }


def auth_users_from_env_json() -> dict[str, AuthUser]:
    raw = os.getenv(AUTH_USERS_ENV)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return auth_users_from_mapping(payload)


def auth_users_from_streamlit_secrets() -> dict[str, AuthUser]:
    try:
        secrets = st.secrets
        users: dict[str, AuthUser] = {}
        users.update(auth_users_from_mapping(secrets.get("users", {})))
        auth_section = secrets.get("auth", {})
        if isinstance(auth_section, Mapping):
            users.update(auth_users_from_mapping(auth_section.get("users", {})))
        return users
    except Exception:
        return {}


def auth_users_from_mapping(value: object) -> dict[str, AuthUser]:
    if not isinstance(value, Mapping):
        return {}

    users: dict[str, AuthUser] = {}
    for raw_username, raw_config in value.items():
        username = str(raw_username).strip()
        if not username:
            continue

        password: str | None = None
        display_name = username
        is_admin = True
        if isinstance(raw_config, str):
            password = raw_config
        elif isinstance(raw_config, Mapping):
            raw_password = raw_config.get("password")
            if raw_password is not None:
                password = str(raw_password)
            display_name = str(
                raw_config.get("name") or raw_config.get("display_name") or username
            ).strip()
            is_admin = bool(raw_config.get("is_admin", True))

        if not password:
            continue
        users[username] = AuthUser(
            username=username,
            display_name=display_name or username,
            password=password,
            is_admin=is_admin,
        )
    return users


def configured_admin_password() -> str:
    env_value = os.getenv("PYDIAG_ADMIN_PASSWORD")
    if env_value:
        return env_value
    if streamlit_secrets_enabled():
        try:
            secret_value = st.secrets.get("admin_password")
            if secret_value:
                return str(secret_value)
        except Exception:
            pass
    return ""


def insecure_admin_mode_enabled() -> bool:
    return os.getenv("PYDIAG_ALLOW_INSECURE_ADMIN") == "1"


def password_is_allowed(password: str) -> bool:
    return insecure_admin_mode_enabled() or len(password) >= MIN_ADMIN_PASSWORD_LENGTH


def admin_password() -> str:
    configured_password = configured_admin_password()
    if configured_password:
        if password_is_allowed(configured_password):
            return configured_password
        return ""
    if insecure_admin_mode_enabled():
        return "admin"
    return ""


def admin_password_warning() -> str:
    configured_password = configured_admin_password()
    if configured_password and not password_is_allowed(configured_password):
        return (
            f"Админ-пароль должен быть не короче {MIN_ADMIN_PASSWORD_LENGTH} символов. "
            "Для локальной отладки можно явно включить PYDIAG_ALLOW_INSECURE_ADMIN=1."
        )
    return (
        "Админ-пароль не настроен. Задайте PYDIAG_ADMIN_PASSWORD или st.secrets['admin_password']."
    )


def auth_config_warning() -> str:
    if configured_admin_password():
        return admin_password_warning()
    if auth_users_from_env_json() or (
        streamlit_secrets_enabled() and auth_users_from_streamlit_secrets()
    ):
        return (
            f"Пароли пользователей должны быть не короче {MIN_ADMIN_PASSWORD_LENGTH} символов. "
            "Для локальной отладки можно явно включить PYDIAG_ALLOW_INSECURE_ADMIN=1."
        )
    return (
        "Пользователи не настроены. Добавьте их в .streamlit/secrets.toml "
        "в формате [users.<login>] password = '...'."
    )


def authenticate_user(username: str, password: str) -> AuthUser | None:
    user = configured_auth_users().get(username.strip())
    if user is None:
        return None
    if hmac.compare_digest(password, user.password):
        return user
    return None


def current_auth_user() -> dict[str, str | bool] | None:
    user = st.session_state.get("authenticated_user")
    return user if isinstance(user, dict) else None


def current_user_is_admin() -> bool:
    user = current_auth_user()
    if user is not None:
        return bool(user.get("is_admin", False))
    return bool(st.session_state.get("admin_authenticated", False))


def login_user(user: AuthUser) -> None:
    st.session_state.authenticated_user = {
        "username": user.username,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
    }
    st.session_state.admin_authenticated = user.is_admin


def logout_user() -> None:
    st.session_state.pop("authenticated_user", None)
    st.session_state.admin_authenticated = False


def render_sidebar(graph: FlowGraphDocument) -> tuple[str, list[str], list[str], str]:
    with st.sidebar:
        st.markdown("### Доступ")
        authenticated_user = current_auth_user()
        if authenticated_user is not None:
            display_name = str(authenticated_user.get("display_name") or "Пользователь")
            username = str(authenticated_user.get("username") or "")
            st.success(f"Пользователь: {display_name}")
            if username and username != display_name:
                st.caption(f"Логин: {username}")
            if current_user_is_admin():
                st.caption("Режим управления активен")
            if st.button("Выйти", width="stretch"):
                logout_user()
                st.rerun()
        else:
            users = configured_auth_users()
            username = st.text_input(
                "Пользователь",
                disabled=not users,
            )
            password = st.text_input(
                "Пароль",
                type="password",
                disabled=not users,
            )
            if not users:
                st.warning(auth_config_warning())
            if insecure_admin_mode_enabled():
                st.caption("Включен локальный небезопасный пароль: admin")
            if st.button("Войти", width="stretch", disabled=not users):
                user = authenticate_user(username, password)
                if user is not None:
                    login_user(user)
                    st.rerun()
                else:
                    st.error("Неверный пользователь или пароль")

        st.divider()
        st.markdown("### Фильтры")
        search = st.text_input("Поиск", placeholder="узел, скважина, ответственный")
        responsible_filter = st.multiselect(
            "Ответственные",
            options=list(graph.responsibles.keys()),
            format_func=lambda key: graph.responsibles[key].label,
        )
        kind_filter = st.multiselect(
            "Тип узла",
            options=list(KIND_LABELS.keys()),
            format_func=lambda key: KIND_FILTER_LABELS[key],
        )
        layout_mode = st.selectbox(
            "Расположение",
            options=["snake", "manual"],
            format_func=lambda key: {
                "snake": "Змейка",
                "manual": "Координаты из JSON",
            }[key],
        )

        st.divider()
        render_legend(graph)

        st.divider()
        if st.button("Перечитать JSON", width="stretch"):
            load_app_data(force=True)
            flash("JSON-файлы перечитаны")
            st.rerun()

    return search, responsible_filter, kind_filter, layout_mode


def render_legend(graph: FlowGraphDocument) -> None:
    st.markdown("### Легенда")
    st.markdown(legend_html(graph), unsafe_allow_html=True)


def legend_html(graph: FlowGraphDocument) -> str:
    type_rows = [
        ("process", "Процесс"),
        ("decision", "Решение"),
        ("database", "База данных"),
        ("input", "Входные данные"),
        ("event", "Событие"),
    ]
    type_items = "\n".join(
        (f'<div class="legend-item">{legend_type_icon(kind)}<span>{safe_text(label)}</span></div>')
        for kind, label in type_rows
    )
    department_items = "\n".join(
        (
            '<div class="legend-dept">'
            f'<span class="legend-swatch" style="background-color: {style.fill}; '
            f'border-color: {style.border};"></span>'
            f'<span class="legend-dept-label">{safe_text(style.label)}</span>'
            f'<span class="legend-dept-code">{safe_text(key)}</span>'
            "</div>"
        )
        for key, style in graph.responsibles.items()
    )
    return f"""
    <div class="legend-shell">
      <div>
        <div class="legend-title">Типы блоков</div>
        <div class="legend-list">{type_items}</div>
      </div>
      <div>
        <div class="legend-title">Цвета ответственных</div>
        <div class="legend-dept-list">{department_items}</div>
      </div>
    </div>
    """


def legend_type_icon(kind: str) -> str:
    stroke = "#111827"
    fill = "#ffffff"
    icon_by_kind = {
        "process": (
            '<rect x="5" y="6" width="34" height="18" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.7" '
            'vector-effect="non-scaling-stroke"/>'
        ),
        "decision": (
            '<polygon points="22,3 40,15 22,27 4,15" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.7" '
            'stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
        ),
        "database": (
            f'<path d="M8 8 V22 C8 27 36 27 36 22 V8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.7" '
            'vector-effect="non-scaling-stroke"/>'
            f'<ellipse cx="22" cy="8" rx="14" ry="4.8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.7" '
            'vector-effect="non-scaling-stroke"/>'
            f'<path d="M8 22 C8 27 36 27 36 22" fill="none" stroke="{stroke}" '
            'stroke-width="1.2" vector-effect="non-scaling-stroke"/>'
        ),
        "input": (
            '<polygon points="9,6 40,6 35,24 4,24" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.7" '
            'stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
        ),
        "event": (
            '<rect x="6" y="5" width="32" height="20" rx="10" '
            f'fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.7" '
            'vector-effect="non-scaling-stroke"/>'
        ),
    }
    return (
        '<span class="legend-symbol">'
        '<svg class="legend-symbol-svg" viewBox="0 0 44 30" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
        f"{icon_by_kind[kind]}"
        "</svg>"
        "</span>"
    )


def render_header(graph: FlowGraphDocument, wells: WellsDocument) -> None:
    active_wells = [well for well in wells.wells if not well.is_archived]
    busy_nodes = len({well.current_node_id for well in active_wells})
    st.markdown(
        """
        <div class="app-title">Карта планирования и бурения</div>
        <div class="app-subtitle">
        Скважины привязаны к этапам процесса через current_node_id, а переходы разрешаются только по ребрам схемы.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="status-row">
          <div class="status-cell"><span>Узлы</span><strong>{len(graph.nodes)}</strong></div>
          <div class="status-cell"><span>Связи</span><strong>{len(graph.edges)}</strong></div>
          <div class="status-cell"><span>Скважины</span><strong>{len(active_wells)}</strong></div>
          <div class="status-cell"><span>Занятые этапы</span><strong>{busy_nodes}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_flow(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    layout_mode: str,
) -> str | None:
    selected_id = st.session_state.get("selected_id")
    nodes, active_node_ids = build_streamlit_nodes(
        graph=graph,
        wells_doc=wells,
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        selected_id=selected_id,
        layout_mode=layout_mode,
    )
    edges = build_streamlit_edges(
        graph,
        active_node_ids=active_node_ids,
        wells_doc=wells,
        layout_mode=layout_mode,
    )
    flow_state = StreamlitFlowState(
        nodes=nodes,
        edges=edges,
        selected_id=selected_id,
        timestamp=flow_state_timestamp(
            graph=graph,
            wells=wells,
            search=search,
            responsible_filter=responsible_filter,
            kind_filter=kind_filter,
            layout_mode=layout_mode,
        ),
    )

    returned = streamlit_flow(
        "well_drilling_flow",
        flow_state,
        layout=ManualLayout(),
        height=flow_canvas_height(graph, wells, layout_mode),
        fit_view=True,
        show_controls=True,
        show_minimap=True,
        allow_new_edges=False,
        get_node_on_click=True,
        get_edge_on_click=True,
        min_zoom=0.08,
        hide_watermark=True,
        style={
            "backgroundColor": "#f8fafc",
            "border": "1px solid rgba(100, 116, 139, 0.18)",
            "borderRadius": "8px",
        },
    )
    st.session_state.flow_component_timestamp = max(
        int(st.session_state.get("flow_component_timestamp", 0)),
        int(returned.timestamp or 0),
    )
    if returned.selected_id != selected_id:
        st.session_state.selected_id = returned.selected_id
    return returned.selected_id


def flow_state_timestamp(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    layout_mode: str,
) -> int:
    signature = (
        graph.version,
        wells.version,
        tuple((well.id, well.current_node_id, well.is_archived) for well in wells.wells),
        search.strip().casefold(),
        tuple(responsible_filter),
        tuple(kind_filter),
        layout_mode,
    )
    if st.session_state.get("flow_view_signature") != signature:
        previous = int(st.session_state.get("flow_state_timestamp", 0))
        component_timestamp = int(st.session_state.get("flow_component_timestamp", 0))
        st.session_state.flow_view_signature = signature
        st.session_state.flow_state_timestamp = max(
            previous + 1,
            component_timestamp + 1,
            int(time.time() * 1000),
        )
    return int(st.session_state.flow_state_timestamp)


def resolve_selection(
    selected_id: str | None,
    graph: FlowGraphDocument,
    wells: WellsDocument,
) -> tuple[str, FlowNode | FlowEdge | Well | None]:
    if not selected_id:
        return "none", None

    nodes = node_by_id(graph)
    wells_map = well_by_id(wells)
    edges = {edge.id: edge for edge in graph.edges}
    if selected_id.startswith("route::"):
        edge_id, separator, _segment = selected_id.removeprefix("route::").rpartition("::")
        if separator and edge_id in edges:
            return ("edge", edges[edge_id])

    if selected_id.startswith("well::"):
        well_id = selected_id.removeprefix("well::")
        return ("well", wells_map.get(well_id))
    if selected_id.startswith("well-extra::"):
        node_id = selected_id.removeprefix("well-extra::")
        return ("node", nodes.get(node_id))
    if selected_id in nodes:
        return ("node", nodes[selected_id])
    if selected_id in edges:
        return ("edge", edges[selected_id])
    return "none", None


def render_inspector(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
) -> None:
    st.markdown('<div class="inspector-shell">', unsafe_allow_html=True)
    st.markdown("### Инспектор")
    selection_kind, selected = resolve_selection(selected_id, graph, wells)

    if selection_kind == "node" and selected is not None:
        render_node_details(graph, wells, selected)
    elif selection_kind == "well" and selected is not None:
        render_well_details(graph, selected)
    elif selection_kind == "edge" and selected is not None:
        render_edge_details(graph, selected)
    else:
        st.info("Выберите узел, связь или фишку скважины на схеме.")
        render_overview_tables(graph, wells)

    if current_user_is_admin():
        st.divider()
        render_admin_panel(graph, wells, selected_id)

    st.markdown("</div>", unsafe_allow_html=True)


def render_node_details(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    node: FlowNode,
) -> None:
    wells_here = [
        well for well in wells.wells if well.current_node_id == node.id and not well.is_archived
    ]
    responsible_label = node_responsible_labels(graph, node)
    time_label = duration_label(node.time) if node.time is not None else "не задано"

    st.markdown(f"#### {node.text}")
    st.markdown(
        f'<p class="muted-line">{safe_text(KIND_LABELS[node.kind])} · {safe_text(node.id)}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="mini-kv">
          <span>Тип</span><span>{safe_text(node.kind)}</span>
          <span>Ответственные</span><span>{responsible_label}</span>
          <span>Время</span><span>{safe_text(time_label)}</span>
          <span>Скважины</span><span>{len(wells_here)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if wells_here:
        st.markdown("##### Скважины на этапе")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "id": well.id,
                        "name": well.name,
                        "field": well.metadata.get("field", ""),
                        "rig": well.metadata.get("rig", ""),
                    }
                    for well in wells_here
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    transitions = outgoing_edges(graph, node.id)
    if transitions:
        st.markdown("##### Доступные переходы")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "тип": edge.kind,
                        "метка": edge.label or "",
                        "куда": node_by_id(graph)[edge.target].text,
                    }
                    for edge in transitions
                ]
            ),
            width="stretch",
            hide_index=True,
        )


def node_responsible_labels(graph: FlowGraphDocument, node: FlowNode) -> str:
    if not node.responsible:
        return "нет"
    labels = [
        graph.responsibles[responsible].label if responsible in graph.responsibles else responsible
        for responsible in node.responsible
    ]
    return safe_text(", ".join(labels))


def render_well_details(graph: FlowGraphDocument, well: Well) -> None:
    nodes = node_by_id(graph)
    current_node = nodes[well.current_node_id]
    st.markdown(f"#### {well.name}")
    st.markdown(f'<p class="muted-line">{safe_text(well.id)}</p>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="mini-kv">
          <span>Текущий этап</span><span>{safe_text(current_node.text)}</span>
          <span>Поле</span><span>{safe_text(well.metadata.get("field", "не задано"))}</span>
          <span>Буровая</span><span>{safe_text(well.metadata.get("rig", "не задано"))}</span>
          <span>История</span><span>{len(well.history)} записей</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if well.history:
        st.markdown("##### Журнал")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ts": item.ts.strftime("%Y-%m-%d %H:%M"),
                        "action": item.action,
                        "node": nodes[item.node_id].text if item.node_id in nodes else item.node_id,
                        "by": item.by or "",
                        "comment": item.comment or "",
                    }
                    for item in reversed(well.history)
                ]
            ),
            width="stretch",
            hide_index=True,
        )


def render_edge_details(graph: FlowGraphDocument, edge: FlowEdge) -> None:
    nodes = node_by_id(graph)
    st.markdown(f"#### {edge.label or edge.kind}")
    st.markdown(f'<p class="muted-line">{safe_text(edge.id)}</p>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="mini-kv">
          <span>Тип</span><span>{safe_text(edge.kind)}</span>
          <span>Откуда</span><span>{safe_text(nodes[edge.source].text)}</span>
          <span>Куда</span><span>{safe_text(nodes[edge.target].text)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview_tables(graph: FlowGraphDocument, wells: WellsDocument) -> None:
    grouped = wells_grouped_by_node(wells)
    top_rows = []
    for node in graph.nodes:
        count = len(grouped.get(node.id, []))
        if count:
            top_rows.append({"этап": node.text, "скважин": count})
    if top_rows:
        st.markdown("##### Распределение")
        st.dataframe(pd.DataFrame(top_rows), width="stretch", hide_index=True)


def safe_text(value: object) -> str:
    return html_escape(str(value))


def render_admin_panel(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    selected_id: str | None,
) -> None:
    st.markdown("### Панель управления")
    selected_kind, selected = resolve_selection(selected_id, graph, wells)
    default_well_id = (
        selected.id if selected_kind == "well" and isinstance(selected, Well) else None
    )
    default_node_id = (
        selected.id if selected_kind == "node" and selected is not None else graph.nodes[0].id
    )

    with st.expander("Переместить или откатить скважину", expanded=True):
        active_wells = [well for well in wells.wells if not well.is_archived]
        if not active_wells:
            st.caption("Активных скважин пока нет.")
        else:
            well_ids = [well.id for well in active_wells]
            default_index = well_ids.index(default_well_id) if default_well_id in well_ids else 0
            well_id = st.selectbox(
                "Скважина",
                options=well_ids,
                index=default_index,
                format_func=lambda item: well_by_id(wells)[item].name,
                key="admin_well_id",
            )
            current_well = well_by_id(wells)[well_id]
            current_node = node_by_id(graph)[current_well.current_node_id]
            st.caption(f"Сейчас: {current_node.text}")

            transitions = outgoing_edges(graph, current_well.current_node_id)
            transition_ids = [edge.id for edge in transitions]
            selected_edge_id = st.selectbox(
                "Переход",
                options=transition_ids,
                format_func=lambda edge_id: transition_label(
                    next(edge for edge in transitions if edge.id == edge_id),
                    graph,
                ),
                disabled=not transitions,
                key="admin_transition_id",
            )
            comment = st.text_area("Комментарий", height=68, key="admin_comment")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(
                    "Продвинуть",
                    disabled=not transitions,
                    width="stretch",
                ):
                    edge = next(edge for edge in transitions if edge.id == selected_edge_id)
                    persist_wells_update(
                        move_well_to_node(
                            graph,
                            wells,
                            well_id=well_id,
                            target_node_id=edge.target,
                            actor="local-admin",
                            comment=comment or None,
                        ),
                        graph=graph,
                        expected_version=wells.version,
                        success_message="Скважина переведена на следующий этап",
                    )
            with col_b:
                if st.button(
                    "Откатить",
                    disabled=len(current_well.history) < 2,
                    width="stretch",
                ):
                    persist_wells_update(
                        rollback_well(
                            wells,
                            well_id=well_id,
                            actor="local-admin",
                            comment=comment or None,
                        ),
                        graph=graph,
                        expected_version=wells.version,
                        success_message="Скважина откатилась на предыдущий этап",
                    )

            confirm_delete = st.checkbox("Подтвердить удаление", key="confirm_delete")
            if st.button(
                "Удалить скважину",
                disabled=not confirm_delete,
                width="stretch",
            ):
                persist_wells_update(
                    delete_well(wells, well_id),
                    graph=graph,
                    expected_version=wells.version,
                    success_message="Скважина удалена",
                )

    with st.expander("Добавить скважину", expanded=False):
        with st.form("create_well_form", clear_on_submit=False):
            suggested_id = suggest_well_id(wells)
            well_id = st.text_input("ID", value=suggested_id)
            name = st.text_input("Название", value=suggested_id.replace("well_", "Скв. "))
            start_node_id = st.selectbox(
                "Начальный этап",
                options=[node.id for node in graph.nodes],
                index=[node.id for node in graph.nodes].index(default_node_id)
                if default_node_id in [node.id for node in graph.nodes]
                else 0,
                format_func=lambda node_id: node_by_id(graph)[node_id].text,
            )
            field = st.text_input("Месторождение / куст")
            rig = st.text_input("Буровая")
            comment = st.text_area("Комментарий", height=68)
            submitted = st.form_submit_button("Создать", width="stretch")

        if submitted:
            normalized_well_id = well_id.strip()
            normalized_name = name.strip()
            if not re.fullmatch(r"[A-Za-z0-9_.:-]+", normalized_well_id):
                st.error("ID должен состоять из латиницы, цифр, _, ., :, -")
            elif not normalized_name:
                st.error("Название скважины обязательно.")
            else:
                metadata = {
                    key: value
                    for key, value in {"field": field.strip(), "rig": rig.strip()}.items()
                    if value
                }
                persist_wells_update(
                    create_well(
                        graph,
                        wells,
                        well_id=normalized_well_id,
                        name=normalized_name,
                        start_node_id=start_node_id,
                        actor="local-admin",
                        metadata=metadata,
                        comment=comment or None,
                    ),
                    graph=graph,
                    expected_version=wells.version,
                    success_message="Скважина создана",
                )


def persist_wells_update(
    updated: WellsDocument,
    graph: FlowGraphDocument,
    expected_version: int,
    success_message: str,
) -> None:
    try:
        saved = save_wells_with_version_check(
            updated,
            expected_version=expected_version,
            path=wells_path(),
            graph=graph,
        )
        st.session_state.wells_doc = saved
        flash(success_message)
        st.rerun()
    except VersionConflictError as exc:
        try:
            load_app_data(force=True)
        except Exception:
            pass
        flash(
            f"Данные уже изменились другим пользователем. Состояние перечитано: {exc}",
            "warning",
        )
        st.rerun()
    except FileLockTimeoutError as exc:
        flash(
            f"Файл состояния сейчас занят другой операцией. Повторите действие: {exc}",
            "warning",
        )
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def suggest_well_id(wells: WellsDocument) -> str:
    max_number = 1000
    for well in wells.wells:
        match = re.search(r"(\d+)$", well.id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"well_{max_number + 1}"


def main() -> None:
    inject_css()
    render_flash()
    try:
        graph, wells = load_app_data()
    except Exception as exc:
        st.error(f"Ошибка загрузки JSON: {exc}")
        st.stop()

    search, responsible_filter, kind_filter, layout_mode = render_sidebar(graph)
    render_header(graph, wells)

    selected_id = render_flow(
        graph,
        wells,
        search=search,
        responsible_filter=responsible_filter,
        kind_filter=kind_filter,
        layout_mode=layout_mode,
    )
    with st.expander(
        "Инспектор и управление",
        expanded=bool(selected_id) or current_user_is_admin(),
    ):
        render_inspector(graph, wells, selected_id)


if __name__ == "__main__":
    main()
