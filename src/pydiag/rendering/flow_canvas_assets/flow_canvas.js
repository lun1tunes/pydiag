const TOOLBAR_BUTTONS = [
  { id: "undo", label: "↶", title: "Отменить (Ctrl+Z)" },
  { id: "redo", label: "↷", title: "Повторить (Ctrl+Shift+Z)" },
  { id: "zoom-in", label: "+" },
  { id: "zoom-out", label: "-" },
  { id: "reset-view", label: "Reset view" },
];
const FIT_VIEW_PADDING_X = 64;
const FIT_VIEW_PADDING_TOP = 48;
const FIT_VIEW_PADDING_BOTTOM = 64;
const PAN_CLICK_SUPPRESS_DISTANCE_PX = 4;
const NODE_DRAG_CLICK_SUPPRESS_DISTANCE_PX = 4;
const MARQUEE_MIN_SIZE_PX = 4;
const CANVAS_STATE_STORE_KEY = "__pydiagFlowCanvasStates";
const CANVAS_STATE_KEY = "well_drilling_flow_canvas_v2";
const IMMERSIVE_STORAGE_KEY = "pydiag-flow-canvas-immersive";

export default function(component) {
  const state = adoptCanvasState(component);
  const nextPayload = normalizePayload(component.data);
  if (nextPayload === null) {
    // Intermediate Streamlit mounts can arrive without valid data.
    // Keep the current scene instead of flashing the empty state.
    return () => detachCanvasState(state);
  }
  state.payload = nextPayload;
  syncStateFromPayload(state);
  queueRender(state);

  // Soft cleanup only: Streamlit remounts the host on fragment/app reruns.
  // Keep scene/view/selection in a document store so the graph stays static.
  return () => detachCanvasState(state);
}

function getCanvasStateStore(ownerDocument) {
  if (!ownerDocument[CANVAS_STATE_STORE_KEY]) {
    ownerDocument[CANVAS_STATE_STORE_KEY] = new Map();
  }
  return ownerDocument[CANVAS_STATE_STORE_KEY];
}

function adoptCanvasState(component) {
  const parentElement = component.parentElement;
  const ownerDocument = getOwnerDocument(parentElement);
  const store = getCanvasStateStore(ownerDocument);
  let state = store.get(CANVAS_STATE_KEY);

  if (state) {
    if (state.root.parentElement !== parentElement && !isImmersiveMode(state)) {
      for (const child of parentElement.querySelectorAll(".flow-canvas-root")) {
        if (child !== state.root) {
          child.remove();
        }
      }
      parentElement.appendChild(state.root);
    }
    state.component = component;
    state.ownerDocument = ownerDocument;
    state._hostParent = parentElement;
    state.root.__flowCanvasState = state;
    attachCanvasObservers(state);
    syncImmersiveHost(state);
    return state;
  }

  const root = ensureRoot(parentElement);
  state = createCanvasState(root, component, ownerDocument);
  state._hostParent = parentElement;
  initializeRootStructure(state);
  attachCanvasObservers(state);
  root.__flowCanvasState = state;
  store.set(CANVAS_STATE_KEY, state);
  syncImmersiveHost(state);
  return state;
}

function detachCanvasState(state) {
  if (state.resizeObserver) {
    state.resizeObserver.disconnect();
    state.resizeObserver = null;
  }
}

function attachCanvasObservers(state) {
  if (!state.resizeObserver) {
    state.resizeObserver = new ResizeObserver(() => {
      // Only auto-fit before the first successful paint. Remount size flicker
      // after title edits must not yank the camera.
      if (!state.userMovedView && !state.hasRenderedScene) {
        fitView(state);
      }
      queueRender(state);
    });
    state.resizeObserver.observe(state.root);
  }
  // Restore immersive chrome after Streamlit remounts the host.
  syncFullscreenClass(state);
}

function ensureRoot(parentElement) {
  let root = parentElement.querySelector(".flow-canvas-root");
  if (!root) {
    root = document.createElement("div");
    root.className = "flow-canvas-root";
    parentElement.appendChild(root);
  }
  return root;
}

function createCanvasState(root, component, ownerDocument) {
  return {
    root,
    component,
    payload: normalizePayload(component.data) || {
      nodes: [],
      edges: [],
      canvas: { width: 1200, height: 900 },
      bounds: { left: 0, top: 0, right: 1200, bottom: 900, width: 1200, height: 900 },
      selected_id: null,
      position_edit_enabled: false,
      edge_edit_enabled: false,
      node_edit_enabled: false,
      revision: null,
    },
    nodePayloadsById: new Map(),
    edgePayloadsById: new Map(),
    tokenPayloadsById: new Map(),
    view: { x: 0, y: 0, scale: 1 },
    userMovedView: false,
    positions: {},
    positionsVersion: 0,
    selectedId: null,
    pendingSelectedId: undefined,
    selectedNodeIds: new Set(),
    selectedEdgeIds: new Set(),
    selectedProcessId: null,
    nodeClipboard: [],
    clipboardPasteCount: 0,
    suppressNextNodeClick: false,
    editingTitleNodeId: null,
    activeEditPopover: null,
    editHud: null,
    marqueeEl: null,
    spacePanHeld: false,
    responsibleFilter: [],
    pendingResponsibleFilter: undefined,
    lastHostResponsibleFilter: [],
    sessionEpoch: null,
    isPanning: false,
    isMarqueeSelecting: false,
    draggingNodeId: null,
    draggingNodeIds: [],
    connectMode: null,
    immersiveMode: readStoredImmersiveMode(ownerDocument),
    _hostParent: null,
    _lightParent: null,
    frameRequested: false,
    lastRevision: null,
    sceneRevision: null,
    sceneTopologySignature: null,
    lastEdgeGeometrySignature: null,
    edgeGeometryVersion: 0,
    renderedSelectedId: null,
    renderedSelectedNodeIds: new Set(),
    renderedSelectedEdgeIds: new Set(),
    renderedPositionsVersion: -1,
    renderedEdgeGeometryVersion: -1,
    renderedDraggingNodeId: null,
    renderedDraggingNodeIds: [],
    resizeObserver: null,
    keydownHandler: null,
    keyupHandler: null,
    ownerDocument,
    dom: null,
    edgeElements: new Map(),
    nodeElements: new Map(),
    processElements: new Map(),
    tokenElements: new Map(),
    minimapNodeElements: new Map(),
    minimapBounds: null,
    hasRenderedScene: false,
  };
}

function initializeRootStructure(state) {
  const root = state.root;
  root.replaceChildren();

  const emptyState = createElement("div", "flow-empty-state", root);
  emptyState.textContent = "На схеме пока нет элементов.";
  emptyState.hidden = true;

  const topbar = createElement("div", "flow-canvas-topbar", root);
  topbar.hidden = true;
  const legend = createElement("div", "flow-canvas-legend", topbar);
  legend.setAttribute("aria-label", "Ответственные");

  const toolbar = createElement("div", "flow-canvas-toolbar", topbar);
  const toolbarButtons = {};
  for (const buttonDef of TOOLBAR_BUTTONS) {
    const button = createElement("button", "flow-canvas-toolbar__button", toolbar);
    button.type = "button";
    button.textContent = buttonDef.label;
    if (buttonDef.title) {
      button.title = buttonDef.title;
      button.setAttribute("aria-label", buttonDef.title);
    }
    button.addEventListener("click", () => {
      if (buttonDef.id === "undo") {
        requestHistoryAction(state, "undo");
        return;
      }
      if (buttonDef.id === "redo") {
        requestHistoryAction(state, "redo");
        return;
      }
      if (buttonDef.id === "zoom-in") {
        zoomAtCenter(state, 1.12);
      } else if (buttonDef.id === "zoom-out") {
        zoomAtCenter(state, 1 / 1.12);
      } else {
        state.userMovedView = false;
        fitView(state);
      }
      queueRender(state);
    });
    toolbarButtons[buttonDef.id] = button;
  }

  const fullscreenButton = createElement(
    "button",
    "flow-canvas-toolbar__button flow-canvas-toolbar__button--icon",
    toolbar,
  );
  fullscreenButton.type = "button";
  fullscreenButton.addEventListener("click", () => {
    toggleFullscreen(state);
    // Immediate visual feedback; fullscreenchange will sync again shortly.
    syncToolbarState(state);
  });

  const connectHint = createElement("div", "flow-canvas-connect-hint", root);
  connectHint.hidden = true;

  const viewport = createElement("div", "flow-canvas-viewport", root);
  viewport.hidden = true;
  attachViewportHandlers(viewport, state);

  const stage = createElement("div", "flow-canvas-stage", viewport);
  const svg = createSvgElement("svg");
  svg.classList.add("flow-canvas-edges");
  stage.appendChild(svg);

  const defs = createSvgElement("defs");
  svg.appendChild(defs);
  const edgeLayer = createSvgElement("g");
  svg.appendChild(edgeLayer);
  const connectPreview = createSvgElement("path");
  connectPreview.classList.add("flow-connect-preview");
  connectPreview.setAttribute("hidden", "");
  svg.appendChild(connectPreview);

  const labelsLayer = createElement("div", "flow-canvas-labels", stage);
  const processesLayer = createElement("div", "flow-canvas-processes", stage);
  const nodesLayer = createElement("div", "flow-canvas-nodes", stage);

  const minimap = createElement("div", "flow-canvas-minimap", root);
  minimap.hidden = true;
  minimap.setAttribute("role", "img");
  minimap.setAttribute("aria-label", "Миникарта схемы");
  attachMinimapHandlers(minimap, state);

  const minimapSvg = createSvgElement("svg");
  minimapSvg.classList.add("flow-canvas-minimap__svg");
  minimap.appendChild(minimapSvg);

  const minimapBackdrop = createSvgElement("rect");
  minimapBackdrop.classList.add("flow-canvas-minimap__backdrop");
  minimapSvg.appendChild(minimapBackdrop);

  const minimapEdgeLayer = createSvgElement("g");
  minimapSvg.appendChild(minimapEdgeLayer);

  const minimapNodeLayer = createSvgElement("g");
  minimapSvg.appendChild(minimapNodeLayer);

  const minimapViewport = createSvgElement("rect");
  minimapViewport.classList.add("flow-canvas-minimap__viewport");
  minimapViewport.setAttribute("rx", "12");
  minimapSvg.appendChild(minimapViewport);

  const addNodeButton = createElement("button", "flow-canvas-add-node", root);
  addNodeButton.type = "button";
  addNodeButton.textContent = "+ Карточка";
  addNodeButton.title = "Добавить карточку";
  addNodeButton.setAttribute("aria-label", "Добавить карточку");
  addNodeButton.hidden = true;
  addNodeButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    requestCreateNode(state);
  });

  const inspectorToggle = createElement("button", "flow-canvas-inspector-toggle", root);
  inspectorToggle.type = "button";
  inspectorToggle.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    toggleInspectorCollapsed(state);
  });

  state.dom = {
    emptyState,
    topbar,
    legend,
    legendClear: null,
    toolbar,
    toolbarButtons,
    fullscreenButton,
    connectHint,
    viewport,
    stage,
    svg,
    defs,
    edgeLayer,
    connectPreview,
    labelsLayer,
    processesLayer,
    nodesLayer,
    minimap,
    minimapSvg,
    minimapBackdrop,
    minimapEdgeLayer,
    minimapNodeLayer,
    minimapViewport,
    addNodeButton,
    inspectorToggle,
  };

  if (!state.keydownHandler) {
    state.keydownHandler = (event) => {
      if (event.code === "Space" && !isEditableKeyboardTarget(event.target)) {
        state.spacePanHeld = true;
        if (!event.repeat) {
          event.preventDefault();
        }
      }
      if (event.key === "Escape" && state.activeEditPopover) {
        closeActiveEditPopover(state);
        return;
      }
      if (event.key === "Escape" && state.connectMode) {
        cancelConnectMode(state);
        return;
      }
      if (event.key === "Escape" && state.immersiveMode) {
        event.preventDefault();
        setImmersiveMode(state, false);
        return;
      }
      if (isEditableKeyboardTarget(event.target)) {
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && canBulkDeleteSelection(state)) {
        event.preventDefault();
        requestBulkDeleteSelection(state);
        return;
      }
      const mod = event.ctrlKey || event.metaKey;
      if (!mod) {
        return;
      }
      const key = String(event.key || "").toLowerCase();
      if (key === "c") {
        if (copySelectedNodesToClipboard(state)) {
          event.preventDefault();
        }
        return;
      }
      if (key === "v") {
        if (pasteNodesFromClipboard(state)) {
          event.preventDefault();
        }
        return;
      }
      if (key === "z" && event.shiftKey) {
        event.preventDefault();
        requestHistoryAction(state, "redo");
        return;
      }
      if (key === "z") {
        event.preventDefault();
        requestHistoryAction(state, "undo");
        return;
      }
      if (key === "y") {
        event.preventDefault();
        requestHistoryAction(state, "redo");
      }
    };
    state.keyupHandler = (event) => {
      if (event.code === "Space") {
        state.spacePanHeld = false;
      }
    };
    state.ownerDocument.addEventListener("keydown", state.keydownHandler);
    state.ownerDocument.addEventListener("keyup", state.keyupHandler);
  }
}

function normalizePayload(data) {
  if (!data || typeof data !== "object" || !Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
    return null;
  }
  if (!data.canvas || typeof data.canvas !== "object" || !data.bounds || typeof data.bounds !== "object") {
    return null;
  }
  return data;
}

function syncStateFromPayload(state) {
  const payload = state.payload;
  if (Object.prototype.hasOwnProperty.call(payload, "session_epoch")) {
    if (state.sessionEpoch === null) {
      state.sessionEpoch = payload.session_epoch;
    } else if (state.sessionEpoch !== payload.session_epoch) {
      state.sessionEpoch = payload.session_epoch;
      state.userMovedView = false;
      state.hasRenderedScene = false;
      state.sceneRevision = null;
      state.sceneTopologySignature = null;
      state.lastRevision = null;
      state.selectedId = null;
      state.pendingSelectedId = undefined;
      state.selectedNodeIds = new Set();
      state.selectedEdgeIds = new Set();
      state.selectedProcessId = null;
      state.renderedSelectedId = null;
      state.renderedSelectedNodeIds = new Set();
      state.renderedSelectedEdgeIds = new Set();
      state.responsibleFilter = [];
      state.pendingResponsibleFilter = undefined;
      state.lastHostResponsibleFilter = [];
      state.draggingNodeId = null;
      state.draggingNodeIds = [];
      state.connectMode = null;
      state.positions = {};
      state.positionsVersion = 0;
      state.renderedPositionsVersion = -1;
      state.lastEdgeGeometrySignature = null;
      state.edgeGeometryVersion = 0;
      state.renderedEdgeGeometryVersion = -1;
    }
  }

  const graphChanged = state.lastRevision !== payload.revision;
  if (graphChanged && state.connectMode) {
    state.connectMode = null;
  }
  const nextPositions = nodePositionMap(payload.nodes);

  state.nodePayloadsById = indexPayloadsById(payload.nodes);
  state.edgePayloadsById = indexPayloadsById(payload.edges);
  state.tokenPayloadsById = indexTokenPayloads(payload.nodes);
  const nextEdgeGeometrySignature = edgeGeometrySignature(payload.edges);
  if (state.lastEdgeGeometrySignature !== nextEdgeGeometrySignature) {
    state.lastEdgeGeometrySignature = nextEdgeGeometrySignature;
    state.edgeGeometryVersion += 1;
  }
  if (state.selectedNodeIds.size) {
    const retained = new Set();
    for (const nodeId of state.selectedNodeIds) {
      if (state.nodePayloadsById.has(nodeId)) {
        retained.add(nodeId);
      }
    }
    state.selectedNodeIds = retained;
  }
  if (state.selectedEdgeIds.size) {
    const retainedEdges = new Set();
    for (const edgeId of state.selectedEdgeIds) {
      if (state.edgePayloadsById.has(edgeId)) {
        retainedEdges.add(edgeId);
      }
    }
    state.selectedEdgeIds = retainedEdges;
  }

  if ((graphChanged || state.draggingNodeId === null) && !samePositionMaps(state.positions, nextPositions)) {
    state.positions = nextPositions;
    state.positionsVersion += 1;
    // Echo host-authoritative positions after graph revision changes (undo/redo
    // of layout). Otherwise stale FE positions re-autosave and wipe the redo stack.
    if (graphChanged && state.component && typeof state.component.setStateValue === "function") {
      state.component.setStateValue("positions", copyPositionMap(state.positions));
    }
  }

  if (Object.prototype.hasOwnProperty.call(payload, "selected_id")) {
    const payloadSelectedId = payload.selected_id ?? null;
    if (state.pendingSelectedId !== undefined) {
      // Keep the local selection until Streamlit echoes it back. A stale null
      // payload during fragment remount was wiping the highlight.
      if (payloadSelectedId === state.pendingSelectedId) {
        state.pendingSelectedId = undefined;
      }
      state.selectedId = state.pendingSelectedId !== undefined
        ? state.pendingSelectedId
        : payloadSelectedId;
    } else if (state.selectedId !== payloadSelectedId) {
      state.selectedId = payloadSelectedId;
      // External selection (inspector / Streamlit) replaces multi-select.
      state.selectedNodeIds = selectedNodeIdsForPrimary(state, payloadSelectedId);
      state.selectedEdgeIds = selectedEdgeIdsForPrimary(state, payloadSelectedId);
    } else {
      state.selectedId = payloadSelectedId;
    }
  }
  if (Object.prototype.hasOwnProperty.call(payload, "responsible_filter")) {
    const payloadFilter = normalizeResponsibleFilter(payload.responsible_filter);
    if (state.pendingResponsibleFilter !== undefined) {
      if (sameResponsibleFilters(payloadFilter, state.pendingResponsibleFilter)) {
        // Host echoed the legend click.
        state.pendingResponsibleFilter = undefined;
        state.responsibleFilter = payloadFilter;
      } else if (sameResponsibleFilters(payloadFilter, state.lastHostResponsibleFilter)) {
        // Host still has the pre-click value; keep the local legend edit.
        state.responsibleFilter = state.pendingResponsibleFilter;
      } else {
        // Host sent a different filter (sidebar / external) — accept override.
        state.pendingResponsibleFilter = undefined;
        state.responsibleFilter = payloadFilter;
      }
    } else {
      state.responsibleFilter = payloadFilter;
    }
    state.lastHostResponsibleFilter = payloadFilter;
  }
  if (graphChanged) {
    state.lastRevision = payload.revision;
    // Fit only on the first paint (or after epoch wipe). Title/metadata edits
    // bump revision but must not recenter the camera.
    if (!state.hasRenderedScene && !state.userMovedView) {
      fitView(state);
    }
  }
}

function queueRender(state) {
  if (state.frameRequested) {
    return;
  }
  state.frameRequested = true;
  requestAnimationFrame(() => {
    state.frameRequested = false;
    renderState(state);
  });
}

