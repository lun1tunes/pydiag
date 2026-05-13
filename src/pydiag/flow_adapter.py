from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from urllib.parse import quote

from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode

from .models import FlowEdge, FlowGraphDocument, FlowNode, Well, WellsDocument

DURATION_BADGE_MIN_WIDTH = 64
DURATION_BADGE_MAX_WIDTH = 128
DURATION_BADGE_CHAR_WIDTH = 6.6
DURATION_BADGE_ICON_WIDTH = 14
DURATION_BADGE_HORIZONTAL_PADDING = 18
KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "decision_card": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
}
SNAKE_COLUMNS = 4
SNAKE_ORIGIN_X = 60
SNAKE_ORIGIN_Y = 80
SNAKE_CELL_WIDTH = 350
SNAKE_CELL_HEIGHT = 220
TEXT_LINE_HEIGHT = 16
TEXT_CHAR_WIDTH = 7.1
WELL_TOKEN_CSS = """
<style>
.well-token-node .react-flow__handle,
.duration-badge-node .react-flow__handle {
  display: none !important;
  pointer-events: none !important;
}
.well-token-node .markdown-node,
.duration-badge-node .markdown-node {
  pointer-events: auto;
  height: 100%;
}
.duration-badge-node .markdown-node {
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.duration-badge-node .duration-badge-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  max-width: 100%;
}
.well-token-node .markdown-node p,
.duration-badge-node .markdown-node p {
  margin: 0 !important;
}
</style>
""".strip()


@dataclass(frozen=True)
class NodeRenderSpec:
    content: str
    width: int
    height: int


def wells_grouped_by_node(wells_doc: WellsDocument) -> dict[str, list[Well]]:
    grouped: dict[str, list[Well]] = defaultdict(list)
    for well in wells_doc.wells:
        if not well.is_archived:
            grouped[well.current_node_id].append(well)
    for wells in grouped.values():
        wells.sort(key=lambda item: item.name)
    return dict(grouped)


def node_matches_filters(
    node: FlowNode,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    wells_here: list[Well],
) -> bool:
    if kind_filter and node.kind not in kind_filter:
        return False

    node_responsible = getattr(node, "responsible", None)
    if responsible_filter and node_responsible not in responsible_filter:
        return False

    query = search.strip().lower()
    if not query:
        return True

    haystack = " ".join(
        [
            node.id,
            node.title,
            node.note or "",
            KIND_LABELS[node.kind],
            node_responsible or "",
            " ".join(well.id for well in wells_here),
            " ".join(well.name for well in wells_here),
        ]
    ).lower()
    return query in haystack


def build_streamlit_nodes(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    layout_mode: str = "snake",
) -> tuple[list[StreamlitFlowNode], set[str]]:
    responsible_filter = responsible_filter or []
    kind_filter = kind_filter or []
    wells_by_node = wells_grouped_by_node(wells_doc)
    nodes: list[StreamlitFlowNode] = []
    active_node_ids: set[str] = set()
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)

    for node_index, node in enumerate(graph.nodes):
        wells_here = wells_by_node.get(node.id, [])
        is_active = node_matches_filters(
            node,
            search,
            responsible_filter,
            kind_filter,
            wells_here,
        )
        if is_active:
            active_node_ids.add(node.id)

        position = positions[node.id]
        render_spec = render_specs[node.id]
        source_position, target_position = node_ports(node_index, layout_mode)
        nodes.append(
            StreamlitFlowNode(
                id=node.id,
                pos=position,
                data={"content": render_spec.content},
                node_type="default",
                source_position=source_position,
                target_position=target_position,
                draggable=False,
                selectable=True,
                connectable=False,
                z_index=10 if node.id == selected_id else 1,
                style=node_style(
                    node,
                    graph,
                    render_spec,
                    selected=node.id == selected_id,
                    active=is_active,
                ),
            )
        )

        if node.duration_hours is not None:
            nodes.append(
                StreamlitFlowNode(
                    id=f"duration::{node.id}",
                    pos=duration_badge_position(position),
                    data={"content": duration_badge_content(node.duration_hours)},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=35,
                    className="duration-badge-node",
                    style=duration_badge_style(
                        active=is_active,
                        duration_hours=node.duration_hours,
                    ),
                )
            )

        for well_index, well in enumerate(wells_here[:4]):
            token_id = f"well::{well.id}"
            token_active = (
                is_active or search.strip().lower() in (well.id + " " + well.name).lower()
            )
            nodes.append(
                StreamlitFlowNode(
                    id=token_id,
                    pos=well_token_position(position, render_spec.height, well_index),
                    data={"content": well_token_content(well)},
                    node_type="default",
                    draggable=False,
                    selectable=True,
                    connectable=False,
                    z_index=30 if token_id == selected_id else 20,
                    className="well-token-node",
                    style=well_token_style(
                        selected=token_id == selected_id,
                        active=token_active,
                    ),
                )
            )

        if len(wells_here) > 4:
            extra_id = f"well-extra::{node.id}"
            nodes.append(
                StreamlitFlowNode(
                    id=extra_id,
                    pos=well_token_position(position, render_spec.height, 4),
                    data={"content": f"{WELL_TOKEN_CSS}\nСкв. **+{len(wells_here) - 4}**"},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=19,
                    className="well-token-node",
                    style=well_token_style(selected=False, active=is_active),
                )
            )

    return nodes, active_node_ids


