from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v2 as components_v2

ASSETS_DIR = Path(__file__).resolve().parent / "flow_canvas_assets"


def render_flow_canvas(
    payload: dict[str, Any],
    *,
    key: str,
    default_selected_id: str | None,
    default_positions: dict[str, dict[str, float]],
) -> Any:
    component = flow_canvas_component()
    return component(
        key=key,
        data=payload,
        default={
            "selected_id": default_selected_id,
            "positions": default_positions,
        },
        height="content",
        on_selected_id_change=lambda: None,
        on_positions_change=lambda: None,
    )


def flow_canvas_component():
    return components_v2.component(
        "pydiag_flow_canvas",
        html="<div id='flow-canvas-root'></div>",
        css=_asset_text("flow_canvas.css"),
        js=_asset_text("flow_canvas.js"),
        isolate_styles=True,
    )


def _asset_text(filename: str) -> str:
    return (ASSETS_DIR / filename).read_text(encoding="utf-8")