function renderState(state) {
  const payload = state.payload;
  if (!payload || !Array.isArray(payload.nodes)) {
    return;
  }

  syncFullscreenClass(state);
  syncToolbarState(state);
  syncViewportState(state);
  syncMinimapGeometry(state);

  if (!payload.nodes.length) {
    clearScene(state);
    state.dom.emptyState.hidden = false;
    state.dom.topbar.hidden = true;
    state.dom.viewport.hidden = true;
    state.dom.minimap.hidden = true;
    state.sceneRevision = payload.revision;
    state.hasRenderedScene = false;
    state.renderedSelectedId = state.selectedId;
    state.renderedSelectedNodeIds = new Set(state.selectedNodeIds);
    state.renderedSelectedEdgeIds = new Set(state.selectedEdgeIds);
    state.renderedPositionsVersion = state.positionsVersion;
    state.renderedEdgeGeometryVersion = state.edgeGeometryVersion;
    state.renderedDraggingNodeId = state.draggingNodeId;
    state.renderedDraggingNodeIds = [...state.draggingNodeIds];
    return;
  }

  state.dom.emptyState.hidden = true;
  state.dom.topbar.hidden = false;
  state.dom.viewport.hidden = false;
  state.dom.minimap.hidden = false;
  syncResponsibleLegend(state);

  const graphChanged = state.sceneRevision !== payload.revision || !state.hasRenderedScene;
  if (graphChanged) {
    const topologyChanged = !state.hasRenderedScene
      || sceneTopologySignature(state.payload) !== state.sceneTopologySignature;
    if (topologyChanged) {
      rebuildGraphScene(state);
    } else {
      // Same node/edge ids (title/roles/note/duration): patch in place — no
      // clearScene flash and no camera jump.
      patchGraphScene(state);
    }
    state.sceneRevision = payload.revision;
    state.sceneTopologySignature = sceneTopologySignature(payload);
    state.hasRenderedScene = true;
    state.renderedSelectedId = state.selectedId;
    state.renderedSelectedNodeIds = new Set(state.selectedNodeIds);
    state.renderedSelectedEdgeIds = new Set(state.selectedEdgeIds);
    state.renderedPositionsVersion = state.positionsVersion;
    state.renderedEdgeGeometryVersion = state.edgeGeometryVersion;
    state.renderedDraggingNodeId = state.draggingNodeId;
    state.renderedDraggingNodeIds = [...state.draggingNodeIds];
    syncSelectionEditHud(state);
  } else {
    const positionsChanged = state.renderedPositionsVersion !== state.positionsVersion;
    const edgeGeometryChanged = state.renderedEdgeGeometryVersion !== state.edgeGeometryVersion;
    if (positionsChanged) {
      if (state.draggingNodeIds.length) {
        for (const nodeId of state.draggingNodeIds) {
          updateDraggedNode(state, nodeId);
        }
        // Keep wires glued to cards while dragging (before save / server rebuild).
        updateEdgeGeometry(state);
      } else if (state.draggingNodeId) {
        updateDraggedNode(state, state.draggingNodeId);
        updateEdgeGeometry(state);
      } else {
        updateNodePositions(state);
        updateMinimapNodePositions(state);
        updateEdgeGeometry(state);
      }
      state.renderedPositionsVersion = state.positionsVersion;
      state.renderedEdgeGeometryVersion = state.edgeGeometryVersion;
      layoutAllNodeNotes(state);
      syncProcessFrames(state);
    } else if (edgeGeometryChanged) {
      // Same revision + same live positions, but host re-routed edges
      // (typical after drag echo). Apply the new points without a full rebuild.
      updateEdgeGeometry(state);
      state.renderedEdgeGeometryVersion = state.edgeGeometryVersion;
    }
    if (
      state.renderedDraggingNodeId !== state.draggingNodeId
      || !sameIdLists(state.renderedDraggingNodeIds, state.draggingNodeIds)
    ) {
      syncDraggingState(state, state.renderedDraggingNodeIds, state.draggingNodeIds);
      state.renderedDraggingNodeId = state.draggingNodeId;
      state.renderedDraggingNodeIds = [...state.draggingNodeIds];
    }
    if (
      state.renderedSelectedId !== state.selectedId
      || !sameIdSets(state.renderedSelectedNodeIds, state.selectedNodeIds)
      || !sameIdSets(state.renderedSelectedEdgeIds, state.selectedEdgeIds)
    ) {
      updateSelectionState(
        state,
        state.renderedSelectedId,
        state.selectedId,
        state.renderedSelectedNodeIds,
        state.selectedNodeIds,
        state.renderedSelectedEdgeIds,
        state.selectedEdgeIds,
      );
      state.renderedSelectedId = state.selectedId;
      state.renderedSelectedNodeIds = new Set(state.selectedNodeIds);
      state.renderedSelectedEdgeIds = new Set(state.selectedEdgeIds);
    }
  }

  syncResponsibleFilterDim(state);
  updateMinimapViewport(state);
  syncConnectModeChrome(state);
  if (state.editHud) {
    positionEditHud(state);
  }
}

function syncToolbarState(state) {
  const fullscreenButton = state.dom.fullscreenButton;
  const fullscreenActive = isImmersiveMode(state);
  const canUndo = state.payload.can_undo === true;
  const canRedo = state.payload.can_redo === true;
  for (const [id, button] of Object.entries(state.dom.toolbarButtons || {})) {
    if (id === "undo") {
      button.disabled = !canUndo;
    } else if (id === "redo") {
      button.disabled = !canRedo;
    }
  }
  fullscreenButton.hidden = false;
  const title = fullscreenActive
    ? "Свернуть схему"
    : "Развернуть схему на весь экран";
  if (
    fullscreenButton.dataset.fullscreenActive !== String(fullscreenActive) ||
    !fullscreenButton.querySelector("svg")
  ) {
    fullscreenButton.dataset.fullscreenActive = String(fullscreenActive);
    fullscreenButton.replaceChildren(
      fullscreenActive ? fullscreenExitIcon() : fullscreenEnterIcon(),
    );
  }
  fullscreenButton.title = title;
  fullscreenButton.setAttribute("aria-label", title);
  fullscreenButton.classList.toggle("is-active", fullscreenActive);
  syncAddNodeButton(state);
  syncInspectorToggle(state);
}

function syncAddNodeButton(state) {
  const button = state.dom.addNodeButton;
  if (!button) {
    return;
  }
  const enabled = state.payload.node_edit_enabled === true;
  button.hidden = !enabled;
  button.disabled = !enabled;
}

function syncInspectorToggle(state) {
  const button = state.dom.inspectorToggle;
  if (!button) {
    return;
  }
  const collapsed = state.payload.inspector_collapsed === true;
  const title = collapsed ? "Показать инспектор" : "Скрыть инспектор";
  button.title = title;
  button.setAttribute("aria-label", title);
  button.setAttribute("aria-pressed", collapsed ? "true" : "false");
  button.classList.toggle("is-collapsed", collapsed);
  button.textContent = collapsed ? "‹" : "›";
}

function toggleInspectorCollapsed(state) {
  const next = state.payload.inspector_collapsed !== true;
  state.payload.inspector_collapsed = next;
  syncInspectorToggle(state);
  if (state.component && typeof state.component.setStateValue === "function") {
    state.component.setStateValue("inspector_collapsed", next);
  }
}

function requestCreateNode(state) {
  if (state.payload.node_edit_enabled !== true) {
    return;
  }
  const viewport = currentViewportWorldRect(state);
  const layoutW = 280;
  const layoutH = 72;
  const layoutX = round(viewport.x + Math.max(0, viewport.width / 2 - layoutW / 2));
  const layoutY = round(viewport.y + Math.max(0, viewport.height / 2 - layoutH / 2));
  const requestId = `nc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  state.component.setStateValue("pending_node_create", {
    request_id: requestId,
    title: "Измени меня",
    kind: "process",
    layout_x: layoutX,
    layout_y: layoutY,
    layout_w: layoutW,
    layout_h: layoutH,
  });
}

function selectedEditableNodeIds(state) {
  const ids = state.selectedNodeIds.size
    ? [...state.selectedNodeIds]
    : (state.selectedId && state.nodePayloadsById.has(state.selectedId) ? [state.selectedId] : []);
  return ids.filter((id) => {
    const node = state.nodePayloadsById.get(id);
    return node && node.editable === true;
  });
}

function copySelectedNodesToClipboard(state) {
  if (state.payload.node_edit_enabled !== true) {
    return false;
  }
  const ids = selectedEditableNodeIds(state);
  if (!ids.length) {
    return false;
  }
  const snapshots = [];
  for (const id of ids) {
    const node = state.nodePayloadsById.get(id);
    if (!node) {
      continue;
    }
    const position = state.positions[id] || node.position || { x: 0, y: 0 };
    const size = node.size || { w: 280, h: 72 };
    snapshots.push({
      title: String(node.title || node.text || "Измени меня").trim() || "Измени меня",
      kind: typeof node.kind === "string" && node.kind ? node.kind : "process",
      layout_w: Number(size.w) || 280,
      layout_h: Number(size.h) || 72,
      base_x: Number(position.x) || 0,
      base_y: Number(position.y) || 0,
      responsible: node.responsible_id ?? null,
      participants: Array.isArray(node.participants) ? [...node.participants] : [],
      approvers: Array.isArray(node.approvers) ? [...node.approvers] : [],
      duration: typeof node.duration === "string" ? node.duration : "",
      duration_context: typeof node.duration_context === "string" ? node.duration_context : "",
      note: typeof node.note === "string" ? node.note : "",
    });
  }
  if (!snapshots.length) {
    return false;
  }
  state.nodeClipboard = snapshots;
  state.clipboardPasteCount = 0;
  return true;
}

function pasteNodesFromClipboard(state) {
  if (state.payload.node_edit_enabled !== true) {
    return false;
  }
  const clipboard = Array.isArray(state.nodeClipboard) ? state.nodeClipboard : [];
  if (!clipboard.length) {
    return false;
  }
  state.clipboardPasteCount = (state.clipboardPasteCount || 0) + 1;
  const offset = 40 * state.clipboardPasteCount;
  const nodes = clipboard.map((item) => {
    const payload = {
      title: item.title,
      kind: item.kind,
      layout_x: round(item.base_x + offset),
      layout_y: round(item.base_y + offset),
      layout_w: item.layout_w,
      layout_h: item.layout_h,
    };
    if (item.responsible != null && item.responsible !== "") {
      payload.responsible = item.responsible;
    } else if (item.kind === "process" || item.kind === "decision_diamond") {
      payload.responsible = "unassigned";
    }
    if (Array.isArray(item.participants) && item.participants.length) {
      payload.participants = [...item.participants];
    }
    if (Array.isArray(item.approvers) && item.approvers.length) {
      payload.approvers = [...item.approvers];
    }
    if (item.duration) {
      payload.duration = item.duration;
    }
    if (item.duration_context) {
      payload.duration_context = item.duration_context;
    }
    if (item.note) {
      payload.note = item.note;
    }
    return payload;
  });
  const requestId = `ncs-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  state.component.setStateValue("pending_node_creates", {
    request_id: requestId,
    nodes,
  });
  return true;
}

function isEditableKeyboardTarget(target) {
  if (!target || typeof target.closest !== "function") {
    return false;
  }
  const tag = String(target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") {
    return true;
  }
  return Boolean(target.isContentEditable || target.closest("[contenteditable='true']"));
}

function requestHistoryAction(state, action) {
  if (action === "undo" && state.payload.can_undo !== true) {
    return;
  }
  if (action === "redo" && state.payload.can_redo !== true) {
    return;
  }
  const requestId = `ha-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  state.component.setStateValue("history_action", {
    action,
    request_id: requestId,
  });
}

function fullscreenEnterIcon() {
  return createToolbarIcon(
    "M4 9 V4 H9 M15 4 H20 V9 M20 15 V20 H15 M9 20 H4 V15",
  );
}

function fullscreenExitIcon() {
  return createToolbarIcon(
    "M9 4 V9 H4 M20 9 H15 V4 M15 20 V15 H20 M4 15 H9 V20",
  );
}

function createToolbarIcon(pathD) {
  const svg = createSvgElement("svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("flow-canvas-toolbar__icon");
  const path = createSvgElement("path");
  path.setAttribute("d", pathD);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "1.8");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

function syncResponsibleLegend(state) {
  const legend = state.dom.legend;
  const items = Array.isArray(state.payload.responsible_legend)
    ? state.payload.responsible_legend
    : [];
  const signature = items
    .map((item) => `${item.key}|${item.label}|${item.fill}|${item.border}`)
    .join(";");
  if (state.legendSignature !== signature) {
    state.legendSignature = signature;
    legend.replaceChildren();
    state.dom.legendClear = null;
    for (const item of items) {
      const chip = createElement("button", "flow-canvas-legend__item", legend);
      chip.type = "button";
      chip.dataset.responsibleKey = item.key;
      chip.title = `Фильтр: ${item.label}`;
      chip.setAttribute("aria-pressed", "false");
      const swatch = createElement("span", "flow-canvas-legend__swatch", chip);
      swatch.style.backgroundColor = item.fill;
      swatch.style.borderColor = item.border;
      const label = createElement("span", "flow-canvas-legend__label", chip);
      label.textContent = item.label;
      chip.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleResponsibleFilter(state, item.key);
      });
    }
    legend.hidden = items.length === 0;
  }
  ensureLegendClearButton(state);
  syncLegendHighlight(state);
}

function ensureLegendClearButton(state) {
  const legend = state.dom.legend;
  let clear = state.dom.legendClear;
  if (!clear || !legend.contains(clear)) {
    clear = createElement("button", "flow-canvas-legend__clear");
    clear.type = "button";
    clear.title = "Сбросить фильтр";
    clear.setAttribute("aria-label", "Сбросить фильтр");
    clear.innerHTML = clearFilterIcon();
    clear.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      setResponsibleFilter(state, []);
    });
    state.dom.legendClear = clear;
    legend.appendChild(clear);
  } else if (clear.nextSibling !== null) {
    legend.appendChild(clear);
  }
}

function clearFilterIcon() {
  return (
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    + '<path d="M4.2 4.2 L11.8 11.8 M11.8 4.2 L4.2 11.8" '
    + 'fill="none" stroke="currentColor" stroke-width="1.8" '
    + 'stroke-linecap="round"/>'
    + "</svg>"
  );
}

function toggleResponsibleFilter(state, responsibleKey) {
  const current = normalizeResponsibleFilter(state.responsibleFilter);
  const next = current.includes(responsibleKey)
    ? current.filter((item) => item !== responsibleKey)
    : [...current, responsibleKey];
  setResponsibleFilter(state, next);
}

function setResponsibleFilter(state, value) {
  const next = normalizeResponsibleFilter(value);
  if (
    sameResponsibleFilters(state.responsibleFilter, next)
    && state.pendingResponsibleFilter === undefined
  ) {
    return;
  }
  state.responsibleFilter = next;
  state.pendingResponsibleFilter = next;
  state.component.setStateValue("responsible_filter", next);
  syncLegendHighlight(state);
  syncResponsibleFilterDim(state);
  queueRender(state);
}

function nodeMatchesResponsibleFilter(node, filterKeys) {
  if (!filterKeys.size) {
    return true;
  }
  const keys = Array.isArray(node.responsible) ? node.responsible : [];
  return keys.some((key) => filterKeys.has(key));
}

function nodeMatchesClientFilters(node, state) {
  const kindFilter = Array.isArray(state.payload?.kind_filter)
    ? state.payload.kind_filter.filter((item) => typeof item === "string" && item)
    : [];
  if (kindFilter.length && !kindFilter.includes(node.kind)) {
    return false;
  }
  const filterKeys = new Set(normalizeResponsibleFilter(state.responsibleFilter));
  if (!nodeMatchesResponsibleFilter(node, filterKeys)) {
    return false;
  }
  const query = String(state.payload?.search || "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  const haystack = String(node.search_text || node.text || node.id || "").toLowerCase();
  return haystack.includes(query);
}

function syncResponsibleFilterDim(state) {
  if (!state.payload || !Array.isArray(state.payload.nodes)) {
    return;
  }
  const activeIds = new Set();
  for (const node of state.payload.nodes) {
    const active = node.active !== false && nodeMatchesClientFilters(node, state);
    if (active) {
      activeIds.add(node.id);
    }
    const elements = state.nodeElements.get(node.id);
    if (elements && elements.shell) {
      elements.shell.classList.toggle("is-filter-dimmed", !active);
    }
    const minimapNode = state.minimapNodeElements.get(node.id);
    if (minimapNode) {
      minimapNode.classList.toggle("is-filter-dimmed", !active);
    }
  }
  for (const edge of state.payload.edges || []) {
    const filterActive = activeIds.has(edge.source) && activeIds.has(edge.target);
    const active = edge.active !== false && filterActive;
    const elements = state.edgeElements.get(edge.id);
    if (!elements) {
      continue;
    }
    const baseOpacity = Number(edge.style?.opacity ?? 1);
    const opacity = active ? baseOpacity : Math.min(baseOpacity, 0.16);
    if (elements.visiblePath) {
      elements.visiblePath.setAttribute("opacity", String(opacity));
    }
    if (elements.label) {
      elements.label.style.opacity = active ? "1" : "0.24";
      elements.label.classList.toggle("is-filter-dimmed", !active);
    }
  }
}

function normalizeResponsibleFilter(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set();
  const result = [];
  for (const item of value) {
    if (typeof item !== "string" || !item || seen.has(item)) {
      continue;
    }
    seen.add(item);
    result.push(item);
  }
  return result;
}

function sameResponsibleFilters(left, right) {
  const a = normalizeResponsibleFilter(left);
  const b = normalizeResponsibleFilter(right);
  if (a.length !== b.length) {
    return false;
  }
  return a.every((item, index) => item === b[index]);
}

function syncLegendHighlight(state) {
  const legend = state.dom.legend;
  const filterKeys = new Set(normalizeResponsibleFilter(state.responsibleFilter));
  const filterActive = filterKeys.size > 0;
  let selectionKey = null;
  if (state.selectedId) {
    const node = state.nodePayloadsById.get(state.selectedId);
    if (node && typeof node.primary_responsible === "string" && node.primary_responsible) {
      selectionKey = node.primary_responsible;
    }
  }
  let hasSelectionHighlight = false;
  for (const chip of legend.children) {
    if (!chip.dataset.responsibleKey) {
      continue;
    }
    const key = chip.dataset.responsibleKey;
    const filtered = filterActive && filterKeys.has(key);
    const highlighted = selectionKey !== null && key === selectionKey;
    chip.classList.toggle("is-filter-active", filtered);
    chip.classList.toggle("is-highlighted", highlighted);
    chip.setAttribute("aria-pressed", filtered ? "true" : "false");
    hasSelectionHighlight = hasSelectionHighlight || highlighted;
  }
  legend.classList.toggle("has-filter", filterActive);
  legend.classList.toggle("has-highlight", hasSelectionHighlight && !filterActive);
  if (state.dom.legendClear) {
    state.dom.legendClear.hidden = !filterActive;
  }
}

function syncViewportState(state) {
  const payload = state.payload;
  state.dom.viewport.classList.toggle("is-panning", state.isPanning);
  state.dom.stage.style.width = `${payload.canvas.width}px`;
  state.dom.stage.style.height = `${payload.canvas.height}px`;
  state.dom.stage.style.transform = `translate(${state.view.x}px, ${state.view.y}px) scale(${state.view.scale})`;
  state.dom.svg.setAttribute("viewBox", `0 0 ${payload.canvas.width} ${payload.canvas.height}`);
  state.dom.svg.setAttribute("width", String(payload.canvas.width));
  state.dom.svg.setAttribute("height", String(payload.canvas.height));
}

function syncMinimapGeometry(state) {
  const bounds = minimapBounds(state.payload.bounds);
  state.minimapBounds = bounds;
  state.dom.minimapSvg.setAttribute(
    "viewBox",
    `${bounds.left} ${bounds.top} ${bounds.width} ${bounds.height}`,
  );
  state.dom.minimapSvg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  state.dom.minimapBackdrop.setAttribute("x", String(bounds.left));
  state.dom.minimapBackdrop.setAttribute("y", String(bounds.top));
  state.dom.minimapBackdrop.setAttribute("width", String(bounds.width));
  state.dom.minimapBackdrop.setAttribute("height", String(bounds.height));
  state.dom.minimapBackdrop.setAttribute("rx", "20");
}

function clearScene(state) {
  closeActiveEditPopover(state);
  destroyEditHud(state);
  state.dom.defs.replaceChildren();
  state.dom.edgeLayer.replaceChildren();
  state.dom.labelsLayer.replaceChildren();
  state.dom.processesLayer.replaceChildren();
  state.dom.nodesLayer.replaceChildren();
  state.dom.minimapEdgeLayer.replaceChildren();
  state.dom.minimapNodeLayer.replaceChildren();
  state.edgeElements = new Map();
  state.nodeElements = new Map();
  state.processElements = new Map();
  state.tokenElements = new Map();
  state.minimapNodeElements = new Map();
}

function rebuildGraphScene(state) {
  clearScene(state);

  for (const edge of state.payload.edges) {
    state.dom.defs.appendChild(buildMarker(edge.color, edge.id));
    buildEdgeElement(state, edge);
    buildMinimapEdgeElement(state, edge);
  }

  for (const node of state.payload.nodes) {
    buildNodeElement(state, node);
    buildMinimapNodeElement(state, node);
  }
  layoutAllNodeNotes(state);
  syncProcessFrames(state);
}

function sceneTopologySignature(payload) {
  const nodes = Array.isArray(payload?.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload?.edges) ? payload.edges : [];
  const processes = Array.isArray(payload?.processes) ? payload.processes : [];
  const nodeIds = nodes.map((node) => String(node.id || "")).sort().join("\0");
  const edgeIds = edges.map((edge) => String(edge.id || "")).sort().join("\0");
  const processSig = processes
    .map((item) => `${item.id}:${(item.member_ids || []).join(",")}`)
    .sort()
    .join("\0");
  return `${nodeIds}|${edgeIds}|${processSig}`;
}

function patchGraphScene(state) {
  for (const node of state.payload.nodes || []) {
    patchNodeElement(state, node);
  }
  updateNodePositions(state);
  updateEdgeGeometry(state);
  for (const edge of state.payload.edges || []) {
    patchEdgeElement(state, edge);
  }
  layoutAllNodeNotes(state);
  syncProcessFrames(state);
}

function patchNodeElement(state, node) {
  const elements = state.nodeElements.get(node.id);
  if (!elements?.shell || !elements?.card || !elements?.textEl) {
    return;
  }
  const nextText = String(node.text || node.title || "");
  if (elements.textEl.textContent !== nextText && state.editingTitleNodeId !== node.id) {
    elements.textEl.textContent = nextText;
  }
  if (node.size) {
    elements.shell.style.width = `${node.size.w}px`;
    elements.shell.style.height = `${node.size.h}px`;
  }
  if (typeof node.kind === "string" && node.kind && elements.card) {
    for (const className of [...elements.card.classList]) {
      if (className.startsWith("is-") && className !== "is-draggable" && className !== "is-dragging" && className !== "is-selected") {
        elements.card.classList.remove(className);
      }
    }
    elements.card.classList.add(`is-${node.kind.replaceAll("_", "-")}`);
  }
  if (node.style) {
    applyStyles(elements.card, node.style);
  }
  let rail = elements.shell.querySelector(".flow-node-top-rail");
  const hasBadges = Boolean(node.time_badge)
    || (Array.isArray(node.responsible_badges) && node.responsible_badges.length > 0);
  if (hasBadges && !rail) {
    rail = createElement("div", "flow-node-top-rail");
    elements.shell.insertBefore(rail, elements.shell.firstChild);
  }
  if (rail) {
    rail.replaceChildren();
    if (node.time_badge) {
      const badge = createElement("div", "flow-node-badge", rail);
      applyStyles(badge, node.time_badge.style);
      badge.textContent = node.time_badge.text;
      badge.title = node.time_badge.title;
    }
    for (const badgePayload of node.responsible_badges || []) {
      const badge = createElement("div", "flow-node-badge", rail);
      applyStyles(badge, badgePayload.style);
      badge.textContent = badgePayload.abbr;
      badge.title = badgePayload.title;
    }
    if (!hasBadges) {
      rail.remove();
    }
  }
  syncNodeShellPosition(elements.shell, state.positions[node.id] || node.position);
  setNodeSelectedState(elements, node, isNodeSelected(state, node.id));
  const minimap = state.minimapNodeElements.get(node.id);
  if (minimap) {
    syncMinimapNodeShape(minimap, node, state.positions[node.id] || node.position);
  }
  syncNodeNoteElement(state, node.id);
}

function patchEdgeElement(state, edge) {
  const elements = state.edgeElements.get(edge.id);
  if (!elements?.visiblePath) {
    return;
  }
  const stroke = edge.style?.stroke || edge.color;
  elements.visiblePath.setAttribute("stroke", stroke);
  elements.visiblePath.setAttribute("opacity", String(edge.style?.opacity ?? 1));
  if (edge.style?.strokeDasharray && edge.style.strokeDasharray !== "0") {
    elements.visiblePath.setAttribute("stroke-dasharray", edge.style.strokeDasharray);
  } else {
    elements.visiblePath.removeAttribute("stroke-dasharray");
  }
  syncEdgeMarker(state, edge, stroke);
  syncEdgeLabelElement(state, elements, edge);
  setEdgeSelectedState(elements, edge, isEdgeSelected(state, edge.id));
}

function syncEdgeMarker(state, edge, color) {
  const markerId = `marker-${edge.id}`;
  let marker = null;
  for (const child of state.dom.defs.children) {
    if (child.getAttribute("id") === markerId) {
      marker = child;
      break;
    }
  }
  if (!marker) {
    state.dom.defs.appendChild(buildMarker(color, edge.id));
    return;
  }
  const path = marker.querySelector("path");
  if (path) {
    path.setAttribute("fill", color);
  }
}

function syncEdgeLabelElement(state, elements, edge) {
  if (!edge.label) {
    if (elements.label) {
      elements.label.remove();
      elements.label = null;
    }
    return;
  }
  if (!elements.label) {
    elements.label = createEdgeLabelElement(state, edge);
  } else {
    applyEdgeLabelContent(elements.label, edge);
  }
}

function createEdgeLabelElement(state, edge) {
  const label = createElement("button", "flow-edge-label", state.dom.labelsLayer);
  label.type = "button";
  applyEdgeLabelContent(label, edge);
  label.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    event.stopPropagation();
    if (state.connectMode) {
      cancelConnectMode(state);
    }
    selectId(state, edge.id, { additive: isMultiSelectModifier(event) });
  });
  label.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  return label;
}

function applyEdgeLabelContent(label, edge) {
  label.textContent = edge.label.text;
  label.style.left = `${edge.label.position.x}px`;
  label.style.top = `${edge.label.position.y}px`;
  label.style.width = `${edge.label.width}px`;
  label.style.height = `${edge.label.height}px`;
  label.style.border = `1px solid ${edge.label.color}`;
  label.style.color = edge.label.color;
  label.style.opacity = String(edge.label.active ? 1 : 0.24);
}

function buildEdgeElement(state, edge) {
  const group = createSvgElement("g");
  state.dom.edgeLayer.appendChild(group);

  const pathData = roundedPath(edge.points);
  const visiblePath = createSvgElement("path");
  visiblePath.classList.add("flow-edge-path");
  visiblePath.setAttribute("d", pathData);
  visiblePath.setAttribute("stroke", edge.style.stroke || edge.color);
  visiblePath.setAttribute("stroke-linecap", edge.style.strokeLinecap || "round");
  visiblePath.setAttribute("stroke-linejoin", edge.style.strokeLinejoin || "round");
  visiblePath.setAttribute("opacity", String(edge.style.opacity ?? 1));
  visiblePath.setAttribute("marker-end", `url(#marker-${edge.id})`);
  if (edge.style.strokeDasharray && edge.style.strokeDasharray !== "0") {
    visiblePath.setAttribute("stroke-dasharray", edge.style.strokeDasharray);
  }
  group.appendChild(visiblePath);

  const hitPath = createSvgElement("path");
  hitPath.classList.add("flow-edge-hit");
  hitPath.setAttribute("d", pathData);
  hitPath.setAttribute("stroke-width", "18");
  hitPath.addEventListener("pointerdown", (event) => {
    // Prefer pointerdown so selection wins over viewport pan start.
    if (event.button !== 0) {
      return;
    }
    event.stopPropagation();
    event.preventDefault();
    if (state.connectMode) {
      cancelConnectMode(state);
    }
    selectId(state, edge.id, { additive: isMultiSelectModifier(event) });
  });
  hitPath.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  group.appendChild(hitPath);

  const label = edge.label ? createEdgeLabelElement(state, edge) : null;

  const elements = { visiblePath, hitPath, label };
  setEdgeSelectedState(elements, edge, isEdgeSelected(state, edge.id));
  state.edgeElements.set(edge.id, elements);
}

function buildNodeElement(state, node) {
  const shell = createElement("div", "flow-node-shell", state.dom.nodesLayer);
  shell.style.width = `${node.size.w}px`;
  shell.style.height = `${node.size.h}px`;

  if (node.time_badge || (node.responsible_badges && node.responsible_badges.length)) {
    const rail = createElement("div", "flow-node-top-rail", shell);
    if (node.time_badge) {
      const badge = createElement("div", "flow-node-badge", rail);
      applyStyles(badge, node.time_badge.style);
      badge.textContent = node.time_badge.text;
      badge.title = node.time_badge.title;
    }
    for (const badgePayload of node.responsible_badges || []) {
      const badge = createElement("div", "flow-node-badge", rail);
      applyStyles(badge, badgePayload.style);
      badge.textContent = badgePayload.abbr;
      badge.title = badgePayload.title;
    }
  }

  const card = createElement("button", "flow-node-card", shell);
  card.type = "button";
  if (typeof node.kind === "string" && node.kind) {
    card.classList.add(`is-${node.kind.replaceAll("_", "-")}`);
  }
  if (node.draggable && state.payload.position_edit_enabled) {
    card.classList.add("is-draggable");
  }
  if (state.draggingNodeIds.includes(node.id) || state.draggingNodeId === node.id) {
    card.classList.add("is-dragging");
  }
  applyStyles(card, node.style);
  card.dataset.nodeId = node.id;
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    if (state.suppressNextNodeClick) {
      state.suppressNextNodeClick = false;
      return;
    }
    if (state.editingTitleNodeId === node.id) {
      return;
    }
    if (state.connectMode) {
      // Drag-to-connect is finalized only by pointerup. Ignoring click here
      // prevents a second pending_edge from the same gesture.
      if (state.connectMode.pointerId != null) {
        return;
      }
      completeConnectMode(state, node.id);
      return;
    }
    selectId(state, node.id, { additive: isMultiSelectModifier(event) });
  });
  if (node.draggable && state.payload.position_edit_enabled) {
    card.addEventListener("pointerdown", (event) => {
      if (state.editingTitleNodeId === node.id) {
        return;
      }
      if (event.target?.closest?.(".flow-node-text.is-editing")) {
        return;
      }
      startNodeDrag(event, state, node.id);
    });
    card.addEventListener("contextmenu", (event) => {
      event.preventDefault();
    });
  }

  const content = createElement("span", "flow-node-content", card);
  const text = createElement("span", "flow-node-text", content);
  text.textContent = node.text;
  if (node.editable) {
    text.title = "Двойной клик — изменить заголовок";
    text.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      event.preventDefault();
      beginTitleEdit(state, node.id);
    });
  }

  if (node.well_tokens.length) {
    const wells = createElement("div", "flow-node-wells", shell);
    for (const tokenPayload of node.well_tokens) {
      const token = createElement("button", "flow-token", wells);
      token.type = "button";
      token.textContent = tokenPayload.text;
      token.title = tokenPayload.title;
      setTokenSelectedState(token, tokenPayload, state.selectedId === tokenPayload.id);
      token.addEventListener("click", (event) => {
        event.stopPropagation();
        selectId(state, tokenPayload.id);
      });
      state.tokenElements.set(tokenPayload.id, token);
    }
  }

  const elements = {
    shell,
    card,
    overlay: null,
    handles: [],
    textEl: text,
    noteEl: null,
  };
  syncNodeShellPosition(shell, state.positions[node.id] || node.position);
  setNodeSelectedState(elements, node, isNodeSelected(state, node.id));
  state.nodeElements.set(node.id, elements);
  syncConnectionHandlesForNode(state, node.id);
  syncNodeNoteElement(state, node.id);
}

