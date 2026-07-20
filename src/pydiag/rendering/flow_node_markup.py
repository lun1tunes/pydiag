from __future__ import annotations

from html import escape

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well

from .flow_node_overlays import (
    duration_label,
    responsible_abbreviation,
    short_well_name,
)

__all__ = [
    "FLOW_NODE_CSS",
    "duration_badge_content",
    "node_content",
    "responsible_badge_content",
    "well_token_content",
]

FLOW_NODE_CSS = """
<style>
.branch-anchor-node .react-flow__handle,
.react-flow__node.branch-anchor-node .react-flow__handle,
.react-flow__node-branch-anchor-node .react-flow__handle {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  width: 6px !important;
  min-width: 6px !important;
  height: 6px !important;
  min-height: 6px !important;
  transform: translate(-50%, -50%) !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  opacity: 0.01 !important;
  visibility: visible !important;
  pointer-events: none !important;
}
.route-anchor-node .react-flow__handle,
.react-flow__node.route-anchor-node .react-flow__handle,
.react-flow__node-route-anchor-node .react-flow__handle {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  width: 6px !important;
  min-width: 6px !important;
  height: 6px !important;
  min-height: 6px !important;
  transform: translate(-50%, -50%) !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  opacity: 0.01 !important;
  visibility: visible !important;
  pointer-events: none !important;
}
.well-token-node .react-flow__handle,
.duration-badge-node .react-flow__handle,
.responsible-badge-node .react-flow__handle,
.edge-label-node .react-flow__handle {
  width: 0 !important;
  min-width: 0 !important;
  height: 0 !important;
  min-height: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  opacity: 0 !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
.route-anchor-node,
.react-flow__node.route-anchor-node,
.react-flow__node-route-anchor-node {
  width: 8px !important;
  min-width: 8px !important;
  height: 8px !important;
  min-height: 8px !important;
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  outline: 0 !important;
  color: transparent !important;
  opacity: 1 !important;
  visibility: visible !important;
  pointer-events: none !important;
}
.well-token-node .markdown-node,
.duration-badge-node .markdown-node,
.responsible-badge-node .markdown-node,
.edge-label-node .markdown-node {
  pointer-events: auto;
  height: 100%;
}
.well-token-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.duration-badge-node .markdown-node {
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.responsible-badge-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.edge-label-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.duration-badge-node .duration-badge-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  max-width: 100%;
}
.responsible-badge-node .responsible-badge-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
}
.well-token-node .markdown-node p,
.duration-badge-node .markdown-node p,
.responsible-badge-node .markdown-node p,
.edge-label-node .markdown-node p {
  width: 100%;
  margin: 0 !important;
  text-align: center;
}
.flow-node-decision-diamond .markdown-node {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.flow-node-decision-diamond .markdown-node p {
  width: 100%;
  margin: 0 !important;
}
.flow-node .markdown-node {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.react-flow__node.flow-node:hover,
.react-flow__node-flow-node:hover,
.react-flow__node-flow-node-process:hover,
.react-flow__node-flow-node-decision-diamond:hover,
.react-flow__node-flow-node-database:hover,
.react-flow__node-flow-node-input-data:hover,
.react-flow__node-flow-node-event:hover,
.flow-node:hover {
  outline: 3px solid rgba(20, 184, 166, 0.36) !important;
  outline-offset: 4px !important;
  box-shadow:
    0 0 0 1px rgba(20, 184, 166, 0.20),
    0 18px 36px rgba(15, 23, 42, 0.18) !important;
}
.flow-node .node-card-text {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-weight: 760;
  line-height: 1.24;
  overflow-wrap: anywhere;
}
.flow-node .process-card-content {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  border-radius: 8px;
}
.flow-node .process-card-text {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-weight: 770;
  line-height: 1.24;
  overflow-wrap: anywhere;
}
</style>
""".strip()


def node_content(node: FlowNode, graph: FlowGraphDocument, wells_here: list[Well]) -> str:
    _ = graph
    _ = wells_here
    if _uses_responsible_card_content(node):
        return _responsible_node_content(node)
    return _generic_node_content(node)


def _uses_responsible_card_content(node: FlowNode) -> bool:
    return node.kind in {"process", "decision_diamond"} and bool(node.responsible)


def _responsible_node_content(node: FlowNode) -> str:
    return (
        f"{FLOW_NODE_CSS}\n"
        '<div class="process-card-content">'
        f'<div class="process-card-text">{escape(node.text)}</div>'
        "</div>"
    )


def _generic_node_content(node: FlowNode) -> str:
    return f'{FLOW_NODE_CSS}\n<div class="node-card-text">{escape(node.text)}</div>'


def well_token_content(well: Well) -> str:
    return f"{FLOW_NODE_CSS}\nСкв. **{short_well_name(well)}**"


def duration_badge_content(time_value: str) -> str:
    return (
        f"{FLOW_NODE_CSS}\n"
        '<span class="duration-badge-content">'
        f"&#9719; <strong>{duration_label(time_value)}</strong>"
        "</span>"
    )


def responsible_badge_content(label: str) -> str:
    return (
        f"{FLOW_NODE_CSS}\n"
        f'<span class="responsible-badge-content" title="{escape(label)}">'
        f"<strong>{escape(responsible_abbreviation(label))}</strong>"
        "</span>"
    )
