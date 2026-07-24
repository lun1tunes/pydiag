"""Inspector collapse + related canvas chrome contracts."""

from __future__ import annotations

from pydiag.application.flow_view import (
    INSPECTOR_COLLAPSED_KEY,
    resolve_inspector_collapsed,
)
from pydiag.rendering.flow_canvas_component import _asset_text
from pydiag.rendering.flow_canvas_payload import build_flow_canvas_payload


def test_resolve_inspector_collapsed_mirrors_component_bool() -> None:
    session: dict = {}
    assert resolve_inspector_collapsed(session) is False

    session["well_drilling_flow_canvas"] = {"inspector_collapsed": True}
    assert resolve_inspector_collapsed(session) is True
    assert session[INSPECTOR_COLLAPSED_KEY] is True

    session["well_drilling_flow_canvas"] = {"inspector_collapsed": False}
    assert resolve_inspector_collapsed(session) is False
    assert session[INSPECTOR_COLLAPSED_KEY] is False


def test_resolve_inspector_collapsed_keeps_session_when_component_missing() -> None:
    session = {INSPECTOR_COLLAPSED_KEY: True}
    assert resolve_inspector_collapsed(session) is True
    session["well_drilling_flow_canvas"] = {"selected_id": "n1"}
    assert resolve_inspector_collapsed(session) is True


def test_payload_includes_inspector_collapsed(documents) -> None:
    graph, wells = documents
    payload = build_flow_canvas_payload(
        graph,
        wells,
        inspector_collapsed=True,
    )
    assert payload["inspector_collapsed"] is True


def test_inspector_toggle_and_immersive_assets() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")
    assert "function toggleInspectorCollapsed(state)" in js
    assert "function syncInspectorToggle(state)" in js
    assert "function syncImmersiveHost(state)" in js
    assert "function getShadowHost(state)" in js
    assert "_lightParent.isConnected" in js
    assert 'setStateValue("inspector_collapsed"' in js
    assert "Скрыть инспектор" in js
    assert "Показать инспектор" in js
    assert ".flow-canvas-inspector-toggle" in css
    assert "function openApproversPopover(state, nodeId, anchor)" in js
    assert 'label: "Согласующие"' in js