def layout_positions(
    graph: FlowGraphDocument,
    layout_mode: str = "snake",
    render_specs: dict[str, NodeRenderSpec] | None = None,
) -> dict[str, tuple[float, float]]:
    if layout_mode == "manual":
        return {node.id: (node.position.x, node.position.y) for node in graph.nodes}
    return snake_layout_positions(graph, render_specs or build_node_render_specs(graph, {}))


def snake_layout_positions(
    graph: FlowGraphDocument,
    render_specs: dict[str, NodeRenderSpec],
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    y = SNAKE_ORIGIN_Y
    row_index = 0
    for row_start in range(0, len(graph.nodes), SNAKE_COLUMNS):
        row_nodes = graph.nodes[row_start : row_start + SNAKE_COLUMNS]
        row_height = max((render_specs[node.id].height for node in row_nodes), default=0)
        for row_col, node in enumerate(row_nodes):
            visual_col = row_col if row_index % 2 == 0 else SNAKE_COLUMNS - row_col - 1
            render_spec = render_specs[node.id]
            x = SNAKE_ORIGIN_X + visual_col * SNAKE_CELL_WIDTH
            x += max(0, (SNAKE_CELL_WIDTH - render_spec.width) / 2)
            positions[node.id] = (x, y)
        y += max(SNAKE_CELL_HEIGHT, row_height + 104)
        row_index += 1
    return positions


def node_ports(index: int, layout_mode: str) -> tuple[str, str]:
    if layout_mode != "snake":
        return "right", "left"
    row = index // SNAKE_COLUMNS
    if row % 2 == 0:
        return "right", "left"
    return "left", "right"


def flow_canvas_height(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> int:
    wells_by_node = wells_grouped_by_node(wells_doc) if wells_doc is not None else {}
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)

    bottom = 760
    for node in graph.nodes:
        wells_here = wells_by_node.get(node.id, [])
        token_space = well_token_stack_height(len(wells_here))
        bottom = max(
            bottom,
            int(positions[node.id][1] + render_specs[node.id].height + token_space + 150),
        )
    return bottom


def build_streamlit_edges(
    graph: FlowGraphDocument,
    active_node_ids: set[str] | None = None,
) -> list[StreamlitFlowEdge]:
    active_node_ids = active_node_ids or {node.id for node in graph.nodes}
    edges: list[StreamlitFlowEdge] = []
    for edge in graph.edges:
        active = edge.source in active_node_ids and edge.target in active_node_ids
        color = edge_color(edge)
        opacity = 1.0 if active else 0.16
        edges.append(
            StreamlitFlowEdge(
                id=edge.id,
                source=edge.source,
                target=edge.target,
                edge_type="smoothstep",
                marker_end={"type": "arrowclosed", "color": color},
                label=edge.label or "",
                label_show_bg=bool(edge.label),
                label_style={
                    "fill": color,
                    "fontWeight": 700,
                    "fontSize": "12px",
                },
                label_bg_style={
                    "fill": "#ffffff",
                    "fillOpacity": 0.92,
                    "rx": 6,
                    "ry": 6,
                },
                style={
                    "stroke": color,
                    "strokeWidth": 2.2,
                    "strokeDasharray": "8 6" if edge.kind == "dashed" else "0",
                    "opacity": opacity,
                },
            )
        )
    return edges


def node_content(node: FlowNode, graph: FlowGraphDocument, wells_here: list[Well]) -> str:
    return content_from_lines(node_content_lines(node, graph, wells_here))


def build_node_render_specs(
    graph: FlowGraphDocument,
    wells_by_node: dict[str, list[Well]],
) -> dict[str, NodeRenderSpec]:
    return {
        node.id: node_render_spec(node, graph, wells_by_node.get(node.id, []))
        for node in graph.nodes
    }


def node_render_spec(
    node: FlowNode,
    graph: FlowGraphDocument,
    wells_here: list[Well],
) -> NodeRenderSpec:
    lines = node_content_lines(node, graph, wells_here)
    width, height = fit_node_size(node, lines)
    return NodeRenderSpec(
        content=content_from_lines(lines),
        width=width,
        height=height,
    )


def node_content_lines(
    node: FlowNode,
    graph: FlowGraphDocument,
    wells_here: list[Well],
) -> list[str]:
    lines: list[str] = []
    lines.append(f"**{node.title}**")

    if node.kind == "process":
        responsible = graph.responsibles[node.responsible]
        lines.append(responsible.label)
    else:
        lines.append(KIND_LABELS[node.kind])

    extra_lines: list[str] = []

    if node.approvers:
        approvers = []
        for approver in node.approvers[:3]:
            style = graph.responsibles[approver.responsible]
            approvers.append(approver.label or style.label)
        if len(node.approvers) > 3:
            approvers.append(f"+{len(node.approvers) - 3}")
        extra_lines.append("Согласующие: " + " · ".join(approvers))

    if wells_here:
        visible = ", ".join(short_well_name(well) for well in wells_here[:3])
        if len(wells_here) > 3:
            visible += f", +{len(wells_here) - 3}"
        extra_lines.insert(0, "Скважины: " + visible)

    if should_show_note_on_canvas(node):
        extra_lines.append(f"_{node.note or ''}_")

    lines.extend(extra_lines)
    return lines


def content_from_lines(lines: list[str]) -> str:
    return "  \n".join(lines)


def fit_node_size(node: FlowNode, lines: list[str]) -> tuple[int, int]:
    width = preferred_node_width(node, lines)
    wrapped_lines = sum(
        estimated_wrapped_lines(line, width, horizontal_text_padding(node)) for line in lines
    )
    height = ceil(
        vertical_text_padding(node)
        + wrapped_lines * TEXT_LINE_HEIGHT
        + markdown_vertical_buffer(node)
    )
    return width, max(node.size.h, minimum_node_height(node), height)


def preferred_node_width(node: FlowNode, lines: list[str]) -> int:
    longest_line = max((len(plain_canvas_text(line)) for line in lines), default=0)
    desired = (
        horizontal_text_padding(node)
        + min(longest_line, max_unwrapped_chars(node)) * TEXT_CHAR_WIDTH
    )
    width = ceil_to_step(int(ceil(desired)), 10)
    return max(node.size.w, minimum_node_width(node), min(width, maximum_node_width(node)))


def minimum_node_width(node: FlowNode) -> int:
    return {
        "process": 280,
        "decision_diamond": 230,
        "decision_card": 250,
        "database": 270,
        "input_data": 260,
    }[node.kind]


def maximum_node_width(node: FlowNode) -> int:
    return {
        "process": 330,
        "decision_diamond": 300,
        "decision_card": 320,
        "database": 330,
        "input_data": 320,
    }[node.kind]


def minimum_node_height(node: FlowNode) -> int:
    return {
        "process": 104,
        "decision_diamond": 112,
        "decision_card": 98,
        "database": 124,
        "input_data": 94,
    }[node.kind]


def horizontal_text_padding(node: FlowNode) -> int:
    return {
        "decision_diamond": 104,
        "input_data": 96,
        "database": 72,
    }.get(node.kind, 28)


def vertical_text_padding(node: FlowNode) -> int:
    return {
        "process": 28,
        "decision_diamond": 52,
        "decision_card": 34,
        "database": 58,
        "input_data": 36,
    }[node.kind]


def markdown_vertical_buffer(node: FlowNode) -> int:
    return {
        "database": 12,
        "decision_diamond": 10,
        "input_data": 8,
    }.get(node.kind, 8)


def max_unwrapped_chars(node: FlowNode) -> int:
    return {
        "decision_diamond": 22,
        "input_data": 28,
        "database": 30,
    }.get(node.kind, 32)


def estimated_wrapped_lines(text: str, width: int, horizontal_padding: int) -> int:
    available_width = max(96, width - horizontal_padding)
    chars_per_line = max(12, int(available_width / TEXT_CHAR_WIDTH))
    normalized = plain_canvas_text(text)
    return max(1, (len(normalized) + chars_per_line - 1) // chars_per_line)


def plain_canvas_text(text: str) -> str:
    without_html = re.sub(r"<[^>]+>", "", text)
    return (
        without_html.replace("*", "").replace("`", "").replace("_", "").replace("TIME ", "").strip()
    )


def should_show_note_on_canvas(node: FlowNode) -> bool:
    return bool(node.note) and node.kind not in {"decision_diamond", "input_data"}


def ceil_to_step(value: int, step: int) -> int:
    return int(ceil(value / step) * step)


def short_well_name(well: Well) -> str:
    name = well.name.replace("Скв.", "").replace("скв.", "").strip()
    return name[:16]


def well_token_content(well: Well) -> str:
    return f"{WELL_TOKEN_CSS}\nСкв. **{short_well_name(well)}**"


def duration_label(duration_hours: int) -> str:
    return f"{duration_hours} ч"


def duration_badge_content(duration_hours: int) -> str:
    return (
        f"{WELL_TOKEN_CSS}\n"
        '<span class="duration-badge-content">'
        f"&#9719; <strong>{duration_label(duration_hours)}</strong>"
        "</span>"
    )


def duration_badge_width(duration_hours: int) -> int:
    text_width = len(duration_label(duration_hours)) * DURATION_BADGE_CHAR_WIDTH
    width = ceil_to_step(
        int(ceil(DURATION_BADGE_HORIZONTAL_PADDING + DURATION_BADGE_ICON_WIDTH + text_width)),
        2,
    )
    return max(DURATION_BADGE_MIN_WIDTH, min(width, DURATION_BADGE_MAX_WIDTH))


def node_style(
    node: FlowNode,
    graph: FlowGraphDocument,
    render_spec: NodeRenderSpec,
    selected: bool,
    active: bool,
) -> dict[str, str | float]:
    style: dict[str, str | float] = {
        "width": f"{render_spec.width}px",
        "height": f"{render_spec.height}px",
        "boxSizing": "border-box",
        "padding": "10px 14px",
        "fontSize": "12px",
        "lineHeight": "1.22",
        "fontFamily": "Inter, system-ui, sans-serif",
        "textAlign": "left",
        "wordBreak": "break-word",
        "overflowWrap": "anywhere",
        "whiteSpace": "normal",
        "overflow": "hidden",
        "opacity": 1.0 if active else 0.28,
        "transition": "opacity 160ms ease, box-shadow 160ms ease, transform 160ms ease",
    }

    if node.kind == "process":
        responsible = graph.responsibles[node.responsible]
        style.update(
            {
                "backgroundColor": responsible.fill,
                "border": f"2px solid {responsible.border}",
                "borderRadius": "8px",
                "color": responsible.text,
                "boxShadow": "0 12px 26px rgba(15, 23, 42, 0.12)",
            }
        )
    elif node.kind == "decision_diamond":
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": polygon_background(
                    points="50,2 98,50 50,98 2,50",
                    fill="#ffffff",
                    stroke="#334155",
                ),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "22px 52px 20px",
                "textAlign": "center",
                "color": "#111827",
                "filter": "drop-shadow(0 12px 18px rgba(51, 65, 85, 0.12))",
            }
        )
    elif node.kind == "decision_card":
        style.update(
            {
                "backgroundColor": "#e7ebf0",
                "border": "2px solid #8a94a6",
                "borderRadius": "22px",
                "color": "#202938",
                "boxShadow": "0 12px 24px rgba(15, 23, 42, 0.10)",
            }
        )
    elif node.kind == "database":
        style.update(
            {
                "background": "transparent",
                "backgroundImage": cylinder_background(),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "borderRadius": "0",
                "padding": "32px 36px 22px",
                "textAlign": "center",
                "color": "#111827",
                "filter": "drop-shadow(0 12px 18px rgba(15, 23, 42, 0.13))",
            }
        )
    elif node.kind == "input_data":
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": polygon_background(
                    points="13,2 98,2 87,98 2,98",
                    fill="#f1f7ff",
                    stroke="#5477aa",
                ),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "14px 48px 18px 44px",
                "color": "#183557",
                "filter": "drop-shadow(0 12px 18px rgba(30, 64, 175, 0.10))",
            }
        )

    if selected:
        style.update(
            {
                "boxShadow": "0 0 0 4px rgba(20, 184, 166, 0.24), 0 18px 36px rgba(15, 23, 42, 0.18)",
                "transform": "translateY(-1px)",
            }
        )

    return style


