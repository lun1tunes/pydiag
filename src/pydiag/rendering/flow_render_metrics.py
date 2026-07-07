from __future__ import annotations

from pydiag.domain.models import FlowGraphDocument, WellsDocument

from .flow_node_overlays import well_token_stack_height
from .flow_render_snapshot import FlowRenderSnapshot, build_flow_render_snapshot

__all__ = [
    "canvas_height_for_snapshot",
    "flow_canvas_height",
]


def canvas_height_for_snapshot(snapshot: FlowRenderSnapshot) -> int:
    bottom = 760
    for node in snapshot.graph.nodes:
        wells_here = snapshot.wells_by_node.get(node.id, [])
        token_space = well_token_stack_height(len(wells_here))
        bottom = max(
            bottom,
            int(
                snapshot.positions[node.id][1]
                + snapshot.render_specs[node.id].height
                + token_space
                + 150
            ),
        )
    return bottom


def flow_canvas_height(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> int:
    snapshot = build_flow_render_snapshot(graph, wells_doc, layout_mode)
    return canvas_height_for_snapshot(snapshot)
