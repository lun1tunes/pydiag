from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument

from .flow_position_edit import (
    ensure_position_edit_positions,
    graph_with_positions,
    position_edit_positions_from_state,
    update_position_edit_positions_from_component,
)

__all__ = ["FlowRenderContext", "prepare_render_context"]


@dataclass(frozen=True)
class FlowRenderContext:
    graph: FlowGraphDocument
    layout_mode: str
    default_positions: dict[str, dict[str, float]]


def prepare_render_context(
    session_state: MutableMapping[str, Any],
    *,
    graph: FlowGraphDocument,
    wells: WellsDocument,
    layout_mode: str,
    position_edit_enabled: bool,
    component_state: Mapping[str, object] | None,
) -> FlowRenderContext:
    if not position_edit_enabled:
        return FlowRenderContext(
            graph=graph,
            layout_mode=layout_mode,
            default_positions=default_positions_for_graph(graph),
        )

    ensure_position_edit_positions(session_state, graph, wells, layout_mode)
    update_position_edit_positions_from_component(session_state, graph, component_state)
    render_graph = graph_with_positions(
        graph,
        position_edit_positions_from_state(session_state, graph),
    )
    return FlowRenderContext(
        graph=render_graph,
        layout_mode="manual",
        default_positions=default_positions_for_graph(render_graph),
    )


def default_positions_for_graph(graph: FlowGraphDocument) -> dict[str, dict[str, float]]:
    return {node.id: {"x": node.position.x, "y": node.position.y} for node in graph.nodes}
