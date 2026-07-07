from __future__ import annotations

from dataclasses import dataclass

from pydiag.domain.models import (
    FlowEdge,
    FlowGraphDocument,
    FlowNode,
    Well,
    WellsDocument,
    node_by_id,
)
from pydiag.domain.services import outgoing_edges
from pydiag.presentation.html_utils import safe_text
from pydiag.rendering import KIND_LABELS, wells_grouped_by_node
from pydiag.rendering.flow_node_overlays import duration_label


@dataclass(frozen=True)
class InspectorSection:
    title: str
    subtitle_html: str
    details_html: str


@dataclass(frozen=True)
class NodeInspectorModel:
    section: InspectorSection
    wells_rows: list[dict[str, str]]
    transitions_rows: list[dict[str, str]]


@dataclass(frozen=True)
class WellInspectorModel:
    section: InspectorSection
    history_rows: list[dict[str, str]]


@dataclass(frozen=True)
class EdgeInspectorModel:
    section: InspectorSection


def node_responsible_labels(graph: FlowGraphDocument, node: FlowNode) -> str:
    if not node.responsible:
        return "нет"
    labels = [
        graph.responsibles[responsible].label if responsible in graph.responsibles else responsible
        for responsible in node.responsible
    ]
    return safe_text(", ".join(labels))


def build_node_inspector_model(
    graph: FlowGraphDocument,
    wells: WellsDocument,
    node: FlowNode,
) -> NodeInspectorModel:
    nodes = node_by_id(graph)
    wells_here = [
        well for well in wells.wells if well.current_node_id == node.id and not well.is_archived
    ]
    section = InspectorSection(
        title=node.text,
        subtitle_html=f"{safe_text(KIND_LABELS[node.kind])} · {safe_text(node.id)}",
        details_html=details_grid_html(
            [
                ("Тип", safe_text(node.kind)),
                ("Ответственные", node_responsible_labels(graph, node)),
                (
                    "Время",
                    safe_text(duration_label(node.time) if node.time is not None else "не задано"),
                ),
                ("Скважины", str(len(wells_here))),
            ]
        ),
    )
    wells_rows = [
        {
            "id": well.id,
            "name": well.name,
            "field": str(well.metadata.get("field", "")),
            "rig": str(well.metadata.get("rig", "")),
        }
        for well in wells_here
    ]
    transitions_rows = [
        {
            "тип": edge.kind,
            "метка": edge.label or "",
            "куда": nodes[edge.target].text,
        }
        for edge in outgoing_edges(graph, node.id)
    ]
    return NodeInspectorModel(
        section=section,
        wells_rows=wells_rows,
        transitions_rows=transitions_rows,
    )


def build_well_inspector_model(graph: FlowGraphDocument, well: Well) -> WellInspectorModel:
    nodes = node_by_id(graph)
    current_node = nodes[well.current_node_id]
    section = InspectorSection(
        title=well.name,
        subtitle_html=safe_text(well.id),
        details_html=details_grid_html(
            [
                ("Текущий этап", safe_text(current_node.text)),
                ("Поле", safe_text(str(well.metadata.get("field", "не задано")))),
                ("Буровая", safe_text(str(well.metadata.get("rig", "не задано")))),
                ("История", f"{len(well.history)} записей"),
            ]
        ),
    )
    history_rows = [
        {
            "ts": item.ts.strftime("%Y-%m-%d %H:%M"),
            "action": item.action,
            "node": nodes[item.node_id].text if item.node_id in nodes else item.node_id,
            "by": item.by or "",
            "comment": item.comment or "",
        }
        for item in reversed(well.history)
    ]
    return WellInspectorModel(section=section, history_rows=history_rows)


def build_edge_inspector_model(graph: FlowGraphDocument, edge: FlowEdge) -> EdgeInspectorModel:
    nodes = node_by_id(graph)
    section = InspectorSection(
        title=edge.label or edge.kind,
        subtitle_html=safe_text(edge.id),
        details_html=details_grid_html(
            [
                ("Тип", safe_text(edge.kind)),
                ("Откуда", safe_text(nodes[edge.source].text)),
                ("Куда", safe_text(nodes[edge.target].text)),
            ]
        ),
    )
    return EdgeInspectorModel(section=section)


def build_overview_rows(
    graph: FlowGraphDocument, wells: WellsDocument
) -> list[dict[str, str | int]]:
    grouped = wells_grouped_by_node(wells)
    return [
        {"этап": node.text, "скважин": count}
        for node in graph.nodes
        if (count := len(grouped.get(node.id, [])))
    ]


def details_grid_html(items: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"<span>{safe_text(label)}</span><span>{value}</span>" for label, value in items
    )
    return f'<div class="mini-kv">{cells}</div>'
