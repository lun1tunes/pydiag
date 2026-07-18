const TOOLBAR_BUTTONS = [
  { id: "zoom-in", label: "+" },
  { id: "zoom-out", label: "-" },
  { id: "reset-view", label: "Reset view" },
];
const FIT_VIEW_PADDING_X = 64;
const FIT_VIEW_PADDING_TOP = 48;
const FIT_VIEW_PADDING_BOTTOM = 64;
const VIEW_STATE_IDLE_SYNC_MS = 360;

export default function(component) {
  const root = ensureRoot(component.parentElement);
  const state = ensureState(root, component);
  state.component = component;
  state.payload = normalizePayload(component.data);
  syncStateFromPayload(state);
  queueRender(state);

  return () => {
    if (state.resizeObserver) {
      state.resizeObserver.disconnect();
      state.resizeObserver = null;
    }
    if (state.viewSyncTimer !== null) {
      clearTimeout(state.viewSyncTimer);
      state.viewSyncTimer = null;
    }
    if (state.fullscreenChangeHandler) {
      state.ownerDocument.removeEventListener("fullscreenchange", state.fullscreenChangeHandler);
      state.ownerDocument.removeEventListener(
        "webkitfullscreenchange",
        state.fullscreenChangeHandler,
      );
      state.fullscreenChangeHandler = null;
    }
  };
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

function ensureState(root, component) {
  if (root.__flowCanvasState) {
    return root.__flowCanvasState;
  }

  const ownerDocument = getOwnerDocument(component.parentElement);
  const state = {
    root,
    component,
    payload: normalizePayload(component.data),
    nodePayloadsById: new Map(),
    edgePayloadsById: new Map(),
    tokenPayloadsById: new Map(),
    view: { x: 0, y: 0, scale: 1 },
    userMovedView: false,
    positions: {},
    positionsVersion: 0,
    selectedId: null,
    isPanning: false,
    draggingNodeId: null,
    frameRequested: false,
    lastRevision: null,
    sceneRevision: null,
    renderedSelectedId: null,
    renderedPositionsVersion: -1,
    renderedDraggingNodeId: null,
    resizeObserver: null,
    viewSyncTimer: null,
    fullscreenChangeHandler: null,
    ownerDocument,
    dom: null,
    edgeElements: new Map(),
    nodeElements: new Map(),
    tokenElements: new Map(),
    minimapNodeElements: new Map(),
    minimapBounds: null,
    lastReportedView: null,
    lastReportedUserMovedView: false,
  };

  initializeRootStructure(state);

  state.resizeObserver = new ResizeObserver(() => {
    if (!state.userMovedView) {
      fitView(state);
    }
    queueRender(state);
  });
  state.resizeObserver.observe(root);
  state.fullscreenChangeHandler = () => {
    syncFullscreenClass(state);
    queueRender(state);
  };
  ownerDocument.addEventListener("fullscreenchange", state.fullscreenChangeHandler);
  ownerDocument.addEventListener("webkitfullscreenchange", state.fullscreenChangeHandler);
  syncFullscreenClass(state);
  root.__flowCanvasState = state;
  return state;
}

function initializeRootStructure(state) {
  const root = state.root;
  root.replaceChildren();

  const emptyState = createElement("div", "flow-empty-state", root);
  emptyState.textContent = "На схеме пока нет элементов.";
  emptyState.hidden = true;

  const toolbar = createElement("div", "flow-canvas-toolbar", root);
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
      syncViewState(state);
      queueRender(state);
    });
    toolbarButtons[buttonDef.id] = button;
  }

  const fullscreenButton = createElement("button", "flow-canvas-toolbar__button", toolbar);
  fullscreenButton.type = "button";
  fullscreenButton.addEventListener("click", () => {
    toggleFullscreen(state);
  });

  const viewport = createElement("div", "flow-canvas-viewport", root);
  attachViewportHandlers(viewport, state);

  const stage = createElement("div", "flow-canvas-stage", viewport);
  const svg = createSvgElement("svg");
  svg.classList.add("flow-canvas-edges");
  stage.appendChild(svg);

  const defs = createSvgElement("defs");
  svg.appendChild(defs);
  const edgeLayer = createSvgElement("g");
  svg.appendChild(edgeLayer);

  const labelsLayer = createElement("div", "flow-canvas-labels", stage);
  const nodesLayer = createElement("div", "flow-canvas-nodes", stage);

  const minimap = createElement("div", "flow-canvas-minimap", root);
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
    toolbar,
    toolbarButtons,
    fullscreenButton,
    viewport,
    stage,
    svg,
    defs,
    edgeLayer,
    labelsLayer,
    nodesLayer,
    minimap,
    minimapSvg,
    minimapBackdrop,
    minimapEdgeLayer,
    minimapNodeLayer,
    minimapViewport,
  };
}

