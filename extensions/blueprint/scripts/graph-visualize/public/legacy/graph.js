import { getEdgeColor, resetEdgeColorCache, TYPE_COLORS } from './config.js';

// ─── Graph State ───
export let graphData = null;
export function getGraphData() { return graphData; }
export function setGraphData(data) { graphData = data; }
export let validEdges = null;
export function setValidEdges(v) { validEdges = v; }
let canvas, ctx;
export let selectedNode = null;
export function setSelectedNode(n) { selectedNode = n; }
let connectedSet = null;
export let showLabels = true;
export function setShowLabels(v) { showLabels = v; }
export let tickCount = 0;
export function setTickCount(v) { tickCount = v; }
export let startTime = 0;
export let activeCategories = new Set();
export function setActiveCategories(v) { activeCategories = v; }
export let searchTerm = "";
export function setSearchTerm(v) { searchTerm = v; }
export let width, height;
export function setWidth(v) { width = v; }
export function setHeight(v) { height = v; }
let draggedNode = null;
export let isDragging = false;

// ─── Progressive Label Disclosure ───
const LABEL_MIN_ZOOM = 0.5;
const LABEL_MAX_ZOOM = 2.0;
const LABEL_NODE_RADIUS_THRESHOLD = 8;
const LABEL_CHAR_WIDTH = 0.62; // Inter average, world-space units
const LABEL_PAD_X = 4; // horizontal padding each side (world-space)
const LABEL_PAD_Y = 2; // vertical padding above node
const LABEL_HYSTERESIS = 0.2; // Zoom change needed before rebuilding label set

// HTML label elements (replaces canvas text rendering)
let _labelElements = new Map(); // nodeId -> HTMLDivElement
let _labelVisibleSet = null; // nodes that should show labels (progressive disclosure)
let _lastLabelZoom = 0; // track last zoom level to detect significant changes
let _labelFadeStartTime = null;

/**
 * Call once per render(), before drawing any labels.
 * Builds a priority-sorted list of candidates and greedily assigns labels
 * using a simple grid spatial index to avoid O(n²).
 */
function buildLabelSet() {
  // Check if zoom changed significantly (hysteresis to prevent flickering)
  const zoomDelta = Math.abs(zoom.k - _lastLabelZoom);
  if (zoomDelta < LABEL_HYSTERESIS && _labelVisibleSet !== null) {
    // Zoom hasn't changed enough, skip rebuilding
    return;
  }
  _lastLabelZoom = zoom.k;

  // Track previous visible labels to detect changes
  const prevVisible = _labelVisibleSet ? new Set(_labelVisibleSet) : null;
  _labelVisibleSet = new Set();
  if (!showLabels || zoom.k < LABEL_MIN_ZOOM || !graphData) {
    // If labels are hidden, clear the set
    if (prevVisible !== null && prevVisible.size > 0) {
      _labelFadeStartTime = performance.now();
    }
    return;
  }

  const candidates = [];
  for (const n of graphData.nodes) {
    if (!n.visible) continue;

    // Gate 1: at max zoom show everything
    if (zoom.k < LABEL_MAX_ZOOM) {
      // Gate 2: node must be large enough on screen
      const screenRadius = getNodeRadius(n) * zoom.k;
      if (screenRadius < LABEL_NODE_RADIUS_THRESHOLD) continue;
    }

    candidates.push(n);
  }

  console.log(
    "[LABELS] zoom:",
    zoom.k.toFixed(2),
    "candidates:",
    candidates.length,
    "showLabels:",
    showLabels,
    "labelSet size:",
    _labelVisibleSet.size,
  );

  // 2. Sort by priority: larger radius first (they win conflicts)
  candidates.sort((a, b) => getNodeRadius(b) - getNodeRadius(a));

  // 3. Greedy placement with a cell grid spatial index
  //    Cell size = typical label bbox half-height in world coords
  const fontSize = 13 / zoom.k;
  const cellSize = fontSize * 2;
  const occupied = new Map(); // "cx,cy" → true

  function cellKey(wx, wy) {
    return `${Math.floor(wx / cellSize)},${Math.floor(wy / cellSize)}`;
  }

  function labelBBox(n) {
    const r = getNodeRadius(n);
    const fs = (n.type === "spec" ? 14 : 13) / zoom.k;
    const text = n.term || n.label || n.id || "";
    const tw = text.length * fs * LABEL_CHAR_WIDTH + LABEL_PAD_X * 2;
    const th = fs;
    // Label baseline is at (n.y - r - 4/zoom.k), box extends upward by th
    return {
      x: n.x - tw / 2,
      y: n.y - getNodeRadius(n) - 4 / zoom.k - th,
      w: tw,
      h: th,
    };
  }
  function overlapsOccupied(bbox) {
    // Check all grid cells this bbox touches
    const x0 = Math.floor(bbox.x / cellSize);
    const x1 = Math.floor((bbox.x + bbox.w) / cellSize);
    const y0 = Math.floor(bbox.y / cellSize);
    const y1 = Math.floor((bbox.y + bbox.h) / cellSize);
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        if (occupied.has(`${cx},${cy}`)) return true;
      }
    }
    return false;
  }

  function markOccupied(bbox) {
    const x0 = Math.floor(bbox.x / cellSize);
    const x1 = Math.floor((bbox.x + bbox.w) / cellSize);
    const y0 = Math.floor(bbox.y / cellSize);
    const y1 = Math.floor((bbox.y + bbox.h) / cellSize);
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        occupied.set(`${cx},${cy}`, true);
      }
    }
  }

  // 4. Greedy: accept label if its bbox doesn't collide
  for (const n of candidates) {
    const bbox = labelBBox(n);
    if (!overlapsOccupied(bbox)) {
      _labelVisibleSet.add(n.id);
      markOccupied(bbox);
    }
  }

  // Reset fade timer only when the label set actually changes
  const setChanged =
    prevVisible === null ||
    _labelVisibleSet.size !== prevVisible.size ||
    [...prevVisible].some(id => !_labelVisibleSet.has(id));
  if (setChanged) {
    _labelFadeStartTime = performance.now();
  }
}