function requestNodeEditId() {
  return `ne-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function requestEdgeEditId() {
  return `ee-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function commitNodeEdit(state, nodeId, patch) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node || node.editable !== true) {
    return;
  }
  const payload = { node_id: nodeId, request_id: requestNodeEditId(), ...patch };
  if ("title" in patch) {
    const next = String(patch.title || "").trim();
    if (!next || next === String(node.title || node.text || "").trim()) {
      return;
    }
    payload.title = next;
  }
  if ("duration" in patch || "duration_context" in patch) {
    let durationChanged = false;
    if ("duration" in patch) {
      const next = String(patch.duration || "").trim();
      const prev = String(node.duration || "").trim();
      if (next !== prev) {
        durationChanged = true;
      }
      payload.duration = next;
    }
    if ("duration_context" in patch) {
      const next = String(patch.duration_context || "").trim();
      const prev = String(node.duration_context || "").trim();
      if (next !== prev) {
        durationChanged = true;
      }
      payload.duration_context = next;
    }
    const onlyDurationFields = Object.keys(patch).every(
      (key) => key === "duration" || key === "duration_context",
    );
    if (!durationChanged && onlyDurationFields) {
      return;
    }
  }
  if ("note" in patch) {
    const next = String(patch.note || "").trim();
    const prev = String(node.note || "").trim();
    if (next === prev) {
      return;
    }
    payload.note = next;
  }
  if ("kind" in patch && patch.kind === node.kind) {
    return;
  }
  if ("responsible" in patch || "participants" in patch || "approvers" in patch) {
    const sameResponsible = !("responsible" in patch)
      || patch.responsible === (node.responsible_id ?? null);
    const sameParticipants = !("participants" in patch)
      || sameStringLists(patch.participants, node.participants || []);
    const sameApprovers = !("approvers" in patch)
      || sameStringLists(patch.approvers, node.approvers || []);
    if (sameResponsible && sameParticipants && sameApprovers && !("deleted" in patch)) {
      return;
    }
  }
  closeActiveEditPopover(state);
  state.suppressNextNodeClick = true;
  applyOptimisticNodeEdit(state, nodeId, payload);
  state.component.setStateValue("pending_node_edit", payload);
}

function applyOptimisticNodeEdit(state, nodeId, payload) {
  const node = state.nodePayloadsById.get(nodeId);
  const elements = state.nodeElements.get(nodeId);
  if (!node) {
    return;
  }
  if (typeof payload.title === "string") {
    node.title = payload.title;
    node.text = payload.title;
    if (elements?.textEl) {
      elements.textEl.textContent = payload.title;
    }
  }
  if ("duration" in payload) {
    node.duration = payload.duration || "";
  }
  if ("duration_context" in payload) {
    node.duration_context = payload.duration_context || "";
  }
  if ("note" in payload) {
    node.note = payload.note || "";
    syncNodeNoteElement(state, nodeId);
    layoutAllNodeNotes(state);
  }
  if ("approvers" in payload) {
    node.approvers = Array.isArray(payload.approvers) ? [...payload.approvers] : [];
  }
  if ("responsible" in payload) {
    node.responsible_id = payload.responsible ?? null;
  }
  if ("participants" in payload) {
    node.participants = Array.isArray(payload.participants) ? [...payload.participants] : [];
  }
  if (typeof payload.kind === "string" && payload.kind && elements?.card) {
    const previous = node.kind;
    if (typeof previous === "string" && previous) {
      elements.card.classList.remove(`is-${previous.replaceAll("_", "-")}`);
    }
    node.kind = payload.kind;
    elements.card.classList.add(`is-${payload.kind.replaceAll("_", "-")}`);
  }
}

function commitEdgeEdit(state, edgeId, patch) {
  const edge = state.edgePayloadsById.get(edgeId);
  if (!edge || state.payload.edge_edit_enabled !== true) {
    return;
  }
  const nextPatch = { ...patch };
  if ("kind" in nextPatch) {
    const next = sourceEdgeKind(nextPatch.kind);
    const prev = sourceEdgeKind(edge.kind);
    if (next === prev && !("deleted" in nextPatch)) {
      return;
    }
    nextPatch.kind = next;
  }
  closeActiveEditPopover(state);
  state.component.setStateValue("pending_edge_edit", {
    edge_id: edgeId,
    request_id: requestEdgeEditId(),
    ...nextPatch,
  });
}

function commitNodeEdits(state, nodeIds, patch) {
  const ids = [...new Set(nodeIds)].filter((id) => {
    const node = state.nodePayloadsById.get(id);
    return node && node.editable === true;
  });
  if (!ids.length) {
    return;
  }
  if (ids.length === 1) {
    commitNodeEdit(state, ids[0], patch);
    return;
  }
  closeActiveEditPopover(state);
  state.suppressNextNodeClick = true;
  for (const nodeId of ids) {
    applyOptimisticNodeEdit(state, nodeId, patch);
  }
  state.component.setStateValue("pending_node_edits", {
    request_id: requestNodeEditId(),
    node_ids: ids,
    patch,
  });
}

function commitEdgeEdits(state, edgeIds, patch) {
  const ids = [...new Set(edgeIds)].filter((id) => state.edgePayloadsById.has(id));
  if (!ids.length || state.payload.edge_edit_enabled !== true) {
    return;
  }
  if (ids.length === 1) {
    commitEdgeEdit(state, ids[0], patch);
    return;
  }
  const nextPatch = { ...patch };
  if ("kind" in nextPatch) {
    nextPatch.kind = sourceEdgeKind(nextPatch.kind);
  }
  closeActiveEditPopover(state);
  state.component.setStateValue("pending_edge_edits", {
    request_id: requestEdgeEditId(),
    edge_ids: ids,
    patch: nextPatch,
  });
}

function sourceEdgeKind(kind) {
  if (kind === "usual") {
    return "default";
  }
  if (kind === "default" || kind === "yes" || kind === "no" || kind === "dashed") {
    return kind;
  }
  return "default";
}

const EDGE_KIND_MENU_OPTIONS = [
  { id: "default", label: "Обычная" },
  { id: "yes", label: "Да" },
  { id: "no", label: "Нет" },
  { id: "dashed", label: "Пунктир" },
];

function sameStringLists(a, b) {
  const left = Array.isArray(a) ? a : [];
  const right = Array.isArray(b) ? b : [];
  if (left.length !== right.length) {
    return false;
  }
  return left.every((value, index) => value === right[index]);
}

function beginTitleEdit(state, nodeId) {
  const node = state.nodePayloadsById.get(nodeId);
  const elements = state.nodeElements.get(nodeId);
  if (!node || !elements?.textEl || node.editable !== true) {
    return;
  }
  if (state.editingTitleNodeId && state.editingTitleNodeId !== nodeId) {
    cancelTitleEdit(state);
  }
  closeActiveEditPopover(state);
  selectId(state, nodeId);
  const textEl = elements.textEl;
  state.editingTitleNodeId = nodeId;
  textEl.classList.add("is-editing");
  textEl.contentEditable = "true";
  textEl.spellcheck = false;
  textEl.focus();
  const selection = state.ownerDocument.getSelection?.();
  if (selection) {
    const range = state.ownerDocument.createRange();
    range.selectNodeContents(textEl);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  const onKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      finishTitleEdit(state, nodeId, true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      finishTitleEdit(state, nodeId, false);
    }
  };
  const onBlur = () => {
    finishTitleEdit(state, nodeId, true);
  };
  textEl._titleEditCleanup = () => {
    textEl.removeEventListener("keydown", onKeyDown);
    textEl.removeEventListener("blur", onBlur);
    delete textEl._titleEditCleanup;
  };
  textEl.addEventListener("keydown", onKeyDown);
  textEl.addEventListener("blur", onBlur);
}

function cancelTitleEdit(state) {
  if (!state.editingTitleNodeId) {
    return;
  }
  finishTitleEdit(state, state.editingTitleNodeId, false);
}

function finishTitleEdit(state, nodeId, commit) {
  if (state.editingTitleNodeId !== nodeId) {
    return;
  }
  const node = state.nodePayloadsById.get(nodeId);
  const elements = state.nodeElements.get(nodeId);
  const textEl = elements?.textEl;
  state.editingTitleNodeId = null;
  if (!textEl) {
    return;
  }
  if (typeof textEl._titleEditCleanup === "function") {
    textEl._titleEditCleanup();
  }
  textEl.contentEditable = "false";
  textEl.classList.remove("is-editing");
  const nextTitle = String(textEl.textContent || "").replace(/\s+/g, " ").trim();
  const previous = String(node?.title || node?.text || "").trim();
  if (!commit || !nextTitle) {
    textEl.textContent = previous;
    return;
  }
  textEl.textContent = nextTitle;
  if (nextTitle !== previous) {
    commitNodeEdit(state, nodeId, { title: nextTitle });
  }
}

function closeActiveEditPopover(state) {
  if (state.activeEditPopover) {
    if (typeof state.activeEditPopover._cleanup === "function") {
      state.activeEditPopover._cleanup();
    }
    state.activeEditPopover.remove();
    state.activeEditPopover = null;
  }
}

function destroyEditHud(state) {
  closeActiveEditPopover(state);
  if (state.editHud) {
    state.editHud.remove();
    state.editHud = null;
  }
}

