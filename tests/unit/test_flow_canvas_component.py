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


def test_flow_canvas_keeps_viewport_local_without_python_sync() -> None:
    js = _asset_text("flow_canvas.js")

    assert 'state.component.setStateValue("view"' not in js
    assert 'state.component.setStateValue("user_moved_view"' not in js
    assert "function syncViewState(" not in js
    assert "function scheduleViewStateSync(" not in js
    assert "persisted_view_state" not in js
    assert 'state.component.setStateValue("selected_id", value);' in js
    assert 'state.component.setStateValue("positions", copyPositionMap(state.positions));' in js


def test_flow_canvas_reuses_persistent_dom_and_patches_only_changed_scene_parts() -> None:
    js = _asset_text("flow_canvas.js")

    assert "function adoptCanvasState(component) {" in js
    assert "const CANVAS_STATE_STORE_KEY = \"__pydiagFlowCanvasStates\";" in js
    assert "store.get(CANVAS_STATE_KEY)" in js
    assert "parentElement.appendChild(state.root);" in js
    assert "return () => detachCanvasState(state);" in js
    assert "initializeRootStructure(state);" in js
    assert "const graphChanged = state.sceneRevision !== payload.revision || !state.hasRenderedScene;" in js
    assert "rebuildGraphScene(state);" in js
    assert "if (state.renderedPositionsVersion !== state.positionsVersion) {" in js
    assert "updateNodePositions(state);" in js
    assert "function updateDraggedNode(state, nodeId) {" in js
    assert "updateDraggedNode(state, state.draggingNodeId);" in js
    assert "updateSelectionState(state, state.renderedSelectedId, state.selectedId);" in js
    assert "state.dom.stage.style.transform =" in js


def test_flow_canvas_ignores_invalid_payload_instead_of_empty_flash() -> None:
    js = _asset_text("flow_canvas.js")

    assert "if (nextPayload === null) {" in js
    assert "Keep the current scene instead of flashing the empty state." in js
    assert "!Array.isArray(data.nodes) || !Array.isArray(data.edges)" in js
    assert "if (!payload || !Array.isArray(payload.nodes)) {" in js
    assert "return;" in js


def test_flow_canvas_minimap_drag_uses_current_svg_after_rerender() -> None:
    js = _asset_text("flow_canvas.js")

    assert "attachMinimapHandlers(minimap, state);" in js
    assert "state.minimapBounds = bounds;" in js
    assert "const point = minimapPointToWorld(state.dom.minimapSvg, pointerEvent, state.minimapBounds);" in js
    assert "updateMinimapNodePositions(state);" in js
    assert "updateMinimapViewport(state);" in js
    assert "if (!rect.width || !rect.height) {" in js
    assert "centerViewAtWorld(state, point.x, point.y);" in js
    assert "state.userMovedView = true;" in js


def test_flow_canvas_pan_does_not_clear_card_selection_on_click() -> None:
    js = _asset_text("flow_canvas.js")

    assert "PAN_CLICK_SUPPRESS_DISTANCE_PX" in js
    assert "if (!panDidMove && state.selectedId !== null) {" in js
    assert "selectId(state, null);" in js
    # Background deselect must not use click — pan synthesizes click after drag.
    assert 'viewport.addEventListener("click"' not in js
    assert "pendingSelectedId" in js
    assert "viewport.setPointerCapture" in js


def test_flow_canvas_root_uses_taller_workspace_height() -> None:
    css = _asset_text("flow_canvas.css")

    assert "height: clamp(575px, calc(100vh - 5rem), 828px);" in css
    assert "height: clamp(575px, calc(100dvh - 5rem), 828px);" in css


def test_flow_canvas_assets_define_shape_aware_blue_selection_effect() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert "buildNodeSelectionOverlay(node)" in js
    assert "nodeSelectionShapeDescriptors(node)" in js
    assert 'points: "50,2 98,50 50,98 2,50"' in js
    assert 'points: "13,2 98,2 87,98 2,98"' in js
    assert "M8 20 L8 78 C8 92 92 92 92 78 L92 20 Z" in js
    assert "flow-node-selection__stroke" in css
    assert "flow-node-selection__glow" in css
    assert "drop-shadow(0 0 16px rgba(59, 130, 246, 0.4))" in css
    assert "fill: none;" in css
    assert "flow-node-selection__sheen" not in css
    assert "--flow-accent-strong: #2563eb;" in css
    assert ".flow-node-card.is-selected {" in css


def test_flow_canvas_assets_define_fullscreen_mode() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert 'ownerDocument.addEventListener("fullscreenchange", state.fullscreenChangeHandler);' in js
    assert "requestElementFullscreen(state.root)" in js
    assert 'fullscreenButton.textContent = fullscreenActive ? "Exit" : "Full";' in js
    assert ".flow-canvas-root.is-fullscreen," in css
    assert ".flow-canvas-toolbar__button.is-active {" in css