function shouldShowLabel(node) {
  if (hoverLabelNode && hoverLabelNode.id === node.id) return true;
  if (_labelVisibleSet === null || !_labelVisibleSet.has(node.id)) return false;
  return true;
}

/**
 * Update HTML label positions and visibility.
 * Called every frame to sync labels with node positions.
 */
export function updateHtmlLabels() {
  const container = document.getElementById("labels-container");
  if (!container) return;

  // Get container rect for coordinate conversion
  const containerRect = container.getBoundingClientRect();

  for (const node of graphData.nodes) {
    if (!node.visible) continue;

    // Calculate position relative to container (not viewport)
    // Node positions are in world coords, transform to container coords
    const labelX = zoom.x + node.x * zoom.k;
    const r = getNodeRadius(node);
    const labelY = zoom.y + node.y * zoom.k - r * zoom.k - 8;

    // Get or create label element
    let labelEl = _labelElements.get(node.id);
    if (!labelEl) {
      labelEl = document.createElement("div");
      labelEl.className = "graph-label";
      labelEl.textContent = node.term || node.label || node.id;
      container.appendChild(labelEl);
      _labelElements.set(node.id, labelEl);
    }

    // Position label relative to container
    labelEl.style.left = `${labelX}px`;
    labelEl.style.top = `${labelY}px`;
    labelEl.style.fontSize = `${node.type === "spec" ? 14 : 13}px`;

    // Show/hide based on progressive disclosure
    const isVisible = shouldShowLabel(node);
    if (isVisible) {
      labelEl.classList.add("visible");
      // Apply dimming for non-connected nodes when a node is selected
      const isConnected = !connectedSet || connectedSet.has(node.id);
      if (connectedSet && !isConnected) {
        labelEl.classList.add("dimmed");
      } else {
        labelEl.classList.remove("dimmed");
      }
    } else {
      labelEl.classList.remove("visible", "dimmed");
    }
  }

  // Remove elements for hidden nodes
  const visibleIds = new Set(graphData.nodes.filter(n => n.visible).map(n => n.id));
  for (const [id, el] of _labelElements) {
    if (!visibleIds.has(id)) {
      el.remove();
      _labelElements.delete(id);
    }
  }
}

// ─── Zoom/Pan State ───
export let zoom = { x: 0, y: 0, k: 1 };
export function setZoom(x, y, k) { if (x !== undefined) zoom.x = x; if (y !== undefined) zoom.y = y; if (k !== undefined) zoom.k = k; }
let isPanning = false;
let panStart = { x: 0, y: 0 };
let zoomStart = { x: 0, y: 0 };
let isMouseDown = false;
let sizeRange = {
  degree: [0, 1],
  blast: [0, 1],
  risk: [0, 1],
  centrality: [0, 1],
  type: [1, 3],
};