function syncSelectionEditHud(state) {
  if (state.draggingNodeId || state.connectMode || state.isMarqueeSelecting) {
    destroyEditHud(state);
    return;
  }
  if (state.selectedProcessId && state.payload.node_edit_enabled !== false) {
    const process = (state.payload.processes || []).find(
      (item) => item.id === state.selectedProcessId,
    );
    if (process) {
      const targetKey = `process:${process.id}`;
      if (state.editHud && state.editHud.dataset.targetKey === targetKey) {
        positionEditHud(state);
        return;
      }
      destroyEditHud(state);
      const hud = createElement("div", "flow-edit-hud", state.root);
      hud.dataset.targetKey = targetKey;
      hud.dataset.processId = process.id;
      const trigger = createElement("button", "flow-edit-hud__trigger", hud);
      trigger.type = "button";
      trigger.textContent = "⋯";
      trigger.title = "Редактировать процесс";
      trigger.setAttribute("aria-label", "Редактировать процесс");
      trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        event.preventDefault();
        openProcessEditActionMenu(state, process.id, trigger);
      });
      hud.addEventListener("pointerdown", (event) => event.stopPropagation());
      state.editHud = hud;
      positionEditHud(state);
      return;
    }
  }
  const multiNodes = [...state.selectedNodeIds].filter((id) => {
    const node = state.nodePayloadsById.get(id);
    return node && node.editable === true;
  });
  const multiEdges = [...state.selectedEdgeIds].filter((id) => state.edgePayloadsById.has(id));
  if (multiNodes.length > 1 && state.payload.node_edit_enabled !== false) {
    const targetKey = `nodes:${multiNodes.slice().sort().join(",")}`;
    if (state.editHud && state.editHud.dataset.targetKey === targetKey) {
      positionEditHud(state);
      return;
    }
    destroyEditHud(state);
    const hud = createElement("div", "flow-edit-hud", state.root);
    hud.dataset.targetKey = targetKey;
    hud.dataset.multiNodeIds = multiNodes.join(",");
    const trigger = createElement("button", "flow-edit-hud__trigger", hud);
    trigger.type = "button";
    trigger.textContent = "⋯";
    trigger.title = `Редактировать ${multiNodes.length}`;
    trigger.setAttribute("aria-label", `Редактировать ${multiNodes.length}`);
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      openMultiNodeEditActionMenu(state, multiNodes, trigger);
    });
    hud.addEventListener("pointerdown", (event) => event.stopPropagation());
    state.editHud = hud;
    positionEditHud(state);
    return;
  }
  if (multiEdges.length > 1 && state.payload.edge_edit_enabled === true) {
    const targetKey = `edges:${multiEdges.slice().sort().join(",")}`;
    if (state.editHud && state.editHud.dataset.targetKey === targetKey) {
      positionEditHud(state);
      return;
    }
    destroyEditHud(state);
    const hud = createElement("div", "flow-edit-hud", state.root);
    hud.dataset.targetKey = targetKey;
    hud.dataset.multiEdgeIds = multiEdges.join(",");
    const trigger = createElement("button", "flow-edit-hud__trigger", hud);
    trigger.type = "button";
    trigger.textContent = "⋯";
    trigger.title = `Редактировать ${multiEdges.length}`;
    trigger.setAttribute("aria-label", `Редактировать ${multiEdges.length}`);
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      openMultiEdgeEditActionMenu(state, multiEdges, trigger);
    });
    hud.addEventListener("pointerdown", (event) => event.stopPropagation());
    state.editHud = hud;
    positionEditHud(state);
    return;
  }

  const selectedId = state.selectedId;
  const node = selectedId ? state.nodePayloadsById.get(selectedId) : null;
  const edge = selectedId ? state.edgePayloadsById.get(selectedId) : null;
  const singleNode = Boolean(
    node
    && node.editable === true
    && state.selectedNodeIds.size <= 1
    && state.selectedEdgeIds.size === 0
    && isNodeSelected(state, selectedId),
  );
  const singleEdge = Boolean(
    edge
    && state.payload.edge_edit_enabled === true
    && state.selectedNodeIds.size === 0
    && state.selectedEdgeIds.size <= 1
    && isEdgeSelected(state, edge.id),
  );
  if (!singleNode && !singleEdge) {
    destroyEditHud(state);
    return;
  }
  const targetKey = singleNode ? `node:${selectedId}` : `edge:${selectedId}`;
  if (state.editHud && state.editHud.dataset.targetKey === targetKey) {
    positionEditHud(state);
    return;
  }
  destroyEditHud(state);
  const hud = createElement("div", "flow-edit-hud", state.root);
  hud.dataset.targetKey = targetKey;
  const trigger = createElement("button", "flow-edit-hud__trigger", hud);
  trigger.type = "button";
  trigger.textContent = "⋯";
  trigger.title = "Редактировать";
  trigger.setAttribute("aria-label", "Редактировать");
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    event.preventDefault();
    if (singleNode) {
      openNodeEditActionMenu(state, selectedId, trigger);
    } else {
      openEdgeEditActionMenu(state, selectedId, trigger);
    }
  });
  hud.addEventListener("pointerdown", (event) => event.stopPropagation());
  state.editHud = hud;
  positionEditHud(state);
}

function positionEditHud(state) {
  const hud = state.editHud;
  if (!hud) {
    return;
  }
  const targetKey = hud.dataset.targetKey || "";
  const rootRect = state.root.getBoundingClientRect();
  let anchorRect = null;
  if (targetKey.startsWith("node:")) {
    const nodeId = targetKey.slice(5);
    const elements = state.nodeElements.get(nodeId);
    if (elements?.shell) {
      anchorRect = elements.shell.getBoundingClientRect();
    }
  } else if (targetKey.startsWith("nodes:")) {
    const nodeIds = (hud.dataset.multiNodeIds || "").split(",").filter(Boolean);
    for (const nodeId of nodeIds) {
      const elements = state.nodeElements.get(nodeId);
      if (!elements?.shell) {
        continue;
      }
      const rect = elements.shell.getBoundingClientRect();
      if (!anchorRect) {
        anchorRect = {
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
        };
      } else {
        anchorRect.left = Math.min(anchorRect.left, rect.left);
        anchorRect.right = Math.max(anchorRect.right, rect.right);
        anchorRect.top = Math.min(anchorRect.top, rect.top);
        anchorRect.bottom = Math.max(anchorRect.bottom, rect.bottom);
      }
    }
  } else if (targetKey.startsWith("edges:")) {
    const edgeIds = (hud.dataset.multiEdgeIds || "").split(",").filter(Boolean);
    const first = edgeIds[0];
    const elements = first ? state.edgeElements.get(first) : null;
    const edge = first ? state.edgePayloadsById.get(first) : null;
    if (elements?.label) {
      anchorRect = elements.label.getBoundingClientRect();
    } else if (edge?.points?.length) {
      const mid = edge.points[Math.floor(edge.points.length / 2)];
      const sx = state.view.x + mid.x * state.view.scale;
      const sy = state.view.y + mid.y * state.view.scale;
      anchorRect = {
        left: rootRect.left + sx,
        right: rootRect.left + sx,
        top: rootRect.top + sy,
        bottom: rootRect.top + sy,
        width: 0,
        height: 0,
      };
    }
  } else if (targetKey.startsWith("edge:")) {
    const edgeId = targetKey.slice(5);
    const elements = state.edgeElements.get(edgeId);
    const edge = state.edgePayloadsById.get(edgeId);
    if (elements?.label) {
      anchorRect = elements.label.getBoundingClientRect();
    } else if (edge?.points?.length) {
      const mid = edge.points[Math.floor(edge.points.length / 2)];
      const sx = state.view.x + mid.x * state.view.scale;
      const sy = state.view.y + mid.y * state.view.scale;
      anchorRect = {
        left: rootRect.left + sx,
        right: rootRect.left + sx,
        top: rootRect.top + sy,
        bottom: rootRect.top + sy,
        width: 0,
        height: 0,
      };
    }
  } else if (targetKey.startsWith("process:")) {
    const processId = targetKey.slice(8);
    const frame = state.processElements?.get(processId);
    if (frame?.titleEl) {
      anchorRect = frame.titleEl.getBoundingClientRect();
    } else if (frame) {
      anchorRect = frame.getBoundingClientRect();
    }
  }
  if (!anchorRect) {
    destroyEditHud(state);
    return;
  }
  const left = Math.max(8, Math.min(
    rootRect.width - 44,
    anchorRect.right - rootRect.left + 6,
  ));
  const top = Math.max(8, Math.min(
    rootRect.height - 44,
    anchorRect.top - rootRect.top - 4,
  ));
  hud.style.left = `${left}px`;
  hud.style.top = `${top}px`;
}

function openNodeEditActionMenu(state, nodeId, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const actions = [
    { id: "title", label: "Заголовок" },
    { id: "kind", label: "Тип" },
    { id: "roles", label: "Роли" },
    { id: "approvers", label: "Согласующие" },
    { id: "process", label: "В процесс…" },
    { id: "duration", label: "Длительность" },
    { id: "note", label: "Заметка" },
    { id: "delete", label: "Удалить", danger: true },
  ];
  for (const action of actions) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = action.label;
    if (action.danger) {
      item.classList.add("is-danger");
    }
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      openNodeFieldEditor(state, nodeId, action.id, anchor);
    });
  }
  positionEditPopover(state, menu, anchor);
}

function openEdgeEditActionMenu(state, edgeId, anchor) {
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const kindItem = createElement("button", "flow-edit-menu__item", menu);
  kindItem.type = "button";
  kindItem.textContent = "Тип связи";
  kindItem.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openEdgeKindEditor(state, edgeId, anchor);
  });
  const deleteItem = createElement("button", "flow-edit-menu__item is-danger", menu);
  deleteItem.type = "button";
  deleteItem.textContent = "Удалить";
  deleteItem.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openDeleteConfirmPopover(state, {
      message: "Удалить связь?",
      anchor,
      onConfirm: () => commitEdgeEdit(state, edgeId, { deleted: true }),
    });
  });
  positionEditPopover(state, menu, anchor);
}

function openMultiNodeEditActionMenu(state, nodeIds, anchor) {
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const actions = [
    { id: "kind", label: "Тип" },
    { id: "roles", label: "Роли" },
    { id: "approvers", label: "Согласующие" },
    { id: "process", label: "В процесс…" },
    { id: "duration", label: "Длительность" },
    { id: "delete", label: `Удалить ${nodeIds.length}`, danger: true },
  ];
  for (const action of actions) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = action.label;
    if (action.danger) {
      item.classList.add("is-danger");
    }
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      if (action.id === "delete") {
        openDeleteConfirmPopover(state, {
          message: `Удалить ${nodeIds.length} карточек?`,
          anchor,
          onConfirm: () => commitNodeEdits(state, nodeIds, { deleted: true }),
        });
        return;
      }
      if (action.id === "kind") {
        openMultiKindMenu(state, nodeIds, anchor);
        return;
      }
      if (action.id === "roles") {
        openMultiRolesPopover(state, nodeIds, anchor);
        return;
      }
      if (action.id === "approvers") {
        openMultiApproversPopover(state, nodeIds, anchor);
        return;
      }
      if (action.id === "process") {
        openAssignToProcessPopover(state, nodeIds, anchor);
        return;
      }
      if (action.id === "duration") {
        openDurationPopover(state, nodeIds[0], anchor, nodeIds);
      }
    });
  }
  positionEditPopover(state, menu, anchor);
}

function openMultiEdgeEditActionMenu(state, edgeIds, anchor) {
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const kindItem = createElement("button", "flow-edit-menu__item", menu);
  kindItem.type = "button";
  kindItem.textContent = "Тип связи";
  kindItem.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openMultiEdgeKindEditor(state, edgeIds, anchor);
  });
  const deleteItem = createElement("button", "flow-edit-menu__item is-danger", menu);
  deleteItem.type = "button";
  deleteItem.textContent = `Удалить ${edgeIds.length}`;
  deleteItem.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openDeleteConfirmPopover(state, {
      message: `Удалить ${edgeIds.length} связей?`,
      anchor,
      onConfirm: () => commitEdgeEdits(state, edgeIds, { deleted: true }),
    });
  });
  positionEditPopover(state, menu, anchor);
}

function openMultiKindMenu(state, nodeIds, anchor) {
  const sample = state.nodePayloadsById.get(nodeIds[0]);
  if (!sample?.editable || !Array.isArray(sample.kind_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  for (const option of sample.kind_options) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = option.label || option.id;
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      commitNodeEdits(state, nodeIds, { kind: option.id });
    });
  }
  positionEditPopover(state, menu, anchor);
}

function openMultiRolesPopover(state, nodeIds, anchor) {
  const sample = state.nodePayloadsById.get(nodeIds[0]);
  if (!sample?.editable || !Array.isArray(sample.responsible_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-node-roles-menu", state.root);
  state.activeEditPopover = menu;
  let responsible = sample.responsible_id ?? null;
  let participants = [...(sample.participants || [])];
  const responsibleRow = createElement("div", "flow-node-roles-menu__section", menu);
  createElement("div", "flow-node-roles-menu__label", responsibleRow).textContent = "Ответственный";
  const responsibleSelect = createElement("select", "flow-node-roles-menu__select", responsibleRow);
  const noneOption = createElement("option", "", responsibleSelect);
  noneOption.value = "";
  noneOption.textContent = "—";
  for (const option of sample.responsible_options) {
    const opt = createElement("option", "", responsibleSelect);
    opt.value = option.id;
    opt.textContent = option.label || option.id;
  }
  responsibleSelect.value = responsible || "";
  const participantsBox = createRoleChecklist(
    menu,
    "Участники",
    sample.responsible_options,
    participants,
  );
  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Применить";
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    responsible = responsibleSelect.value || null;
    participants = participantsBox.getSelected().filter((id) => id !== responsible);
    closeActiveEditPopover(state);
    commitNodeEdits(state, nodeIds, { responsible, participants });
  });
  positionEditPopover(state, menu, anchor);
}

function openMultiApproversPopover(state, nodeIds, anchor) {
  const sample = state.nodePayloadsById.get(nodeIds[0]);
  if (!sample?.editable || !Array.isArray(sample.responsible_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-node-roles-menu", state.root);
  state.activeEditPopover = menu;
  const responsible = sample.responsible_id ?? null;
  const participants = new Set(sample.participants || []);
  const approversBox = createRoleChecklist(
    menu,
    "Согласующие",
    sample.responsible_options,
    [...(sample.approvers || [])],
  );
  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Применить";
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    const approvers = approversBox.getSelected().filter(
      (id) => id !== responsible && !participants.has(id),
    );
    closeActiveEditPopover(state);
    commitNodeEdits(state, nodeIds, { approvers });
  });
  positionEditPopover(state, menu, anchor);
}

function openMultiEdgeKindEditor(state, edgeIds, anchor) {
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  for (const option of EDGE_KIND_MENU_OPTIONS) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = option.label;
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      commitEdgeEdits(state, edgeIds, { kind: option.id });
    });
  }
  positionEditPopover(state, menu, anchor);
}

function canBulkDeleteSelection(state) {
  if (state.payload.node_edit_enabled === false && state.payload.edge_edit_enabled !== true) {
    return false;
  }
  const editableNodes = [...state.selectedNodeIds].filter((id) => {
    const node = state.nodePayloadsById.get(id);
    return node && node.editable === true;
  });
  const edges = [...state.selectedEdgeIds].filter((id) => state.edgePayloadsById.has(id));
  return editableNodes.length > 0 || (state.payload.edge_edit_enabled === true && edges.length > 0);
}

function requestBulkDeleteSelection(state) {
  const editableNodes = [...state.selectedNodeIds].filter((id) => {
    const node = state.nodePayloadsById.get(id);
    return node && node.editable === true;
  });
  const edges = [...state.selectedEdgeIds].filter((id) => state.edgePayloadsById.has(id));
  const anchor = state.editHud || state.root;
  if (editableNodes.length) {
    openDeleteConfirmPopover(state, {
      message: editableNodes.length === 1
        ? "Удалить карточку?"
        : `Удалить ${editableNodes.length} карточек?`,
      anchor,
      onConfirm: () => {
        if (editableNodes.length === 1) {
          commitNodeEdit(state, editableNodes[0], { deleted: true });
        } else {
          commitNodeEdits(state, editableNodes, { deleted: true });
        }
      },
    });
    return;
  }
  if (edges.length && state.payload.edge_edit_enabled === true) {
    openDeleteConfirmPopover(state, {
      message: edges.length === 1 ? "Удалить связь?" : `Удалить ${edges.length} связей?`,
      anchor,
      onConfirm: () => {
        if (edges.length === 1) {
          commitEdgeEdit(state, edges[0], { deleted: true });
        } else {
          commitEdgeEdits(state, edges, { deleted: true });
        }
      },
    });
  }
}

function openNodeFieldEditor(state, nodeId, field, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable) {
    return;
  }
  if (field === "title") {
    beginTitleEdit(state, nodeId);
    return;
  }
  if (field === "kind") {
    openKindMenu(state, nodeId, anchor);
    return;
  }
  if (field === "roles") {
    openRolesPopover(state, nodeId, anchor);
    return;
  }
  if (field === "approvers") {
    openApproversPopover(state, nodeId, anchor);
    return;
  }
  if (field === "process") {
    openAssignToProcessPopover(state, [nodeId], anchor);
    return;
  }
  if (field === "delete") {
    openDeleteConfirmPopover(state, {
      message: "Удалить карточку?",
      anchor,
      onConfirm: () => commitNodeEdit(state, nodeId, { deleted: true }),
    });
    return;
  }
  if (field === "duration") {
    openDurationPopover(state, nodeId, anchor);
    return;
  }
  if (field === "note") {
    openTextFieldPopover(state, nodeId, field, anchor);
  }
}

function openDeleteConfirmPopover(state, { message, anchor, onConfirm }) {
  closeActiveEditPopover(state);
  const pop = createElement("div", "flow-edit-field-popover flow-edit-confirm", state.root);
  state.activeEditPopover = pop;
  const label = createElement("div", "flow-edit-confirm__message", pop);
  label.textContent = message;
  const actions = createElement("div", "flow-edit-confirm__actions", pop);
  const cancel = createElement("button", "flow-edit-menu__item", actions);
  cancel.type = "button";
  cancel.textContent = "Отмена";
  cancel.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
  });
  const confirmBtn = createElement("button", "flow-edit-menu__item is-danger is-apply", actions);
  confirmBtn.type = "button";
  confirmBtn.textContent = "Удалить";
  confirmBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    onConfirm();
  });
  positionEditPopover(state, pop, anchor);
  confirmBtn.focus();
}

function openTextFieldPopover(state, nodeId, field, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable) {
    return;
  }
  closeActiveEditPopover(state);
  const pop = createElement("div", "flow-edit-field-popover", state.root);
  state.activeEditPopover = pop;
  const label = createElement("div", "flow-edit-field-popover__label", pop);
  label.textContent = "Заметка";
  const input = createElement("input", "flow-edit-field-popover__input", pop);
  input.type = "text";
  input.value = node.note || "";
  input.placeholder = "…";
  const apply = createElement("button", "flow-edit-menu__item is-apply", pop);
  apply.type = "button";
  apply.textContent = "Применить";
  const commit = () => {
    closeActiveEditPopover(state);
    commitNodeEdit(state, nodeId, { note: input.value });
  };
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    commit();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeActiveEditPopover(state);
    }
  });
  positionEditPopover(state, pop, anchor);
  input.focus();
  input.select();
}

const DURATION_UNIT_OPTIONS = [
  { id: "minutes", label: "минут", singular: "minute", plural: "minutes" },
  { id: "hours", label: "час", singular: "hour", plural: "hours" },
  { id: "days", label: "день", singular: "day", plural: "days" },
];

function parseDurationParts(raw) {
  const text = String(raw || "").trim().toLowerCase().replace(/\s+/g, " ");
  if (!text) {
    return { amount: "", unit: "hours" };
  }
  const match = text.match(
    /^(?:(\d+)\s*-\s*(\d+)|(\d+))\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$/,
  );
  if (!match) {
    return { amount: "", unit: "hours" };
  }
  const amount = match[1] && match[2] ? `${match[1]}-${match[2]}` : match[3];
  const token = match[4];
  let unit = "hours";
  if (token === "m" || token.startsWith("min")) {
    unit = "minutes";
  } else if (token === "d" || token.startsWith("day")) {
    unit = "days";
  }
  return { amount, unit };
}

function formatDurationValue(amountRaw, unitId) {
  const text = String(amountRaw || "").trim();
  if (!text) {
    return "";
  }
  const rangeMatch = text.match(/^(\d+)\s*-\s*(\d+)$/);
  const option = DURATION_UNIT_OPTIONS.find((item) => item.id === unitId)
    || DURATION_UNIT_OPTIONS[1];
  if (rangeMatch) {
    const lo = Number.parseInt(rangeMatch[1], 10);
    const hi = Number.parseInt(rangeMatch[2], 10);
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo <= 0 || hi <= 0 || lo > hi) {
      return "";
    }
    if (lo === hi) {
      const unit = lo === 1 ? option.singular : option.plural;
      return `${lo} ${unit}`;
    }
    return `${lo}-${hi} ${option.plural}`;
  }
  const amount = Number.parseInt(text, 10);
  if (!Number.isFinite(amount) || amount < 0) {
    return "";
  }
  if (amount === 0) {
    return "";
  }
  const unit = amount === 1 ? option.singular : option.plural;
  return `${amount} ${unit}`;
}

function openDurationPopover(state, nodeId, anchor, nodeIds = null) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable) {
    return;
  }
  const targets = Array.isArray(nodeIds) && nodeIds.length ? nodeIds : [nodeId];
  closeActiveEditPopover(state);
  const parsed = parseDurationParts(node.duration);
  const pop = createElement("div", "flow-edit-field-popover flow-edit-duration", state.root);
  state.activeEditPopover = pop;
  const label = createElement("div", "flow-edit-field-popover__label", pop);
  label.textContent = "Длительность";
  const row = createElement("div", "flow-edit-duration__row", pop);
  const input = createElement("input", "flow-edit-field-popover__input flow-edit-duration__amount", row);
  input.type = "text";
  input.inputMode = "numeric";
  input.placeholder = "1 или 1-2";
  input.value = parsed.amount;
  const unitSelect = createElement("select", "flow-edit-duration__unit", row);
  for (const option of DURATION_UNIT_OPTIONS) {
    const opt = createElement("option", "", unitSelect);
    opt.value = option.id;
    opt.textContent = option.label;
  }
  unitSelect.value = parsed.unit;
  const contextLabel = createElement("div", "flow-edit-field-popover__label", pop);
  contextLabel.textContent = "Уточнение";
  const contextInput = createElement("input", "flow-edit-field-popover__input", pop);
  contextInput.type = "text";
  contextInput.placeholder = "после запроса, до глубины…";
  contextInput.value = node.duration_context || "";
  const apply = createElement("button", "flow-edit-menu__item is-apply", pop);
  apply.type = "button";
  apply.textContent = "Применить";
  const commit = () => {
    closeActiveEditPopover(state);
    const patch = {
      duration: formatDurationValue(input.value, unitSelect.value),
      duration_context: String(contextInput.value || "").trim(),
    };
    if (targets.length === 1) {
      commitNodeEdit(state, targets[0], patch);
    } else {
      commitNodeEdits(state, targets, patch);
    }
  };
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    commit();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeActiveEditPopover(state);
    }
  });
  contextInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeActiveEditPopover(state);
    }
  });
  positionEditPopover(state, pop, anchor);
  input.focus();
  input.select();
}

