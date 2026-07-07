from __future__ import annotations

from pydiag.rendering.flow_figma_text_styles import (
    figma_font_weight,
    figma_text_align,
    figma_text_style,
    figma_vertical_align,
)


def test_figma_font_weight_and_alignment_normalize_imported_tokens() -> None:
    assert figma_font_weight(None) == 500
    assert figma_font_weight("ExtraBold Italic") == 800
    assert figma_font_weight("Heavy") == 900
    assert figma_text_align("CENTER") == "center"
    assert figma_text_align("unknown") == "left"
    assert figma_vertical_align("BOTTOM") == "flex-end"
    assert figma_vertical_align(None) == "flex-start"


def test_figma_text_style_preserves_imported_typography_and_active_opacity(documents) -> None:
    graph, _ = documents
    payload = graph.model_dump(mode="json")
    payload["nodes"][0]["type"] = "figma_text"
    payload["nodes"][0]["responsible"] = []
    payload["nodes"][0]["metadata"] = {
        "figma_font_size": 21,
        "figma_font_family": "IBM Plex Sans",
        "figma_font_style": "Bold Italic",
        "figma_text_align_horizontal": "LEFT",
        "figma_text_align_vertical": "TOP",
        "figma_letter_spacing_value": 1.5,
        "figma_line_height_value": 28,
        "figma_opacity": 0.85,
    }
    node = type(graph).model_validate(payload, strict=True).nodes[0]

    active_style = figma_text_style(node, active=True)
    inactive_style = figma_text_style(node, active=False)

    assert active_style["backgroundColor"] == "transparent"
    assert active_style["padding"] == "0"
    assert active_style["fontSize"] == "21.0px"
    assert "IBM Plex Sans" in str(active_style["fontFamily"])
    assert active_style["fontStyle"] == "italic"
    assert active_style["fontWeight"] == 700
    assert active_style["textAlign"] == "left"
    assert active_style["justifyContent"] == "flex-start"
    assert active_style["lineHeight"] == "28.0px"
    assert active_style["letterSpacing"] == "1.5px"
    assert active_style["opacity"] == 0.85
    assert inactive_style["opacity"] == 0.85 * 0.28
