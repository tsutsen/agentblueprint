// ─── Graph State ───
let graphData = null;
let validEdges = null;
let canvas, ctx;
let selectedNode = null;
let showLabels = false;
let showSpecs = true;
let tickCount = 0;
let startTime = 0;
let activeCategories = new Set();
let searchTerm = '';
let width, height;
let draggedNode = null;
let isDragging = false;

// ─── Zoom/Pan State ───
let zoom = { x: 0, y: 0, k: 1 };
let isPanning = false;
let panStart = { x: 0, y: 0 };

// ─── Init graph ───
function initGraph() {
  const container = document.getElementById('graph-container');
  width = container.clientWidth;
  height = container.clientHeight;

  canvas = document.getElementById('graph-canvas');
  console.log('Canvas element:', canvas);
  if (!canvas) {
    console.error('Canvas element not found!');
    return;
  }
  canvas.width = width * window.devicePixelRatio;
  canvas.height = height * window.devicePixelRatio;
  canvas.style.width = width + 'px';
  canvas.style.height = height + 'px';
  ctx = canvas.getContext('2d');
  console.log('Canvas context:', ctx);
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  // ── Pre-resolve edges ──
  const nodeMap = new Map();
  // Initialize visible for all nodes
  for (const n of graphData.nodes) n.visible = true;
  for (const n of graphData.nodes) nodeMap.set(n.id, n);
  validEdges = [];
  for (const e of graphData.edges) {
    e.visible = true; // Initialize edge visibility
    const srcId = typeof e.source === 'object' ? e.source.id : e.source;
    const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
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

  const simulation = d3.forceSimulation(graphData.nodes)
    .force('link', linkForce)
    .force('charge', chargeForce)
    .force('center', centerForce)
    .force('collision', collisionForce)
    .alpha(0.3)
    .alphaDecay(0.1)
    .velocityDecay(0.4);

  for (let i = 0; i < 200; i++) simulation.tick();
  simulation.stop();

  // ── Initial render ──
  console.log('Initial render:', graphData.nodes.length, 'nodes');
  console.log('First node:', graphData.nodes[0]);
  render();

  // ── Event listeners ──
  canvas.addEventListener('mousedown', onMouseDown);
  canvas.addEventListener('mousemove', onMouseMove);
  canvas.addEventListener('mouseup', onMouseUp);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('click', onClick);

  // ── Render ──
  render();

  document.getElementById('loading-overlay').classList.add('hidden');
}

// ─── Render ───
function render() {
  if (!ctx) {
    console.error('Canvas context not initialized!');
    return;
  }
  console.log('Rendering:', graphData.nodes.filter(n => n.visible).length, 'visible nodes');
  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(zoom.x, zoom.y);
  ctx.scale(zoom.k, zoom.k);

  // Grid background
  drawGrid();

  // Edges
  for (const e of validEdges) {
    if (!e.visible) continue;
    ctx.beginPath();
    ctx.moveTo(e.source.x, e.source.y);
    ctx.lineTo(e.target.x, e.target.y);
    ctx.strokeStyle = EDGE_COLOR;
    ctx.lineWidth = 0.8 / zoom.k;
    ctx.globalAlpha = 0.5;
    ctx.stroke();
  }

  // Nodes
  for (const n of graphData.nodes) {
    if (!n.visible) continue;
    const r = getNodeRadius(n);
    const color = getNodeColor(n);
    const isSelected = selectedNode && selectedNode.id === n.id;
    const isHovered = hoveredNode && hoveredNode.id === n.id;

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // Stroke
    ctx.strokeStyle = isSelected ? '#fff' : d3.color(color).darker(0.8).formatHex();
    ctx.lineWidth = (isSelected ? 2 : 1) / zoom.k;
    ctx.stroke();

    // Hover highlight
    if (isHovered && !isSelected) {
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2 / zoom.k;
      ctx.stroke();
    }

    // Labels
    if (showLabels) {
      ctx.font = `${(n.type === 'spec' ? 10 : 9) / zoom.k}px Inter, sans-serif`;
      ctx.fillStyle = d3.color(color).darker(0.8).formatHex();
      ctx.textAlign = 'center';
      ctx.globalAlpha = 0.7;
      ctx.fillText(n.term || n.label || n.id, n.x, n.y - r - 4 / zoom.k);
    }
  }

  ctx.restore();
  ctx.globalAlpha = 1;
}

// ─── Draw Grid ───
function drawGrid() {
  const gridSize = 40 * zoom.k;
  const offsetX = zoom.x % gridSize;
  const offsetY = zoom.y % gridSize;

  ctx.strokeStyle = 'rgba(255,255,255,0.02)';
  ctx.lineWidth = 0.5 / zoom.k;

  for (let x = offsetX; x < width; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = offsetY; y < height; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
}

// ─── Mouse Events ───
function getMousePos(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - zoom.x) / zoom.k,
    y: (event.clientY - rect.top - zoom.y) / zoom.k
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
    const pos = getMousePos(event);
    const node = findNodeAt(pos);
    if (node) {
      draggedNode = node;
      panStart = { x: event.clientX, y: event.clientY };
      isDragging = false;
    } else {
      isPanning = true;
      panStart = { x: event.clientX - zoom.x, y: event.clientY - zoom.y };
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
    render();
    return;
  }

  if (isPanning) {
    zoom.x = event.clientX - panStart.x;
    zoom.y = event.clientY - panStart.y;
    render();
    return;
  }

  // Hover detection
  const node = findNodeAt(pos);
  if (node !== hoveredNode) {
    hoveredNode = node;
    canvas.style.cursor = node ? 'pointer' : 'grab';
    render();
  }
}

function onMouseUp(event) {
  if (isPanning) {
    isPanning = false;
    canvas.style.cursor = 'grab';
  }
  if (draggedNode && !isDragging) {
    // It was a click, not a drag
    const pos = getMousePos(event);
    const node = findNodeAt(pos);
    if (node) selectNode(event, node);
    else deselectNode();
  }
  draggedNode = null;
  isDragging = false;
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
function getNodeRadius(d) {
  if (d.type === 'spec' || d.category === 'spec') return 15;

  // Size based on selected metric
  let value = 0;
  if (sizeMetric === 'relatedCount') {
    value = d.relatedCount || 0;
  } else if (sizeMetric === 'degree') {
    value = d.degree || 0;
  } else if (sizeMetric === 'type') {
    // Size by type category
    const typeSizes = { CON: 12, FN: 10, REQ: 9, US: 9, SC: 8, Entity: 8, GL: 7, TST: 6, Enum: 6, API: 8, EP: 10, TASK: 7, ISSUE: 8, DG: 7, UJ: 8, UXAC: 8, NFR: 9, IS: 8, spec: 10 };
    value = typeSizes[d.type] || 5;
  }

  // Scale: min 6px, max 35px
  const r = Math.max(6, Math.min(35, 6 + value * 1.5));
  console.log('getNodeRadius:', d.id, 'metric:', sizeMetric, 'value:', value, 'radius:', r);
  return r;
}

function getNodeColor(d) {
  if (d.type && TYPE_COLORS[d.type]) return TYPE_COLORS[d.type];
  return '#94a3b8';
}

let hoveredNode = null;
let isSimulating = false;
let simulation = null;
let sizeMetric = 'relatedCount'; // Default sizing metric

// ─── Simulation Control ───
function toggleSimulation() {
  // Stop any running simulation first
  if (simulation) {
    simulation.stop();
  }

  // Start fresh simulation
  simulation = d3.forceSimulation(graphData.nodes.filter(n => n.visible))
    .force('link', d3.forceLink(validEdges.filter(e => e.visible)).distance(120).strength(0.05))
    .force('charge', d3.forceManyBody().strength(-150))
    .force('center', d3.forceCenter(width / 2, height / 2).strength(0.02))
    .force('collision', d3.forceCollide().radius(25))
    .alpha(0.5)
    .alphaDecay(0.01)
    .on('tick', () => { render(); });

  // Auto-stop after 3 seconds
  setTimeout(() => {
    if (simulation) {
      simulation.stop();
      simulation = null;
    }
  }, 3000);
}

// ─── Theme Update ───
function updateThemeColors() {
  render();
}

window.updateThemeColors = updateThemeColors;
window.toggleSimulation = toggleSimulation;