function openKindMenu(state, nodeId, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable || !Array.isArray(node.kind_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  for (const option of node.kind_options) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = option.label || option.id;
    if (option.id === node.kind) {
      item.classList.add("is-active");
    }
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      commitNodeEdit(state, nodeId, { kind: option.id });
    });
  }
  positionEditPopover(state, menu, anchor);
}

function openEdgeKindEditor(state, edgeId, anchor) {
  const edge = state.edgePayloadsById.get(edgeId);
  if (!edge) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const current = sourceEdgeKind(edge.kind);
  for (const option of EDGE_KIND_MENU_OPTIONS) {
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = option.label;
    if (option.id === current) {
      item.classList.add("is-active");
    }
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      commitEdgeEdit(state, edgeId, { kind: option.id });
    });
  }
  positionEditPopover(state, menu, anchor);
}

function openRolesPopover(state, nodeId, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable || !Array.isArray(node.responsible_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-node-roles-menu", state.root);
  state.activeEditPopover = menu;

  let responsible = node.responsible_id ?? null;
  let participants = [...(node.participants || [])];

  const responsibleRow = createElement("div", "flow-node-roles-menu__section", menu);
  createElement("div", "flow-node-roles-menu__label", responsibleRow).textContent = "Ответственный";
  const responsibleSelect = createElement("select", "flow-node-roles-menu__select", responsibleRow);
  const noneOption = createElement("option", "", responsibleSelect);
  noneOption.value = "";
  noneOption.textContent = "—";
  for (const option of node.responsible_options) {
    const opt = createElement("option", "", responsibleSelect);
    opt.value = option.id;
    opt.textContent = option.label || option.id;
  }
  responsibleSelect.value = responsible || "";

  const participantsBox = createRoleChecklist(
    menu,
    "Участники",
    node.responsible_options,
    participants,
  );

  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Применить";
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    responsible = responsibleSelect.value || null;
    participants = participantsBox.getSelected().filter((id) => id !== responsible);
    closeActiveEditPopover(state);
    commitNodeEdit(state, nodeId, {
      responsible,
      participants,
    });
  });

  positionEditPopover(state, menu, anchor);
}

function openApproversPopover(state, nodeId, anchor) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node?.editable || !Array.isArray(node.responsible_options)) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-node-roles-menu", state.root);
  state.activeEditPopover = menu;
  const responsible = node.responsible_id ?? null;
  const participants = new Set(node.participants || []);
  const approversBox = createRoleChecklist(
    menu,
    "Согласующие",
    node.responsible_options,
    [...(node.approvers || [])],
  );
  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Применить";
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    const approvers = approversBox.getSelected().filter(
      (id) => id !== responsible && !participants.has(id),
    );
    closeActiveEditPopover(state);
    commitNodeEdit(state, nodeId, { approvers });
  });
  positionEditPopover(state, menu, anchor);
}

function openAssignToProcessPopover(state, nodeIds, anchor) {
  if (!nodeIds?.length || state.payload.node_edit_enabled !== true) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const membership = processMembershipByNodeId(state);
  const current = membership.get(nodeIds[0]);
  const sameCurrent = nodeIds.every((id) => membership.get(id)?.id === current?.id);

  if (sameCurrent && current) {
    const removeItem = createElement("button", "flow-edit-menu__item", menu);
    removeItem.type = "button";
    removeItem.textContent = `Убрать из «${current.title || "Процесс"}»`;
    removeItem.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      const nextMembers = (current.member_ids || []).filter(
        (id) => !nodeIds.includes(id),
      );
      commitProcessEdit(state, current.id, { member_ids: nextMembers });
    });
  }

  for (const process of state.payload.processes || []) {
    if (sameCurrent && current && process.id === current.id) {
      continue;
    }
    const item = createElement("button", "flow-edit-menu__item", menu);
    item.type = "button";
    item.textContent = process.title || "Процесс";
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      closeActiveEditPopover(state);
      const merged = [
        ...new Set([...(process.member_ids || []), ...nodeIds]),
      ];
      commitProcessEdit(state, process.id, { member_ids: merged });
    });
  }

  const createItem = createElement("button", "flow-edit-menu__item", menu);
  createItem.type = "button";
  createItem.textContent = "Новый процесс…";
  createItem.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openCreateProcessTitlePopover(state, nodeIds, anchor);
  });
  positionEditPopover(state, menu, anchor);
}

function openCreateProcessTitlePopover(state, nodeIds, anchor) {
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-edit-process-title", state.root);
  state.activeEditPopover = menu;
  const input = createElement("input", "", menu);
  input.type = "text";
  input.placeholder = "Название процесса";
  input.value = "Процесс";
  input.addEventListener("pointerdown", (event) => event.stopPropagation());
  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Создать";
  const submit = () => {
    const title = String(input.value || "").trim();
    if (!title) {
      return;
    }
    closeActiveEditPopover(state);
    commitProcessCreate(state, title, nodeIds);
  };
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    submit();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  });
  positionEditPopover(state, menu, anchor);
  input.focus();
  input.select();
}

function openProcessEditActionMenu(state, processId, anchor) {
  const process = (state.payload.processes || []).find((item) => item.id === processId);
  if (!process) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu", state.root);
  state.activeEditPopover = menu;
  const rename = createElement("button", "flow-edit-menu__item", menu);
  rename.type = "button";
  rename.textContent = "Название";
  rename.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openRenameProcessPopover(state, processId, anchor);
  });
  const remove = createElement("button", "flow-edit-menu__item is-danger", menu);
  remove.type = "button";
  remove.textContent = "Удалить процесс";
  remove.addEventListener("click", (event) => {
    event.stopPropagation();
    closeActiveEditPopover(state);
    openDeleteConfirmPopover(state, {
      message: "Удалить рамку процесса? Карточки останутся.",
      anchor,
      onConfirm: () => commitProcessDelete(state, processId),
    });
  });
  positionEditPopover(state, menu, anchor);
}

function openRenameProcessPopover(state, processId, anchor) {
  const process = (state.payload.processes || []).find((item) => item.id === processId);
  if (!process) {
    return;
  }
  closeActiveEditPopover(state);
  const menu = createElement("div", "flow-edit-menu flow-edit-process-title", state.root);
  state.activeEditPopover = menu;
  const input = createElement("input", "", menu);
  input.type = "text";
  input.value = process.title || "";
  input.addEventListener("pointerdown", (event) => event.stopPropagation());
  const apply = createElement("button", "flow-edit-menu__item is-apply", menu);
  apply.type = "button";
  apply.textContent = "Применить";
  const submit = () => {
    const title = String(input.value || "").trim();
    if (!title || title === process.title) {
      closeActiveEditPopover(state);
      return;
    }
    closeActiveEditPopover(state);
    commitProcessEdit(state, processId, { title });
  };
  apply.addEventListener("click", (event) => {
    event.stopPropagation();
    submit();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  });
  positionEditPopover(state, menu, anchor);
  input.focus();
  input.select();
}

function createRoleChecklist(parent, label, options, selectedIds) {
  const section = createElement("div", "flow-node-roles-menu__section", parent);
  createElement("div", "flow-node-roles-menu__label", section).textContent = label;
  const list = createElement("div", "flow-node-roles-menu__list", section);
  const checks = [];
  for (const option of options) {
    const row = createElement("label", "flow-node-roles-menu__check", list);
    const input = createElement("input", "", row);
    input.type = "checkbox";
    input.value = option.id;
    input.checked = selectedIds.includes(option.id);
    row.append(option.label || option.id);
    checks.push(input);
  }
  return {
    getSelected() {
      return checks.filter((input) => input.checked).map((input) => input.value);
    },
  };
}

function positionEditPopover(state, menu, anchor) {
  const rootRect = state.root.getBoundingClientRect();
  const anchorRect = anchor.getBoundingClientRect();
  menu.style.left = `${Math.max(8, anchorRect.left - rootRect.left)}px`;
  menu.style.top = `${Math.max(8, anchorRect.bottom - rootRect.top + 6)}px`;
  // Keep pointer events from falling through to the canvas/viewport under the menu.
  menu.addEventListener("pointerdown", (event) => {
    event.stopPropagation();
  });
  const onDocPointer = (event) => {
    // Streamlit hosts the canvas in Shadow DOM: document capture sees a
    // retargeted host as event.target, so contains() alone falsely closes
    // the menu before the item click fires.
    if (
      eventPathIncludes(event, menu)
      || eventPathIncludes(event, anchor)
      || eventPathIncludes(event, state.editHud)
    ) {
      return;
    }
    closeActiveEditPopover(state);
  };
  menu._cleanup = () => {
    state.ownerDocument.removeEventListener("pointerdown", onDocPointer, true);
    if (menu._outsideAttachTimer != null) {
      state.ownerDocument.defaultView?.clearTimeout(menu._outsideAttachTimer);
      menu._outsideAttachTimer = null;
    }
  };
  // Attach on next tick so the opening click cannot dismiss immediately.
  const view = state.ownerDocument.defaultView;
  if (view) {
    menu._outsideAttachTimer = view.setTimeout(() => {
      menu._outsideAttachTimer = null;
      if (state.activeEditPopover !== menu) {
        return;
      }
      state.ownerDocument.addEventListener("pointerdown", onDocPointer, true);
    }, 0);
  } else {
    state.ownerDocument.addEventListener("pointerdown", onDocPointer, true);
  }
}

function buildMinimapEdgeElement(state, edge) {
  const path = createSvgElement("path");
  path.classList.add("flow-canvas-minimap__edge");
  path.dataset.edgeId = edge.id;
  path.setAttribute("d", roundedPath(edge.points));
  state.dom.minimapEdgeLayer.appendChild(path);
}

function buildMinimapNodeElement(state, node) {
  const shape = createMinimapNodeShape(node);
  shape.classList.add("flow-canvas-minimap__node", `is-${node.kind.replaceAll("_", "-")}`);
  shape.classList.toggle("is-selected", isNodeSelected(state, node.id));
  syncMinimapNodeShape(shape, node, state.positions[node.id] || node.position);
  state.dom.minimapNodeLayer.appendChild(shape);
  state.minimapNodeElements.set(node.id, shape);
}

function updateNodePositions(state) {
  for (const node of state.payload.nodes) {
    const elements = state.nodeElements.get(node.id);
    if (!elements) {
      continue;
    }
    syncNodeShellPosition(elements.shell, state.positions[node.id] || node.position);
  }
  syncProcessFrames(state);
}

function updateEdgeGeometry(state) {
  for (const edge of state.payload.edges || []) {
    const elements = state.edgeElements.get(edge.id);
    if (!elements || !Array.isArray(edge.points) || edge.points.length < 2) {
      continue;
    }
    const points = liveEdgePoints(state, edge);
    const pathData = roundedPath(points);
    if (elements.visiblePath) {
      elements.visiblePath.setAttribute("d", pathData);
    }
    if (elements.hitPath) {
      elements.hitPath.setAttribute("d", pathData);
    }
    if (elements.label && edge.label) {
      const labelPos = liveEdgeLabelPosition(edge, points);
      elements.label.style.left = `${labelPos.x}px`;
      elements.label.style.top = `${labelPos.y}px`;
      elements.label.style.width = `${edge.label.width}px`;
      elements.label.style.height = `${edge.label.height}px`;
    }
  }
  for (const path of state.dom.minimapEdgeLayer.querySelectorAll("[data-edge-id]")) {
    const edge = state.edgePayloadsById.get(path.dataset.edgeId);
    if (!edge || !Array.isArray(edge.points) || edge.points.length < 2) {
      continue;
    }
    path.setAttribute("d", roundedPath(liveEdgePoints(state, edge)));
  }
}

function nodePositionDelta(state, nodeId) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node || !node.position) {
    return { x: 0, y: 0 };
  }
  const live = state.positions[nodeId] || node.position;
  return {
    x: live.x - node.position.x,
    y: live.y - node.position.y,
  };
}

function liveEdgePoints(state, edge) {
  const points = edge.points;
  if (!Array.isArray(points) || points.length < 2) {
    return points || [];
  }
  const ds = nodePositionDelta(state, edge.source);
  const dt = nodePositionDelta(state, edge.target);
  if (ds.x === 0 && ds.y === 0 && dt.x === 0 && dt.y === 0) {
    return points;
  }
  if (ds.x === dt.x && ds.y === dt.y) {
    return points.map((point) => ({ x: point.x + ds.x, y: point.y + ds.y }));
  }

  const first = points[0];
  const last = points[points.length - 1];
  return points.map((point, index) => {
    if (index === 0) {
      return { x: point.x + ds.x, y: point.y + ds.y };
    }
    if (index === points.length - 1) {
      return { x: point.x + dt.x, y: point.y + dt.y };
    }
    // Sticky orthogonal: coords shared with an endpoint follow that card.
    const shareXWithStart = Math.abs(point.x - first.x) < 0.51;
    const shareYWithStart = Math.abs(point.y - first.y) < 0.51;
    const shareXWithEnd = Math.abs(point.x - last.x) < 0.51;
    const shareYWithEnd = Math.abs(point.y - last.y) < 0.51;
    let x = point.x;
    let y = point.y;
    if (shareXWithStart && !shareXWithEnd) {
      x += ds.x;
    } else if (shareXWithEnd && !shareXWithStart) {
      x += dt.x;
    } else {
      x += (ds.x + dt.x) / 2;
    }
    if (shareYWithStart && !shareYWithEnd) {
      y += ds.y;
    } else if (shareYWithEnd && !shareYWithStart) {
      y += dt.y;
    } else {
      y += (ds.y + dt.y) / 2;
    }
    return { x: round(x), y: round(y) };
  });
}

function liveEdgeLabelPosition(edge, livePoints) {
  const label = edge.label;
  const basePoints = edge.points;
  const baseMid = basePoints[Math.floor((basePoints.length - 1) / 2)];
  const liveMid = livePoints[Math.floor((livePoints.length - 1) / 2)];
  return {
    x: label.position.x + (liveMid.x - baseMid.x),
    y: label.position.y + (liveMid.y - baseMid.y),
  };
}

function updateMinimapNodePositions(state) {
  for (const node of state.payload.nodes) {
    const shape = state.minimapNodeElements.get(node.id);
    if (!shape) {
      continue;
    }
    syncMinimapNodeShape(shape, node, state.positions[node.id] || node.position);
  }
}

function updateDraggedNode(state, nodeId) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node) {
    return;
  }
  const position = state.positions[nodeId] || node.position;
  const elements = state.nodeElements.get(nodeId);
  if (elements) {
    syncNodeShellPosition(elements.shell, position);
  }
  const minimapNode = state.minimapNodeElements.get(nodeId);
  if (minimapNode) {
    syncMinimapNodeShape(minimapNode, node, position);
  }
}

function updateSelectionState(
  state,
  previousSelectedId,
  nextSelectedId,
  previousSelectedNodeIds = null,
  nextSelectedNodeIds = null,
  previousSelectedEdgeIds = null,
  nextSelectedEdgeIds = null,
) {
  const previousEdges = previousSelectedEdgeIds || selectedEdgeIdsForPrimary(state, previousSelectedId);
  const nextEdges = nextSelectedEdgeIds || state.selectedEdgeIds;
  const touchedEdgeIds = new Set([...previousEdges, ...nextEdges]);
  if (previousSelectedId) {
    touchedEdgeIds.add(previousSelectedId);
  }
  if (nextSelectedId) {
    touchedEdgeIds.add(nextSelectedId);
  }
  for (const edgeId of touchedEdgeIds) {
    syncEdgeSelectionById(state, edgeId);
  }
  const previousNodes = previousSelectedNodeIds || selectedNodeIdsForPrimary(state, previousSelectedId);
  const nextNodes = nextSelectedNodeIds || state.selectedNodeIds;
  const touchedNodeIds = new Set([...previousNodes, ...nextNodes]);
  if (previousSelectedId) {
    touchedNodeIds.add(previousSelectedId);
  }
  if (nextSelectedId) {
    touchedNodeIds.add(nextSelectedId);
  }
  for (const nodeId of touchedNodeIds) {
    syncNodeSelectionById(state, nodeId);
  }
  syncTokenSelectionById(state, previousSelectedId);
  syncTokenSelectionById(state, nextSelectedId);
  syncLegendHighlight(state);
  syncConnectModeChrome(state);
  syncSelectionEditHud(state);
}

function syncEdgeSelectionById(state, selectedId) {
  if (!selectedId) {
    return;
  }
  const edge = state.edgePayloadsById.get(selectedId);
  const elements = state.edgeElements.get(selectedId);
  if (!edge || !elements) {
    return;
  }
  setEdgeSelectedState(elements, edge, isEdgeSelected(state, selectedId));
}

function syncNodeSelectionById(state, selectedId) {
  if (!selectedId) {
    return;
  }
  const node = state.nodePayloadsById.get(selectedId);
  const elements = state.nodeElements.get(selectedId);
  if (!node || !elements) {
    return;
  }
  setNodeSelectedState(elements, node, isNodeSelected(state, selectedId));
  syncConnectionHandlesForNode(state, selectedId);

  const minimapNode = state.minimapNodeElements.get(selectedId);
  if (minimapNode) {
    minimapNode.classList.toggle("is-selected", isNodeSelected(state, selectedId));
  }
}

function syncTokenSelectionById(state, selectedId) {
  if (!selectedId) {
    return;
  }
  const tokenPayload = state.tokenPayloadsById.get(selectedId);
  const token = state.tokenElements.get(selectedId);
  if (!tokenPayload || !token) {
    return;
  }
  setTokenSelectedState(token, tokenPayload, state.selectedId === selectedId);
}

function syncDraggingState(state, previousNodeIds, nextNodeIds) {
  const previousIds = Array.isArray(previousNodeIds)
    ? previousNodeIds
    : previousNodeIds
      ? [previousNodeIds]
      : [];
  const nextIds = Array.isArray(nextNodeIds)
    ? nextNodeIds
    : nextNodeIds
      ? [nextNodeIds]
      : [];
  for (const nodeId of previousIds) {
    const previous = state.nodeElements.get(nodeId);
    if (previous) {
      previous.card.classList.remove("is-dragging");
    }
  }
  for (const nodeId of nextIds) {
    const next = state.nodeElements.get(nodeId);
    if (next) {
      next.card.classList.add("is-dragging");
    }
  }
}

function updateMinimapViewport(state) {
  const viewportRect = currentViewportWorldRect(state);
  state.dom.minimapViewport.setAttribute("x", String(round(viewportRect.x)));
  state.dom.minimapViewport.setAttribute("y", String(round(viewportRect.y)));
  state.dom.minimapViewport.setAttribute("width", String(round(viewportRect.width)));
  state.dom.minimapViewport.setAttribute("height", String(round(viewportRect.height)));
}

function setEdgeSelectedState(elements, edge, selected) {
  elements.visiblePath.classList.toggle("is-selected", selected);
  elements.visiblePath.setAttribute(
    "stroke-width",
    String(selected ? 3.3 : edge.style.strokeWidth || 2.4),
  );
  if (elements.label) {
    elements.label.classList.toggle("is-selected", selected);
    elements.label.style.transform = selected ? "translateY(-1px)" : "none";
  }
}

function setNodeSelectedState(elements, node, selected) {
  elements.shell.classList.toggle("is-selected", selected);
  elements.card.classList.toggle("is-selected", selected);
  if (selected && elements.overlay === null) {
    elements.overlay = buildNodeSelectionOverlay(node);
    elements.card.appendChild(elements.overlay);
  } else if (!selected && elements.overlay !== null) {
    elements.overlay.remove();
    elements.overlay = null;
  }
}

function setTokenSelectedState(element, tokenPayload, selected) {
  applyStyles(element, tokenPayload.style);
  element.textContent = tokenPayload.text;
  element.title = tokenPayload.title;
  if (selected) {
    element.style.boxShadow =
      "0 0 0 1px rgba(59, 130, 246, 0.55), 0 0 0 4px rgba(59, 130, 246, 0.14), 0 0 18px rgba(96, 165, 250, 0.35)";
  } else {
    element.style.boxShadow = "";
  }
}

