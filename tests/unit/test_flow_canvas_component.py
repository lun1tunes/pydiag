from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

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


def test_flow_canvas_fit_view_centers_within_padded_viewport() -> None:
    js = _asset_text("flow_canvas.js")

    assert "const FIT_VIEW_PADDING_TOP = 48;" in js
    assert "const FIT_VIEW_PADDING_BOTTOM = 64;" in js
    assert "const FIT_VIEW_PADDING_X = 64;" in js
    assert "rect.height - FIT_VIEW_PADDING_TOP - FIT_VIEW_PADDING_BOTTOM" in js
    assert "(availableHeight - bounds.height * scale) / 2" in js
    assert "(availableWidth - bounds.width * scale) / 2" in js
    assert "FIT_VIEW_PADDING_TOP - bounds.top * scale);" not in js

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
    assert "const positionsChanged = state.renderedPositionsVersion !== state.positionsVersion;" in js
    assert "const edgeGeometryChanged = state.renderedEdgeGeometryVersion !== state.edgeGeometryVersion;" in js
    assert "updateNodePositions(state);" in js
    assert "updateEdgeGeometry(state);" in js
    assert "function updateEdgeGeometry(state) {" in js
    assert "function nodeMatchesClientFilters(node, state) {" in js
    assert "state.payload?.kind_filter" in js
    assert "state.payload?.search" in js
    assert "function updateDraggedNode(state, nodeId) {" in js
    assert "updateDraggedNode(state, state.draggingNodeId);" in js
    assert "updateEdgeGeometry(state);" in js
    assert "function liveEdgePoints(state, edge) {" in js
    assert "function nodePositionDelta(state, nodeId) {" in js
    # Drag path must refresh wires, not only the card shell.
    drag_block_start = js.index("if (state.draggingNodeIds.length) {")
    drag_block = js[drag_block_start : drag_block_start + 450]
    assert "updateDraggedNode(state, nodeId);" in drag_block
    assert "updateEdgeGeometry(state);" in drag_block
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
    assert "if (!panDidMove) {" in js
    assert "selectId(state, null);" in js
    assert "cancelConnectMode(state);" in js
    # Background deselect must not use click — pan synthesizes click after drag.
    assert 'viewport.addEventListener("click"' not in js
    assert "pendingSelectedId" in js
    assert "viewport.setPointerCapture" in js


def test_flow_canvas_edges_are_clickable_through_node_layer() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert "flow-edge-hit" in js
    assert "selectId(state, edge.id)" in js
    assert ".flow-canvas-nodes" in css
    assert "pointer-events: none;" in css
    assert ".flow-node-shell" in css
    assert "pointer-events: auto;" in css
    assert "pointer-events: stroke;" in css
    assert 'hitPath.setAttribute("stroke-width", "18")' in js


def test_flow_canvas_supports_drag_to_connect_handles() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert "edge_edit_enabled" in js
    assert "buildConnectionHandles(state, elements.shell, node)" in js
    assert 'setStateValue("pending_edge"' in js
    assert "request_id: requestId" in js
    assert "connectMode.submitted" in js
    assert "function canvasHasDirectedEdge(state, sourceId, targetId)" in js
    assert "Между этими карточками уже есть связь" in js
    assert "Drag-to-connect is finalized only by pointerup" in js
    assert "startConnectDrag(event, state, node.id, side, handle)" in js
    assert "completeConnectMode(state, dropId)" in js
    assert "function syncConnectPreview(state)" in js
    assert "function nodeIdFromWorldPoint(state, worldX, worldY)" in js
    assert "nodeIdFromDomPoint(state, clientX, clientY" in js
    assert "geometryFirst: true" in js
    assert "ignoreNodeId: sourceId" in js
    assert "Do NOT setPointerCapture on the handle" in js
    assert "function nodePaintRank(state, nodeId)" in js
    assert "ownerDocument.addEventListener(\"pointermove\", move, true);" in js
    assert "let stopped = false;" in js
    assert "flow-connect-preview" in js
    assert ".flow-node-handle" in css
    assert ".flow-connect-preview" in css
    assert ".flow-canvas-connect-hint" in css
    assert ".flow-canvas-root.is-connecting .flow-canvas-edges" in css
    assert "Потяните точку на карточке" not in js
    # Connect drag must not capture the handle (that stuck hit-tests to source).
    connect_start = js.index("function startConnectDrag(event, state, sourceId, side, handle)")
    connect_fn = js[connect_start : connect_start + 3500]
    assert "handle.setPointerCapture" not in connect_fn
    assert "geometryFirst: true" in connect_fn
    assert "stopped = true" in connect_fn


def test_flow_canvas_supports_undo_redo_toolbar_and_hotkeys() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")

    assert '{ id: "undo", label: "↶"' in js
    assert '{ id: "redo", label: "↷"' in js
    assert "function requestHistoryAction(state, action)" in js
    assert 'setStateValue("history_action"' in js
    assert "state.payload.can_undo" in js
    assert "state.payload.can_redo" in js
    assert 'requestHistoryAction(state, "undo")' in js
    assert 'requestHistoryAction(state, "redo")' in js
    assert ".flow-canvas-toolbar__button:disabled" in css