// ── Common scaling function ──
// Scales a value from [minVal, maxVal] to [minRadius, maxRadius] using power-1.5 scaling
// (steeper than linear: small values stay small, high values climb noticeably)
function scaleValue(value, minVal, maxVal, minRadius = 8, maxRadius = 40) {
  if (maxVal === minVal) {
    if (minVal === 0 && maxVal === 0) {
      // When range is [0,0] (all zeros), return max radius to highlight the node
      if (value === 0) return maxRadius;
    }
    return minRadius;
  }
  const normalized = Math.max(
    0,
    Math.min(1, (value - minVal) / (maxVal - minVal)),
  );
  return minRadius + Math.pow(normalized, 1.5) * (maxRadius - minRadius);
}

// ─── Size Metric Lookup ───
const SIZE_METRIC_KEYS = {
  degree: 'degree',
  blast: 'blastRadius',
  risk: 'risk',
  centrality: 'centrality',
  responsibility: 'responsibility',
  interfacePressure: 'interfacePressure',
};

// ─── Init graph ───
export function initGraph() {
  const container = document.getElementById("graph-container");
  width = container.clientWidth;
  height = container.clientHeight;

  canvas = document.getElementById("graph-canvas");
  console.log("Canvas element:", canvas);
  if (!canvas) {
    console.error("Canvas element not found!");
    return;
  }
  canvas.width = width * window.devicePixelRatio;
  canvas.height = height * window.devicePixelRatio;
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  ctx = canvas.getContext("2d");
  console.log("Canvas context:", ctx);
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  // ── Pre-resolve edges ──
  const nodeMap = new Map();
  // Initialize visible for all nodes
  for (const n of graphData.nodes) n.visible = true;
  for (const n of graphData.nodes) nodeMap.set(n.id, n);

  // ── Compute dynamic size ranges (initial only) ──
  const _initMetrics = [
    "blastRadius",
    "degree",
    "risk",
    "volume",
    "centrality",
  ];
  const rangeKeys = [
    "blast",
    "degree",
    "risk",
    "volume",
    "centrality",
  ];
  for (let i = 0; i < _initMetrics.length; i++) {
    const key = _initMetrics[i];
    const rkey = rangeKeys[i];
    const values = graphData.nodes.map((n) => n[key] || 0).filter((v) => v > 0);
    if (values.length > 0) sizeRange[rkey] = [0, Math.max(...values)];
  }
  validEdges = [];
  for (const e of graphData.edges) {
    e.visible = true; // Initialize edge visibility
    const srcId = typeof e.source === "object" ? e.source.id : e.source;
    const tgtId = typeof e.target === "object" ? e.target.id : e.target;
    const srcNode = nodeMap.get(srcId);
    const tgtNode = nodeMap.get(tgtId);
    if (!srcNode || !tgtNode) continue;
    e.source = srcNode;
    e.target = tgtNode;
    validEdges.push(e);
  }

  // ── Static layout — force-directed once ──
  graphData.nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / graphData.nodes.length;
    const radius = 200 + Math.random() * 200;
    n.x = width / 2 + radius * Math.cos(angle);
    n.y = height / 2 + radius * Math.sin(angle);
    n.vx = 0;
    n.vy = 0;
  });

  const linkForce = d3.forceLink(validEdges).distance(120).strength(0.05);
  const chargeForce = d3.forceManyBody().strength(-150);
  const centerForce = d3.forceCenter(width / 2, height / 2).strength(0.02);
  const collisionForce = d3.forceCollide().radius(25);

  const simulation = d3
    .forceSimulation(graphData.nodes)
    .force("link", linkForce)
    .force("charge", chargeForce)
    .force("center", centerForce)
    .force("collision", collisionForce)
    .alpha(0.3)
    .alphaDecay(0.1)
    .velocityDecay(0.4);

  for (let i = 0; i < 200; i++) simulation.tick();
  simulation.stop();

  // ── Initial render ──
  console.log("Initial render:", graphData.nodes.length, "nodes");
  console.log("First node:", graphData.nodes[0]);
  render();

  // ── Event listeners ──
  canvas.addEventListener("mousedown", onMouseDown);
  canvas.addEventListener("mousemove", onMouseMove);
  canvas.addEventListener("mouseup", onMouseUp);
  canvas.addEventListener("wheel", onWheel, { passive: false });
  canvas.addEventListener("click", onClick);

  // ── Render ──
  render();

  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.add("hidden");
}

