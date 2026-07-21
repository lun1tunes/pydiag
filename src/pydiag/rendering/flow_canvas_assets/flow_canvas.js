const TOOLBAR_BUTTONS = [
  { id: "zoom-in", label: "+" },
  { id: "zoom-out", label: "-" },
  { id: "reset-view", label: "Reset view" },
];
const FIT_VIEW_PADDING_X = 64;
const FIT_VIEW_PADDING_TOP = 48;
const FIT_VIEW_PADDING_BOTTOM = 64;
const PAN_CLICK_SUPPRESS_DISTANCE_PX = 4;
const NODE_DRAG_CLICK_SUPPRESS_DISTANCE_PX = 4;
const CANVAS_STATE_STORE_KEY = "__pydiagFlowCanvasStates";
const CANVAS_STATE_KEY = "well_drilling_flow_canvas_v2";

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
    if (state.root.parentElement !== parentElement) {
      for (const child of parentElement.querySelectorAll(".flow-canvas-root")) {
        if (child !== state.root) {
          child.remove();
        }
      }
      parentElement.appendChild(state.root);
    }
    state.component = component;
    state.ownerDocument = ownerDocument;
    state.root.__flowCanvasState = state;
    attachCanvasObservers(state);
    return state;
  }

  const root = ensureRoot(parentElement);
  state = createCanvasState(root, component, ownerDocument);
  initializeRootStructure(state);
  attachCanvasObservers(state);
  root.__flowCanvasState = state;
  store.set(CANVAS_STATE_KEY, state);
  return state;
}

function detachCanvasState(state) {
  if (state.resizeObserver) {
    state.resizeObserver.disconnect();
    state.resizeObserver = null;
  }
  if (state.fullscreenChangeHandler) {
    state.ownerDocument.removeEventListener("fullscreenchange", state.fullscreenChangeHandler);
    state.ownerDocument.removeEventListener(
      "webkitfullscreenchange",
      state.fullscreenChangeHandler,
    );
    state.fullscreenChangeHandler = null;
  }
}

