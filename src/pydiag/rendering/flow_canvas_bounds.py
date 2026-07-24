from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .flow_edge_labels import EDGE_LABEL_GAP
from .flow_node_overlays import (
    RESPONSIBLE_BADGE_GAP,
    WELL_TOKEN_COLUMN_GAP,
    WELL_TOKEN_WIDTH,
    well_token_stack_height,
)


def flow_canvas_bounds(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, float]:
    left = 10_000.0
    top = 10_000.0
    right = 0.0
    bottom = 0.0

    for node in nodes:
        x = float(node["position"]["x"])
        y = float(node["position"]["y"])
        w = float(node["size"]["w"])
        h = float(node["size"]["h"])
        left = min(left, x)
        top = min(top, y - 36)
        right = max(right, x + max(w, node_overlay_width(node)))
        bottom = max(bottom, y + h + well_token_stack_height(len(node["well_tokens"])))

    for edge in edges:
        for point in edge["points"]:
            left = min(left, float(point["x"]))
            top = min(top, float(point["y"]))
            right = max(right, float(point["x"]))
            bottom = max(bottom, float(point["y"]))
        label = edge["label"]
        if label is not None:
            left = min(left, float(label["position"]["x"]) - EDGE_LABEL_GAP)
            top = min(top, float(label["position"]["y"]) - EDGE_LABEL_GAP)
            right = max(
                right, float(label["position"]["x"]) + float(label["width"]) + EDGE_LABEL_GAP
            )
            bottom = max(
                bottom,
                float(label["position"]["y"]) + float(label["height"]) + EDGE_LABEL_GAP,
            )

    if left == 10_000.0:
        left = 0.0
    return {
        "left": round(left - 60, 2),
        "top": round(top - 40, 2),
        "right": round(right + 60, 2),
        "bottom": round(bottom + 60, 2),
        "width": round(max(0.0, right - left + 120), 2),
        "height": round(max(0.0, bottom - top + 100), 2),
    }


def node_overlay_width(node_payload: Mapping[str, Any]) -> float:
    size_width = float(node_payload["size"]["w"])
    top_width = 10.0
    time_badge = node_payload["time_badge"]
    if time_badge is not None:
        top_width += float(time_badge["style"].get("width", "0").removesuffix("px"))
        top_width += RESPONSIBLE_BADGE_GAP
    for badge in node_payload["responsible_badges"]:
        top_width += float(badge["style"].get("width", "0").removesuffix("px"))
        top_width += RESPONSIBLE_BADGE_GAP

    token_width = size_width
    token_count = len(node_payload["well_tokens"])
    if token_count:
        visible_cols = 2 if token_count > 1 else 1
        token_width = max(
            token_width,
            14 + visible_cols * WELL_TOKEN_WIDTH + max(0, visible_cols - 1) * WELL_TOKEN_COLUMN_GAP,
        )
    note_width = size_width
    note = node_payload.get("note")
    if isinstance(note, str) and note.strip():
        # Prefer placing the note to the right of the card.
        note_width = size_width + 12 + min(200.0, max(72.0, len(note.strip()) * 6.5 + 20))
    return max(size_width, top_width, token_width, note_width)