// ─── Render ───
let _lastVisibleCount = -1;

export function recalcSizeRange() {
  // Get currently visible nodes (sidebar filter)
  const visibleNodes = graphData.nodes.filter((n) => n.visible !== false);
  if (visibleNodes.length === 0) return;

  // Store the full visible set range
  const fullRanges = {};
  const _metrics = [
    { nodeKey: "blastRadius", rangeKey: "blast" },
    { nodeKey: "degree", rangeKey: "degree" },
    { nodeKey: "risk", rangeKey: "risk" },
    { nodeKey: "centrality", rangeKey: "centrality" },
  ];

  for (const m of _metrics) {
    const values = visibleNodes
      .map((n) => n[m.nodeKey] || 0)
      .filter((v) => v > 0);
    if (values.length > 0) {
      fullRanges[m.rangeKey] = [0, Math.max(...values)];
    }
  }

  // If a node is selected, also compute range for connected neighborhood
  if (selectedNode && connectedSet) {
    const connectedNodes = visibleNodes.filter((n) => connectedSet.has(n.id));
    if (connectedNodes.length > 0) {
      for (const m of _metrics) {
        const values = connectedNodes.map((n) => n[m.nodeKey] || 0);
        const maxVal = Math.max(...values);
        // When all connected nodes have 0 for a metric, use [0,0] so scaleValue hits the
        // minVal===maxVal===0 path and returns maxRadius (highlighting isolated/zero-value nodes)
        sizeRange[m.rangeKey] = maxVal > 0 ? [0, maxVal] : [0, 0];
      }
      sizeRange._connected = true;
      sizeRange._fullRanges = fullRanges;
      console.log(
        "[RECALC] connected set:",
        connectedSet.size,
        "nodes | ranges:",
        JSON.stringify({
          degree: sizeRange.degree,
          blast: sizeRange.blast,
        }),
      );
    } else {
      // Connected node is selected but all its neighbors are filtered out.
      // Fall back to full visible-set ranges instead of keeping stale connected-set values.
      sizeRange._connected = false;
      for (const m of _metrics) {
        if (fullRanges[m.rangeKey]) {
          sizeRange[m.rangeKey] = fullRanges[m.rangeKey];
        }
      }
      sizeRange._fullRanges = fullRanges;
    }
  } else {
    // Restore full ranges
    sizeRange._connected = false;
    for (const m of _metrics) {
      if (fullRanges[m.rangeKey]) {
        sizeRange[m.rangeKey] = fullRanges[m.rangeKey];
      }
    }
  }

  // Only log when visible count changes
  if (visibleNodes.length !== _lastVisibleCount) {
    const maxDeg = Math.max(...visibleNodes.map((n) => n.degree || 0));
    console.log(
      "[SIZE] visible:",
      _lastVisibleCount,
      "->",
      visibleNodes.length,
      "| maxDeg:",
      maxDeg,
      "connected:",
      sizeRange._connected,
    );
    _lastVisibleCount = visibleNodes.length;
  }
}