def polygon_background(points: str, fill: str, stroke: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' "
        "preserveAspectRatio='none'>"
        f"<polygon points='{points}' fill='{fill}' stroke='{stroke}' "
        "stroke-width='2.4' stroke-linejoin='round'/>"
        "</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def cylinder_background() -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' "
        "preserveAspectRatio='none'>"
        "<defs>"
        "<linearGradient id='body' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#f8fafc'/>"
        "<stop offset='0.48' stop-color='#e3e8ef'/>"
        "<stop offset='1' stop-color='#cfd6e1'/>"
        "</linearGradient>"
        "<linearGradient id='top' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#ffffff'/>"
        "<stop offset='1' stop-color='#e4e9f1'/>"
        "</linearGradient>"
        "</defs>"
        "<path d='M8 24 C8 9 92 9 92 24 L92 76 "
        "C92 91 8 91 8 76 Z' fill='url(#body)' stroke='#5f6877' "
        "stroke-width='2.4'/>"
        "<ellipse cx='50' cy='24' rx='42' ry='14' fill='url(#top)' "
        "stroke='#5f6877' stroke-width='2.4'/>"
        "<path d='M8 76 C8 91 92 91 92 76' fill='none' "
        "stroke='#5f6877' stroke-width='2.4'/>"
        "<path d='M14 27 C28 36 72 36 86 27' fill='none' "
        "stroke='#9aa4b2' stroke-width='1.2' opacity='0.7'/>"
        "</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def well_token_position(
    node_position: tuple[float, float],
    node_height: int,
    index: int,
) -> tuple[float, float]:
    row = index // 2
    col = index % 2
    return (
        node_position[0] + 14 + col * 128,
        node_position[1] + node_height + 12 + row * 44,
    )


