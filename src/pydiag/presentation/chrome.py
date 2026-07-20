from __future__ import annotations

from dataclasses import dataclass

from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.presentation.html_utils import safe_text

__all__ = [
    "APP_CSS",
    "CLIPBOARD_SHORTCUT_GUARD_HTML",
    "build_header_model",
    "build_legend_model",
    "inject_css",
    "install_clipboard_shortcut_guard",
    "legend_html",
    "legend_type_icon",
    "render_header",
    "render_legend",
]

HEADER_TITLE = "Схема планирования и строительства скважин"
HEADER_SUBTITLE = (
    "Скважины привязаны к этапам процесса через current_node_id, "
    "а переходы разрешаются только по ребрам схемы."
)
LEGEND_KIND_TITLE = "Типы блоков"
LEGEND_RESPONSIBLE_TITLE = "Цвета ответственных"
LEGEND_TYPE_ITEMS = (
    ("process", "Процесс"),
    ("decision", "Решение"),
    ("database", "База данных"),
    ("input", "Входные данные"),
    ("event", "Событие"),
)
APP_CSS = """
<style>
:root {
    /* Compact density profile. Tweak these tokens to relax or tighten the whole UI. */
    --app-page-pad-top: 0.32rem;
    --app-page-pad-x: 1.2rem;
    --app-page-pad-bottom: 0.5rem;
    --app-sidebar-pad-top: 0.18rem;
    --app-stack-gap: 0.42rem;
    --app-stack-gap-sidebar: 0.3rem;
    --app-divider-gap: 0.4rem;
    --app-paragraph-gap-top: 0.05rem;
    --app-paragraph-gap-bottom: 0.26rem;
    --app-expander-gap-top: 0.08rem;
    --app-expander-gap-bottom: 0.14rem;
    --app-title-gap: 0.12rem;
    --app-subtitle-gap: 0.5rem;
    --app-status-gap-top: 0.16rem;
    --app-status-gap-bottom: 0.44rem;
    --app-status-pad-top: 6px;
    --app-muted-gap-bottom: 0.18rem;
    --app-kv-gap-top: 0.18rem;
    --app-kv-gap-bottom: 0.28rem;
    --app-legend-gap-top: 0.12rem;
    --app-legend-gap-bottom: 0.36rem;
    --app-control-height: 2rem;
    --app-alert-gap: 0.05rem;
    --app-mobile-inspector-gap: 0.75rem;
    --app-inspector-stack-gap: 0.42rem;
    --app-inspector-form-gap: 0.22rem;
    --app-inspector-control-height: 1.7rem;
}
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
[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],
.stDeployButton {
    display: none !important;
}
/* Clipboard shortcut guard iframe: must be non-zero for st.iframe, but invisible. */
iframe[title="st.iframe"],
[data-testid="stIFrame"] {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
    border: 0 !important;
}
.block-container {
    max-width: none;
    padding: var(--app-page-pad-top) var(--app-page-pad-x) var(--app-page-pad-bottom);
}
div[data-testid="stVerticalBlock"] {
    gap: var(--app-stack-gap);
}
[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
    gap: var(--app-stack-gap-sidebar);
}
.stApp hr {
    margin: var(--app-divider-gap) 0;
}
div[data-testid="stMarkdownContainer"] p {
    margin: var(--app-paragraph-gap-top) 0 var(--app-paragraph-gap-bottom);
}
div[data-testid="stExpander"] {
    margin: var(--app-expander-gap-top) 0 var(--app-expander-gap-bottom);
}
[data-testid="stSidebar"] {
    background: #eef2f6;
    border-right: 1px solid rgba(100, 116, 139, 0.18);
}
[data-testid="stSidebarContent"] {
    padding-top: 0 !important;
}
[data-testid="stSidebarUserContent"] {
    padding-top: var(--app-sidebar-pad-top) !important;
}
[data-testid="stSidebar"] .block-container {
    padding-top: var(--app-sidebar-pad-top);
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
    margin: 0 0 var(--app-title-gap);
}
.app-subtitle {
    color: #526173;
    font-size: 0.94rem;
    margin: 0 0 var(--app-subtitle-gap);
}
.status-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(120px, 1fr));
    gap: 10px;
    margin: var(--app-status-gap-top) 0 var(--app-status-gap-bottom);
}
.status-cell {
    border-top: 1px solid rgba(100, 116, 139, 0.22);
    padding-top: var(--app-status-pad-top);
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
.inspector-kicker {
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin: 0;
    padding: 0 0 0.12rem;
}
.inspector-entity {
    color: #111827;
    font-size: 1.02rem;
    font-weight: 700;
    line-height: 1.25;
    margin: 0 !important;
    padding: 0 0 0.1rem;
}
.inspector-sub {
    color: #64748b;
    font-size: 0.78rem;
    margin: 0 !important;
    padding: 0.04rem 0 0.28rem;
}
.inspector-status {
    color: #64748b;
    font-size: 0.76rem;
    margin: 0 !important;
    padding: 0 0 0.28rem;
}
.inspector-section-label {
    color: #526173;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    /* padding (not margin): Streamlit markdown parents collapse margins and
       let section titles paint over the previous block. */
    margin: 0 !important;
    padding: 0.85rem 0 0.4rem;
}
/*
 * Inspector density (Streamlit 1.57+):
 * bordered panels use stLayoutWrapper; forms set gap via emotion (spacing.lg).
 * Keep the panel readable: only forms get ultra-tight field spacing.
 */
[data-testid="stLayoutWrapper"] [data-testid="stVerticalBlock"] {
    gap: var(--app-inspector-stack-gap) !important;
}
[data-testid="stForm"] {
    padding: 0.45rem 0.55rem !important;
}
[data-testid="stForm"] [data-testid="stVerticalBlock"] {
    gap: var(--app-inspector-form-gap) !important;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
    gap: 0.35rem !important;
}
[data-testid="stForm"] [data-testid="stElementContainer"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
/*
 * Height-limited inspector panels use a flex column. Streamlit element
 * containers default to flex-shrink:1, and markdown containers get a negative
 * bottom margin from emotion CSS — both crush blocks so titles paint over
 * neighbors. Force natural height and kill the negative margin.
 */
[data-testid="stLayoutWrapper"] [data-testid="stElementContainer"] {
    flex-shrink: 0 !important;
    height: auto !important;
    min-height: fit-content !important;
    overflow: visible !important;
}
[data-testid="stLayoutWrapper"] [data-testid="stElementContainer"]:has(.stMarkdown),
[data-testid="stLayoutWrapper"] .stMarkdown,
[data-testid="stLayoutWrapper"] [data-testid="stMarkdownContainer"] {
    display: flow-root;
    height: auto !important;
    min-height: fit-content !important;
    overflow: visible;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
[data-testid="stForm"] div[data-testid="stMarkdownContainer"] p {
    margin: 0.02rem 0 0.06rem;
}
[data-testid="stLayoutWrapper"] .mini-kv {
    margin: 0 !important;
    padding: 0.2rem 0 0.35rem;
}
[data-testid="stLayoutWrapper"] div[data-testid="stCaptionContainer"],
[data-testid="stLayoutWrapper"] [data-testid="stCaption"],
[data-testid="stForm"] div[data-testid="stCaptionContainer"],
[data-testid="stForm"] [data-testid="stCaption"] {
    margin-top: 0 !important;
    margin-bottom: 0.2rem !important;
}
[data-testid="stLayoutWrapper"] div[data-testid="stTabs"] {
    margin-top: 0.2rem;
}
[data-testid="stLayoutWrapper"] div[data-testid="stButton"] button,
[data-testid="stLayoutWrapper"] div[data-testid="stFormSubmitButton"] button,
[data-testid="stForm"] div[data-testid="stButton"] button,
[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
    min-height: var(--app-inspector-control-height);
}
[data-testid="stForm"] div[data-testid="stTextInput"],
[data-testid="stForm"] div[data-testid="stSelectbox"],
[data-testid="stForm"] div[data-testid="stMultiSelect"],
[data-testid="stForm"] div[data-testid="stTextArea"],
[data-testid="stForm"] div[data-testid="stCheckbox"],
[data-testid="stForm"] div[data-testid="stNumberInput"] {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
[data-testid="stForm"] label[data-testid="stWidgetLabel"] {
    margin-bottom: 0.02rem !important;
    min-height: 0 !important;
    padding-bottom: 0 !important;
}
[data-testid="stLayoutWrapper"] [data-testid="InputInstructions"],
[data-testid="stForm"] [data-testid="InputInstructions"] {
    display: none !important;
}
[data-testid="stLayoutWrapper"] div[data-testid="stExpander"],
[data-testid="stForm"] div[data-testid="stExpander"] {
    margin: 0.12rem 0 0.16rem;
}
.muted-line {
    color: #64748b;
    font-size: 0.8rem;
    margin: 0.04rem 0 var(--app-muted-gap-bottom);
}
.mini-kv {
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr);
    gap: 4px 8px;
    font-size: 0.82rem;
    line-height: 1.35;
    margin: 0;
    padding: var(--app-kv-gap-top) 0 var(--app-kv-gap-bottom);
}
.mini-kv span:nth-child(odd) {
    color: #64748b;
}
.mini-kv span:nth-child(even) {
    color: #111827;
    font-weight: 600;
}
.legend-shell {
    display: grid;
    gap: 12px;
    margin: var(--app-legend-gap-top) 0 var(--app-legend-gap-bottom);
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
    min-height: var(--app-control-height);
}
div[data-testid="stFormSubmitButton"] button {
    border-radius: 7px;
    min-height: var(--app-control-height);
}
div[data-testid="stAlert"] {
    border-radius: 8px;
    margin: var(--app-alert-gap) 0;
}
@media (max-width: 900px) {
    .status-row {
        grid-template-columns: repeat(2, minmax(120px, 1fr));
    }
}
</style>
""".strip()