function render() {
  if (!ctx) {
    console.error("Canvas context not initialized!");
    return;
  }

  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(zoom.x, zoom.y);
  ctx.scale(zoom.k, zoom.k);

  // Grid background is now handled by CSS (background-image on #graph-container)

  // Compute connected set if a node is selected
  connectedSet = null;
  let connectedEdges = null;
  if (selectedNode) {
    connectedSet = new Set([selectedNode.id]);
    connectedEdges = new Set();
    for (const e of validEdges) {
      if (e.source.id === selectedNode.id || e.target.id === selectedNode.id) {
        connectedSet.add(e.source.id);
        connectedSet.add(e.target.id);
        connectedEdges.add(e);
      }
    }
  }

  // Dynamically recalculate size ranges AFTER connected set is built
  recalcSizeRange();

  // Build label placement set (progressive disclosure)
  buildLabelSet();

  // Edges (drawn first, under nodes)
  ctx.globalAlpha = 0.3;
  const edgeColor = getEdgeColor();
  for (const e of validEdges) {
    if (!e.visible) continue;
    ctx.beginPath();
    ctx.moveTo(e.source.x, e.source.y);
    ctx.lineTo(e.target.x, e.target.y);
    ctx.strokeStyle = edgeColor;
    ctx.lineWidth = 0.6 / zoom.k;
    // Dim edges if not connected to selected node
    if (connectedEdges && !connectedEdges.has(e)) {
      ctx.globalAlpha = currentDim * 0.3;
    } else {
      ctx.globalAlpha = currentDim * 0.5 + (1 - currentDim) * 0.3;
    }
    ctx.stroke();
  }

  // Reset alpha for nodes
  ctx.globalAlpha = 1;

  // Nodes
  for (const n of graphData.nodes) {
    if (!n.visible) continue;
    const r = getNodeAnimatedRadius(n);
    const color = getNodeColor(n);
    const isSelected = selectedNode && selectedNode.id === n.id;
    const isHovered = hoveredNode && hoveredNode.id === n.id;
    const isConnected = !connectedSet || connectedSet.has(n.id);

    // Dim non-connected nodes when one is selected
    if (connectedSet && !isConnected) {
      ctx.globalAlpha = currentDim;
    } else {
      ctx.globalAlpha = 1;
    }

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // Stroke
    ctx.strokeStyle = isSelected
      ? "#fff"
      : d3.color(color).darker(0.8).formatHex();
    ctx.lineWidth = (isSelected ? 2 : 1) / zoom.k;
    ctx.stroke();

    // Hover highlight
    if (isHovered && !isSelected) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2 / zoom.k;
      ctx.stroke();
    }
  }

  // Position HTML labels (replaces canvas text rendering)
  updateHtmlLabels();

  // Reset alpha
  ctx.globalAlpha = 1;

  ctx.restore();
  ctx.globalAlpha = 1;
}

export function renderGraph() {
  render();
}

// ─── Scale Animation Engine ───
// One-shot animation: smoothly transitions node radii over ~350ms when sizes change.
// Call after selection changes, metric switches, or filter changes.
// Internally computes connectedSet and recalculates size ranges so targets are correct.
export function startScaleAnimation() {
  // Cancel any previous animation
  if (scaleAnimFrame) cancelAnimationFrame(scaleAnimFrame);

  // Capture the currently displayed radius for each node BEFORE any state changes.
  // This is the "from" value for the animation. If a previous animation is in-flight,
  // its _animRadius holds the current interpolated value. Otherwise, getNodeRadius()
  // returns the last rendered size.
  const prevRadii = new Map();
  for (const n of graphData.nodes) {
    if (!n.visible) continue;
    prevRadii.set(n.id, n._animRadius ?? getNodeRadius(n));
  }

  // Compute connected set (needed for correct target radii)
  connectedSet = null;
  if (selectedNode) {
    connectedSet = new Set([selectedNode.id]);
    for (const e of validEdges) {
      if (e.source.id === selectedNode.id || e.target.id === selectedNode.id) {
        connectedSet.add(e.source.id);
        connectedSet.add(e.target.id);
      }
    }
  }

  // Recalculate size ranges so getNodeRadius() returns correct targets
  recalcSizeRange();

  // Build label placement set (progressive disclosure)
  buildLabelSet();

  // Capture target radii and start the animation
  scaleAnimStartRadii = new Map();
  scaleAnimTargets = new Map();
  scaleAnimStartTime = performance.now();

  for (const n of graphData.nodes) {
    if (!n.visible) continue;
    const startRadius = prevRadii.get(n.id);
    const targetRadius = getNodeRadius(n);
    scaleAnimStartRadii.set(n.id, startRadius);
    scaleAnimTargets.set(n.id, targetRadius);
    n._animRadius = startRadius;
  }

  scaleAnimFrame = requestAnimationFrame(scaleAnimStep);
}

function scaleAnimStep(now) {
  const elapsed = now - scaleAnimStartTime;
  const progress = Math.min(elapsed / SCALE_ANIM_DURATION, 1);

  // Ease out cubic (same curve as dim animation for consistency)
  const ease = 1 - Math.pow(1 - progress, 3);

  for (const n of graphData.nodes) {
    if (!n.visible) continue;
    const start = scaleAnimStartRadii.get(n.id) ?? 0;
    const target = scaleAnimTargets.get(n.id) ?? 0;
    n._animRadius = start + (target - start) * ease;
  }

  render();

  if (progress < 1) {
    scaleAnimFrame = requestAnimationFrame(scaleAnimStep);
  } else {
    // Animation complete — flush any remaining animated radii to final values
    for (const n of graphData.nodes) {
      if (!n.visible) continue;
      n._animRadius = undefined; // will use getNodeRadius() next time
    }
    scaleAnimFrame = null;
  }
}

