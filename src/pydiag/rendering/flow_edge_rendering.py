from __future__ import annotations

from math import ceil

from pydiag.domain.models import FlowEdge

from .flow_render_math import ceil_to_step

EDGE_LABEL_MIN_WIDTH = 42
EDGE_LABEL_CHAR_WIDTH = 9
EDGE_LABEL_HORIZONTAL_PADDING = 18
DEFAULT_EDGE_LABELS = {
    "yes": "Да",
    "no": "Нет",
}

__all__ = [
    "DEFAULT_EDGE_LABELS",
    "EDGE_LABEL_CHAR_WIDTH",
    "EDGE_LABEL_HORIZONTAL_PADDING",
    "EDGE_LABEL_MIN_WIDTH",
    "edge_color",
    "edge_label_text",
    "edge_label_width",
    "edge_opacity",
    "edge_style",
    "edge_stroke_width",
]


def edge_label_text(edge: FlowEdge) -> str:
    return edge.label or DEFAULT_EDGE_LABELS.get(edge.kind, "")


def edge_label_width(edge: FlowEdge) -> int:
    text_width = len(edge_label_text(edge)) * EDGE_LABEL_CHAR_WIDTH
    return max(
        EDGE_LABEL_MIN_WIDTH,
        ceil_to_step(int(ceil(text_width + EDGE_LABEL_HORIZONTAL_PADDING)), 2),
    )


def edge_style(
    edge: FlowEdge,
    opacity: float,
    is_route_segment: bool,
) -> dict[str, str | float]:
    return {
        "stroke": edge_color(edge),
        "strokeWidth": edge_stroke_width(edge, is_route_segment),
        "strokeDasharray": "8 6" if edge.kind == "dashed" else "0",
        "strokeLinecap": "round",
        "strokeLinejoin": "round",
        "opacity": opacity,
    }


def edge_opacity(edge: FlowEdge, active: bool) -> float:
    if not active:
        return 0.12
    return {
        "usual": 0.78,
        "yes": 0.9,
        "no": 0.9,
        "dashed": 0.5,
    }[edge.kind]


def edge_stroke_width(edge: FlowEdge, is_route_segment: bool) -> float:
    if edge.kind == "dashed":
        return 1.8 if not is_route_segment else 2.0
    if edge.kind in {"yes", "no"}:
        return 2.4 if not is_route_segment else 2.5
    return 2.0 if not is_route_segment else 2.2


def edge_color(edge: FlowEdge) -> str:
    return {
        "usual": "#111827",
        "yes": "#16a34a",
        "no": "#dc2626",
        "dashed": "#64748b",
    }[edge.kind]