function syncNodeShellPosition(shell, position) {
  shell.style.left = `${position.x}px`;
  shell.style.top = `${position.y}px`;
}

const NOTE_GAP_PX = 10;
const NOTE_MAX_WIDTH_PX = 200;

function nodeNoteText(node) {
  const raw = node?.note;
  if (typeof raw !== "string") {
    return "";
  }
  return raw.trim();
}

function syncNodeNoteElement(state, nodeId) {
  const node = state.nodePayloadsById.get(nodeId);
  const elements = state.nodeElements.get(nodeId);
  if (!node || !elements?.shell) {
    return;
  }
  const text = nodeNoteText(node);
  if (!text) {
    if (elements.noteEl) {
      elements.noteEl.remove();
      elements.noteEl = null;
    }
    return;
  }
  let noteEl = elements.noteEl;
  if (!noteEl) {
    noteEl = createElement("div", "flow-node-note", elements.shell);
    noteEl.setAttribute("aria-hidden", "true");
    elements.noteEl = noteEl;
  }
  if (noteEl.textContent !== text) {
    noteEl.textContent = text;
    noteEl.title = text;
  }
  noteEl.hidden = false;
}

function estimateNoteSize(text) {
  const maxInner = NOTE_MAX_WIDTH_PX - 18;
  const charWidth = 6.6;
  const lineHeight = 16;
  const charsPerLine = Math.max(8, Math.floor(maxInner / charWidth));
  const lines = Math.max(1, Math.ceil(String(text).length / charsPerLine));
  const width = Math.min(
    NOTE_MAX_WIDTH_PX,
    Math.max(72, Math.ceil(Math.min(String(text).length, charsPerLine) * charWidth + 18)),
  );
  const height = 12 + lines * lineHeight;
  return { width, height };
}

function nodeWorldRect(state, nodeId) {
  const node = state.nodePayloadsById.get(nodeId);
  if (!node) {
    return null;
  }
  const position = state.positions[nodeId] || node.position || { x: 0, y: 0 };
  const size = node.size || { w: 280, h: 72 };
  const wellRows = Array.isArray(node.well_tokens) && node.well_tokens.length
    ? Math.ceil(Math.min(node.well_tokens.length, 5) / 2)
    : 0;
  const wellsExtra = wellRows ? 12 + wellRows * 50 : 0;
  const hasTopBadges = Boolean(node.time_badge)
    || (Array.isArray(node.responsible_badges) && node.responsible_badges.length > 0);
  return {
    left: position.x,
    top: position.y - (hasTopBadges ? 30 : 0),
    right: position.x + (size.w || 0),
    bottom: position.y + (size.h || 0) + wellsExtra,
    cardTop: position.y,
    cardBottom: position.y + (size.h || 0),
  };
}

const PROCESS_FRAME_PAD = 24;
const PROCESS_FRAME_TITLE_GAP = 22;

function processFrameRect(state, memberIds) {
  let left = Infinity;
  let top = Infinity;
  let right = -Infinity;
  let bottom = -Infinity;
  let found = false;
  for (const id of memberIds || []) {
    const rect = nodeWorldRect(state, id);
    if (!rect) {
      continue;
    }
    found = true;
    left = Math.min(left, rect.left);
    top = Math.min(top, rect.top);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }
  if (!found) {
    return null;
  }
  return {
    x: left - PROCESS_FRAME_PAD,
    y: top - PROCESS_FRAME_PAD - PROCESS_FRAME_TITLE_GAP,
    w: (right - left) + PROCESS_FRAME_PAD * 2,
    h: (bottom - top) + PROCESS_FRAME_PAD * 2 + PROCESS_FRAME_TITLE_GAP,
  };
}

function processMembershipByNodeId(state) {
  const map = new Map();
  for (const process of state.payload.processes || []) {
    for (const memberId of process.member_ids || []) {
      map.set(memberId, process);
    }
  }
  return map;
}

function syncProcessFrames(state) {
  if (!state.dom?.processesLayer) {
    return;
  }
  if (!state.processElements) {
    state.processElements = new Map();
  }
  const processes = Array.isArray(state.payload.processes) ? state.payload.processes : [];
  const keep = new Set();
  for (const process of processes) {
    if (!process?.id || !(process.member_ids || []).length) {
      continue;
    }
    keep.add(process.id);
    let frame = state.processElements.get(process.id);
    if (!frame) {
      frame = createElement("div", "flow-process-frame", state.dom.processesLayer);
      frame.dataset.processId = process.id;
      const title = createElement("div", "flow-process-frame__title", frame);
      title.addEventListener("click", (event) => {
        event.stopPropagation();
        event.preventDefault();
        selectProcessFrame(state, process.id);
      });
      title.addEventListener("pointerdown", (event) => event.stopPropagation());
      frame.titleEl = title;
      state.processElements.set(process.id, frame);
    }
    frame.titleEl.textContent = process.title || "Процесс";
    frame.titleEl.title = process.title || "Процесс";
    frame.classList.toggle("is-selected", state.selectedProcessId === process.id);
    const rect = processFrameRect(state, process.member_ids);
    if (!rect) {
      frame.hidden = true;
      continue;
    }
    frame.hidden = false;
    frame.style.left = `${rect.x}px`;
    frame.style.top = `${rect.y}px`;
    frame.style.width = `${rect.w}px`;
    frame.style.height = `${rect.h}px`;
  }
  for (const [processId, frame] of [...state.processElements.entries()]) {
    if (!keep.has(processId)) {
      frame.remove();
      state.processElements.delete(processId);
    }
  }
}

function selectProcessFrame(state, processId) {
  state.selectedProcessId = processId;
  state.selectedNodeIds = new Set();
  state.selectedEdgeIds = new Set();
  state.selectedId = null;
  state.pendingSelectedId = null;
  for (const [nodeId, elements] of state.nodeElements) {
    const node = state.nodePayloadsById.get(nodeId);
    if (node) {
      setNodeSelectedState(elements, node, false);
    }
  }
  syncProcessFrames(state);
  syncSelectionEditHud(state);
}