def test_flow_canvas_supports_selection_edit_hud() -> None:
    js = _asset_text("flow_canvas.js")
    css = _asset_text("flow_canvas.css")
    dom_utils = _asset_text("flow_canvas_dom_utils.js")

    assert "node_edit_enabled" in js
    assert "function beginTitleEdit(state, nodeId)" in js
    assert "function commitNodeEdit(state, nodeId, patch)" in js
    assert "function commitEdgeEdit(state, edgeId, patch)" in js
    assert "function syncSelectionEditHud(state)" in js
    assert 'setStateValue("pending_node_edit"' in js
    assert 'setStateValue("pending_edge_edit"' in js
    assert "function openKindMenu(state, nodeId, anchor)" in js
    assert "function openRolesPopover(state, nodeId, anchor)" in js
    assert "function applyOptimisticNodeEdit(state, nodeId, payload)" in js
    assert "function openDeleteConfirmPopover(state," in js
    assert "function openDurationPopover(state, nodeId, anchor)" in js
    assert "function parseDurationParts(raw)" in js
    assert "function formatDurationValue(amountRaw, unitId)" in js
    assert 'label: "минут"' in js
    assert 'label: "час"' in js
    assert 'label: "день"' in js
    assert "flow-edit-duration__unit" in js
    assert ".flow-edit-duration__unit" in css
    assert "flow-edit-confirm" in js
    assert "Удалить карточку?" in js
    assert "Удалить связь?" in js
    assert ".confirm(" not in js
    assert "window.confirm" not in js
    assert "flow-edit-hud" in js
    assert "flow-edit-menu" in js
    assert "flow-edit-field-popover" in js
    assert "function positionEditPopover(state, menu, anchor)" in js
    # Outside-dismiss must use Shadow-DOM-safe path (not contains(target) alone).
    assert "eventPathIncludes(event, menu)" in js
    assert "eventPathIncludes(event, anchor)" in js
    assert "eventPathIncludes(event, state.editHud)" in js
    assert "menu.contains(event.target)" not in js
    assert "_outsideAttachTimer" in js
    assert "opening click cannot dismiss immediately" in js
    assert "export function eventPathIncludes(event, node)" in dom_utils
    assert "composedPath" in dom_utils
    assert "Заголовок" in js
    assert "Тип связи" in js
    assert "flow-node-edit-panel" not in js
    assert "flow-node-roles-add" not in js
    assert "flow-node-kind-chip" not in js
    assert 'contentEditable = "true"' in js
    assert ".flow-edit-hud" in css
    assert ".flow-edit-menu" in css
    assert ".flow-edit-field-popover" in css
    assert ".flow-edit-confirm__message" in css
    assert ".flow-node-text.is-editing" in css
    assert ".flow-node-edit-panel" not in css


def test_flow_canvas_bundles_dom_utils_into_component_js() -> None:
    from pydiag.rendering import flow_canvas_component as mod

    source = inspect.getsource(mod._register_flow_canvas_component)
    assert "flow_canvas_dom_utils.js" in source
    assert 'replace("export "' in source


def test_event_path_includes_shadow_dom_regression_via_node() -> None:
    script = (
        Path(__file__).resolve().parent / "js" / "event_path_includes.test.mjs"
    )
    result = subprocess.run(
        ["node", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "event_path_includes: ok" in result.stdout


def test_duration_unit_helpers_via_node() -> None:
    script = Path(__file__).resolve().parent / "js" / "duration_units.test.mjs"
    result = subprocess.run(
        ["node", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "duration_units: ok" in result.stdout


def test_flow_canvas_refreshes_edge_geometry_without_revision_bump() -> None:
    js = _asset_text("flow_canvas.js")

    assert "function edgeGeometrySignature(edges)" in js
    assert "state.edgeGeometryVersion += 1" in js
    assert "edgeGeometryChanged" in js
    assert "Same revision + same live positions, but host re-routed edges" in js
    assert "updateEdgeGeometry(state)" in js
    assert "Keep wires glued to cards while dragging" in js


def test_flow_canvas_root_uses_viewport_workspace_height() -> None:
    css = _asset_text("flow_canvas.css")

    assert "height: var(--pydiag-workspace-height, max(575px, calc(100dvh - 5rem)));" in css
    assert "828px" not in css
    assert "clamp(575px" not in css


def test_flow_canvas_fit_view_scales_up_on_large_monitors() -> None:
    js = _asset_text("flow_canvas.js")

    assert "Math.min(availableWidth / bounds.width, availableHeight / bounds.height)," in js
    assert "1.75," in js
    assert "FIT_VIEW_PADDING_TOP" in js
    assert "(availableHeight - bounds.height * scale) / 2" in js
    # Legacy hard caps that left empty space on 2K monitors.
    assert "Math.min(availableWidth / bounds.width, availableHeight / bounds.height, 1.2)" not in js


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

    # CSS immersive mode survives Streamlit remounts (native Fullscreen does not).
    assert "immersiveMode: false" in js
    assert "function setImmersiveMode(state, enabled)" in js
    assert "function isImmersiveMode(state)" in js
    assert "state.immersiveMode" in js
    assert "requestElementFullscreen" not in js
    assert "exitDocumentFullscreen" not in js
    assert 'ownerDocument.addEventListener("fullscreenchange"' not in js
    assert "fullscreenEnterIcon()" in js
    assert "fullscreenExitIcon()" in js
    assert "fullscreenActive ? fullscreenExitIcon() : fullscreenEnterIcon()" in js
    assert "Escape" in js and "state.immersiveMode" in js
    assert ".flow-canvas-root.is-fullscreen {" in css
    assert "position: fixed;" in css
    assert "z-index: 10000;" in css
    assert ".flow-canvas-root:fullscreen" not in css
    assert ".flow-canvas-toolbar__button--icon {" in css
    assert ".flow-canvas-toolbar__button.is-active {" in css