// Returns the animated radius for a node (interpolated toward target)
function getNodeAnimatedRadius(n) {
  if (n._animRadius !== undefined) {
    return n._animRadius;
  }
  return getNodeRadius(n);
}

// ─── Mouse Events ───
function getMousePos(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - zoom.x) / zoom.k,
    y: (event.clientY - rect.top - zoom.y) / zoom.k,
  };
}

function findNodeAt(pos) {
  // Search in reverse (top-most first)
  for (let i = graphData.nodes.length - 1; i >= 0; i--) {
    const n = graphData.nodes[i];
    if (!n.visible) continue;
    const dx = pos.x - n.x;
    const dy = pos.y - n.y;
    const r = getNodeRadius(n) + 5; // Hit area
    if (dx * dx + dy * dy < r * r) return n;
  }
  return null;
}

function onMouseDown(event) {
  if (event.button === 0) {
    isMouseDown = true;
    const pos = getMousePos(event);
    const node = findNodeAt(pos);
    if (node) {
      draggedNode = node;
      panStart = { x: event.clientX, y: event.clientY };
      isDragging = false;
    } else {
      isPanning = false; // Don't start pan yet, wait to see if mouse moves
      panStart = { x: event.clientX, y: event.clientY };
      zoomStart = { x: zoom.x, y: zoom.y };
    }
  }
}

function onMouseMove(event) {
  const pos = getMousePos(event);

  if (draggedNode) {
    const dx = event.clientX - panStart.x;
    const dy = event.clientY - panStart.y;
    if (dx * dx + dy * dy < 100) return; // Click threshold

    isDragging = true;
    draggedNode.x = pos.x;
    draggedNode.y = pos.y;
    draggedNode.vx = 0;
    draggedNode.vy = 0;
    // Pin node so simulation ticks don't override drag position
    if (simulation) {
      draggedNode.fx = pos.x;
      draggedNode.fy = pos.y;
    }
    render();
    return;
  }

  // Start panning if mouse moved significantly (only when mouse is held down)
  if (!draggedNode && !isPanning && isMouseDown) {
    const dx = event.clientX - panStart.x;
    const dy = event.clientY - panStart.y;
    if (dx * dx + dy * dy > 25) {
      // 5px threshold
      isPanning = true;
    }
  }

  if (isPanning) {
    zoom.x = zoomStart.x + (event.clientX - panStart.x);
    zoom.y = zoomStart.y + (event.clientY - panStart.y);
    render();
    return;
  }

  // Hover detection
  const node = findNodeAt(pos);
  if (node !== hoveredNode) {
    // Clear any pending label timer on hover change
    if (hoverLabelTimeout) {
      clearTimeout(hoverLabelTimeout);
      hoverLabelTimeout = null;
    }
    // Hide previously forced label
    if (hoverLabelNode && hoverLabelNode !== node) {
      hoverLabelNode = null;
      render();
    }
    hoveredNode = node;
    canvas.style.cursor = node ? "pointer" : "grab";
    // Start timer to show label after holding hover
    if (node) {
      hoverLabelTimeout = setTimeout(() => {
        hoverLabelTimeout = null;
        hoverLabelNode = node;
        render();
      }, HOVER_LABEL_DELAY);
    }
    render();
  }
}

function onMouseUp(event) {
  const wasPanning = isPanning;
  if (isPanning) {
    isPanning = false;
  }
  isMouseDown = false;
  if (draggedNode && !isDragging) {
    // It was a click on a node
    const pos = getMousePos(event);
    const node = findNodeAt(pos);
    if (node) selectNode(event, node);
    else deselectNode();
    draggedNode = null;
    isDragging = false;
  } else if (draggedNode && isDragging) {
    isDragging = false;
    if (simulation) {
      // Unpin node so simulation takes over
      draggedNode.fx = null;
      draggedNode.fy = null;
      draggedNode = null;
    } else {
      // Pin and run settlement for non-simulation mode
      draggedNode.fx = draggedNode.x;
      draggedNode.fy = draggedNode.y;
      const nodeRef = draggedNode;
      draggedNode = null;
      settleAfterDrag(nodeRef);
    }
  } else if (!draggedNode && !wasPanning) {
    // Click on empty space - deselect
    deselectNode();
  }
  // If wasPanning, preserve selection (don't deselect)
}

