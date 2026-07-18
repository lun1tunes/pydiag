from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v2 as components_v2
from streamlit.components.v2.get_bidi_component_manager import (
    get_bidi_component_manager,
)
from streamlit.runtime import Runtime

ASSETS_DIR = Path(__file__).resolve().parent / "flow_canvas_assets"
FLOW_CANVAS_COMPONENT_NAME = "pydiag_flow_canvas"
_FLOW_CANVAS_COMPONENTS: dict[int, Any] = {}


def render_flow_canvas(
    payload: dict[str, Any],
    *,
    key: str,
    default_selected_id: str | None,
    default_positions: dict[str, dict[str, float]],
    persisted_view_state: dict[str, float | bool] | None = None,
) -> Any:
    component_payload = dict(payload)
    component_payload["persisted_view_state"] = persisted_view_state
    return flow_canvas_component()(
        key=key,
        data=component_payload,
        default={
            "selected_id": default_selected_id,
            "positions": default_positions,
            "view": (
                {
                    "x": float(persisted_view_state["x"]),
                    "y": float(persisted_view_state["y"]),
                    "scale": float(persisted_view_state["scale"]),
                }
                if persisted_view_state is not None
                else None
            ),
            "user_moved_view": (
                bool(persisted_view_state.get("user_moved_view"))
                if persisted_view_state is not None
                else False
            ),
        },
        height="content",
        on_selected_id_change=lambda: None,
        on_positions_change=lambda: None,
        on_view_change=lambda: None,
        on_user_moved_view_change=lambda: None,
    )


def flow_canvas_component():
    if not Runtime.exists():
        component = _FLOW_CANVAS_COMPONENTS.get(0)
        if component is None:
            component = _register_flow_canvas_component()
            _FLOW_CANVAS_COMPONENTS[0] = component
        return component

    manager = get_bidi_component_manager()
    manager_key = id(manager)
    component = _FLOW_CANVAS_COMPONENTS.get(manager_key)
    if component is None or manager.get(FLOW_CANVAS_COMPONENT_NAME) is None:
        component = _register_flow_canvas_component()
        _FLOW_CANVAS_COMPONENTS[manager_key] = component
    return component


def _asset_text(filename: str) -> str:
    return (ASSETS_DIR / filename).read_text(encoding="utf-8")


def _register_flow_canvas_component():
    return components_v2.component(
        FLOW_CANVAS_COMPONENT_NAME,
        html="<div id='flow-canvas-root'></div>",
        css=_asset_text("flow_canvas.css"),
        js=_asset_text("flow_canvas.js"),
        isolate_styles=True,
    )
