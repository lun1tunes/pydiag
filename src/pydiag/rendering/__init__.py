"""Rendering layer public API."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "KIND_LABELS": ("pydiag.rendering.flow_node_rendering", "KIND_LABELS"),
    "build_flow_canvas_payload": (
        "pydiag.rendering.flow_canvas_adapter",
        "build_flow_canvas_payload",
    ),
    "build_node_render_specs": (
        "pydiag.rendering.flow_node_rendering",
        "build_node_render_specs",
    ),
    "build_streamlit_edges": (
        "pydiag.rendering.flow_streamlit_edges",
        "build_streamlit_edges",
    ),
    "build_streamlit_nodes": (
        "pydiag.rendering.flow_streamlit_nodes",
        "build_streamlit_nodes",
    ),
    "component_history_action_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_history_action_from_state",
    ),
    "component_pending_edge_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_pending_edge_from_state",
    ),
    "component_pending_node_edit_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_pending_node_edit_from_state",
    ),
    "component_pending_edge_edit_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_pending_edge_edit_from_state",
    ),
    "component_positions_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_positions_from_state",
    ),
    "component_responsible_filter_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_responsible_filter_from_state",
    ),
    "component_selected_id_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_selected_id_from_state",
    ),
    "component_view_state_from_state": (
        "pydiag.rendering.flow_canvas_adapter",
        "component_view_state_from_state",
    ),
    "flow_canvas_height": ("pydiag.rendering.flow_render_metrics", "flow_canvas_height"),
    "layout_positions": ("pydiag.rendering.flow_layout_routing", "layout_positions"),
    "render_flow_canvas": (
        "pydiag.rendering.flow_canvas_component",
        "render_flow_canvas",
    ),
    "wells_grouped_by_node": (
        "pydiag.rendering.flow_node_rendering",
        "wells_grouped_by_node",
    ),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
