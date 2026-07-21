from __future__ import annotations

import re
from dataclasses import dataclass
from math import ceil

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well

from .flow_node_markup import node_content
from .flow_render_math import ceil_to_step

# Tuned for ~14px bold UI font (Cyrillic) so fitted boxes hug readable labels.
TEXT_LINE_HEIGHT = 19
TEXT_CHAR_WIDTH = 8.2
MANUAL_LAYOUT_SIZE_META = "manual_layout_size"

__all__ = [
    "MANUAL_LAYOUT_SIZE_META",
    "NodeRenderSpec",
    "build_node_render_specs",
]


@dataclass(frozen=True)
class NodeRenderSpec:
    content: str
    width: int
    height: int


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
    lines = [node.text]
    width, height = fit_node_size(node, lines)
    return NodeRenderSpec(
        content=node_content(node, graph, wells_here),
        width=width,
        height=height,
    )


def fit_node_size(node: FlowNode, lines: list[str]) -> tuple[int, int]:
    if (
        node.metadata.get("figma_fixed_size") is True
        or node.metadata.get(MANUAL_LAYOUT_SIZE_META) is True
    ):
        # Explicit admin / Figma size: YAML layout is authoritative.
        return (
            max(minimum_node_width(node), min(int(node.size.w), 1200)),
            max(minimum_node_height(node), min(int(node.size.h), 800)),
        )

    # Default: content-hug so imported Figma YAML boxes do not stay oversized.
    width = preferred_node_width(node, lines)
    char_width = text_char_width(node)
    wrapped_lines = sum(
        estimated_wrapped_lines(
            line,
            width,
            horizontal_text_padding(node),
            char_width=char_width,
        )
        for line in lines
    )
    height = ceil(
        vertical_text_padding(node)
        + wrapped_lines * TEXT_LINE_HEIGHT
        + markdown_vertical_buffer(node)
    )
    return width, max(minimum_node_height(node), height)


def preferred_node_width(node: FlowNode, lines: list[str]) -> int:
    longest_line = max((len(plain_canvas_text(line)) for line in lines), default=0)
    char_width = text_char_width(node)
    desired = (
        horizontal_text_padding(node)
        + min(longest_line, max_unwrapped_chars(node)) * char_width
    )
    width = ceil_to_step(int(ceil(desired)), 10)
    return max(minimum_node_width(node), min(width, maximum_node_width(node)))


def text_char_width(node: FlowNode) -> float:
    if node.kind == "decision_diamond":
        return 9.0
    return TEXT_CHAR_WIDTH


def minimum_node_width(node: FlowNode) -> int:
    return {
        "process": 200,
        "decision_diamond": 200,
        "database": 200,
        "input_data": 190,
        "event": 160,
        "figma_text": 20,
    }[node.kind]


def maximum_node_width(node: FlowNode) -> int:
    return {
        "process": 380,
        "decision_diamond": 400,
        "database": 360,
        "input_data": 340,
        "event": 320,
        "figma_text": 2000,
    }[node.kind]


def minimum_node_height(node: FlowNode) -> int:
    return {
        "process": 56,
        "decision_diamond": 72,
        "database": 96,
        "input_data": 56,
        "event": 48,
        "figma_text": 20,
    }[node.kind]


def horizontal_text_padding(node: FlowNode) -> int:
    return {
        "decision_diamond": 112,
        "input_data": 72,
        "database": 64,
        "event": 44,
        "figma_text": 0,
    }.get(node.kind, 24)


def vertical_text_padding(node: FlowNode) -> int:
    return {
        "process": 20,
        "decision_diamond": 44,
        "database": 64,
        "input_data": 28,
        "event": 24,
        "figma_text": 0,
    }[node.kind]


def markdown_vertical_buffer(node: FlowNode) -> int:
    return {
        "database": 8,
        "decision_diamond": 6,
        "input_data": 4,
        "figma_text": 0,
    }.get(node.kind, 4)


def max_unwrapped_chars(node: FlowNode) -> int:
    return {
        "decision_diamond": 28,
        "input_data": 34,
        "database": 34,
        "figma_text": 200,
    }.get(node.kind, 40)


def estimated_wrapped_lines(
    text: str,
    width: int,
    horizontal_padding: int,
    *,
    char_width: float = TEXT_CHAR_WIDTH,
) -> int:
    available_width = max(96, width - horizontal_padding)
    chars_per_line = max(12, int(available_width / char_width))
    normalized = plain_canvas_text(text)
    return max(1, (len(normalized) + chars_per_line - 1) // chars_per_line)


def plain_canvas_text(text: str) -> str:
    without_html = re.sub(r"<[^>]+>", "", text)
    return (
        without_html.replace("*", "").replace("`", "").replace("_", "").replace("TIME ", "").strip()
    )