def duration_badge_position(node_position: tuple[float, float]) -> tuple[float, float]:
    return (node_position[0] + 10, node_position[1] - 30)


def well_token_stack_height(well_count: int) -> int:
    if well_count <= 0:
        return 0
    visible_tokens = min(well_count, 5)
    rows = (visible_tokens + 1) // 2
    return 12 + rows * 44


def well_token_style(selected: bool, active: bool) -> dict[str, str | float]:
    accent = "#0f766e" if selected else "#14b8a6"
    fill = "#ccfbf1" if selected else "#f0fdfa"
    return {
        "width": "118px",
        "height": "36px",
        "boxSizing": "border-box",
        "padding": "7px 12px 7px 18px",
        "borderRadius": "999px",
        "border": f"1px solid {accent}",
        "background": f"linear-gradient(90deg, {accent} 0 7px, {fill} 7px 100%)",
        "color": "#064e3b",
        "fontSize": "12px",
        "fontWeight": 650,
        "lineHeight": "1.1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 10px 22px rgba(15, 118, 110, 0.16)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease, background 160ms ease, border-color 160ms ease",
    }


def duration_badge_style(
    active: bool,
    duration_hours: int,
) -> dict[str, str | float]:
    return {
        "width": f"{duration_badge_width(duration_hours)}px",
        "height": "24px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": "1px solid #fda4af",
        "backgroundColor": "#fff1f2",
        "color": "#9f1239",
        "fontSize": "11px",
        "fontWeight": 700,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 8px 18px rgba(190, 18, 60, 0.12)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }


def edge_color(edge: FlowEdge) -> str:
    return {
        "default": "#475569",
        "yes": "#16834a",
        "no": "#c2410c",
        "dashed": "#64748b",
    }[edge.kind]
