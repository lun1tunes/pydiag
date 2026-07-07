from __future__ import annotations

import re
from dataclasses import dataclass
from math import ceil

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well

from .flow_node_markup import node_content
from .flow_render_math import ceil_to_step

TEXT_LINE_HEIGHT = 16
TEXT_CHAR_WIDTH = 7.1

__all__ = [
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
    if node.metadata.get("figma_fixed_size") is True:
        return max(20, int(node.size.w)), max(20, int(node.size.h))
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
        "event": 240,
        "figma_text": 20,
    }[node.kind]


def maximum_node_width(node: FlowNode) -> int:
    return {
        "process": 330,
        "decision_diamond": 300,
        "decision_card": 320,
        "database": 330,
        "input_data": 320,
        "event": 300,
        "figma_text": 2000,
    }[node.kind]


def minimum_node_height(node: FlowNode) -> int:
    return {
        "process": 104,
        "decision_diamond": 112,
        "decision_card": 98,
        "database": 158,
        "input_data": 94,
        "event": 84,
        "figma_text": 20,
    }[node.kind]


def horizontal_text_padding(node: FlowNode) -> int:
    return {
        "decision_diamond": 104,
        "input_data": 96,
        "database": 80,
        "event": 56,
        "figma_text": 0,
    }.get(node.kind, 28)


def vertical_text_padding(node: FlowNode) -> int:
    return {
        "process": 28,
        "decision_diamond": 52,
        "decision_card": 34,
        "database": 92,
        "input_data": 36,
        "event": 32,
        "figma_text": 0,
    }[node.kind]


def markdown_vertical_buffer(node: FlowNode) -> int:
    return {
        "database": 12,
        "decision_diamond": 10,
        "input_data": 8,
        "figma_text": 0,
    }.get(node.kind, 8)


def max_unwrapped_chars(node: FlowNode) -> int:
    return {
        "decision_diamond": 22,
        "input_data": 28,
        "database": 30,
        "figma_text": 200,
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
