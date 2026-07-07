from __future__ import annotations

from pydiag.domain.models import FlowNode

__all__ = [
    "figma_font_weight",
    "figma_text_align",
    "figma_text_style",
    "figma_vertical_align",
    "metadata_float",
    "metadata_text",
]


def metadata_float(node: FlowNode, key: str) -> float | None:
    value = node.metadata.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def metadata_text(node: FlowNode, key: str) -> str | None:
    value = node.metadata.get(key)
    if isinstance(value, str):
        return value
    return None


def figma_font_weight(font_style: str | None) -> int:
    if not font_style:
        return 500
    normalized = font_style.casefold()
    if "thin" in normalized:
        return 100
    if "extralight" in normalized or "ultralight" in normalized:
        return 200
    if "light" in normalized:
        return 300
    if "regular" in normalized or "normal" in normalized:
        return 400
    if "medium" in normalized:
        return 500
    if "semibold" in normalized or "demibold" in normalized:
        return 600
    if "extrabold" in normalized or "ultrabold" in normalized:
        return 800
    if "bold" in normalized:
        return 700
    if "black" in normalized or "heavy" in normalized:
        return 900
    return 500


def figma_text_align(value: str | None) -> str:
    return {
        "LEFT": "left",
        "CENTER": "center",
        "RIGHT": "right",
        "JUSTIFIED": "justify",
    }.get((value or "").upper(), "left")


def figma_vertical_align(value: str | None) -> str:
    return {
        "TOP": "flex-start",
        "CENTER": "center",
        "BOTTOM": "flex-end",
    }.get((value or "").upper(), "flex-start")


def figma_text_style(node: FlowNode, *, active: bool) -> dict[str, str | float | int]:
    font_family = metadata_text(node, "figma_font_family") or "Inter"
    font_style = metadata_text(node, "figma_font_style")
    font_size = metadata_float(node, "figma_font_size") or 16
    line_height_value = metadata_float(node, "figma_line_height_value")
    letter_spacing = metadata_float(node, "figma_letter_spacing_value")
    imported_opacity = metadata_float(node, "figma_opacity")
    style: dict[str, str | float | int] = {
        "backgroundColor": "transparent",
        "backgroundImage": "none",
        "border": "0",
        "borderRadius": "0",
        "padding": "0",
        "boxShadow": "none",
        "filter": "none",
        "overflow": "visible",
        "fontFamily": f'"{font_family}", Inter, system-ui, sans-serif',
        "fontSize": f"{font_size}px",
        "fontWeight": figma_font_weight(font_style),
        "fontStyle": "italic" if font_style and "italic" in font_style.casefold() else "normal",
        "textAlign": figma_text_align(metadata_text(node, "figma_text_align_horizontal")),
        "display": "flex",
        "alignItems": "stretch",
        "justifyContent": figma_vertical_align(metadata_text(node, "figma_text_align_vertical")),
        "color": "#111827",
    }
    if line_height_value is not None and line_height_value > 0:
        style["lineHeight"] = f"{line_height_value}px"
    if letter_spacing is not None:
        style["letterSpacing"] = f"{letter_spacing}px"
    if imported_opacity is not None:
        style["opacity"] = imported_opacity if active else imported_opacity * 0.28
    return style
