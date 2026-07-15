const TOOLBAR_BUTTONS = [
  { id: "zoom-in", label: "+" },
  { id: "zoom-out", label: "-" },
  { id: "reset-view", label: "Fit" },
];

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
    view: { x: 0, y: 0, scale: 1 },
    userMovedView: false,
    positions: {},
    selectedId: null,
    isPanning: false,
    draggingNodeId: null,
    frameRequested: false,
    lastRevision: null,
    resizeObserver: null,
    ownerDocument,
  };

  state.resizeObserver = new ResizeObserver(() => {
    if (!state.userMovedView) {
      fitView(state);
    }
    queueRender(state);
  });
  state.resizeObserver.observe(root);
  root.__flowCanvasState = state;
  return state;
}

function normalizePayload(data) {
  if (!data || typeof data !== "object") {
    return {
      nodes: [],
      edges: [],
      canvas: { width: 1200, height: 720 },
      bounds: { left: 0, top: 0, right: 1200, bottom: 720, width: 1200, height: 720 },
      selected_id: null,
      position_edit_enabled: false,
      revision: 0,
    };
  }
  return data;
}

function syncStateFromPayload(state) {
  const payload = state.payload;
  const graphChanged = state.lastRevision !== payload.revision;
  if (graphChanged || state.draggingNodeId === null) {
    state.positions = nodePositionMap(payload.nodes);
  }
  state.selectedId = payload.selected_id ?? state.selectedId ?? null;
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
  const root = state.root;
  root.innerHTML = "";

  if (!payload.nodes.length) {
    const empty = createElement("div", "flow-empty-state", root);
    empty.textContent = "На схеме пока нет элементов.";
    return;
  }

  const toolbar = createElement("div", "flow-canvas-toolbar", root);
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
  }

  if (payload.position_edit_enabled) {
    const hint = createElement("div", "flow-canvas-hint", root);
    hint.innerHTML =
      "<strong>Режим layout</strong><span>Тяните карточку за сам блок. Пустой фон двигает сцену.</span>";
  }

  const viewport = createElement(
    "div",
    state.isPanning ? "flow-canvas-viewport is-panning" : "flow-canvas-viewport",
    root,
  );
  const stage = createElement("div", "flow-canvas-stage", viewport);
  stage.style.width = `${payload.canvas.width}px`;
  stage.style.height = `${payload.canvas.height}px`;
  stage.style.transform = `translate(${state.view.x}px, ${state.view.y}px) scale(${state.view.scale})`;

  const svg = createSvgElement("svg");
  svg.classList.add("flow-canvas-edges");
  svg.setAttribute("viewBox", `0 0 ${payload.canvas.width} ${payload.canvas.height}`);
  svg.setAttribute("width", String(payload.canvas.width));
  svg.setAttribute("height", String(payload.canvas.height));
  stage.appendChild(svg);

  const defs = createSvgElement("defs");
  svg.appendChild(defs);
  for (const edge of payload.edges) {
    defs.appendChild(buildMarker(edge.color, edge.id));
  }

  const labelsLayer = createElement("div", "flow-canvas-labels", stage);
  const nodesLayer = createElement("div", "flow-canvas-nodes", stage);

  attachViewportHandlers(viewport, state);
  renderEdges(svg, labelsLayer, state);
  renderNodes(nodesLayer, state);
  renderMinimap(root, state);
}

function renderEdges(svg, labelsLayer, state) {
  for (const edge of state.payload.edges) {
    const edgeSelected = state.selectedId === edge.id;
    const group = createSvgElement("g");
    svg.appendChild(group);

    const pathData = roundedPath(edge.points);
    const visiblePath = createSvgElement("path");
    visiblePath.classList.add("flow-edge-path");
    if (edgeSelected) {
      visiblePath.classList.add("is-selected");
    }
    visiblePath.setAttribute("d", pathData);
    visiblePath.setAttribute("stroke", edge.style.stroke || edge.color);
    visiblePath.setAttribute("stroke-width", String(edgeSelected ? 3.3 : edge.style.strokeWidth || 2.4));
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

    if (edge.label) {
      const label = createElement("button", "flow-edge-label", labelsLayer);
      label.type = "button";
      label.textContent = edge.label.text;
      label.style.left = `${edge.label.position.x}px`;
      label.style.top = `${edge.label.position.y}px`;
      label.style.width = `${edge.label.width}px`;
      label.style.height = `${edge.label.height}px`;
      label.style.border = `1px solid ${edge.label.color}`;
      label.style.color = edge.label.color;
      label.style.opacity = String(edge.label.active ? 1 : 0.24);
      label.style.transform = edgeSelected ? "translateY(-1px)" : "none";
      label.addEventListener("click", (event) => {
        event.stopPropagation();
        selectId(state, edge.id);
      });
    }
  }
}