@dataclass(frozen=True)
class HeaderMetric:
    label: str
    value: int


@dataclass(frozen=True)
class HeaderModel:
    title: str
    subtitle: str
    metrics: tuple[HeaderMetric, ...]


@dataclass(frozen=True)
class LegendTypeItem:
    kind: str
    label: str


@dataclass(frozen=True)
class LegendResponsibleItem:
    key: str
    label: str
    fill: str
    border: str


@dataclass(frozen=True)
class LegendModel:
    kind_title: str
    responsible_title: str
    kind_items: tuple[LegendTypeItem, ...]
    responsible_items: tuple[LegendResponsibleItem, ...]


def build_header_model(graph: FlowGraphDocument, wells: WellsDocument) -> HeaderModel:
    active_wells = tuple(well for well in wells.wells if not well.is_archived)
    busy_node_count = len({well.current_node_id for well in active_wells})
    return HeaderModel(
        title=HEADER_TITLE,
        subtitle=HEADER_SUBTITLE,
        metrics=(
            HeaderMetric("Узлы", len(graph.nodes)),
            HeaderMetric("Связи", len(graph.edges)),
            HeaderMetric("Скважины", len(active_wells)),
            HeaderMetric("Занятые этапы", busy_node_count),
        ),
    )


def build_legend_model(graph: FlowGraphDocument) -> LegendModel:
    return LegendModel(
        kind_title=LEGEND_KIND_TITLE,
        responsible_title=LEGEND_RESPONSIBLE_TITLE,
        kind_items=tuple(LegendTypeItem(kind, label) for kind, label in LEGEND_TYPE_ITEMS),
        responsible_items=tuple(
            LegendResponsibleItem(
                key=key,
                label=style.label,
                fill=style.fill,
                border=style.border,
            )
            for key, style in graph.responsibles.items()
        ),
    )


