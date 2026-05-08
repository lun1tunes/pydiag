from __future__ import annotations

from collections import defaultdict

from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode

from .models import FlowEdge, FlowGraphDocument, FlowNode, Well, WellsDocument

KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "decision_card": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
}


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
) -> tuple[list[StreamlitFlowNode], set[str]]:
    responsible_filter = responsible_filter or []
    kind_filter = kind_filter or []
    wells_by_node = wells_grouped_by_node(wells_doc)
    nodes: list[StreamlitFlowNode] = []
    active_node_ids: set[str] = set()

    for node in graph.nodes:
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

        nodes.append(
            StreamlitFlowNode(
                id=node.id,
                pos=(node.position.x, node.position.y),
                data={"content": node_content(node, graph, wells_here)},
                node_type="default",
                source_position="right",
                target_position="left",
                draggable=False,
                selectable=True,
                connectable=False,
                z_index=10 if node.id == selected_id else 1,
                style=node_style(node, graph, selected=node.id == selected_id, active=is_active),
            )
        )

        for index, well in enumerate(wells_here[:4]):
            token_id = f"well::{well.id}"
            token_active = (
                is_active or search.strip().lower() in (well.id + " " + well.name).lower()
            )
            nodes.append(
                StreamlitFlowNode(
                    id=token_id,
                    pos=well_token_position(node, index),
                    data={"content": f"**{short_well_name(well)}**"},
                    node_type="default",
                    draggable=False,
                    selectable=True,
                    connectable=False,
                    z_index=30 if token_id == selected_id else 20,
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
                    pos=well_token_position(node, 4),
                    data={"content": f"**+{len(wells_here) - 4}**"},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=19,
                    style=well_token_style(selected=False, active=is_active),
                )
            )

    return nodes, active_node_ids


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
    lines: list[str] = []
    if node.duration_hours is not None:
        lines.append(f"`TIME {node.duration_hours} ч`")

    lines.append(f"**{node.title}**")

    if node.kind == "process":
        responsible = graph.responsibles[node.responsible]
        lines.append(responsible.label)
    else:
        lines.append(KIND_LABELS[node.kind])

    if node.note:
        lines.append(f"_{node.note}_")

    if node.approvers:
        approvers = []
        for approver in node.approvers[:3]:
            style = graph.responsibles[approver.responsible]
            approvers.append(approver.label or style.label)
        if len(node.approvers) > 3:
            approvers.append(f"+{len(node.approvers) - 3}")
        lines.append("Согласующие: " + " · ".join(approvers))

    if wells_here:
        visible = ", ".join(short_well_name(well) for well in wells_here[:3])
        if len(wells_here) > 3:
            visible += f", +{len(wells_here) - 3}"
        lines.append("Скважины: " + visible)

    return "  \n".join(lines)


def short_well_name(well: Well) -> str:
    name = well.name.replace("Скв.", "").replace("скв.", "").strip()
    return name[:16]


def node_style(
    node: FlowNode,
    graph: FlowGraphDocument,
    selected: bool,
    active: bool,
) -> dict[str, str | float]:
    style: dict[str, str | float] = {
        "width": f"{node.size.w}px",
        "height": f"{node.size.h}px",
        "boxSizing": "border-box",
        "padding": "10px 14px",
        "fontSize": "12px",
        "lineHeight": "1.22",
        "fontFamily": "Inter, system-ui, sans-serif",
        "textAlign": "left",
        "wordBreak": "break-word",
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
                "backgroundColor": "#ffffff",
                "border": "2px solid #334155",
                "clipPath": "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)",
                "padding": "22px 34px",
                "textAlign": "center",
                "color": "#111827",
                "boxShadow": "0 14px 26px rgba(51, 65, 85, 0.14)",
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
                "background": "linear-gradient(180deg, #f8fafc 0%, #d8dee8 100%)",
                "border": "2px solid #6b7280",
                "borderRadius": "50% / 18%",
                "textAlign": "center",
                "color": "#111827",
                "boxShadow": "inset 0 10px 0 rgba(255,255,255,0.65), 0 12px 24px rgba(15, 23, 42, 0.12)",
            }
        )
    elif node.kind == "input_data":
        style.update(
            {
                "backgroundColor": "#f1f7ff",
                "border": "2px solid #5477aa",
                "clipPath": "polygon(13% 0%, 100% 0%, 87% 100%, 0% 100%)",
                "padding": "12px 24px",
                "color": "#183557",
                "boxShadow": "0 12px 24px rgba(30, 64, 175, 0.10)",
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


def well_token_position(node: FlowNode, index: int) -> tuple[float, float]:
    row = index // 2
    col = index % 2
    return (
        node.position.x + 14 + col * 84,
        node.position.y + node.size.h + 12 + row * 34,
    )


def well_token_style(selected: bool, active: bool) -> dict[str, str | float]:
    return {
        "width": "74px",
        "height": "28px",
        "boxSizing": "border-box",
        "padding": "4px 8px",
        "borderRadius": "999px",
        "border": "2px solid #ffffff",
        "backgroundColor": "#0f766e" if selected else "#0f172a",
        "color": "#ffffff",
        "fontSize": "11px",
        "lineHeight": "1.05",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 10px 22px rgba(15, 23, 42, 0.22)",
        "opacity": 1.0 if active else 0.24,
        "transition": "opacity 160ms ease, background-color 160ms ease",
    }


def edge_color(edge: FlowEdge) -> str:
    return {
        "default": "#475569",
        "yes": "#16834a",
        "no": "#c2410c",
        "dashed": "#64748b",
    }[edge.kind]
