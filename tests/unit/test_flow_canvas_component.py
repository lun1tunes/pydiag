from __future__ import annotations

from pydiag.rendering.flow_canvas_component import _asset_text, flow_canvas_component


def test_flow_canvas_component_reuses_single_registration() -> None:
    assert flow_canvas_component() is flow_canvas_component()


def test_flow_canvas_fit_view_starts_from_top_padding() -> None:
    js = _asset_text("flow_canvas.js")

    assert "const FIT_VIEW_PADDING_TOP = 48;" in js
    assert "const FIT_VIEW_PADDING_BOTTOM = 64;" in js
    assert "state.view.y = round(FIT_VIEW_PADDING_TOP - bounds.top * scale);" in js
    assert "rect.height - FIT_VIEW_PADDING_TOP - FIT_VIEW_PADDING_BOTTOM" in js


def test_flow_canvas_persists_viewport_state_between_rerenders() -> None:
    js = _asset_text("flow_canvas.js")

    assert 'state.component.setStateValue("view"' in js
    assert 'state.component.setStateValue("user_moved_view", state.userMovedView);' in js
    assert "normalizePersistedViewState(payload.persisted_view_state)" in js
    assert "if (persistedViewState && state.lastRevision === null) {" in js
    assert "if (!persistedViewState && !state.userMovedView) {" in js


def test_flow_canvas_reuses_persistent_dom_and_patches_only_changed_scene_parts() -> None:
    js = _asset_text("flow_canvas.js")

    assert "if (root.__flowCanvasState) {" in js
    assert "return root.__flowCanvasState;" in js
    assert "initializeRootStructure(state);" in js
    assert "const graphChanged = state.sceneRevision !== payload.revision;" in js
    assert "rebuildGraphScene(state);" in js
    assert "if (state.renderedPositionsVersion !== state.positionsVersion) {" in js
    assert "updateNodePositions(state);" in js
    assert "updateSelectionState(state, state.renderedSelectedId, state.selectedId);" in js
    assert "state.dom.stage.style.transform =" in js


def test_flow_canvas_debounces_wheel_viewport_sync() -> None:
    js = _asset_text("flow_canvas.js")

    assert '{ id: "reset-view", label: "Reset view" },' in js
    assert "const VIEW_STATE_IDLE_SYNC_MS = 360;" in js
    assert "viewSyncTimer: null," in js
    assert "if (state.viewSyncTimer !== null) {" in js
    assert "scheduleViewStateSync(state);" in js
    assert "function scheduleViewStateSync(state, delay = VIEW_STATE_IDLE_SYNC_MS) {" in js


def test_flow_canvas_minimap_drag_uses_current_svg_after_rerender() -> None:
    js = _asset_text("flow_canvas.js")

    assert "attachMinimapHandlers(minimap, state);" in js
    assert "state.minimapBounds = bounds;" in js
    assert "const point = minimapPointToWorld(state.dom.minimapSvg, pointerEvent, state.minimapBounds);" in js
    assert "updateMinimapNodePositions(state);" in js
    assert "updateMinimapViewport(state);" in js
    assert "if (!rect.width || !rect.height) {" in js
    assert "syncViewState(state);" in js


def test_flow_canvas_root_uses_taller_workspace_height() -> None:
    css = _asset_text("flow_canvas.css")

    assert "height: clamp(575px, calc(100vh - 5rem), 828px);" in css
    assert "height: clamp(575px, calc(100dvh - 5rem), 828px);" in css


def test_flow_canvas_assets_define_shape_aware_blue_selection_effect() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert "buildNodeSelectionOverlay(node)" in js
    assert 'kind === "database"' in js
    assert "flow-node-selection__stroke" in css
    assert "--flow-accent-strong: #1d4ed8;" in css
    assert ".flow-node-card.is-selected {" in css


def test_flow_canvas_assets_define_fullscreen_mode() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert 'ownerDocument.addEventListener("fullscreenchange", state.fullscreenChangeHandler);' in js
    assert "requestElementFullscreen(state.root)" in js
    assert 'fullscreenButton.textContent = fullscreenActive ? "Exit" : "Full";' in js
    assert ".flow-canvas-root.is-fullscreen," in css
    assert ".flow-canvas-toolbar__button.is-active {" in css
