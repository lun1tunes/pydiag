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
    default_responsible_filter: list[str] | None = None,
) -> Any:
    return flow_canvas_component()(
        key=key,
        data=payload,
        default={
            "selected_id": default_selected_id,
            "positions": default_positions,
            "responsible_filter": list(default_responsible_filter or []),
            "pending_edge": None,
            "pending_node_edit": None,
            "pending_edge_edit": None,
            "history_action": None,
        },
        height="content",
        on_selected_id_change=lambda: None,
        on_positions_change=lambda: None,
        on_responsible_filter_change=lambda: None,
        on_pending_edge_change=lambda: None,
        on_pending_node_edit_change=lambda: None,
        on_pending_edge_edit_change=lambda: None,
        on_history_action_change=lambda: None,
    )


def flow_canvas_component():
    """Return the mount callable for the current Streamlit component manager.

    Registration is keyed by the active ``BidiComponentManager`` so a definition
    from one runtime/session cannot be reused after the manager is replaced.
    """
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
    # Dom utils are a separate asset so Node can unit-test Shadow DOM hit logic;
    # Streamlit injects one JS blob, so strip `export` and prepend.
    dom_utils = _asset_text("flow_canvas_dom_utils.js").replace("export ", "", 1)
    return components_v2.component(
        FLOW_CANVAS_COMPONENT_NAME,
        html="<div id='flow-canvas-root'></div>",
        css=_asset_text("flow_canvas.css"),
        js=f"{dom_utils}\n{_asset_text('flow_canvas.js')}",
        isolate_styles=True,
    )