function onClick(event) {
  // Handled in onMouseUp
}

function onWheel(event) {
  event.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  const delta = event.deltaY > 0 ? 0.9 : 1.1;
  const newK = Math.max(0.05, Math.min(8, zoom.k * delta));

  // Zoom toward mouse position
  zoom.x = mouseX - (mouseX - zoom.x) * (newK / zoom.k);
  zoom.y = mouseY - (mouseY - zoom.y) * (newK / zoom.k);
  zoom.k = newK;

  render();
}

// ─── Helper Functions ───
// Computes the *target* radius for a node (the final size it should animate toward).
// This does NOT include animation interpolation — use getNodeAnimatedRadius() for rendering.
function getNodeRadius(d) {
  if (d.type === "spec" || d.category === "spec") return 15;

  // Determine which range to use: connected set or full visible set
  let useConnected =
    sizeRange._connected && connectedSet && connectedSet.has(d.id);
  let rangeKey;

  if (sizeMetric === "type") {
    const typeSizes = {
      CON: 6, FN: 5, REQ: 4.5, NFR: 4.5, US: 4.5,
      SC: 4, Entity: 4, GL: 3.5, TST: 2.5, Enum: 2.5,
      API: 4, EP: 5, TASK: 3, ISSUE: 4, DG: 3, UJ: 4,
      UXAC: 4, IS: 4, spec: 5,
    };
    const value = typeSizes[d.type] || 1;
    return scaleValue(value, 1, 6, 8, 40);
  }

  // Use sizeMetric itself as the range key ("blast", "degree", etc.)
  // SIZE_METRIC_KEYS maps to the NODE property ("blastRadius") — not the range storage key.
  rangeKey = sizeMetric ?? "degree";

  let minVal, maxVal;
  if (useConnected) {
    minVal = sizeRange[rangeKey]?.[0] ?? 0;
    maxVal = sizeRange[rangeKey]?.[1] ?? 0;
  } else {
    const fr = sizeRange._fullRanges;
    if (fr && fr[rangeKey]) {
      minVal = fr[rangeKey][0];
      maxVal = fr[rangeKey][1];
    } else {
      minVal = sizeRange[rangeKey]?.[0] ?? 0;
      maxVal = sizeRange[rangeKey]?.[1] ?? 0;
    }
  }

  // Debug: log for selected node with 0 connections
  if (
    selectedNode &&
    selectedNode.id === d.id &&
    connectedSet &&
    connectedSet.size <= 1
  ) {
    console.log(
      "[RADIUS]",
      d.id,
      "| metric:",
      sizeMetric,
      "rangeKey:",
      rangeKey,
      "useConnected:",
      useConnected,
      "sizeRange[" + rangeKey + "]:",
      sizeRange[rangeKey],
      "range:",
      `[${minVal},${maxVal}]`,
      "_connected:",
      sizeRange._connected,
    );
  }

  const nodeKey = SIZE_METRIC_KEYS[sizeMetric] ?? "degree";
  let value = d[nodeKey] ?? 0;

  const radius = scaleValue(value, minVal, maxVal, 8, 40);
  if (
    selectedNode &&
    selectedNode.id === d.id &&
    connectedSet &&
    connectedSet.size <= 1
  ) {
    console.log(
      "[RADIUS-RESULT]",
      d.id,
      "| value:",
      value,
      "radius:",
      radius.toFixed(1),
    );
  }
  return radius;
}

function getNodeColor(d) {
  if (d.type && TYPE_COLORS[d.type]) return TYPE_COLORS[d.type];
  return "#94a3b8";
}

let hoveredNode = null;
let hoverLabelNode = null; // Node whose label is forced visible by hover
let hoverLabelTimeout = null; // Timer for delayed label show
const HOVER_LABEL_DELAY = 300; // ms to hold hover before label appears
let isSimulating = false;
let simulation = null;
export let sizeMetric = "degree"; // Default sizing metric
export function setSizeMetric(v) { sizeMetric = v; }
let dimAnimation = null; // Animation frame for dimming
let currentDim = 1; // Current dim opacity (1 = full, 0.15 = dimmed)

// Callbacks set by ui.js to avoid circular imports
let _onSelectNode = null;
let _onDeselectNode = null;
export function setNodeSelectCallbacks(onSelect, onDeselect) {
  _onSelectNode = onSelect;
  _onDeselectNode = onDeselect;
}