CLIPBOARD_SHORTCUT_GUARD_HTML = """
<script>
(() => {
  const doc = window.parent.document;
  if (doc.documentElement.dataset.pydiagClipboardGuard === "1") {
    return;
  }
  doc.documentElement.dataset.pydiagClipboardGuard = "1";
  // Streamlit binds bare "c"/"r" hotkeys and overwrites the library filter that
  // would ignore Ctrl/Meta, so Ctrl+C outside inputs opens "Clear caches".
  doc.addEventListener(
    "keydown",
    (event) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      const key = String(event.key || "").toLowerCase();
      if (key === "c" || key === "v" || key === "x" || key === "a") {
        event.stopPropagation();
      }
    },
    true,
  );
})();
</script>
"""


CLIPBOARD_GUARD_SESSION_KEY = "_pydiag_clipboard_guard_installed"


def install_clipboard_shortcut_guard(st_module) -> None:
    session_state = getattr(st_module, "session_state", None)
    if isinstance(session_state, dict) or hasattr(session_state, "__contains__"):
        if session_state.get(CLIPBOARD_GUARD_SESSION_KEY):
            return
        session_state[CLIPBOARD_GUARD_SESSION_KEY] = True
    # st.iframe replaces deprecated st.components.v1.html for embedding HTML.
    # Zero size is rejected by Streamlit; hide the 1px host via CSS instead.
    st_module.iframe(CLIPBOARD_SHORTCUT_GUARD_HTML, height=1, width=1)


def inject_css(st_module) -> None:
    st_module.markdown(APP_CSS, unsafe_allow_html=True)
    try:
        st_module.set_option("client.toolbarMode", "viewer")
    except Exception:
        pass
    install_clipboard_shortcut_guard(st_module)


def render_legend(st_module, graph: FlowGraphDocument) -> None:
    st_module.markdown("### Типы блоков")
    st_module.markdown(legend_html(graph), unsafe_allow_html=True)


def legend_html(graph: FlowGraphDocument) -> str:
    model = build_legend_model(graph)
    type_items = "\n".join(
        (
            f'<div class="legend-item">{legend_type_icon(item.kind)}'
            f"<span>{safe_text(item.label)}</span></div>"
        )
        for item in model.kind_items
    )
    # Responsible colors live on the canvas topbar next to zoom controls.
    return f"""
    <div class="legend-shell">
      <div>
        <div class="legend-title">{safe_text(model.kind_title)}</div>
        <div class="legend-list">{type_items}</div>
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
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.7" '
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


def render_header(st_module, graph: FlowGraphDocument, wells: WellsDocument) -> None:
    model = build_header_model(graph, wells)
    metrics_html = "\n".join(
        (
            '<div class="status-cell">'
            f"<span>{safe_text(metric.label)}</span><strong>{metric.value}</strong>"
            "</div>"
        )
        for metric in model.metrics
    )
    st_module.markdown(
        f"""
        <div class="app-title">{safe_text(model.title)}</div>
        <div class="app-subtitle">{safe_text(model.subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )
    st_module.markdown(
        f"""
        <div class="status-row">
          {metrics_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
