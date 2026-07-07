from __future__ import annotations

from pydiag.domain.models import (
    FlowEdge,
    FlowGraphDocument,
    FlowNode,
    Well,
    WellsDocument,
    node_by_id,
    well_by_id,
)


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