// ─── Node selection ───
export function selectNode(event, node) {
  event.stopPropagation();
  if (selectedNode && selectedNode.id === node.id) {
    deselectNode();
    return;
  }
  selectedNode = node;
  animateDim(0.15);
  startScaleAnimation();
  if (_onSelectNode) _onSelectNode(event, node);
}

export function deselectNode() {
  selectedNode = null;
  animateDim(1);
  startScaleAnimation();
  if (_onDeselectNode) _onDeselectNode();
}

// ─── Node Scale Animation ───
let scaleAnimFrame = null; // requestAnimationFrame id for scale animation loop
let scaleAnimStartTime = null;
let scaleAnimTargets = null; // Map<nodeId, targetRadius>
let scaleAnimStartRadii = null; // Map<nodeId, startRadius>
const SCALE_ANIM_DURATION = 350; // ms — how long a scale transition takes

// ─── Simulation Control ───

/**
 * Lightweight post-drag settlement.
 * Pins the dragged node so it stays put, runs a short heavily-damped
 * simulation so neighbors relax around the new position, then unpins.
 *
 * Parameters tuned for stability + low cost:
 *   No center force — only local relaxation, no global drift
 *   alpha 0.15 + decay 0.12 → energy localized to dragged node's neighborhood
 *   velocityDecay 0.7 → strong damping, no jitter/oscillation
 *   tick cap 60        → hard upper bound regardless of alpha
 */
export function settleAfterDrag(pinnedNode) {
  if (simulation) simulation.stop();

  const visibleNodes = graphData.nodes.filter((n) => n.visible);
  const visibleEdges = validEdges.filter((e) => e.visible);

  // No center force — we only want local relaxation, not global drift.
  simulation = d3
    .forceSimulation(visibleNodes)
    .force(
      "link",
      d3.forceLink(visibleEdges).distance(120).strength(0.08),
    )
    .force(
      "charge",
      d3.forceManyBody().strength(-350).distanceMax(300),
    )
    .force(
      "collision",
      d3.forceCollide().radius(25).strength(0.7),
    )
    .alpha(0.15)
    .alphaDecay(0.12)
    .velocityDecay(0.7)
    .on("tick", () => {
      render();
    })
    .on("end", () => {
      pinnedNode.fx = null;
      pinnedNode.fy = null;
      simulation = null;
    });

  // Hard tick cap: stop after 60 ticks even if alpha hasn't cooled
  const maxTicks = 60;
  let ticks = 0;
  const originalTick = simulation.tick.bind(simulation);
  simulation.tick = function () {
    if (++ticks >= maxTicks) {
      pinnedNode.fx = null;
      pinnedNode.fy = null;
      simulation.stop();
      simulation = null;
      render();
      return false;
    }
    return originalTick();
  };
}

/**
 * Start continuous simulation.
 * Runs the force simulation indefinitely until stopSimulation() is called.
 */
export function startSimulation() {
  if (simulation) simulation.stop();

  simulation = d3
    .forceSimulation(graphData.nodes.filter((n) => n.visible))
    .force(
      "link",
      d3
        .forceLink(validEdges.filter((e) => e.visible))
        .distance(120)
        .strength(0.05),
    )
    .force("charge", d3.forceManyBody().strength(-150))
    .force("center", d3.forceCenter(width / 2, height / 2).strength(0.02))
    .force("collision", d3.forceCollide().radius(25))
    .alpha(0.3)
    .alphaDecay(0)
    .alphaMin(0)
    .on("tick", () => {
      render();
    });
}

/**
 * Stop the continuous simulation.
 */
export function stopSimulation() {
  if (simulation) {
    simulation.stop();
    simulation = null;
  }
}

// ─── Theme Update ───
export function updateThemeColors() {
  resetEdgeColorCache();
  render();
}

// ─── Dim Animation ───
export function animateDim(target) {
  if (dimAnimation) cancelAnimationFrame(dimAnimation);
  const start = performance.now();
  const from = currentDim;
  const duration = 400; // ms

  function step(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const ease = 1 - Math.pow(1 - progress, 3);
    currentDim = from + (target - from) * ease;
    render();
    if (progress < 1) {
      dimAnimation = requestAnimationFrame(step);
    }
  }
  dimAnimation = requestAnimationFrame(step);
}
