from __future__ import annotations

from dataclasses import dataclass

from pydiag.domain.models import FlowGraphDocument, WellsDocument
from pydiag.presentation.html_utils import safe_text

__all__ = [
    "APP_CSS",
    "build_header_model",
    "build_legend_model",
    "inject_css",
    "legend_html",
    "legend_type_icon",
    "render_header",
    "render_legend",
]

HEADER_TITLE = "Карта планирования и бурения"
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
    padding: 0.55rem 1.35rem 0.8rem;
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
    padding-top: 0.15rem;
    margin-top: 0;
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


def inject_css(st_module) -> None:
    st_module.markdown(APP_CSS, unsafe_allow_html=True)


def render_legend(st_module, graph: FlowGraphDocument) -> None:
    st_module.markdown("### Легенда")
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
    department_items = "\n".join(
        (
            '<div class="legend-dept">'
            f'<span class="legend-swatch" style="background-color: {item.fill}; '
            f'border-color: {item.border};"></span>'
            f'<span class="legend-dept-label">{safe_text(item.label)}</span>'
            f'<span class="legend-dept-code">{safe_text(item.key)}</span>'
            "</div>"
        )
        for item in model.responsible_items
    )
    return f"""
    <div class="legend-shell">
      <div>
        <div class="legend-title">{safe_text(model.kind_title)}</div>
        <div class="legend-list">{type_items}</div>
      </div>
      <div>
        <div class="legend-title">{safe_text(model.responsible_title)}</div>
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