function normalizePayload(data) {
  if (!data || typeof data !== "object") {
    return {
      nodes: [],
      edges: [],
      canvas: { width: 1200, height: 828 },
      bounds: { left: 0, top: 0, right: 1200, bottom: 828, width: 1200, height: 828 },
      selected_id: null,
      position_edit_enabled: false,
      persisted_view_state: null,
      revision: 0,
    };
  }
  return data;
}

function syncStateFromPayload(state) {
  const payload = state.payload;
  const persistedViewState = normalizePersistedViewState(payload.persisted_view_state);
  const graphChanged = state.lastRevision !== payload.revision;
  const nextPositions = nodePositionMap(payload.nodes);

  state.nodePayloadsById = indexPayloadsById(payload.nodes);
  state.edgePayloadsById = indexPayloadsById(payload.edges);
  state.tokenPayloadsById = indexTokenPayloads(payload.nodes);

  if ((graphChanged || state.draggingNodeId === null) && !samePositionMaps(state.positions, nextPositions)) {
    state.positions = nextPositions;
    state.positionsVersion += 1;
  }

  state.selectedId = payload.selected_id ?? state.selectedId ?? null;
  if (persistedViewState && state.lastRevision === null) {
    state.view = persistedViewState.view;
    state.userMovedView = persistedViewState.userMovedView;
    state.lastReportedView = { ...persistedViewState.view };
    state.lastReportedUserMovedView = persistedViewState.userMovedView;
  }
  if (graphChanged) {
    state.lastRevision = payload.revision;
    if (!persistedViewState && !state.userMovedView) {
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
  syncFullscreenClass(state);
  syncToolbarState(state);
  syncViewportState(state);
  syncMinimapGeometry(state);

  if (!payload.nodes.length) {
    clearScene(state);
    state.dom.emptyState.hidden = false;
    state.dom.toolbar.hidden = true;
    state.dom.viewport.hidden = true;
    state.dom.minimap.hidden = true;
    state.sceneRevision = null;
    state.renderedSelectedId = state.selectedId;
    state.renderedPositionsVersion = state.positionsVersion;
    state.renderedDraggingNodeId = state.draggingNodeId;
    return;
  }

  state.dom.emptyState.hidden = true;
  state.dom.toolbar.hidden = false;
  state.dom.viewport.hidden = false;
  state.dom.minimap.hidden = false;

  const graphChanged = state.sceneRevision !== payload.revision;
  if (graphChanged) {
    rebuildGraphScene(state);
    state.sceneRevision = payload.revision;
    state.renderedSelectedId = state.selectedId;
    state.renderedPositionsVersion = state.positionsVersion;
    state.renderedDraggingNodeId = state.draggingNodeId;
  } else {
    if (state.renderedPositionsVersion !== state.positionsVersion) {
      updateNodePositions(state);
      updateMinimapNodePositions(state);
      state.renderedPositionsVersion = state.positionsVersion;
    }
    if (state.renderedDraggingNodeId !== state.draggingNodeId) {
      syncDraggingState(state, state.renderedDraggingNodeId, state.draggingNodeId);
      state.renderedDraggingNodeId = state.draggingNodeId;
    }
    if (state.renderedSelectedId !== state.selectedId) {
      updateSelectionState(state, state.renderedSelectedId, state.selectedId);
      state.renderedSelectedId = state.selectedId;
    }
  }

  updateMinimapViewport(state);
}

function syncToolbarState(state) {
  const fullscreenButton = state.dom.fullscreenButton;
  const fullscreenSupported = isFullscreenSupported(state.root);
  const fullscreenActive = isRootFullscreen(state);

  fullscreenButton.hidden = !fullscreenSupported;
  if (!fullscreenSupported) {
    return;
  }

  fullscreenButton.textContent = fullscreenActive ? "Exit" : "Full";
  fullscreenButton.title = fullscreenActive
    ? "Выйти из полноэкранного режима"
    : "Развернуть схему на весь экран";
  fullscreenButton.setAttribute("aria-label", fullscreenButton.title);
  fullscreenButton.classList.toggle("is-active", fullscreenActive);
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
  hitPath.addEventListener("click", (event) => {
    event.stopPropagation();
    selectId(state, edge.id);
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
    label.addEventListener("click", (event) => {
      event.stopPropagation();
      selectId(state, edge.id);
    });
  }

  const elements = { visiblePath, label };
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
  if (node.draggable && state.payload.position_edit_enabled) {
    card.classList.add("is-draggable");
  }
  if (state.draggingNodeId === node.id) {
    card.classList.add("is-dragging");
  }
  applyStyles(card, node.style);
  card.dataset.nodeId = node.id;
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    selectId(state, node.id);
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

  const elements = { shell, card, overlay: null };
  syncNodeShellPosition(shell, state.positions[node.id] || node.position);
  setNodeSelectedState(elements, node, state.selectedId === node.id);
  state.nodeElements.set(node.id, elements);
}

function buildMinimapEdgeElement(state, edge) {
  const path = createSvgElement("path");
  path.classList.add("flow-canvas-minimap__edge");
  path.setAttribute("d", roundedPath(edge.points));
  state.dom.minimapEdgeLayer.appendChild(path);
}

function buildMinimapNodeElement(state, node) {
  const shape = createMinimapNodeShape(node);
  shape.classList.add("flow-canvas-minimap__node", `is-${node.kind.replaceAll("_", "-")}`);
  shape.classList.toggle("is-selected", state.selectedId === node.id);
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

function updateMinimapNodePositions(state) {
  for (const node of state.payload.nodes) {
    const shape = state.minimapNodeElements.get(node.id);
    if (!shape) {
      continue;
    }
    syncMinimapNodeShape(shape, node, state.positions[node.id] || node.position);
  }
}

function updateSelectionState(state, previousSelectedId, nextSelectedId) {
  syncEdgeSelectionById(state, previousSelectedId);
  syncEdgeSelectionById(state, nextSelectedId);
  syncNodeSelectionById(state, previousSelectedId);
  syncNodeSelectionById(state, nextSelectedId);
  syncTokenSelectionById(state, previousSelectedId);
  syncTokenSelectionById(state, nextSelectedId);
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
  setNodeSelectedState(elements, node, state.selectedId === selectedId);

  const minimapNode = state.minimapNodeElements.get(selectedId);
  if (minimapNode) {
    minimapNode.classList.toggle("is-selected", state.selectedId === selectedId);
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

function syncDraggingState(state, previousNodeId, nextNodeId) {
  if (previousNodeId) {
    const previous = state.nodeElements.get(previousNodeId);
    if (previous) {
      previous.card.classList.remove("is-dragging");
    }
  }
  if (nextNodeId) {
    const next = state.nodeElements.get(nextNodeId);
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
      "0 0 0 3px rgba(59, 130, 246, 0.2), 0 12px 28px rgba(37, 99, 235, 0.16)";
    element.style.transform = "translateY(-1px)";
  } else {
    element.style.transform = "";
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

  const descriptors = nodeSelectionShapeDescriptors(node.kind);
  for (const className of [
    "flow-node-selection__glow",
    "flow-node-selection__stroke",
    "flow-node-selection__sheen",
  ]) {
    for (const descriptor of descriptors) {
      svg.appendChild(buildNodeSelectionShape(descriptor, className));
    }
  }
  return overlay;
}

function nodeSelectionShapeDescriptors(kind) {
  if (kind === "decision_diamond") {
    return [{ tag: "polygon", attrs: { points: "50,4 96,50 50,96 4,50" } }];
  }
  if (kind === "input_data") {
    return [{ tag: "polygon", attrs: { points: "14,4 96,4 86,96 4,96" } }];
  }
  if (kind === "database") {
    return [
      { tag: "path", attrs: { d: "M10 20 L10 78 C10 90 90 90 90 78 L90 20" } },
      { tag: "ellipse", attrs: { cx: "50", cy: "20", rx: "40", ry: "12" } },
    ];
  }
  if (kind === "event") {
    return [{ tag: "rect", attrs: { x: "4", y: "4", width: "92", height: "92", rx: "28" } }];
  }
  if (kind === "decision_card") {
    return [{ tag: "rect", attrs: { x: "4", y: "4", width: "92", height: "92", rx: "22" } }];
  }
  if (kind === "figma_text") {
    return [{ tag: "rect", attrs: { x: "5", y: "5", width: "90", height: "90", rx: "10" } }];
  }
  return [{ tag: "rect", attrs: { x: "4", y: "4", width: "92", height: "92", rx: "10" } }];
}

function buildNodeSelectionShape(descriptor, className) {
  const shape = createSvgElement(descriptor.tag);
  shape.classList.add(className);
  for (const [key, value] of Object.entries(descriptor.attrs)) {
    shape.setAttribute(key, value);
  }
  return shape;
}

function attachViewportHandlers(viewport, state) {
  viewport.addEventListener("click", (event) => {
    if (isCanvasInteractiveTarget(event.target)) {
      return;
    }
    if (state.selectedId !== null) {
      selectId(state, null);
    }
  });

  viewport.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = viewport.getBoundingClientRect();
      const scaleFactor = event.deltaY < 0 ? 1.08 : 1 / 1.08;
      const cursor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      zoomAt(state, cursor, scaleFactor);
      state.userMovedView = true;
      scheduleViewStateSync(state);
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
    const ownerDocument = state.ownerDocument;
    const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
    if (ownerDocument.body) {
      ownerDocument.body.style.userSelect = "none";
    }
    const start = {
      x: event.clientX,
      y: event.clientY,
      viewX: state.view.x,
      viewY: state.view.y,
    };
    const move = (moveEvent) => {
      moveEvent.preventDefault();
      state.view.x = start.viewX + (moveEvent.clientX - start.x);
      state.view.y = start.viewY + (moveEvent.clientY - start.y);
      queueRender(state);
    };
    const stop = () => {
      state.isPanning = false;
      if (ownerDocument.body) {
        ownerDocument.body.style.userSelect = previousUserSelect;
      }
      ownerDocument.removeEventListener("pointermove", move);
      ownerDocument.removeEventListener("pointerup", stop);
      ownerDocument.removeEventListener("pointercancel", stop);
      syncViewState(state);
      queueRender(state);
    };
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
      ".flow-canvas-toolbar, .flow-canvas-minimap, .flow-node-shell, .flow-edge-label, .flow-edge-hit",
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
  state.draggingNodeId = nodeId;
  const origin = { ...nodePosition };
  const start = { x: event.clientX, y: event.clientY };
  const ownerDocument = state.ownerDocument;
  const previousUserSelect = ownerDocument.body ? ownerDocument.body.style.userSelect : "";
  const previousCursor = ownerDocument.body ? ownerDocument.body.style.cursor : "";
  if (ownerDocument.body) {
    ownerDocument.body.style.userSelect = "none";
    ownerDocument.body.style.cursor = "grabbing";
  }
  const move = (moveEvent) => {
    moveEvent.preventDefault();
    const nextPosition = {
      x: round(origin.x + (moveEvent.clientX - start.x) / state.view.scale),
      y: round(origin.y + (moveEvent.clientY - start.y) / state.view.scale),
    };
    if (
      nextPosition.x === state.positions[nodeId].x &&
      nextPosition.y === state.positions[nodeId].y
    ) {
      return;
    }
    state.positions[nodeId] = nextPosition;
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
    state.draggingNodeId = null;
    state.component.setStateValue("positions", copyPositionMap(state.positions));
    queueRender(state);
  };
  ownerDocument.addEventListener("pointermove", move, { passive: false });
  ownerDocument.addEventListener("pointerup", stop);
  ownerDocument.addEventListener("pointercancel", stop);
  queueRender(state);
}

function selectId(state, value) {
  if (state.selectedId === value) {
    return;
  }
  state.selectedId = value;
  state.component.setStateValue("selected_id", value);
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
  const scale = clamp(
    Math.min(availableWidth / bounds.width, availableHeight / bounds.height, 1.2),
    0.32,
    1.2,
  );
  state.view.scale = scale;
  state.view.x = round((rect.width - bounds.width * scale) / 2 - bounds.left * scale);
  state.view.y = round(FIT_VIEW_PADDING_TOP - bounds.top * scale);
}

function syncViewState(state) {
  const nextView = {
    x: round(state.view.x, 4),
    y: round(state.view.y, 4),
    scale: round(state.view.scale, 4),
  };
  if (
    sameViewState(state.lastReportedView, nextView) &&
    state.lastReportedUserMovedView === state.userMovedView
  ) {
    return;
  }
  state.component.setStateValue("view", nextView);
  state.component.setStateValue("user_moved_view", state.userMovedView);
  state.lastReportedView = nextView;
  state.lastReportedUserMovedView = state.userMovedView;
}

function scheduleViewStateSync(state, delay = VIEW_STATE_IDLE_SYNC_MS) {
  if (state.viewSyncTimer !== null) {
    clearTimeout(state.viewSyncTimer);
  }
  state.viewSyncTimer = setTimeout(() => {
    state.viewSyncTimer = null;
    syncViewState(state);
  }, delay);
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

function normalizePersistedViewState(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const x = finiteNumber(value.x);
  const y = finiteNumber(value.y);
  const scale = finiteNumber(value.scale);
  if (x === null || y === null || scale === null || scale <= 0) {
    return null;
  }
  return {
    view: { x, y, scale },
    userMovedView: Boolean(value.user_moved_view),
  };
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
      syncViewState(state);
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
    node.kind === "event" ? "26" : node.kind === "decision_card" ? "20" : "10",
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
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const firstLength = distance(previous, current);
    const secondLength = distance(current, next);
    if (!firstLength || !secondLength || isCollinear(previous, current, next)) {
      d += ` L ${current.x} ${current.y}`;
      continue;
    }
    const radius = Math.min(18, firstLength / 2, secondLength / 2);
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

function sameViewState(first, second) {
  if (!first || !second) {
    return false;
  }
  return (
    first.x === second.x &&
    first.y === second.y &&
    first.scale === second.scale
  );
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

function finiteNumber(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
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