function attachCanvasObservers(state) {
  if (!state.resizeObserver) {
    state.resizeObserver = new ResizeObserver(() => {
      if (!state.userMovedView) {
        fitView(state);
      }
      queueRender(state);
    });
    state.resizeObserver.observe(state.root);
  }
  if (!state.fullscreenChangeHandler) {
    state.fullscreenChangeHandler = () => {
      syncFullscreenClass(state);
      queueRender(state);
    };
    state.ownerDocument.addEventListener("fullscreenchange", state.fullscreenChangeHandler);
    state.ownerDocument.addEventListener(
      "webkitfullscreenchange",
      state.fullscreenChangeHandler,
    );
  }
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
    suppressNextNodeClick: false,
    responsibleFilter: [],
    pendingResponsibleFilter: undefined,
    lastHostResponsibleFilter: [],
    sessionEpoch: null,
    isPanning: false,
    draggingNodeId: null,
    draggingNodeIds: [],
    connectMode: null,
    frameRequested: false,
    lastRevision: null,
    sceneRevision: null,
    lastEdgeGeometrySignature: null,
    edgeGeometryVersion: 0,
    renderedSelectedId: null,
    renderedSelectedNodeIds: new Set(),
    renderedPositionsVersion: -1,
    renderedEdgeGeometryVersion: -1,
    renderedDraggingNodeId: null,
    renderedDraggingNodeIds: [],
    resizeObserver: null,
    fullscreenChangeHandler: null,
    keydownHandler: null,
    ownerDocument,
    dom: null,
    edgeElements: new Map(),
    nodeElements: new Map(),
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
    button.addEventListener("click", () => {
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
    nodesLayer,
    minimap,
    minimapSvg,
    minimapBackdrop,
    minimapEdgeLayer,
    minimapNodeLayer,
    minimapViewport,
  };

  if (!state.keydownHandler) {
    state.keydownHandler = (event) => {
      if (event.key === "Escape" && state.connectMode) {
        cancelConnectMode(state);
      }
    };
    state.ownerDocument.addEventListener("keydown", state.keydownHandler);
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
      state.lastRevision = null;
      state.selectedId = null;
      state.pendingSelectedId = undefined;
      state.selectedNodeIds = new Set();
      state.renderedSelectedId = null;
      state.renderedSelectedNodeIds = new Set();
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

  if ((graphChanged || state.draggingNodeId === null) && !samePositionMaps(state.positions, nextPositions)) {
    state.positions = nextPositions;
    state.positionsVersion += 1;
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
    if (!state.userMovedView) {
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
    rebuildGraphScene(state);
    state.sceneRevision = payload.revision;
    state.hasRenderedScene = true;
    state.renderedSelectedId = state.selectedId;
    state.renderedSelectedNodeIds = new Set(state.selectedNodeIds);
    state.renderedPositionsVersion = state.positionsVersion;
    state.renderedEdgeGeometryVersion = state.edgeGeometryVersion;
    state.renderedDraggingNodeId = state.draggingNodeId;
    state.renderedDraggingNodeIds = [...state.draggingNodeIds];
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
    ) {
      updateSelectionState(
        state,
        state.renderedSelectedId,
        state.selectedId,
        state.renderedSelectedNodeIds,
        state.selectedNodeIds,
      );
      state.renderedSelectedId = state.selectedId;
      state.renderedSelectedNodeIds = new Set(state.selectedNodeIds);
    }
  }

  syncResponsibleFilterDim(state);
  updateMinimapViewport(state);
  syncConnectModeChrome(state);
}

function syncToolbarState(state) {
  const fullscreenButton = state.dom.fullscreenButton;
  const fullscreenSupported = isFullscreenSupported(state.root);
  const fullscreenActive = isRootFullscreen(state);

  fullscreenButton.hidden = !fullscreenSupported;
  if (!fullscreenSupported) {
    return;
  }

  const title = fullscreenActive
    ? "Выйти из полноэкранного режима"
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
  state.dom.defs.replaceChildren();
  state.dom.edgeLayer.replaceChildren();
  state.dom.labelsLayer.replaceChildren();
  state.dom.nodesLayer.replaceChildren();
  state.dom.minimapEdgeLayer.replaceChildren();
  state.dom.minimapNodeLayer.replaceChildren();
  state.edgeElements = new Map();
  state.nodeElements = new Map();
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
    selectId(state, edge.id);
  });
  hitPath.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  group.appendChild(hitPath);

  let label = null;
  if (edge.label) {
    label = createElement("button", "flow-edge-label", state.dom.labelsLayer);
    label.type = "button";
    label.textContent = edge.label.text;
    label.style.left = `${edge.label.position.x}px`;
    label.style.top = `${edge.label.position.y}px`;
    label.style.width = `${edge.label.width}px`;
    label.style.height = `${edge.label.height}px`;
    label.style.border = `1px solid ${edge.label.color}`;
    label.style.color = edge.label.color;
    label.style.opacity = String(edge.label.active ? 1 : 0.24);
    label.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }
      event.stopPropagation();
      if (state.connectMode) {
        cancelConnectMode(state);
      }
      selectId(state, edge.id);
    });
    label.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  const elements = { visiblePath, hitPath, label };
  setEdgeSelectedState(elements, edge, state.selectedId === edge.id);
  state.edgeElements.set(edge.id, elements);
}

function buildNodeElement(state, node) {
  const shell = createElement("div", "flow-node-shell", state.dom.nodesLayer);
  shell.style.width = `${node.size.w}px`;
  shell.style.height = `${node.size.h}px`;

  if (node.time_badge || node.responsible_badges.length) {
    const rail = createElement("div", "flow-node-top-rail", shell);
    if (node.time_badge) {
      const badge = createElement("div", "flow-node-badge", rail);
      applyStyles(badge, node.time_badge.style);
      badge.textContent = node.time_badge.text;
      badge.title = node.time_badge.title;
    }
    for (const badgePayload of node.responsible_badges) {
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
    if (state.connectMode) {
      completeConnectMode(state, node.id);
      return;
    }
    selectId(state, node.id, { additive: isMultiSelectModifier(event) });
  });
  if (node.draggable && state.payload.position_edit_enabled) {
    card.addEventListener("pointerdown", (event) => startNodeDrag(event, state, node.id));
  }

  const content = createElement("span", "flow-node-content", card);
  const text = createElement("span", "flow-node-text", content);
  text.textContent = node.text;

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

  const elements = { shell, card, overlay: null, handles: [] };
  syncNodeShellPosition(shell, state.positions[node.id] || node.position);
  setNodeSelectedState(elements, node, isNodeSelected(state, node.id));
  state.nodeElements.set(node.id, elements);
  syncConnectionHandlesForNode(state, node.id);
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
) {
  syncEdgeSelectionById(state, previousSelectedId);
  syncEdgeSelectionById(state, nextSelectedId);
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
  setEdgeSelectedState(elements, edge, state.selectedId === selectedId);
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
    if (event.button !== 0 || isCanvasInteractiveTarget(event.target)) {
      return;
    }
    event.preventDefault();
    clearSelection(state.ownerDocument);
    state.isPanning = true;
    state.userMovedView = true;
    let panDidMove = false;
    let panFinished = false;
    const ownerDocument = state.ownerDocument;
    const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = "none";
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
      // Deselect only on a true background tap. A pan must not clear selection.
      if (!panDidMove) {
        if (state.connectMode) {
          cancelConnectMode(state);
        } else if (state.selectedId !== null || state.selectedNodeIds.size > 0) {
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
  });
}