function requestProcessEditId() {
  return `pe-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function commitProcessCreate(state, title, memberIds) {
  const cleaned = String(title || "").trim();
  if (!cleaned || !memberIds?.length || state.payload.node_edit_enabled !== true) {
    return;
  }
  state.component.setStateValue("pending_process_create", {
    request_id: requestProcessEditId(),
    title: cleaned,
    member_ids: [...memberIds],
  });
}

function commitProcessEdit(state, processId, patch) {
  if (!processId || state.payload.node_edit_enabled !== true) {
    return;
  }
  state.component.setStateValue("pending_process_edit", {
    request_id: requestProcessEditId(),
    process_id: processId,
    ...patch,
  });
}

function commitProcessDelete(state, processId) {
  if (!processId || state.payload.node_edit_enabled !== true) {
    return;
  }
  state.component.setStateValue("pending_process_delete", {
    request_id: requestProcessEditId(),
    process_id: processId,
  });
  if (state.selectedProcessId === processId) {
    state.selectedProcessId = null;
  }
}

function noteCandidateRects(nodeRect, noteSize) {
  const midY = nodeRect.cardTop
    + Math.max(0, (nodeRect.cardBottom - nodeRect.cardTop - noteSize.height) / 2);
  return [
    {
      left: nodeRect.right + NOTE_GAP_PX,
      top: midY,
      right: nodeRect.right + NOTE_GAP_PX + noteSize.width,
      bottom: midY + noteSize.height,
      side: "right",
    },
    {
      left: nodeRect.left - NOTE_GAP_PX - noteSize.width,
      top: midY,
      right: nodeRect.left - NOTE_GAP_PX,
      bottom: midY + noteSize.height,
      side: "left",
    },
    {
      left: nodeRect.left,
      top: nodeRect.bottom + NOTE_GAP_PX,
      right: nodeRect.left + noteSize.width,
      bottom: nodeRect.bottom + NOTE_GAP_PX + noteSize.height,
      side: "bottom",
    },
    {
      left: nodeRect.left,
      top: nodeRect.top - NOTE_GAP_PX - noteSize.height,
      right: nodeRect.left + noteSize.width,
      bottom: nodeRect.top - NOTE_GAP_PX,
      side: "top",
    },
  ];
}

function rectsOverlap(a, b, pad = 4) {
  return !(
    a.right + pad <= b.left
    || a.left - pad >= b.right
    || a.bottom + pad <= b.top
    || a.top - pad >= b.bottom
  );
}

function layoutAllNodeNotes(state) {
  const obstacles = [];
  for (const node of state.payload.nodes || []) {
    const rect = nodeWorldRect(state, node.id);
    if (rect) {
      obstacles.push({ id: node.id, rect });
    }
  }
  const placedNotes = [];
  for (const node of state.payload.nodes || []) {
    const elements = state.nodeElements.get(node.id);
    const text = nodeNoteText(node);
    if (!elements?.noteEl || !text) {
      continue;
    }
    const hostRect = nodeWorldRect(state, node.id);
    if (!hostRect) {
      continue;
    }
    const noteSize = estimateNoteSize(text);
    const candidates = noteCandidateRects(hostRect, noteSize);
    let chosen = candidates[0];
    let bestOverlap = Number.POSITIVE_INFINITY;
    for (const candidate of candidates) {
      let overlapArea = 0;
      let hits = false;
      for (const obstacle of obstacles) {
        if (obstacle.id === node.id) {
          continue;
        }
        if (rectsOverlap(candidate, obstacle.rect)) {
          hits = true;
          const w = Math.max(
            0,
            Math.min(candidate.right, obstacle.rect.right) - Math.max(candidate.left, obstacle.rect.left),
          );
          const h = Math.max(
            0,
            Math.min(candidate.bottom, obstacle.rect.bottom) - Math.max(candidate.top, obstacle.rect.top),
          );
          overlapArea += w * h;
        }
      }
      for (const placed of placedNotes) {
        if (rectsOverlap(candidate, placed)) {
          hits = true;
          const w = Math.max(
            0,
            Math.min(candidate.right, placed.right) - Math.max(candidate.left, placed.left),
          );
          const h = Math.max(
            0,
            Math.min(candidate.bottom, placed.bottom) - Math.max(candidate.top, placed.top),
          );
          overlapArea += w * h;
        }
      }
      if (!hits) {
        chosen = candidate;
        bestOverlap = 0;
        break;
      }
      if (overlapArea < bestOverlap) {
        bestOverlap = overlapArea;
        chosen = candidate;
      }
    }
    const shellX = (state.positions[node.id] || node.position || { x: 0 }).x;
    const shellY = (state.positions[node.id] || node.position || { y: 0 }).y;
    elements.noteEl.style.left = `${Math.round(chosen.left - shellX)}px`;
    elements.noteEl.style.top = `${Math.round(chosen.top - shellY)}px`;
    elements.noteEl.style.width = `${noteSize.width}px`;
    placedNotes.push(chosen);
  }
}

function buildNodeSelectionOverlay(node) {
  const overlay = createElement("span", "flow-node-selection");
  overlay.setAttribute("aria-hidden", "true");

  const svg = createSvgElement("svg");
  svg.classList.add("flow-node-selection__svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "none");
  overlay.appendChild(svg);

  // Soft bloom first, then a thin edge — both use the true silhouette.
  const descriptors = nodeSelectionShapeDescriptors(node);
  for (const className of ["flow-node-selection__glow", "flow-node-selection__stroke"]) {
    const group = createSvgElement("g");
    group.classList.add(className);
    for (const descriptor of descriptors) {
      group.appendChild(buildNodeSelectionShape(descriptor));
    }
    svg.appendChild(group);
  }
  return overlay;
}

function nodeSelectionShapeDescriptors(node) {
  const kind = node.kind;
  // Match flow_node_shape_backgrounds.py silhouettes exactly.
  if (kind === "decision_diamond") {
    return [{ tag: "polygon", attrs: { points: "50,2 98,50 50,98 2,50" } }];
  }
  if (kind === "input_data") {
    return [{ tag: "polygon", attrs: { points: "13,2 98,2 87,98 2,98" } }];
  }
  if (kind === "database") {
    return [
      {
        tag: "path",
        attrs: { d: "M8 20 L8 78 C8 92 92 92 92 78 L92 20 Z" },
      },
      { tag: "ellipse", attrs: { cx: "50", cy: "20", rx: "42", ry: "13" } },
    ];
  }

  // Rounded HTML cards: express CSS border-radius in non-uniform viewBox units
  // so corners stay circular on screen after preserveAspectRatio=none stretch.
  const width = Math.max(1, Number(node.size?.w) || 1);
  const height = Math.max(1, Number(node.size?.h) || 1);
  const radiusPx =
    kind === "event" ? 32 : kind === "figma_text" ? 10 : 8;
  const rx = String(round(Math.min(50, (radiusPx / width) * 100), 3));
  const ry = String(round(Math.min(50, (radiusPx / height) * 100), 3));
  return [{ tag: "rect", attrs: { x: "0", y: "0", width: "100", height: "100", rx, ry } }];
}

function buildNodeSelectionShape(descriptor) {
  const shape = createSvgElement(descriptor.tag);
  for (const [key, value] of Object.entries(descriptor.attrs)) {
    shape.setAttribute(key, value);
  }
  return shape;
}

function attachViewportHandlers(viewport, state) {
  viewport.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const scaleFactor = event.deltaY < 0 ? 1.08 : 1 / 1.08;
      const cursor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      zoomAt(state, cursor, scaleFactor);
      state.userMovedView = true;
      queueRender(state);
    },
    { passive: false },
  );

  viewport.addEventListener("pointerdown", (event) => {
    const wantPan = event.button === 1
      || event.button === 2
      || (event.button === 0 && state.spacePanHeld);
    if (wantPan) {
      event.preventDefault();
      startViewportPan(event, state, viewport);
      return;
    }
    if (isCanvasInteractiveTarget(event.target)) {
      return;
    }
    if (event.button === 0) {
      event.preventDefault();
      startMarqueeSelect(event, state, viewport);
    }
  });

  viewport.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });
}

function startViewportPan(event, state, viewport) {
  clearSelection(state.ownerDocument);
  state.isPanning = true;
  state.userMovedView = true;
  viewport.classList.add("is-panning");
  let panDidMove = false;
  let panFinished = false;
  const ownerDocument = state.ownerDocument;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  const previousCursor = ownerDocument.body ? ownerDocument.body.style.cursor : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
    ownerDocument.body.style.cursor = "grabbing";
  }
  if (typeof viewport.setPointerCapture === "function") {
    try {
      viewport.setPointerCapture(event.pointerId);
    } catch (_error) {
      // Ignore capture failures; document listeners remain as fallback.
    }
  }
  const start = {
    x: event.clientX,
    y: event.clientY,
    viewX: state.view.x,
    viewY: state.view.y,
  };
  const move = (moveEvent) => {
    if (panFinished) {
      return;
    }
    moveEvent.preventDefault();
    const dx = moveEvent.clientX - start.x;
    const dy = moveEvent.clientY - start.y;
    if (
      !panDidMove
      && (Math.abs(dx) >= PAN_CLICK_SUPPRESS_DISTANCE_PX
        || Math.abs(dy) >= PAN_CLICK_SUPPRESS_DISTANCE_PX)
    ) {
      panDidMove = true;
    }
    state.view.x = start.viewX + dx;
    state.view.y = start.viewY + dy;
    queueRender(state);
  };
  const stop = (stopEvent) => {
    if (panFinished) {
      return;
    }
    panFinished = true;
    state.isPanning = false;
    viewport.classList.remove("is-panning");
    if (!panDidMove) {
      if (state.connectMode) {
        cancelConnectMode(state);
      } else if (
        state.selectedId !== null
        || state.selectedNodeIds.size > 0
        || state.selectedEdgeIds.size > 0
      ) {
        selectId(state, null);
      }
    }
    if (
      stopEvent
      && typeof viewport.releasePointerCapture === "function"
      && typeof viewport.hasPointerCapture === "function"
      && viewport.hasPointerCapture(stopEvent.pointerId)
    ) {
      try {
        viewport.releasePointerCapture(stopEvent.pointerId);
      } catch (_error) {
        // no-op
      }
    }
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = previousUserSelect;
      ownerDocument.body.style.cursor = previousCursor;
    }
    viewport.removeEventListener("pointermove", move);
    viewport.removeEventListener("pointerup", stop);
    viewport.removeEventListener("pointercancel", stop);
    ownerDocument.removeEventListener("pointermove", move);
    ownerDocument.removeEventListener("pointerup", stop);
    ownerDocument.removeEventListener("pointercancel", stop);
    queueRender(state);
  };
  viewport.addEventListener("pointermove", move, { passive: false });
  viewport.addEventListener("pointerup", stop);
  viewport.addEventListener("pointercancel", stop);
  ownerDocument.addEventListener("pointermove", move, { passive: false });
  ownerDocument.addEventListener("pointerup", stop);
  ownerDocument.addEventListener("pointercancel", stop);
  queueRender(state);
}

function startMarqueeSelect(event, state, viewport) {
  clearSelection(state.ownerDocument);
  state.isMarqueeSelecting = true;
  let finished = false;
  let didDrag = false;
  const ownerDocument = state.ownerDocument;
  const rootRect = state.root.getBoundingClientRect();
  const startClient = { x: event.clientX, y: event.clientY };
  const startWorld = clientToWorld(state, event.clientX, event.clientY, viewport);
  destroyMarquee(state);
  const marquee = createElement("div", "flow-canvas-marquee", state.root);
  state.marqueeEl = marquee;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
  }
  if (typeof viewport.setPointerCapture === "function") {
    try {
      viewport.setPointerCapture(event.pointerId);
    } catch (_error) {
      // no-op
    }
  }
  const updateBox = (clientX, clientY) => {
    const left = Math.min(startClient.x, clientX) - rootRect.left;
    const top = Math.min(startClient.y, clientY) - rootRect.top;
    const width = Math.abs(clientX - startClient.x);
    const height = Math.abs(clientY - startClient.y);
    marquee.style.left = `${left}px`;
    marquee.style.top = `${top}px`;
    marquee.style.width = `${width}px`;
    marquee.style.height = `${height}px`;
  };
  updateBox(event.clientX, event.clientY);
  const move = (moveEvent) => {
    if (finished) {
      return;
    }
    moveEvent.preventDefault();
    const dx = moveEvent.clientX - startClient.x;
    const dy = moveEvent.clientY - startClient.y;
    if (!didDrag && (Math.abs(dx) >= MARQUEE_MIN_SIZE_PX || Math.abs(dy) >= MARQUEE_MIN_SIZE_PX)) {
      didDrag = true;
    }
    updateBox(moveEvent.clientX, moveEvent.clientY);
  };
  const stop = (stopEvent) => {
    if (finished) {
      return;
    }
    finished = true;
    state.isMarqueeSelecting = false;
    const endX = stopEvent?.clientX ?? startClient.x;
    const endY = stopEvent?.clientY ?? startClient.y;
    destroyMarquee(state);
    if (
      stopEvent
      && typeof viewport.releasePointerCapture === "function"
      && typeof viewport.hasPointerCapture === "function"
      && viewport.hasPointerCapture(stopEvent.pointerId)
    ) {
      try {
        viewport.releasePointerCapture(stopEvent.pointerId);
      } catch (_error) {
        // no-op
      }
    }
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = previousUserSelect;
    }
    viewport.removeEventListener("pointermove", move);
    viewport.removeEventListener("pointerup", stop);
    viewport.removeEventListener("pointercancel", stop);
    ownerDocument.removeEventListener("pointermove", move);
    ownerDocument.removeEventListener("pointerup", stop);
    ownerDocument.removeEventListener("pointercancel", stop);
    if (!didDrag) {
      if (state.connectMode) {
        cancelConnectMode(state);
      } else {
        selectId(state, null);
      }
      queueRender(state);
      return;
    }
    const endWorld = clientToWorld(state, endX, endY, viewport);
    const rect = normalizeWorldRect(startWorld, endWorld);
    applyMarqueeSelection(state, rect, isMultiSelectModifier(event));
    queueRender(state);
  };
  viewport.addEventListener("pointermove", move, { passive: false });
  viewport.addEventListener("pointerup", stop);
  viewport.addEventListener("pointercancel", stop);
  ownerDocument.addEventListener("pointermove", move, { passive: false });
  ownerDocument.addEventListener("pointerup", stop);
  ownerDocument.addEventListener("pointercancel", stop);
}

function destroyMarquee(state) {
  if (state.marqueeEl) {
    state.marqueeEl.remove();
    state.marqueeEl = null;
  }
}

function clientToWorld(state, clientX, clientY, viewport) {
  const rect = viewport.getBoundingClientRect();
  return {
    x: (clientX - rect.left - state.view.x) / state.view.scale,
    y: (clientY - rect.top - state.view.y) / state.view.scale,
  };
}

function normalizeWorldRect(a, b) {
  return {
    left: Math.min(a.x, b.x),
    top: Math.min(a.y, b.y),
    right: Math.max(a.x, b.x),
    bottom: Math.max(a.y, b.y),
  };
}

function applyMarqueeSelection(state, rect, additive) {
  const nextNodes = additive ? new Set(state.selectedNodeIds) : new Set();
  const nextEdges = additive ? new Set(state.selectedEdgeIds) : new Set();
  for (const node of state.payload.nodes || []) {
    const position = state.positions[node.id] || node.position;
    const size = node.size || { w: 280, h: 72 };
    const nodeRect = {
      left: position.x,
      top: position.y,
      right: position.x + (size.w || 0),
      bottom: position.y + (size.h || 0),
    };
    if (rectsIntersect(rect, nodeRect)) {
      nextNodes.add(node.id);
    }
  }
  for (const edge of state.payload.edges || []) {
    if (edgeIntersectsRect(edge, rect)) {
      nextEdges.add(edge.id);
    }
  }
  // Prefer nodes over edges when both are hit; keep edges only if no nodes.
  if (nextNodes.size > 0) {
    nextEdges.clear();
  } else if (nextEdges.size > 0) {
    nextNodes.clear();
  }
  const primary = nextNodes.size
    ? [...nextNodes][nextNodes.size - 1]
    : nextEdges.size
      ? [...nextEdges][nextEdges.size - 1]
      : null;
  setSelectionSets(state, primary, nextNodes, nextEdges);
}

function rectsIntersect(a, b) {
  return a.left <= b.right && a.right >= b.left && a.top <= b.bottom && a.bottom >= b.top;
}

function edgeIntersectsRect(edge, rect) {
  const points = Array.isArray(edge.points) ? edge.points : [];
  if (!points.length) {
    return false;
  }
  for (const point of points) {
    if (
      point.x >= rect.left
      && point.x <= rect.right
      && point.y >= rect.top
      && point.y <= rect.bottom
    ) {
      return true;
    }
  }
  for (let index = 0; index < points.length - 1; index += 1) {
    if (segmentIntersectsRect(points[index], points[index + 1], rect)) {
      return true;
    }
  }
  if (edge.label?.position) {
    const lx = edge.label.position.x;
    const ly = edge.label.position.y;
    const lw = edge.label.width || 40;
    const lh = edge.label.height || 20;
    return rectsIntersect(rect, {
      left: lx,
      top: ly,
      right: lx + lw,
      bottom: ly + lh,
    });
  }
  return false;
}

function segmentIntersectsRect(a, b, rect) {
  if (
    (a.x >= rect.left && a.x <= rect.right && a.y >= rect.top && a.y <= rect.bottom)
    || (b.x >= rect.left && b.x <= rect.right && b.y >= rect.top && b.y <= rect.bottom)
  ) {
    return true;
  }
  const edges = [
    [{ x: rect.left, y: rect.top }, { x: rect.right, y: rect.top }],
    [{ x: rect.right, y: rect.top }, { x: rect.right, y: rect.bottom }],
    [{ x: rect.right, y: rect.bottom }, { x: rect.left, y: rect.bottom }],
    [{ x: rect.left, y: rect.bottom }, { x: rect.left, y: rect.top }],
  ];
  return edges.some(([p, q]) => segmentsIntersect(a, b, p, q));
}

function segmentsIntersect(a, b, c, d) {
  const orient = (p, q, r) => Math.sign((q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y));
  const o1 = orient(a, b, c);
  const o2 = orient(a, b, d);
  const o3 = orient(c, d, a);
  const o4 = orient(c, d, b);
  return o1 !== 0 && o2 !== 0 && o3 !== 0 && o4 !== 0 && o1 !== o2 && o3 !== o4;
}

function isCanvasInteractiveTarget(target) {
  if (!target || typeof target.closest !== "function") {
    return false;
  }
  return (
    target.closest(
      ".flow-canvas-topbar, .flow-canvas-toolbar, .flow-canvas-legend, .flow-canvas-minimap, .flow-canvas-add-node, .flow-canvas-inspector-toggle, .flow-node-shell, .flow-edge-label, .flow-edge-hit",
    ) !== null
  );
}

function clearSelection(ownerDocument) {
  const selection = ownerDocument.getSelection ? ownerDocument.getSelection() : null;
  if (selection && selection.rangeCount > 0) {
    selection.removeAllRanges();
  }
}

function startNodeDrag(event, state, nodeId) {
  if (event.button !== 0 || state.spacePanHeld) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  clearSelection(state.ownerDocument);

  const nodePosition = state.positions[nodeId];
  if (!nodePosition) {
    return;
  }
  const dragIds = resolveDragNodeIds(state, nodeId);
  const origins = {};
  for (const id of dragIds) {
    const position = state.positions[id];
    if (!position) {
      continue;
    }
    origins[id] = { ...position };
  }
  if (!origins[nodeId]) {
    return;
  }
  state.draggingNodeId = nodeId;
  state.draggingNodeIds = Object.keys(origins);
  destroyEditHud(state);
  const start = { x: event.clientX, y: event.clientY };
  let dragDistancePx = 0;
  const ownerDocument = state.ownerDocument;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  const previousCursor = ownerDocument.body ? ownerDocument.body.style.cursor : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
    ownerDocument.body.style.cursor = "grabbing";
  }
  const move = (moveEvent) => {
    moveEvent.preventDefault();
    const dxScreen = moveEvent.clientX - start.x;
    const dyScreen = moveEvent.clientY - start.y;
    dragDistancePx = Math.max(dragDistancePx, Math.hypot(dxScreen, dyScreen));
    const dx = dxScreen / state.view.scale;
    const dy = dyScreen / state.view.scale;
    let changed = false;
    for (const id of state.draggingNodeIds) {
      const origin = origins[id];
      if (!origin) {
        continue;
      }
      const nextPosition = {
        x: round(origin.x + dx),
        y: round(origin.y + dy),
      };
      const current = state.positions[id];
      if (current && nextPosition.x === current.x && nextPosition.y === current.y) {
        continue;
      }
      state.positions[id] = nextPosition;
      changed = true;
    }
    if (!changed) {
      return;
    }
    state.positionsVersion += 1;
    queueRender(state);
  };
  const stop = () => {
    ownerDocument.removeEventListener("pointermove", move);
    ownerDocument.removeEventListener("pointerup", stop);
    ownerDocument.removeEventListener("pointercancel", stop);
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = previousUserSelect;
      ownerDocument.body.style.cursor = previousCursor;
    }
    if (dragDistancePx >= NODE_DRAG_CLICK_SUPPRESS_DISTANCE_PX) {
      // Keep multi-select after a real drag; the synthetic click would collapse it.
      state.suppressNextNodeClick = true;
    }
    state.draggingNodeId = null;
    state.draggingNodeIds = [];
    state.component.setStateValue("positions", copyPositionMap(state.positions));
    syncSelectionEditHud(state);
    queueRender(state);
  };
  ownerDocument.addEventListener("pointermove", move, { passive: false });
  ownerDocument.addEventListener("pointerup", stop);
  ownerDocument.addEventListener("pointercancel", stop);
  queueRender(state);
}

function resolveDragNodeIds(state, nodeId) {
  if (state.selectedNodeIds.has(nodeId) && state.selectedNodeIds.size > 1) {
    return [...state.selectedNodeIds].filter((id) => state.positions[id]);
  }
  return [nodeId];
}

function isMultiSelectModifier(event) {
  return Boolean(event && (event.ctrlKey || event.metaKey));
}

function isNodeSelected(state, nodeId) {
  return state.selectedNodeIds.has(nodeId);
}

function isEdgeSelected(state, edgeId) {
  return state.selectedEdgeIds.has(edgeId) || state.selectedId === edgeId;
}

function selectedNodeIdsForPrimary(state, selectedId) {
  if (selectedId && state.nodePayloadsById.has(selectedId)) {
    return new Set([selectedId]);
  }
  return new Set();
}

function selectedEdgeIdsForPrimary(state, selectedId) {
  if (selectedId && state.edgePayloadsById.has(selectedId)) {
    return new Set([selectedId]);
  }
  return new Set();
}

function sameIdSets(a, b) {
  if (a === b) {
    return true;
  }
  if (!a || !b || a.size !== b.size) {
    return false;
  }
  for (const value of a) {
    if (!b.has(value)) {
      return false;
    }
  }
  return true;
}

function sameIdLists(a, b) {
  if (a === b) {
    return true;
  }
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    return false;
  }
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) {
      return false;
    }
  }
  return true;
}

const CONNECTION_HANDLE_SIDES = ["top", "right", "bottom", "left"];

function clearConnectionHandles(elements) {
  if (!elements || !Array.isArray(elements.handles)) {
    return;
  }
  for (const handle of elements.handles) {
    handle.remove();
  }
  elements.handles = [];
}

function preferredSourceSide(node) {
  const value = node?.source_position;
  if (CONNECTION_HANDLE_SIDES.includes(value)) {
    return value;
  }
  return "right";
}

function buildConnectionHandles(state, shell, node) {
  const handles = [];
  const preferred = preferredSourceSide(node);
  for (const side of CONNECTION_HANDLE_SIDES) {
    const handle = createElement("button", "flow-node-handle", shell);
    handle.type = "button";
    handle.classList.add(`is-${side}`);
    handle.dataset.side = side;
    handle.dataset.nodeId = node.id;
    handle.title = side === preferred
      ? "Потяните к другой карточке (основной выход)"
      : "Потяните к другой карточке";
    handle.setAttribute("aria-label", `Точка связи: ${side}`);
    if (side === preferred) {
      handle.classList.add("is-primary");
    }
    handle.addEventListener("pointerdown", (event) => {
      startConnectDrag(event, state, node.id, side, handle);
    });
    handles.push(handle);
  }
  return handles;
}

function syncConnectionHandlesForNode(state, nodeId) {
  const elements = state.nodeElements.get(nodeId);
  const node = state.nodePayloadsById.get(nodeId);
  if (!elements || !node) {
    return;
  }
  clearConnectionHandles(elements);
  const canEdit = state.payload.edge_edit_enabled === true;
  if (!canEdit || !isNodeSelected(state, nodeId)) {
    return;
  }
  elements.handles = buildConnectionHandles(state, elements.shell, node);
  syncHandleActiveStates(state);
}

function syncHandleActiveStates(state) {
  for (const elements of state.nodeElements.values()) {
    for (const handle of elements.handles || []) {
      const active = Boolean(
        state.connectMode
        && state.connectMode.sourceId === handle.dataset.nodeId
        && state.connectMode.side === handle.dataset.side,
      );
      handle.classList.toggle("is-active", active);
    }
  }
}

function syncConnectModeChrome(state) {
  const connecting = Boolean(state.connectMode);
  state.root.classList.toggle("is-connecting", connecting);
  const sourceId = state.connectMode?.sourceId || null;
  const hoverTargetId = state.connectMode?.targetId || null;
  for (const [nodeId, elements] of state.nodeElements) {
    elements.shell.classList.toggle("is-connect-source", connecting && nodeId === sourceId);
    elements.shell.classList.toggle(
      "is-connect-target",
      connecting && nodeId !== sourceId && nodeId === hoverTargetId,
    );
  }
  syncHandleActiveStates(state);
  updateConnectHint(state);
  syncConnectPreview(state);
}

function updateConnectHint(state) {
  const hint = state.dom?.connectHint;
  if (!hint) {
    return;
  }
  const canEdit = state.payload.edge_edit_enabled === true;
  if (!canEdit) {
    hint.hidden = true;
    hint.textContent = "";
    return;
  }
  if (state.connectMode) {
    hint.hidden = false;
    hint.textContent = state.connectMode.targetId
      ? "Отпустите кнопку мыши — связь будет создана · Esc — отмена"
      : "Ведите линию до другой карточки · Esc — отмена";
    hint.classList.add("is-active");
    return;
  }
  hint.hidden = true;
  hint.textContent = "";
  hint.classList.remove("is-active");
}

function handleAnchorWorldPoint(state, nodeId, side) {
  const node = state.nodePayloadsById.get(nodeId);
  const position = state.positions[nodeId] || node?.position;
  if (!node || !position) {
    return null;
  }
  const width = Number(node.size?.w) || 0;
  const height = Number(node.size?.h) || 0;
  if (side === "top") {
    return { x: position.x + width / 2, y: position.y };
  }
  if (side === "right") {
    return { x: position.x + width, y: position.y + height / 2 };
  }
  if (side === "bottom") {
    return { x: position.x + width / 2, y: position.y + height };
  }
  return { x: position.x, y: position.y + height / 2 };
}

function clientPointToWorld(state, clientX, clientY) {
  const rect = state.dom.viewport.getBoundingClientRect();
  return {
    x: round((clientX - rect.left - state.view.x) / state.view.scale),
    y: round((clientY - rect.top - state.view.y) / state.view.scale),
  };
}

function nodePaintRank(state, nodeId) {
  const shell = state.nodeElements.get(nodeId)?.shell;
  let z = 2;
  let index = 0;
  if (shell) {
    if (shell.classList?.contains("is-selected")) {
      z = 4;
    }
    const inlineZ = shell.style?.zIndex;
    if (inlineZ && inlineZ !== "auto") {
      const parsed = Number.parseInt(inlineZ, 10);
      if (Number.isFinite(parsed)) {
        z = parsed;
      }
    }
    const parent = shell.parentElement;
    if (parent) {
      index = Array.prototype.indexOf.call(parent.children, shell);
    }
  } else if (state.selectedId === nodeId || state.selectedNodeIds.has(nodeId)) {
    z = 4;
  }
  return z * 100000 + index;
}

function nodeIdFromWorldPoint(state, worldX, worldY) {
  // Slight pad so dropping near a card edge still counts while zoomed out.
  const pad = 6;
  let bestId = null;
  let bestRank = -Infinity;
  for (const [nodeId, node] of state.nodePayloadsById) {
    const position = state.positions[nodeId] || node?.position;
    if (!position) {
      continue;
    }
    const width = Number(node.size?.w) || 0;
    const height = Number(node.size?.h) || 0;
    if (width <= 0 || height <= 0) {
      continue;
    }
    if (
      worldX < position.x - pad
      || worldX > position.x + width + pad
      || worldY < position.y - pad
      || worldY > position.y + height + pad
    ) {
      continue;
    }
    const rank = nodePaintRank(state, nodeId);
    if (rank >= bestRank) {
      bestRank = rank;
      bestId = nodeId;
    }
  }
  return bestId;
}

function hitElementsFromPoint(state, clientX, clientY) {
  const roots = [];
  const rootNode = typeof state.root?.getRootNode === "function"
    ? state.root.getRootNode()
    : null;
  if (rootNode && typeof rootNode.elementsFromPoint === "function") {
    roots.push(rootNode);
  }
  if (state.ownerDocument && !roots.includes(state.ownerDocument)) {
    roots.push(state.ownerDocument);
  }
  const seen = new Set();
  const stack = [];
  for (const root of roots) {
    let hits = [];
    if (typeof root.elementsFromPoint === "function") {
      hits = root.elementsFromPoint(clientX, clientY) || [];
    } else if (typeof root.elementFromPoint === "function") {
      const one = root.elementFromPoint(clientX, clientY);
      hits = one ? [one] : [];
    }
    for (const hit of hits) {
      if (!hit || seen.has(hit)) {
        continue;
      }
      seen.add(hit);
      stack.push(hit);
    }
  }
  return stack;
}

function nodeIdFromDomPoint(state, clientX, clientY, ignoreNodeId = null) {
  for (const hit of hitElementsFromPoint(state, clientX, clientY)) {
    if (typeof hit.closest !== "function") {
      continue;
    }
    const card = hit.closest(".flow-node-card");
    if (card?.dataset?.nodeId && card.dataset.nodeId !== ignoreNodeId) {
      return card.dataset.nodeId;
    }
    const handle = hit.closest(".flow-node-handle");
    if (handle?.dataset?.nodeId && handle.dataset.nodeId !== ignoreNodeId) {
      return handle.dataset.nodeId;
    }
    const shell = hit.closest(".flow-node-shell");
    if (!shell) {
      continue;
    }
    const shellCard = shell.querySelector(".flow-node-card");
    if (shellCard?.dataset?.nodeId && shellCard.dataset.nodeId !== ignoreNodeId) {
      return shellCard.dataset.nodeId;
    }
  }
  return null;
}

function nodeIdFromClientPoint(state, clientX, clientY, options = {}) {
  const ignoreNodeId = options.ignoreNodeId || null;
  // Geometry is authoritative during connect-drag: pointer-capture on the
  // source handle makes elementsFromPoint stick to the source card.
  const world = clientPointToWorld(state, clientX, clientY);
  const geomId = nodeIdFromWorldPoint(state, world.x, world.y);
  if (options.geometryFirst) {
    if (geomId && geomId !== ignoreNodeId) {
      return geomId;
    }
    const domId = nodeIdFromDomPoint(state, clientX, clientY, ignoreNodeId);
    if (domId && domId !== ignoreNodeId) {
      return domId;
    }
    return null;
  }
  const domId = nodeIdFromDomPoint(state, clientX, clientY, ignoreNodeId);
  if (domId && domId !== ignoreNodeId) {
    return domId;
  }
  if (geomId && geomId !== ignoreNodeId) {
    return geomId;
  }
  return null;
}

function syncConnectPreview(state) {
  const preview = state.dom?.connectPreview;
  if (!preview) {
    return;
  }
  if (!state.connectMode?.start || !state.connectMode?.cursor) {
    preview.setAttribute("hidden", "");
    preview.removeAttribute("d");
    return;
  }
  const start = state.connectMode.start;
  const cursor = state.connectMode.cursor;
  preview.removeAttribute("hidden");
  preview.setAttribute(
    "d",
    `M ${start.x} ${start.y} L ${cursor.x} ${cursor.y}`,
  );
}

function startConnectDrag(event, state, sourceId, side, handle) {
  if (event.button !== 0 || state.payload.edge_edit_enabled !== true) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  clearSelection(state.ownerDocument);

  const start = handleAnchorWorldPoint(state, sourceId, side);
  if (!start) {
    return;
  }
  const cursor = clientPointToWorld(state, event.clientX, event.clientY);
  state.connectMode = {
    sourceId,
    side,
    pointerId: event.pointerId,
    start,
    cursor,
    targetId: null,
  };
  destroyEditHud(state);
  syncConnectModeChrome(state);
  queueRender(state);

  const ownerDocument = state.ownerDocument;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  const previousCursor = ownerDocument.body ? ownerDocument.body.style.cursor : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
    ownerDocument.body.style.cursor = "crosshair";
  }
  // Do NOT setPointerCapture on the handle: with capture, hit-testing sticks
  // to the source card and hover/drop never resolve other cards. Document
  // listeners below track the drag instead.

  const hitOptions = { geometryFirst: true, ignoreNodeId: sourceId };
  let stopped = false;

  const move = (moveEvent) => {
    if (stopped || !state.connectMode || state.connectMode.pointerId !== moveEvent.pointerId) {
      return;
    }
    moveEvent.preventDefault();
    const nextCursor = clientPointToWorld(state, moveEvent.clientX, moveEvent.clientY);
    const hoverId = nodeIdFromClientPoint(
      state,
      moveEvent.clientX,
      moveEvent.clientY,
      hitOptions,
    );
    const targetId = hoverId && state.nodePayloadsById.has(hoverId) ? hoverId : null;
    state.connectMode.cursor = nextCursor;
    if (state.connectMode.targetId !== targetId) {
      state.connectMode.targetId = targetId;
      syncConnectModeChrome(state);
    } else {
      syncConnectPreview(state);
      updateConnectHint(state);
    }
  };

  const stop = (stopEvent) => {
    if (stopped) {
      return;
    }
    if (state.connectMode && state.connectMode.pointerId !== stopEvent.pointerId) {
      return;
    }
    stopped = true;
    ownerDocument.removeEventListener("pointermove", move, true);
    ownerDocument.removeEventListener("pointerup", stop, true);
    ownerDocument.removeEventListener("pointercancel", stop, true);
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = previousUserSelect;
      ownerDocument.body.style.cursor = previousCursor;
    }
    if (!state.connectMode) {
      return;
    }
    const dropId = nodeIdFromClientPoint(
      state,
      stopEvent.clientX,
      stopEvent.clientY,
      hitOptions,
    );
    state.suppressNextNodeClick = true;
    if (dropId && state.nodePayloadsById.has(dropId)) {
      completeConnectMode(state, dropId);
      return;
    }
    cancelConnectMode(state);
  };

  // Capture phase on document so we keep receiving moves even if Streamlit
  // or shadow retargeting swallows bubble listeners.
  ownerDocument.addEventListener("pointermove", move, true);
  ownerDocument.addEventListener("pointerup", stop, true);
  ownerDocument.addEventListener("pointercancel", stop, true);
}

function beginConnectMode(state, sourceId, side) {
  if (state.payload.edge_edit_enabled !== true) {
    return;
  }
  const start = handleAnchorWorldPoint(state, sourceId, side) || { x: 0, y: 0 };
  state.connectMode = {
    sourceId,
    side,
    pointerId: null,
    start,
    cursor: { ...start },
    targetId: null,
  };
  destroyEditHud(state);
  syncConnectModeChrome(state);
  queueRender(state);
}

function cancelConnectMode(state) {
  if (!state.connectMode) {
    updateConnectHint(state);
    syncConnectPreview(state);
    return;
  }
  state.connectMode = null;
  syncConnectModeChrome(state);
  syncSelectionEditHud(state);
  queueRender(state);
}

function completeConnectMode(state, targetId) {
  const connectMode = state.connectMode;
  const sourceId = connectMode?.sourceId;
  if (!sourceId || sourceId === targetId || !state.nodePayloadsById.has(targetId)) {
    cancelConnectMode(state);
    return;
  }
  // One gesture → one pending_edge (pointerup + click / duplicate listeners).
  if (connectMode.submitted) {
    return;
  }
  if (canvasHasDirectedEdge(state, sourceId, targetId)) {
    cancelConnectMode(state);
    flashConnectHint(state, "Между этими карточками уже есть связь");
    return;
  }
  connectMode.submitted = true;
  const requestId = `pe-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  state.component.setStateValue("pending_edge", {
    source: sourceId,
    target: targetId,
    kind: "default",
    request_id: requestId,
  });
  state.connectMode = null;
  syncConnectModeChrome(state);
  // Keep the source card selected locally. Avoid a second setStateValue
  // (selected_id) in the same gesture — that can re-trigger the fragment with
  // a still-hot pending_edge and create the link twice.
  if (state.selectedId !== sourceId) {
    state.selectedId = sourceId;
    state.selectedNodeIds = new Set([sourceId]);
    state.pendingSelectedId = sourceId;
  }
  syncSelectionEditHud(state);
  queueRender(state);
}

