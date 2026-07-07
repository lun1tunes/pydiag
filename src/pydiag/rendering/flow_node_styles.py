from __future__ import annotations

from pydiag.domain.models import FlowGraphDocument, FlowNode

from .flow_figma_text_styles import (
    figma_font_weight,
    figma_text_align,
    figma_text_style,
    figma_vertical_align,
)
from .flow_node_shape_backgrounds import (
    database_background,
    decision_diamond_background,
    input_data_background,
)

__all__ = [
    "figma_font_weight",
    "figma_text_align",
    "figma_vertical_align",
    "flow_node_class_name",
    "node_style",
]


def flow_node_class_name(node: FlowNode) -> str:
    return f"flow-node flow-node-{node.kind.replace('_', '-')}"


def primary_responsible_style(node: FlowNode, graph: FlowGraphDocument):
    primary_responsible = node.primary_responsible
    if primary_responsible in graph.responsibles:
        return graph.responsibles[primary_responsible]
    return next(iter(graph.responsibles.values()))


def node_style(
    node: FlowNode,
    graph: FlowGraphDocument,
    *,
    node_width: int,
    node_height: int,
    selected: bool,
    active: bool,
) -> dict[str, str | float | int]:
    style: dict[str, str | float | int] = {
        "width": f"{node_width}px",
        "height": f"{node_height}px",
        "boxSizing": "border-box",
        "padding": "10px 14px",
        "fontSize": "12px",
        "lineHeight": "1.22",
        "fontFamily": "Inter, system-ui, sans-serif",
        "textAlign": "center",
        "wordBreak": "break-word",
        "overflowWrap": "anywhere",
        "whiteSpace": "normal",
        "overflow": "hidden",
        "opacity": 1.0 if active else 0.28,
        "transition": "opacity 160ms ease, box-shadow 160ms ease, transform 160ms ease",
    }

    if node.kind == "process":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": responsible.fill,
                "border": f"2px solid {responsible.border}",
                "borderRadius": "8px",
                "color": responsible.text,
                "overflow": "visible",
                "boxShadow": "0 12px 26px rgba(15, 23, 42, 0.12)",
            }
        )
    elif node.kind == "decision_diamond":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": decision_diamond_background(responsible.fill),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "24px 52px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "textAlign": "center",
                "color": responsible.text,
                "filter": "drop-shadow(0 12px 18px rgba(51, 65, 85, 0.12))",
            }
        )
    elif node.kind == "decision_card":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": responsible.fill,
                "border": f"2px solid {responsible.border}",
                "borderRadius": "22px",
                "color": responsible.text,
                "boxShadow": "0 12px 24px rgba(15, 23, 42, 0.10)",
            }
        )
    elif node.kind == "database":
        style.update(
            {
                "background": "transparent",
                "backgroundImage": database_background(),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "borderRadius": "0",
                "padding": "38px 40px",
                "fontSize": "11.5px",
                "lineHeight": "1.2",
                "textAlign": "center",
                "color": "#111827",
                "filter": "drop-shadow(0 12px 18px rgba(15, 23, 42, 0.13))",
            }
        )
    elif node.kind == "input_data":
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": input_data_background(),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "16px 48px",
                "color": "#183557",
                "filter": "drop-shadow(0 12px 18px rgba(30, 64, 175, 0.10))",
            }
        )
    elif node.kind == "event":
        style.update(
            {
                "backgroundColor": "#ffffff",
                "border": "2px solid #111827",
                "borderRadius": "32px",
                "padding": "12px 28px",
                "color": "#111827",
                "boxShadow": "0 12px 22px rgba(15, 23, 42, 0.10)",
            }
        )
    elif node.kind == "figma_text":
        style.update(figma_text_style(node, active=active))

    if selected:
        style.update(
            {
                "boxShadow": "0 0 0 4px rgba(20, 184, 166, 0.24), 0 18px 36px rgba(15, 23, 42, 0.18)",
                "transform": "translateY(-1px)",
            }
        )

    return style