function isCanvasInteractiveTarget(target) {
  if (!target || typeof target.closest !== "function") {
    return false;
  }
  return (
    target.closest(
      ".flow-canvas-topbar, .flow-canvas-toolbar, .flow-canvas-legend, .flow-canvas-minimap, .flow-node-shell, .flow-edge-label, .flow-edge-hit",
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
  if (event.button !== 0) {
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

function selectedNodeIdsForPrimary(state, selectedId) {
  if (selectedId && state.nodePayloadsById.has(selectedId)) {
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
  const hasSelectedNode = [...state.selectedNodeIds].some((nodeId) => (
    state.nodePayloadsById.has(nodeId)
  )) || (
    typeof state.selectedId === "string" && state.nodePayloadsById.has(state.selectedId)
  );
  if (hasSelectedNode) {
    hint.hidden = false;
    hint.textContent = "Потяните точку на карточке к другой карточке, чтобы создать связь.";
    hint.classList.remove("is-active");
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
      worldX < position.x
      || worldX > position.x + width
      || worldY < position.y
      || worldY > position.y + height
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

function nodeIdFromDomPoint(state, clientX, clientY) {
  for (const hit of hitElementsFromPoint(state, clientX, clientY)) {
    if (typeof hit.closest !== "function") {
      continue;
    }
    const card = hit.closest(".flow-node-card");
    if (card?.dataset?.nodeId) {
      return card.dataset.nodeId;
    }
    const handle = hit.closest(".flow-node-handle");
    if (handle?.dataset?.nodeId) {
      return handle.dataset.nodeId;
    }
    const shell = hit.closest(".flow-node-shell");
    if (!shell) {
      continue;
    }
    const shellCard = shell.querySelector(".flow-node-card");
    if (shellCard?.dataset?.nodeId) {
      return shellCard.dataset.nodeId;
    }
  }
  return null;
}

function nodeIdFromClientPoint(state, clientX, clientY) {
  // Prefer DOM (paint / z-index order) when a card is under the cursor.
  // Fall back to world geometry when capture / edge hits make DOM miss.
  const domId = nodeIdFromDomPoint(state, clientX, clientY);
  if (domId) {
    return domId;
  }
  const world = clientPointToWorld(state, clientX, clientY);
  return nodeIdFromWorldPoint(state, world.x, world.y);
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
  syncConnectModeChrome(state);
  queueRender(state);

  const ownerDocument = state.ownerDocument;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  const previousCursor = ownerDocument.body ? ownerDocument.body.style.cursor : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
    ownerDocument.body.style.cursor = "crosshair";
  }
  try {
    handle.setPointerCapture(event.pointerId);
  } catch (_error) {
    // Some environments may reject capture; document listeners still work.
  }

  const move = (moveEvent) => {
    if (!state.connectMode || state.connectMode.pointerId !== moveEvent.pointerId) {
      return;
    }
    moveEvent.preventDefault();
    const nextCursor = clientPointToWorld(state, moveEvent.clientX, moveEvent.clientY);
    const hoverId = nodeIdFromClientPoint(state, moveEvent.clientX, moveEvent.clientY);
    const targetId = hoverId && hoverId !== sourceId && state.nodePayloadsById.has(hoverId)
      ? hoverId
      : null;
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
    if (state.connectMode && state.connectMode.pointerId !== stopEvent.pointerId) {
      return;
    }
    ownerDocument.removeEventListener("pointermove", move);
    ownerDocument.removeEventListener("pointerup", stop);
    ownerDocument.removeEventListener("pointercancel", stop);
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = previousUserSelect;
      ownerDocument.body.style.cursor = previousCursor;
    }
    try {
      if (handle.hasPointerCapture?.(stopEvent.pointerId)) {
        handle.releasePointerCapture(stopEvent.pointerId);
      }
    } catch (_error) {
      // ignore
    }
    if (!state.connectMode) {
      return;
    }
    const dropId = nodeIdFromClientPoint(state, stopEvent.clientX, stopEvent.clientY);
    state.suppressNextNodeClick = true;
    if (dropId && dropId !== sourceId && state.nodePayloadsById.has(dropId)) {
      completeConnectMode(state, dropId);
      return;
    }
    cancelConnectMode(state);
  };

  ownerDocument.addEventListener("pointermove", move);
  ownerDocument.addEventListener("pointerup", stop);
  ownerDocument.addEventListener("pointercancel", stop);
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
  queueRender(state);
}

function completeConnectMode(state, targetId) {
  const sourceId = state.connectMode?.sourceId;
  if (!sourceId || sourceId === targetId || !state.nodePayloadsById.has(targetId)) {
    cancelConnectMode(state);
    return;
  }
  state.component.setStateValue("pending_edge", {
    source: sourceId,
    target: targetId,
    kind: "default",
  });
  state.connectMode = null;
  syncConnectModeChrome(state);
  // Keep the source card selected so the new edge appears under «Связи».
  if (state.selectedId !== sourceId) {
    selectId(state, sourceId);
  } else {
    queueRender(state);
  }
}

function selectId(state, value, options = {}) {
  const additive = options.additive === true;
  const previousSelectedId = state.selectedId;
  const previousSelectedNodeIds = new Set(state.selectedNodeIds);
  let nextSelectedId = value;
  let nextSelectedNodeIds = new Set(state.selectedNodeIds);

  if (value === null) {
    nextSelectedNodeIds = new Set();
  } else if (state.nodePayloadsById.has(value)) {
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
  } else {
    // Edges / well tokens stay single-select and clear node multi-select.
    nextSelectedNodeIds = new Set();
  }

  if (
    state.selectedId === nextSelectedId
    && sameIdSets(state.selectedNodeIds, nextSelectedNodeIds)
    && state.pendingSelectedId === undefined
  ) {
    return;
  }

  state.selectedId = nextSelectedId;
  state.selectedNodeIds = nextSelectedNodeIds;
  state.pendingSelectedId = nextSelectedId;
  state.component.setStateValue("selected_id", nextSelectedId);
  if (
    state.hasRenderedScene
    && (
      state.renderedSelectedId !== nextSelectedId
      || !sameIdSets(state.renderedSelectedNodeIds, nextSelectedNodeIds)
    )
  ) {
    updateSelectionState(
      state,
      previousSelectedId,
      nextSelectedId,
      previousSelectedNodeIds,
      nextSelectedNodeIds,
    );
    state.renderedSelectedId = nextSelectedId;
    state.renderedSelectedNodeIds = new Set(nextSelectedNodeIds);
  }
  queueRender(state);
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
  const request = isRootFullscreen(state)
    ? exitDocumentFullscreen(state.ownerDocument)
    : requestElementFullscreen(state.root);
  if (request && typeof request.catch === "function") {
    request.catch(() => {});
  }
}

function requestElementFullscreen(element) {
  if (typeof element.requestFullscreen === "function") {
    return element.requestFullscreen();
  }
  if (typeof element.webkitRequestFullscreen === "function") {
    return element.webkitRequestFullscreen();
  }
  return null;
}

function exitDocumentFullscreen(ownerDocument) {
  if (typeof ownerDocument.exitFullscreen === "function") {
    return ownerDocument.exitFullscreen();
  }
  if (typeof ownerDocument.webkitExitFullscreen === "function") {
    return ownerDocument.webkitExitFullscreen();
  }
  return null;
}

function isFullscreenSupported(element) {
  return (
    typeof element.requestFullscreen === "function" ||
    typeof element.webkitRequestFullscreen === "function"
  );
}

function fullscreenElementOfDocument(ownerDocument) {
  return ownerDocument.fullscreenElement || ownerDocument.webkitFullscreenElement || null;
}

function isRootFullscreen(state) {
  return fullscreenElementOfDocument(state.ownerDocument) === state.root;
}

function syncFullscreenClass(state) {
  state.root.classList.toggle("is-fullscreen", isRootFullscreen(state));
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
