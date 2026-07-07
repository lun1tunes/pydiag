from __future__ import annotations

import re
from math import ceil

from pydiag.domain.models import FlowGraphDocument, FlowNode, Well, parse_node_time

from .flow_render_math import ceil_to_step

DURATION_BADGE_MIN_WIDTH = 64
DURATION_BADGE_MAX_WIDTH = 128
DURATION_BADGE_CHAR_WIDTH = 6.6
DURATION_BADGE_ICON_WIDTH = 14
DURATION_BADGE_HORIZONTAL_PADDING = 18
RESPONSIBLE_BADGE_MIN_WIDTH = 42
RESPONSIBLE_BADGE_MAX_WIDTH = 86
RESPONSIBLE_BADGE_HEIGHT = 24
RESPONSIBLE_BADGE_CHAR_WIDTH = 7.2
RESPONSIBLE_BADGE_HORIZONTAL_PADDING = 18
RESPONSIBLE_BADGE_GAP = 6
WELL_TOKEN_WIDTH = 136
WELL_TOKEN_HEIGHT = 42
WELL_TOKEN_COLUMN_GAP = 10
WELL_TOKEN_ROW_STEP = 50
WELL_TOKEN_STRIPE_WIDTH = 8
MAX_VISIBLE_WELL_TOKENS = 4

__all__ = [
    "MAX_VISIBLE_WELL_TOKENS",
    "RESPONSIBLE_BADGE_GAP",
    "WELL_TOKEN_COLUMN_GAP",
    "WELL_TOKEN_WIDTH",
    "ceil_to_step",
    "duration_badge_position",
    "duration_badge_style",
    "duration_badge_width",
    "duration_label",
    "responsible_abbreviation",
    "responsible_badge_position",
    "responsible_badge_style",
    "responsible_badge_width",
    "short_well_name",
    "well_token_position",
    "well_token_stack_height",
    "well_token_style",
]


def short_well_name(well: Well) -> str:
    name = well.name.replace("Скв.", "").replace("скв.", "").strip()
    return name[:16]


def responsible_abbreviation(label: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", label)
    if not words:
        return label[:4].upper()
    if len(words) > 1:
        return "".join(word[0] for word in words[:4]).upper()
    word = words[0]
    if word.isupper() and len(word) <= 6:
        return word
    return word[:3].upper()


def duration_label(time_value: str) -> str:
    amount, unit = parse_node_time(time_value)
    unit_label = {
        "minute": "мин",
        "hour": "ч",
        "day": "д",
    }[unit]
    return f"{amount} {unit_label}"


def duration_badge_width(time_value: str) -> int:
    text_width = len(duration_label(time_value)) * DURATION_BADGE_CHAR_WIDTH
    width = ceil_to_step(
        int(ceil(DURATION_BADGE_HORIZONTAL_PADDING + DURATION_BADGE_ICON_WIDTH + text_width)),
        2,
    )
    return max(DURATION_BADGE_MIN_WIDTH, min(width, DURATION_BADGE_MAX_WIDTH))


def responsible_badge_width(label: str) -> int:
    text_width = len(responsible_abbreviation(label)) * RESPONSIBLE_BADGE_CHAR_WIDTH
    width = ceil_to_step(
        int(ceil(RESPONSIBLE_BADGE_HORIZONTAL_PADDING + text_width)),
        2,
    )
    return max(RESPONSIBLE_BADGE_MIN_WIDTH, min(width, RESPONSIBLE_BADGE_MAX_WIDTH))


def well_token_position(
    node_position: tuple[float, float],
    node_height: int,
    index: int,
) -> tuple[float, float]:
    row = index // 2
    col = index % 2
    return (
        node_position[0] + 14 + col * (WELL_TOKEN_WIDTH + WELL_TOKEN_COLUMN_GAP),
        node_position[1] + node_height + 12 + row * WELL_TOKEN_ROW_STEP,
    )


def duration_badge_position(node_position: tuple[float, float]) -> tuple[float, float]:
    return (node_position[0] + 10, node_position[1] - 30)


def responsible_badge_position(
    node_position: tuple[float, float],
    node: FlowNode,
    graph: FlowGraphDocument,
    responsible_index: int,
) -> tuple[float, float]:
    x = node_position[0] + 10
    if node.time is not None:
        x += duration_badge_width(node.time) + RESPONSIBLE_BADGE_GAP
    for responsible in node.secondary_responsibles[:responsible_index]:
        if responsible in graph.responsibles:
            x += responsible_badge_width(graph.responsibles[responsible].label)
            x += RESPONSIBLE_BADGE_GAP
    return (x, node_position[1] - 30)


def well_token_stack_height(well_count: int) -> int:
    if well_count <= 0:
        return 0
    visible_tokens = min(well_count, MAX_VISIBLE_WELL_TOKENS + 1)
    rows = (visible_tokens + 1) // 2
    return 12 + rows * WELL_TOKEN_ROW_STEP


def well_token_style(selected: bool, active: bool) -> dict[str, str | float]:
    accent = "#0f766e" if selected else "#14b8a6"
    fill = "#ccfbf1" if selected else "#f0fdfa"
    return {
        "width": f"{WELL_TOKEN_WIDTH}px",
        "height": f"{WELL_TOKEN_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "0 16px",
        "borderRadius": "999px",
        "border": f"1px solid {accent}",
        "background": (
            f"linear-gradient(90deg, {accent} 0 {WELL_TOKEN_STRIPE_WIDTH}px, "
            f"{fill} {WELL_TOKEN_STRIPE_WIDTH}px 100%)"
        ),
        "color": "#064e3b",
        "fontSize": "13px",
        "fontWeight": 750,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 10px 22px rgba(15, 118, 110, 0.16)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease, background 160ms ease, border-color 160ms ease",
    }


def duration_badge_style(
    active: bool,
    time_value: str,
) -> dict[str, str | float]:
    return {
        "width": f"{duration_badge_width(time_value)}px",
        "height": "24px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": "1px solid #fda4af",
        "backgroundColor": "#fff1f2",
        "color": "#9f1239",
        "fontSize": "11px",
        "fontWeight": 700,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 8px 18px rgba(190, 18, 60, 0.12)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }


def responsible_badge_style(
    active: bool,
    label: str,
    fill: str,
    border: str,
    text: str,
) -> dict[str, str | float]:
    return {
        "width": f"{responsible_badge_width(label)}px",
        "height": f"{RESPONSIBLE_BADGE_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": f"1px solid {border}",
        "backgroundColor": fill,
        "color": text,
        "fontSize": "10.5px",
        "fontWeight": 780,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 8px 18px rgba(15, 23, 42, 0.12)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }
