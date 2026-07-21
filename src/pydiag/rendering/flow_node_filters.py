from __future__ import annotations

from collections import defaultdict

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well, WellsDocument

KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
    "figma_text": "Текст Figma",
}

__all__ = [
    "KIND_LABELS",
    "node_matches_filters",
    "node_search_haystack",
    "wells_grouped_by_node",
]


def wells_grouped_by_node(wells_doc: WellsDocument) -> dict[str, list[Well]]:
    grouped: dict[str, list[Well]] = defaultdict(list)
    for well in wells_doc.wells:
        if not well.is_archived:
            grouped[well.current_node_id].append(well)
    for wells in grouped.values():
        wells.sort(key=lambda item: item.name)
    return dict(grouped)


def node_matches_filters(
    graph: FlowGraphDocument,
    node: FlowNode,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    wells_here: list[Well],
) -> bool:
    if kind_filter and node.kind not in kind_filter:
        return False

    node_responsibles = node.responsible
    if responsible_filter and not set(node_responsibles).intersection(responsible_filter):
        return False

    query = search.strip().lower()
    if not query:
        return True

    return query in node_search_haystack(graph, node, wells_here)


def node_search_haystack(
    graph: FlowGraphDocument,
    node: FlowNode,
    wells_here: list[Well],
) -> str:
    return " ".join(_node_search_terms(graph, node, wells_here)).lower()


def _node_search_terms(
    graph: FlowGraphDocument,
    node: FlowNode,
    wells_here: list[Well],
) -> list[str]:
    node_responsibles = node.responsible
    return [
        node.id,
        node.text,
        KIND_LABELS[node.kind],
        " ".join(node_responsibles),
        " ".join(
            graph.responsibles[responsible].label
            for responsible in node_responsibles
            if responsible in graph.responsibles
        ),
        " ".join(well.id for well in wells_here),
        " ".join(well.name for well in wells_here),
    ]