function canvasHasDirectedEdge(state, sourceId, targetId) {
  const edges = Array.isArray(state.payload?.edges) ? state.payload.edges : [];
  return edges.some(
    (edge) => edge
      && edge.source === sourceId
      && edge.target === targetId,
  );
}

function flashConnectHint(state, message) {
  const hint = state.dom?.connectHint;
  if (!hint) {
    return;
  }
  hint.hidden = false;
  hint.textContent = message;
  hint.classList.add("is-active");
  if (state._connectHintTimer) {
    state.ownerDocument.defaultView?.clearTimeout(state._connectHintTimer);
  }
  const view = state.ownerDocument.defaultView;
  if (view) {
    state._connectHintTimer = view.setTimeout(() => {
      updateConnectHint(state);
    }, 2200);
  }
}

function selectId(state, value, options = {}) {
  const additive = options.additive === true;
  if (state.selectedProcessId) {
    state.selectedProcessId = null;
    syncProcessFrames(state);
  }
  const previousSelectedId = state.selectedId;
  const previousSelectedNodeIds = new Set(state.selectedNodeIds);
  const previousSelectedEdgeIds = new Set(state.selectedEdgeIds);
  let nextSelectedId = value;
  let nextSelectedNodeIds = new Set(state.selectedNodeIds);
  let nextSelectedEdgeIds = new Set(state.selectedEdgeIds);

  if (value === null) {
    nextSelectedNodeIds = new Set();
    nextSelectedEdgeIds = new Set();
  } else if (state.nodePayloadsById.has(value)) {
    nextSelectedEdgeIds = new Set();
    if (additive) {
      if (nextSelectedNodeIds.has(value)) {
        nextSelectedNodeIds.delete(value);
        nextSelectedId = nextSelectedNodeIds.size
          ? [...nextSelectedNodeIds][nextSelectedNodeIds.size - 1]
          : null;
      } else {
        nextSelectedNodeIds.add(value);
        nextSelectedId = value;
      }
    } else {
      nextSelectedNodeIds = new Set([value]);
      nextSelectedId = value;
    }
  } else if (state.edgePayloadsById.has(value)) {
    nextSelectedNodeIds = new Set();
    if (additive) {
      if (nextSelectedEdgeIds.has(value)) {
        nextSelectedEdgeIds.delete(value);
        nextSelectedId = nextSelectedEdgeIds.size
          ? [...nextSelectedEdgeIds][nextSelectedEdgeIds.size - 1]
          : null;
      } else {
        nextSelectedEdgeIds.add(value);
        nextSelectedId = value;
      }
    } else {
      nextSelectedEdgeIds = new Set([value]);
      nextSelectedId = value;
    }
  } else {
    // Well tokens stay single-select and clear multi-select sets.
    nextSelectedNodeIds = new Set();
    nextSelectedEdgeIds = new Set();
  }

  if (
    state.selectedId === nextSelectedId
    && sameIdSets(state.selectedNodeIds, nextSelectedNodeIds)
    && sameIdSets(state.selectedEdgeIds, nextSelectedEdgeIds)
    && state.pendingSelectedId === undefined
  ) {
    return;
  }

  state.selectedId = nextSelectedId;
  state.selectedNodeIds = nextSelectedNodeIds;
  state.selectedEdgeIds = nextSelectedEdgeIds;
  state.pendingSelectedId = nextSelectedId;
  state.component.setStateValue("selected_id", nextSelectedId);
  if (
    state.hasRenderedScene
    && (
      state.renderedSelectedId !== nextSelectedId
      || !sameIdSets(state.renderedSelectedNodeIds, nextSelectedNodeIds)
      || !sameIdSets(state.renderedSelectedEdgeIds, nextSelectedEdgeIds)
    )
  ) {
    updateSelectionState(
      state,
      previousSelectedId,
      nextSelectedId,
      previousSelectedNodeIds,
      nextSelectedNodeIds,
      previousSelectedEdgeIds,
      nextSelectedEdgeIds,
    );
    state.renderedSelectedId = nextSelectedId;
    state.renderedSelectedNodeIds = new Set(nextSelectedNodeIds);
    state.renderedSelectedEdgeIds = new Set(nextSelectedEdgeIds);
  }
  queueRender(state);
}

function setSelectionSets(state, primaryId, nextNodeIds, nextEdgeIds) {
  const previousSelectedId = state.selectedId;
  const previousSelectedNodeIds = new Set(state.selectedNodeIds);
  const previousSelectedEdgeIds = new Set(state.selectedEdgeIds);
  state.selectedId = primaryId;
  state.selectedNodeIds = nextNodeIds;
  state.selectedEdgeIds = nextEdgeIds;
  state.pendingSelectedId = primaryId;
  state.component.setStateValue("selected_id", primaryId);
  if (state.hasRenderedScene) {
    updateSelectionState(
      state,
      previousSelectedId,
      primaryId,
      previousSelectedNodeIds,
      nextNodeIds,
      previousSelectedEdgeIds,
      nextEdgeIds,
    );
    state.renderedSelectedId = primaryId;
    state.renderedSelectedNodeIds = new Set(nextNodeIds);
    state.renderedSelectedEdgeIds = new Set(nextEdgeIds);
  }
  syncSelectionEditHud(state);
}

function zoomAtCenter(state, scaleFactor) {
  const rect = state.root.getBoundingClientRect();
  zoomAt(state, { x: rect.width / 2, y: rect.height / 2 }, scaleFactor);
  state.userMovedView = true;
}

function zoomAt(state, cursor, scaleFactor) {
  const nextScale = clamp(round(state.view.scale * scaleFactor, 4), 0.32, 1.75);
  const worldX = (cursor.x - state.view.x) / state.view.scale;
  const worldY = (cursor.y - state.view.y) / state.view.scale;
  state.view.x = cursor.x - worldX * nextScale;
  state.view.y = cursor.y - worldY * nextScale;
  state.view.scale = nextScale;
}

function fitView(state) {
  const bounds = state.payload.bounds;
  const rect = state.root.getBoundingClientRect();
  if (!rect.width || !rect.height || !bounds.width || !bounds.height) {
    return;
  }

  const availableWidth = Math.max(120, rect.width - FIT_VIEW_PADDING_X * 2);
  const availableHeight = Math.max(
    120,
    rect.height - FIT_VIEW_PADDING_TOP - FIT_VIEW_PADDING_BOTTOM,
  );
  // Match zoomAt max (1.75) so large monitors can fill the workspace.
  const scale = clamp(
    Math.min(availableWidth / bounds.width, availableHeight / bounds.height),
    0.42,
    1.75,
  );
  state.view.scale = scale;
  state.view.x = round(
    FIT_VIEW_PADDING_X
      + (availableWidth - bounds.width * scale) / 2
      - bounds.left * scale,
  );
  state.view.y = round(
    FIT_VIEW_PADDING_TOP
      + (availableHeight - bounds.height * scale) / 2
      - bounds.top * scale,
  );
}

function toggleFullscreen(state) {
  setImmersiveMode(state, !state.immersiveMode);
}

function setImmersiveMode(state, enabled) {
  state.immersiveMode = Boolean(enabled);
  writeStoredImmersiveMode(state.ownerDocument, state.immersiveMode);
  // Entering immersive: hide the inspector so edits don't resurrect the side panel.
  if (state.immersiveMode && state.payload.inspector_collapsed !== true) {
    state.payload.inspector_collapsed = true;
    syncInspectorToggle(state);
    if (state.component && typeof state.component.setStateValue === "function") {
      state.component.setStateValue("inspector_collapsed", true);
    }
  }
  syncImmersiveHost(state);
  syncFullscreenClass(state);
  syncToolbarState(state);
  // Layout size changes under position:fixed — refit unless the user panned.
  const view = state.ownerDocument.defaultView;
  const refit = () => {
    if (!state.userMovedView) {
      fitView(state);
    }
    queueRender(state);
  };
  if (view) {
    view.requestAnimationFrame(refit);
  } else {
    refit();
  }
}

function isImmersiveMode(state) {
  return Boolean(state.immersiveMode);
}

function syncFullscreenClass(state) {
  state.root.classList.toggle("is-fullscreen", isImmersiveMode(state));
}

function getShadowHost(state) {
  const rootNode = state.root.getRootNode?.();
  if (rootNode && rootNode !== state.ownerDocument && rootNode.host) {
    return rootNode.host;
  }
  return null;
}

function syncImmersiveHost(state) {
  // Streamlit columns apply transforms that trap position:fixed. Move the
  // shadow host (keeps component CSS) to document.body while immersive.
  const host = getShadowHost(state);
  const body = state.ownerDocument.body;
  if (!host || !body) {
    syncFullscreenClass(state);
    return;
  }
  if (isImmersiveMode(state)) {
    if (!state._lightParent || !state._lightParent.isConnected) {
      // Remember the light-DOM parent only while the host is still in-layout.
      if (host.parentElement && host.parentElement !== body) {
        state._lightParent = host.parentElement;
      }
    }
    if (host.parentElement !== body) {
      body.appendChild(host);
    }
    syncFullscreenClass(state);
    return;
  }
  const home =
    state._lightParent && state._lightParent.isConnected ? state._lightParent : null;
  if (home && host.parentElement !== home) {
    home.appendChild(host);
  }
  state._lightParent = null;
  syncFullscreenClass(state);
}

function readStoredImmersiveMode(ownerDocument) {
  try {
    const storage = ownerDocument.defaultView?.sessionStorage;
    return storage?.getItem(IMMERSIVE_STORAGE_KEY) === "1";
  } catch (_error) {
    return false;
  }
}

function writeStoredImmersiveMode(ownerDocument, enabled) {
  try {
    const storage = ownerDocument.defaultView?.sessionStorage;
    if (!storage) {
      return;
    }
    if (enabled) {
      storage.setItem(IMMERSIVE_STORAGE_KEY, "1");
    } else {
      storage.removeItem(IMMERSIVE_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore quota / private-mode failures.
  }
}

function attachMinimapHandlers(minimap, state) {
  minimap.addEventListener("pointerdown", (event) => {
    if (
      event.button !== 0 ||
      state.isPanning ||
      state.draggingNodeId !== null ||
      state.minimapBounds === null
    ) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    clearSelection(state.ownerDocument);

    const updateView = (pointerEvent) => {
      const point = minimapPointToWorld(state.dom.minimapSvg, pointerEvent, state.minimapBounds);
      if (!point) {
        return;
      }
      centerViewAtWorld(state, point.x, point.y);
      state.userMovedView = true;
      queueRender(state);
    };

    updateView(event);
    const ownerDocument = state.ownerDocument;
    const move = (moveEvent) => {
      moveEvent.preventDefault();
      updateView(moveEvent);
    };
    const stop = () => {
      ownerDocument.removeEventListener("pointermove", move);
      ownerDocument.removeEventListener("pointerup", stop);
      ownerDocument.removeEventListener("pointercancel", stop);
    };
    ownerDocument.addEventListener("pointermove", move, { passive: false });
    ownerDocument.addEventListener("pointerup", stop);
    ownerDocument.addEventListener("pointercancel", stop);
  });
}

function createMinimapNodeShape(node) {
  if (node.kind === "decision_diamond" || node.kind === "input_data") {
    return createSvgElement("polygon");
  }
  if (node.kind === "database") {
    const group = createSvgElement("g");
    group.appendChild(createSvgElement("path"));
    group.appendChild(createSvgElement("ellipse"));
    const bottom = createSvgElement("path");
    bottom.setAttribute("fill", "none");
    group.appendChild(bottom);
    return group;
  }

  return createSvgElement("rect");
}

function syncMinimapNodeShape(shape, node, position) {
  const x = round(position.x);
  const y = round(position.y);
  const width = round(node.size.w);
  const height = round(node.size.h);

  if (node.kind === "decision_diamond") {
    shape.setAttribute(
      "points",
      `${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`,
    );
    return;
  }
  if (node.kind === "input_data") {
    shape.setAttribute(
      "points",
      `${x + width * 0.12},${y} ${x + width},${y} ${x + width * 0.88},${y + height} ${x},${y + height}`,
    );
    return;
  }
  if (node.kind === "database") {
    const [body, top, bottom] = shape.children;
    body.setAttribute(
      "d",
      `M ${x + width * 0.08} ${y + height * 0.2} L ${x + width * 0.08} ${y + height * 0.78} ` +
        `C ${x + width * 0.08} ${y + height * 0.92} ${x + width * 0.92} ${y + height * 0.92} ` +
        `${x + width * 0.92} ${y + height * 0.78} L ${x + width * 0.92} ${y + height * 0.2} Z`,
    );
    top.setAttribute("cx", String(round(x + width / 2)));
    top.setAttribute("cy", String(round(y + height * 0.2)));
    top.setAttribute("rx", String(round(width * 0.42)));
    top.setAttribute("ry", String(round(height * 0.13)));
    bottom.setAttribute(
      "d",
      `M ${x + width * 0.08} ${y + height * 0.78} ` +
        `C ${x + width * 0.08} ${y + height * 0.92} ${x + width * 0.92} ${y + height * 0.92} ` +
        `${x + width * 0.92} ${y + height * 0.78}`,
    );
    return;
  }

  shape.setAttribute("x", String(x));
  shape.setAttribute("y", String(y));
  shape.setAttribute("width", String(width));
  shape.setAttribute("height", String(height));
  shape.setAttribute(
    "rx",
    node.kind === "event" ? "26" : "10",
  );
}

function minimapBounds(bounds) {
  const padding = 36;
  return {
    left: round(bounds.left - padding),
    top: round(bounds.top - padding),
    width: round(bounds.width + padding * 2),
    height: round(bounds.height + padding * 2),
  };
}

function currentViewportWorldRect(state) {
  const rect = state.root.getBoundingClientRect();
  return {
    x: round(-state.view.x / state.view.scale),
    y: round(-state.view.y / state.view.scale),
    width: round(rect.width / state.view.scale),
    height: round(rect.height / state.view.scale),
  };
}

function minimapPointToWorld(svg, event, bounds) {
  if (!svg) {
    return null;
  }
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  const ratioX = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const ratioY = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  return {
    x: round(bounds.left + bounds.width * ratioX),
    y: round(bounds.top + bounds.height * ratioY),
  };
}

function centerViewAtWorld(state, worldX, worldY) {
  const rect = state.root.getBoundingClientRect();
  state.view.x = round(rect.width / 2 - worldX * state.view.scale);
  state.view.y = round(rect.height / 2 - worldY * state.view.scale);
}

function roundedPath(points) {
  if (!points.length) {
    return "";
  }
  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }
  // Keep orthogonal 90° elbows; only soften when both legs are long enough that
  // rounding won't crush the stub into the arrowhead.
  const CORNER_RADIUS = 14;
  const MIN_LEG_FOR_ROUND = 28;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const firstLength = distance(previous, current);
    const secondLength = distance(current, next);
    if (
      !firstLength ||
      !secondLength ||
      isCollinear(previous, current, next) ||
      firstLength < MIN_LEG_FOR_ROUND ||
      secondLength < MIN_LEG_FOR_ROUND
    ) {
      d += ` L ${current.x} ${current.y}`;
      continue;
    }
    const radius = Math.min(CORNER_RADIUS, firstLength / 2, secondLength / 2);
    const start = moveTowards(current, previous, radius);
    const end = moveTowards(current, next, radius);
    d += ` L ${start.x} ${start.y} Q ${current.x} ${current.y} ${end.x} ${end.y}`;
  }
  const last = points[points.length - 1];
  d += ` L ${last.x} ${last.y}`;
  return d;
}

function buildMarker(color, edgeId) {
  const marker = createSvgElement("marker");
  marker.setAttribute("id", `marker-${edgeId}`);
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "10");
  marker.setAttribute("markerHeight", "10");
  marker.setAttribute("orient", "auto-start-reverse");
  const path = createSvgElement("path");
  path.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  path.setAttribute("fill", color);
  marker.appendChild(path);
  return marker;
}

function nodePositionMap(nodes) {
  const result = {};
  for (const node of nodes) {
    result[node.id] = {
      x: round(node.position.x),
      y: round(node.position.y),
    };
  }
  return result;
}

function copyPositionMap(positions) {
  const result = {};
  for (const [nodeId, position] of Object.entries(positions)) {
    result[nodeId] = {
      x: round(position.x),
      y: round(position.y),
    };
  }
  return result;
}

function indexPayloadsById(payloads) {
  const result = new Map();
  for (const payload of payloads) {
    result.set(payload.id, payload);
  }
  return result;
}

function indexTokenPayloads(nodes) {
  const result = new Map();
  for (const node of nodes) {
    for (const token of node.well_tokens || []) {
      result.set(token.id, token);
    }
  }
  return result;
}

function samePositionMaps(first, second) {
  const firstKeys = Object.keys(first);
  const secondKeys = Object.keys(second);
  if (firstKeys.length !== secondKeys.length) {
    return false;
  }
  for (const key of firstKeys) {
    const firstPosition = first[key];
    const secondPosition = second[key];
    if (
      !secondPosition ||
      firstPosition.x !== secondPosition.x ||
      firstPosition.y !== secondPosition.y
    ) {
      return false;
    }
  }
  return true;
}

function edgeGeometrySignature(edges) {
  if (!Array.isArray(edges) || edges.length === 0) {
    return "";
  }
  const parts = [];
  for (const edge of edges) {
    parts.push(String(edge?.id || ""));
    const points = edge?.points;
    if (Array.isArray(points)) {
      for (const point of points) {
        parts.push(point?.x, point?.y);
      }
    }
    const label = edge?.label;
    if (label?.position) {
      parts.push(label.position.x, label.position.y, label.width, label.height);
    }
  }
  return parts.join("\0");
}

function createElement(tagName, className, parent) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (parent) {
    parent.appendChild(element);
  }
  return element;
}

function createSvgElement(tagName) {
  return document.createElementNS("http://www.w3.org/2000/svg", tagName);
}

function applyStyles(element, styles) {
  if (!styles) {
    return;
  }
  for (const [key, value] of Object.entries(styles)) {
    element.style[key] = String(value);
  }
}

function moveTowards(origin, target, distanceValue) {
  const dx = target.x - origin.x;
  const dy = target.y - origin.y;
  const length = Math.hypot(dx, dy) || 1;
  return {
    x: round(origin.x + (dx / length) * distanceValue, 2),
    y: round(origin.y + (dy / length) * distanceValue, 2),
  };
}

function distance(first, second) {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function isCollinear(first, second, third) {
  return (first.x === second.x && second.x === third.x) || (first.y === second.y && second.y === third.y);
}

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function getOwnerDocument(parentElement) {
  if (parentElement.ownerDocument) {
    return parentElement.ownerDocument;
  }
  if (parentElement.host && parentElement.host.ownerDocument) {
    return parentElement.host.ownerDocument;
  }
  return document;
}