function renderNodes(layer, state) {
  const payload = state.payload;
  for (const node of payload.nodes) {
    const nodeSelected = state.selectedId === node.id;
    const position = state.positions[node.id] || node.position;
    const shell = createElement("div", "flow-node-shell", layer);
    shell.style.left = `${position.x}px`;
    shell.style.top = `${position.y}px`;
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
    if (node.draggable && payload.position_edit_enabled) {
      card.classList.add("is-draggable");
    }
    if (state.draggingNodeId === node.id) {
      card.classList.add("is-dragging");
    }
    applyStyles(card, node.style);
    if (nodeSelected) {
      card.style.boxShadow =
        "0 0 0 4px rgba(20, 184, 166, 0.24), 0 18px 36px rgba(15, 23, 42, 0.18)";
      card.style.transform = "translateY(-1px)";
    }
    card.dataset.nodeId = node.id;
    card.addEventListener("click", (event) => {
      event.stopPropagation();
      selectId(state, node.id);
    });
    if (node.draggable && payload.position_edit_enabled) {
      card.addEventListener("pointerdown", (event) => startNodeDrag(event, state, node.id));
    }

    const text = createElement("span", "flow-node-text", card);
    text.textContent = node.text;

    if (node.well_tokens.length) {
      const wells = createElement("div", "flow-node-wells", shell);
      for (const tokenPayload of node.well_tokens) {
        const tokenSelected = state.selectedId === tokenPayload.id;
        const token = createElement("button", "flow-token", wells);
        token.type = "button";
        token.textContent = tokenPayload.text;
        token.title = tokenPayload.title;
        applyStyles(token, tokenPayload.style);
        if (tokenSelected) {
          token.style.boxShadow = "0 0 0 3px rgba(20, 184, 166, 0.24), 0 10px 24px rgba(15, 23, 42, 0.16)";
          token.style.transform = "translateY(-1px)";
        }
        token.addEventListener("click", (event) => {
          event.stopPropagation();
          if (tokenPayload.id.startsWith("well-extra::")) {
            selectId(state, tokenPayload.id);
            return;
          }
          selectId(state, tokenPayload.id);
        });
      }
    }
  }
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
    const dx = (moveEvent.clientX - start.x) / state.view.scale;
    const dy = (moveEvent.clientY - start.y) / state.view.scale;
    state.positions[nodeId] = {
      x: round(origin.x + dx),
      y: round(origin.y + dy),
    };
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
}

function selectId(state, value) {
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

  const padding = 64;
  const availableWidth = Math.max(120, rect.width - padding * 2);
  const availableHeight = Math.max(120, rect.height - padding * 2);
  const scale = clamp(
    Math.min(availableWidth / bounds.width, availableHeight / bounds.height, 1.2),
    0.32,
    1.2,
  );
  state.view.scale = scale;
  state.view.x = round((rect.width - bounds.width * scale) / 2 - bounds.left * scale);
  state.view.y = round((rect.height - bounds.height * scale) / 2 - bounds.top * scale);
}

function renderMinimap(root, state) {
  const bounds = minimapBounds(state.payload.bounds);
  const minimap = createElement("div", "flow-canvas-minimap", root);
  minimap.setAttribute("role", "img");
  minimap.setAttribute("aria-label", "Миникарта схемы");

  const svg = createSvgElement("svg");
  svg.classList.add("flow-canvas-minimap__svg");
  svg.setAttribute("viewBox", `${bounds.left} ${bounds.top} ${bounds.width} ${bounds.height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  minimap.appendChild(svg);

  const backdrop = createSvgElement("rect");
  backdrop.classList.add("flow-canvas-minimap__backdrop");
  backdrop.setAttribute("x", String(bounds.left));
  backdrop.setAttribute("y", String(bounds.top));
  backdrop.setAttribute("width", String(bounds.width));
  backdrop.setAttribute("height", String(bounds.height));
  backdrop.setAttribute("rx", "20");
  svg.appendChild(backdrop);

  for (const edge of state.payload.edges) {
    const path = createSvgElement("path");
    path.classList.add("flow-canvas-minimap__edge");
    path.setAttribute("d", roundedPath(edge.points));
    svg.appendChild(path);
  }

  for (const node of state.payload.nodes) {
    const position = state.positions[node.id] || node.position;
    svg.appendChild(buildMinimapNode(node, position, state.selectedId === node.id));
  }

  const viewportRect = currentViewportWorldRect(state);
  const frame = createSvgElement("rect");
  frame.classList.add("flow-canvas-minimap__viewport");
  frame.setAttribute("x", String(round(viewportRect.x)));
  frame.setAttribute("y", String(round(viewportRect.y)));
  frame.setAttribute("width", String(round(viewportRect.width)));
  frame.setAttribute("height", String(round(viewportRect.height)));
  frame.setAttribute("rx", "12");
  svg.appendChild(frame);

  attachMinimapHandlers(minimap, svg, state, bounds);
}

function buildMinimapNode(node, position, selected) {
  const shape = minimapNodeShape(node, position);
  shape.classList.add("flow-canvas-minimap__node", `is-${node.kind.replaceAll("_", "-")}`);
  if (selected) {
    shape.classList.add("is-selected");
  }
  return shape;
}

function minimapNodeShape(node, position) {
  const x = round(position.x);
  const y = round(position.y);
  const width = round(node.size.w);
  const height = round(node.size.h);

  if (node.kind === "decision_diamond") {
    const shape = createSvgElement("polygon");
    shape.setAttribute(
      "points",
      `${x + width / 2},${y} ${x + width},${y + height / 2} ${x + width / 2},${y + height} ${x},${y + height / 2}`,
    );
    return shape;
  }

  const shape = createSvgElement("rect");
  shape.setAttribute("x", String(x));
  shape.setAttribute("y", String(y));
  shape.setAttribute("width", String(width));
  shape.setAttribute("height", String(height));
  shape.setAttribute("rx", node.kind === "event" ? "26" : node.kind === "decision_card" ? "20" : "10");
  return shape;
}

function attachMinimapHandlers(minimap, svg, state, bounds) {
  minimap.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    clearSelection(state.ownerDocument);

    const updateView = (pointerEvent) => {
      const point = minimapPointToWorld(svg, pointerEvent, bounds);
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
  const rect = svg.getBoundingClientRect();
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
