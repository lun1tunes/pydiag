from __future__ import annotations

from pydiag.rendering.flow_canvas_component import (
    _FLOW_CANVAS_COMPONENTS,
    _asset_text,
    flow_canvas_component,
)


def test_flow_canvas_component_reuses_registration_for_same_manager() -> None:
    _FLOW_CANVAS_COMPONENTS.clear()
    first = flow_canvas_component()
    second = flow_canvas_component()
    assert first is second
    assert 0 in _FLOW_CANVAS_COMPONENTS or len(_FLOW_CANVAS_COMPONENTS) >= 1


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
    assert 'state.component.setStateValue("selected_id", nextSelectedId);' in js
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
    assert "updateSelectionState(" in js
    assert "state.dom.stage.style.transform =" in js


def test_flow_canvas_supports_ctrl_multiselect_and_group_drag() -> None:
    js = _asset_text("flow_canvas.js")

    assert "selectedNodeIds: new Set()," in js
    assert "function isMultiSelectModifier(event)" in js
    assert "function resolveDragNodeIds(state, nodeId)" in js
    assert "selectId(state, node.id, { additive: isMultiSelectModifier(event) });" in js
    assert "state.suppressNextNodeClick = true;" in js
    assert "NODE_DRAG_CLICK_SUPPRESS_DISTANCE_PX" in js
    assert "event.ctrlKey || event.metaKey" in js
    assert "state.selectedNodeIds.has(nodeId) && state.selectedNodeIds.size > 1" in js
    assert "for (const id of state.draggingNodeIds)" in js


def test_flow_canvas_resets_positions_version_on_session_epoch_change() -> None:
    js = _asset_text("flow_canvas.js")

    assert "state.sessionEpoch !== payload.session_epoch" in js
    assert "state.positions = {};" in js
    assert "state.positionsVersion = 0;" in js
    assert "state.renderedPositionsVersion = -1;" in js
    # Epoch reset must not merely bump the counter.
    epoch_block_start = js.index("state.sessionEpoch !== payload.session_epoch")
    epoch_block = js[epoch_block_start : epoch_block_start + 800]
    assert "state.positionsVersion += 1;" not in epoch_block


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
    assert "if (!panDidMove && (state.selectedId !== null || state.selectedNodeIds.size > 0)) {" in js
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


def test_flow_canvas_edge_corners_keep_orthogonal_rounds_without_crushing_stubs() -> None:
    js = _asset_text("flow_canvas.js")

    assert "const CORNER_RADIUS = 14;" in js
    assert "const MIN_LEG_FOR_ROUND = 28;" in js
    assert "Q ${current.x} ${current.y} ${end.x} ${end.y}" in js


def test_flow_canvas_hosts_responsible_legend_beside_toolbar() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert 'createElement("div", "flow-canvas-topbar", root)' in js
    assert 'createElement("div", "flow-canvas-legend", topbar)' in js
    assert "function syncResponsibleLegend(state)" in js
    assert "function syncLegendHighlight(state)" in js
    assert "function toggleResponsibleFilter(state, responsibleKey)" in js
    assert "function syncResponsibleFilterDim(state)" in js
    assert "function ensureLegendClearButton(state)" in js
    assert 'createElement("button", "flow-canvas-legend__clear")' in js
    assert "setResponsibleFilter(state, [])" in js
    assert "state.dom.legendClear.hidden = !filterActive" in js
    assert 'state.component.setStateValue("responsible_filter", next)' in js
    assert "lastHostResponsibleFilter" in js
    assert "Host sent a different filter (sidebar / external)" in js
    assert "primary_responsible" in js
    assert "responsible_legend" in js
    assert ".flow-canvas-topbar {" in css
    assert ".flow-canvas-legend__item {" in css
    assert ".flow-canvas-legend__item.is-filter-active," in css
    assert ".flow-canvas-legend__clear {" in css
    assert ".flow-node-shell.is-filter-dimmed," in css
    assert ".flow-canvas-toolbar {" in css
    assert "margin-left: auto;" in css


def test_flow_canvas_assets_define_fullscreen_mode() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert 'ownerDocument.addEventListener("fullscreenchange", state.fullscreenChangeHandler);' in js
    assert "requestElementFullscreen(state.root)" in js
    assert "exitDocumentFullscreen(state.ownerDocument)" in js
    assert "fullscreenEnterIcon()" in js
    assert "fullscreenExitIcon()" in js
    assert 'fullscreenActive ? fullscreenExitIcon() : fullscreenEnterIcon()' in js
    assert ".flow-canvas-root.is-fullscreen," in css
    assert ".flow-canvas-toolbar__button--icon {" in css
    assert ".flow-canvas-toolbar__button.is-active {" in css
