
// ─── Component Loader ───
async function loadComponent(id, path) {
  const container = document.getElementById(id);
  const response = await fetch(path);
  const html = await response.text();
  container.insertAdjacentHTML('beforeend', html);
}

// ─── Load all components ───
document.addEventListener('DOMContentLoaded', async () => {
  try {
    await Promise.all([
      loadComponent('sidebar-container', 'components/sidebar.html'),
      loadComponent('canvas-container', 'components/canvas.html'),
      loadComponent('detail-container', 'components/detail.html'),
      loadComponent('debug-container', 'components/debug.html'),
    ]);

    // Move detail and debug panels to canvas container
    const canvasContainer = document.getElementById('canvas-container');
    const detailPanel = document.getElementById('detail-panel');
    const debugPanel = document.getElementById('debug-panel');
    if (detailPanel) canvasContainer.appendChild(detailPanel);
    if (debugPanel) canvasContainer.appendChild(debugPanel);

    // Start the app
    loadGraphData();

    // ─── Event listeners (need DOM elements to exist) ───
    // Click background to deselect (same as pressing × close button)
    // Distinguish click from drag by tracking mouse movement distance
    let pointerDownPos = null;
    const graphContainer = document.getElementById('graph-container');
    if (graphContainer) {
      graphContainer.addEventListener('pointerdown', (e) => {
        pointerDownPos = { x: e.clientX, y: e.clientY };
      });
      graphContainer.addEventListener('click', (e) => {
        if (pointerDownPos) {
          const dx = e.clientX - pointerDownPos.x;
          const dy = e.clientY - pointerDownPos.y;
          if (Math.sqrt(dx * dx + dy * dy) > 5) return;
        }
        const isOnNode = e.target.closest('.node') || e.target.closest('circle');
        if (!isOnNode) {
          deselectNode();
        }
      });
    }

    // Global error handler
    window.addEventListener('error', (e) => {
      err('Global error:', e.message, 'at', e.filename, ':', e.lineno);
      const overlay = document.getElementById('loading-overlay');
      if (overlay) {
        overlay.innerHTML = `<div style="color:#f44;font-size:14px;padding:20px;text-align:center;">
          <strong>❌ JavaScript Error</strong><br><br>
          <code style="font-size:11px;word-break:break-all;">${e.message}</code><br><br>
          <span style="font-size:11px;color:#888;">${e.filename}:${e.lineno}</span><br><br>
          <span style="font-size:11px;color:#f80;">Check browser console (F12) for details</span>
        </div>`;
      }
    });

    window.addEventListener('unhandledrejection', (e) => {
      err('Unhandled promise rejection:', e.reason);
    });

    // Resize handler
    window.addEventListener('resize', () => {
      const container = document.getElementById('graph-container');
      width = container.clientWidth;
      height = container.clientHeight;
      svg.attr('width', width).attr('height', height);
      simulation.force('center', d3.forceCenter(width / 2, height / 2));
    });
  } catch (e) {
    console.error('Failed to load components:', e);
  }
});

// ─── Graph Data & State ───
let graphData = null;
let simulation = null;
let validEdges = null;
let svg, g, linkGroup, nodeGroup, labelsG;
let link, node, labelText;
let selectedNode = null;
let showLabels = true;
let showSpecs = true;
let debugVisible = false;
let tickCount = 0;
let startTime = 0;
let activeCategories = new Set();
let activeEdgeTypes = new Set();
let searchTerm = '';
let width, height;
let draggedNode = null;
let dragTargetX = 0, dragTargetY = 0;
let isDragging = false;
const DRAG_FRICTION = 0.6;
const DRAG_SMOOTHING = 0.3;
const SETTLE_FRICTION = 0.8;

// ─── Color Schemes ───
const CATEGORY_COLORS = {
  domain: '#f472b6',
  technical: '#38bdf8',
  security: '#fbbf24',
  ui: '#a78bfa',
  spec: '#34d399',
};

const EDGE_COLORS = {
  relatedTerms: 'rgba(100, 110, 160, 0.25)',
  specRef: 'rgba(56, 189, 248, 0.15)',
  crossSpec: 'rgba(251, 191, 36, 0.15)',
};

// ─── Debug helpers ───
function log(...args) {
  console.log('[GlossaryGraph]', ...args);
}
function warn(...args) {
  console.warn('[GlossaryGraph]', ...args);
}
function err(...args) {
  console.error('[GlossaryGraph]', ...args);
}
function updateDebug() {
  if (!debugVisible || !simulation) return;
  const el = document.getElementById('debug-content');
  if (!el) return;
  const elapsed = ((performance.now() - startTime) / 1000).toFixed(1);
  const alpha = simulation.alpha().toFixed(4);
  const nodeCount = simulation.nodes().length;
  const linkCount = simulation.force('link').links().length;

  // Check for stuck nodes (all at origin)
  let stuckNodes = 0;
  let validPositions = 0;
  let edgeIssues = 0;
  for (const n of simulation.nodes()) {
    if (n.x === undefined && n.y === undefined) stuckNodes++;
    else if (n.x !== undefined || n.y !== undefined) validPositions++;
  }
  for (const e of validEdges) {
    const src = e.source;
    const tgt = e.target;
    if (typeof src === 'string' || typeof tgt === 'string') {
      edgeIssues++;
    }
  }

  el.innerHTML = `
    <div class="debug-row"><span class="debug-label">Time:</span><span class="debug-value">${elapsed}s</span></div>
    <div class="debug-row"><span class="debug-label">Ticks:</span><span class="debug-value">${tickCount}</span></div>
    <div class="debug-row"><span class="debug-label">Alpha:</span><span class="debug-value">${alpha}</span></div>
    <div class="debug-row"><span class="debug-label">Nodes:</span><span class="debug-value">${nodeCount}</span></div>
    <div class="debug-row"><span class="debug-label">Links:</span><span class="debug-value">${linkCount}</span></div>
    <div class="debug-row"><span class="debug-label">Valid pos:</span><span class="debug-value">${validPositions}</span></div>
    <div class="debug-row"><span class="debug-label">Stuck (0,0):</span><span class="${stuckNodes > 0 ? 'debug-warn' : 'debug-value'}">${stuckNodes}</span></div>
    <div class="debug-row"><span class="debug-label">Unresolved edges:</span><span class="${edgeIssues > 0 ? 'debug-err' : 'debug-value'}">${edgeIssues}</span></div>
    <div class="debug-row"><span class="debug-label">Sim running:</span><span class="debug-value">${simulation.alpha() > simulation.alphaMin() ? 'yes' : 'no'}</span></div>
  `;
}

// ─── Load data ───
async function loadGraphData() {
  log('loadGraphData: starting');
  try {
    log('  fetching graph-data.json');
    const resp = await fetch('graph-data.json');
    log('  fetch status:', resp.status);
    graphData = await resp.json();
    log('  loaded:', graphData.summary.totalTerms, 'terms,', graphData.summary.totalEdges, 'edges');
  } catch (e) {
    err('  fetch failed:', e.message);
    try {
      log('  trying ./graph-data.json');
      const resp = await fetch('./graph-data.json');
      graphData = await resp.json();
      log('  loaded:', graphData.summary.totalTerms, 'terms');
    } catch (e2) {
      err('  also failed:', e2.message);
      document.getElementById('loading-text').textContent =
        'Could not load graph-data.json. Run `node extract-graph-data.js` first.';
      return;
    }
  }
  log('  calling initUI');
  initUI();
  log('  calling initGraph');
  startTime = performance.now();
  tickCount = 0;
  initGraph();
  log('  initGraph done');
}

// ─── Init UI ───
function initUI() {
  document.getElementById('project-name').textContent =
    `${graphData.project} · v${graphData.version}`;

  // Category filters
  const catContainer = document.getElementById('category-filters');
  for (const [cat, count] of Object.entries(graphData.summary.categories)) {
    const div = document.createElement('div');
    div.className = 'filter-item';
    div.innerHTML = `
      <input type="checkbox" checked data-category="${cat}">
      <div class="filter-dot" style="background:${CATEGORY_COLORS[cat]}"></div>
      <span>${cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
      <span class="filter-count">${count}</span>`;
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      applyFilters();
    });
    activeCategories.add(cat);
    catContainer.appendChild(div);
  }

  // Edge type filters
  const edgeContainer = document.getElementById('edge-type-filters');
  const edgeLabels = { relatedTerms: 'Related', specRef: 'Spec refs', crossSpec: 'Cross-spec' };
  for (const [type, color] of Object.entries(EDGE_COLORS)) {
    const div = document.createElement('div');
    div.className = 'edge-filter-item';
    div.innerHTML = `
      <input type="checkbox" checked data-edgetype="${type}">
      <div class="edge-line" style="background:${color}"></div>
      <span>${edgeLabels[type] || type}</span>`;
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeEdgeTypes.add(type) : activeEdgeTypes.delete(type);
      applyFilters();
    });
    activeEdgeTypes.add(type);
    edgeContainer.appendChild(div);
  }

  // ── Term List ──
  const termList = document.getElementById('term-list');
  const sortedNodes = [...graphData.nodes]
    .filter(n => n.category !== 'spec')
    .sort((a, b) => a.term.localeCompare(b.term));

  sortedNodes.forEach(n => {
    const div = document.createElement('div');
    div.className = 'term-list-item';
    div.dataset.nodeId = n.id;
    div.innerHTML = `
      <div class="item-id">${n.id}</div>
      <div class="item-name">${n.term}</div>
      <div class="item-cat">${n.category}</div>`;
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      const node = graphData.nodes.find(nd => nd.id === n.id);
      if (node) selectNode(e, node);
      document.querySelectorAll('.term-list-item').forEach(el => el.classList.remove('active'));
      div.classList.add('active');
    });
    termList.appendChild(div);
  });

  // ── Search ──
  const searchInput = document.getElementById('search-input');
  let searchTimeout;
  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      searchTerm = e.target.value.toLowerCase().trim();
      applyFilters();
    }, 200);
  });

  // Controls
  document.getElementById('btn-zoom-reset').addEventListener('click', resetZoom);
  document.getElementById('btn-labels').addEventListener('click', toggleLabels);
  document.getElementById('btn-specs').addEventListener('click', toggleSpecs);
  document.getElementById('btn-reheat').addEventListener('click', reheatSimulation);

  // Close detail panel
  document.getElementById('close-detail').addEventListener('click', deselectNode);
}

// ─── Filters ───
function applyFilters() {
  // Apply category filter
  const filteredIds = new Set();
  for (const n of graphData.nodes) {
    const catVisible = activeCategories.has(n.category);
    const searchMatch = searchTerm ? n.term.toLowerCase().includes(searchTerm) ||
      n.id.toLowerCase().includes(searchTerm) : true;
    n.visible = catVisible && searchMatch;
    if (n.visible) filteredIds.add(n.id);
  }

  // Apply edge type filter
  for (const e of validEdges) {
    const typeVisible = activeEdgeTypes.has(e.type);
    const srcVisible = filteredIds.has(e.source.id);
    const tgtVisible = filteredIds.has(e.target.id);
    e.visible = typeVisible && srcVisible && tgtVisible;
  }

  // Update node visibility
  for (const n of graphData.nodes) {
    const nodeEl = nodeGroup.selectAll('g').filter(d => d.id === n.id);
    nodeEl.classed('dimmed', !n.visible).classed('visible', n.visible);
  }

  // Update link visibility
  for (const e of validEdges) {
    const linkEl = linkGroup.selectAll('line').filter(d => d === e);
    linkEl.classed('dimmed', !e.visible).classed('visible', e.visible);
  }

  // Update term list
  document.querySelectorAll('.term-list-item').forEach(el => {
    const nodeId = el.dataset.nodeId;
    const node = graphData.nodes.find(n => n.id === nodeId);
    el.style.display = node && node.visible ? 'block' : 'none';
  });
}

// ─── Zoom ───
function resetZoom() {
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
}

let zoom;

// ─── Init graph ───
function initGraph() {
  log('initGraph called');
  log('  graphData.nodes:', graphData.nodes.length);
  log('  graphData.edges:', graphData.edges.length);

  const container = document.getElementById('graph-container');
  width = container.clientWidth;
  height = container.clientHeight;
  log('  container:', width, 'x', height);

  svg = d3.select('#graph-svg')
    .attr('width', width)
    .attr('height', height);

  log('  SVG created');

  // ── Pre-resolve edges: filter dangling refs, resolve string IDs to node objects ──
  const nodeMap = new Map();
  for (const n of graphData.nodes) nodeMap.set(n.id, n);
  validEdges = [];
  for (const e of graphData.edges) {
    const srcId = typeof e.source === 'object' ? e.source.id : e.source;
    const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
    const srcNode = nodeMap.get(srcId);
    const tgtNode = nodeMap.get(tgtId);
    if (!srcNode || !tgtNode) {
      warn(`Skipping edge: ${srcId} -> ${tgtId} (missing node)`);
      continue;
    }
    e.source = srcNode;
    e.target = tgtNode;
    validEdges.push(e);
  }
  log(`Edges: ${graphData.edges.length} total, ${validEdges.length} valid`);

  const defs = svg.append('defs');

  // Grid pattern
  const pattern = defs.append('pattern')
    .attr('id', 'grid')
    .attr('width', 40)
    .attr('height', 40)
    .attr('patternUnits', 'userSpaceOnUse');
  pattern.append('path')
    .attr('d', 'M 40 0 L 0 0 0 40')
    .attr('fill', 'none')
    .attr('stroke', 'rgba(255,255,255,0.02)')
    .attr('stroke-width', 0.5);

  svg.append('rect')
    .attr('width', width)
    .attr('height', height)
    .attr('fill', 'url(#grid)');

  // ── Zoom ──
  zoom = d3.zoom()
    .scaleExtent([0.05, 8])
    .on('zoom', (event) => {
      g.attr('transform', event.transform);
      const k = event.transform.k;
      labelsG.selectAll('text')
        .attr('font-size', d => {
          const base = d.category === 'spec' ? 10 : 9;
          return Math.max(base / Math.sqrt(k), 6);
        });
    });
  svg.call(zoom);

  g = svg.append('g');

  // ── Labels group ──
  labelsG = g.append('g').attr('class', 'labels');

  // ── Links ──
  linkGroup = g.append('g').attr('class', 'links');
  link = linkGroup.selectAll('line')
    .data(validEdges)
    .join('line')
    .attr('stroke', d => EDGE_COLORS[d.type])
    .attr('stroke-width', d => d.type === 'crossSpec' ? 1.5 : d.type === 'relatedTerms' ? 1 : 0.7)
    .attr('stroke-dasharray', d => d.type === 'specRef' ? '3,4' : d.type === 'crossSpec' ? '5,4' : 'none')
    .attr('opacity', 1);

  // ── Nodes ──
  nodeGroup = g.append('g').attr('class', 'nodes');
  node = nodeGroup.selectAll('g')
    .data(graphData.nodes)
    .join('g')
    .attr('class', 'node')
    .call(d3.drag()
      .on('start', dragStart)
      .on('drag', dragged)
      .on('end', dragEnded));

  node.append('circle')
    .attr('r', d => {
      if (d.category === 'spec') return 10;
      const totalConn = (d.specRefCount || 0) + (d.relatedCount || 0);
      return Math.max(4, Math.min(12, 3 + totalConn * 0.6));
    })
    .attr('fill', d => CATEGORY_COLORS[d.category])
    .attr('stroke', d => d3.color(CATEGORY_COLORS[d.category]).darker(0.8).formatHex())
    .attr('stroke-width', 1)
    .on('click', (event, d) => { event.stopPropagation(); selectNode(event, d); });

  node.on('mouseenter', function(event, d) {
    if (selectedNode && selectedNode.id === d.id) return;
    d3.select(this).select('circle')
      .transition().duration(100)
      .attr('stroke', '#fff').attr('stroke-width', 2);
  }).on('mouseleave', function(event, d) {
    if (selectedNode && selectedNode.id === d.id) return;
    d3.select(this).select('circle')
      .transition().duration(100)
      .attr('stroke', d3.color(CATEGORY_COLORS[d.category]).darker(0.8).formatHex())
      .attr('stroke-width', 1);
  });

  // ── Labels ──
  labelsG.selectAll('text')
    .data(graphData.nodes)
    .join('text')
    .text(d => d.term)
    .attr('font-size', d => d.category === 'spec' ? 10 : 9)
    .attr('fill', d => CATEGORY_COLORS[d.category])
    .attr('dy', d => d.category === 'spec' ? -14 : -12)
    .attr('text-anchor', 'middle')
    .style('opacity', showLabels ? 0.7 : 0)
    .style('font-weight', d => d.category === 'spec' ? 600 : 400)
    .style('paint-order', 'stroke')
    .style('stroke', '#0f111a')
    .style('stroke-width', '3px')
    .style('stroke-linecap', 'round')
    .style('stroke-linejoin', 'round');

  // ─── Force Simulation ───
  // Compute degree for collision radius
  const degreeMap = new Map();
  for (const n of graphData.nodes) degreeMap.set(n.id, 0);
  for (const e of validEdges) {
    const srcId = e.source.id;
    const tgtId = e.target.id;
    degreeMap.set(srcId, (degreeMap.get(srcId) || 0) + 1);
    degreeMap.set(tgtId, (degreeMap.get(tgtId) || 0) + 1);
  }

  // Create the simulation — pass ALL nodes, NOT filtered
  simulation = d3.forceSimulation(graphData.nodes)
    .alpha(1)
    .alphaMin(0.001)
    // Governs how fast alpha (and therefore every force's strength) falls
    // back toward 0 once released. 0.0228 is d3's stock default and takes
    // ~250 ticks (~4s @60fps) to fully settle — that's the "coasts too
    // long" feeling. 0.06 settles in ~70-90 ticks (~1.2-1.5s): still a
    // visible, smooth tail, just not a long drift. Raise toward ~0.1 for
    // an even snappier stop, lower toward ~0.03 for more glide.
    .alphaDecay(0.06)
    .velocityDecay(DRAG_FRICTION)
    .force('link', d3.forceLink(validEdges)
      .distance(d => {
        if (d.type === 'crossSpec') return 250;
        if (d.type === 'specRef') return 150;
        return 55;
      })
      .strength(d => {
        if (d.type === 'crossSpec') return 0.1;
        if (d.type === 'specRef') return 0.15;
        return 0.5;
      }))
    .force('charge', d3.forceManyBody()
      .strength(-100)
      .distanceMax(350))
    .force('collision', d3.forceCollide()
      .radius(d => {
        if (d.category === 'spec') return 35;
        const deg = degreeMap.get(d.id) || 0;
        return 18 + Math.min(deg * 1.2, 20);
      })
      .strength(0.6))
    .force('center', d3.forceCenter(width / 2, height / 2)
      .strength(0.015))
    .on('tick', ticked);

  log('  simulation created, alpha:', simulation.alpha());
  log('  first node x:', graphData.nodes[0].x, 'y:', graphData.nodes[0].y);

  // Run enough ticks synchronously for a stable initial layout.
  // With alphaDecay(0.06), alpha halves roughly every 12 ticks.
  // After ~800 ticks, alpha is ~0 and nodes have naturally slowed down.
  // The key is running enough ticks — the simulation naturally coasts
  // to a stop rather than halting abruptly.
  simulation.tick(800);

  // Render the settled layout
  ticked();

  // Hide overlay — layout is complete
  document.getElementById('loading-overlay').classList.add('hidden');

  // Stop the simulation completely — no more drift
  simulation.stop();

  // Pin every node at its settled position AND zero out velocity.
  // stop() only halts the ticker; it does NOT freeze positions or velocities.
  // Anything that later calls simulation.restart() (resize, reheat, browser
  // firing a spurious 'resize' on initial layout) will otherwise send every
  // node back into free-floating physics. Pinning fx/fy + zeroing vx/vy makes
  // that impossible regardless of what touches the simulation later.
  graphData.nodes.forEach(d => {
    d.fx = d.x;
    d.fy = d.y;
    d.vx = 0;
    d.vy = 0;
  });

  log('  simulation stopped + nodes pinned + velocities zeroed after warmup');
}

function ticked() {
  tickCount++;

  // Ease the dragged node toward the cursor each tick instead of having
  // it hard-pinned to the raw mouse position. This runs through the same
  // integrator/smoothing as everything else, which is what removes the
  // jitter — neighbors now see continuous motion instead of being
  // shoved by sudden teleport jumps.
  if (draggedNode) {
    draggedNode.fx += (dragTargetX - draggedNode.fx) * DRAG_SMOOTHING;
    draggedNode.fy += (dragTargetY - draggedNode.fy) * DRAG_SMOOTHING;
  }

  link
    .attr('x1', d => d.source.x)
    .attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x)
    .attr('y2', d => d.target.y);

  node.attr('transform', d => `translate(${d.x},${d.y})`);

  labelsG.selectAll('text')
    .attr('x', d => d.x)
    .attr('y', d => d.y);

  if (tickCount % 10 === 0) updateDebug();
}

// ─── Node selection ───
function selectNode(event, d) {
  event.stopPropagation();
  selectedNode = d;

  const connectedIds = new Set([d.id]);
  const connectedEdgeSet = new Set();

  for (const e of validEdges) {
    if (e.source.id === d.id || e.target.id === d.id) {
      connectedIds.add(e.source.id);
      connectedIds.add(e.target.id);
      connectedEdgeSet.add(e);
    }
  }

  // Highlight connected nodes
  node.classed('highlighted', n => connectedIds.has(n.id))
      .classed('dimmed', n => !connectedIds.has(n.id));

  // Highlight connected edges
  link.classed('highlighted', e => connectedEdgeSet.has(e))
      .classed('dimmed', e => !connectedEdgeSet.has(e));

  // Show detail panel
  showDetail(d);

  // Highlight in term list
  document.querySelectorAll('.term-list-item').forEach(el => {
    el.classList.toggle('active', el.dataset.nodeId === d.id);
  });
}

function deselectNode() {
  selectedNode = null;
  node.classed('highlighted', false).classed('dimmed', false);
  link.classed('highlighted', false).classed('dimmed', false);
  labelsG.selectAll('text')
    .transition().duration(200)
    .style('opacity', showLabels ? 0.7 : 0);
  document.querySelectorAll('.term-list-item').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-panel').classList.remove('visible');
}

function showDetail(d) {
  const panel = document.getElementById('detail-panel');
  document.getElementById('detail-id').textContent = d.id;
  document.getElementById('detail-name').textContent = d.term;

  const catBadge = document.getElementById('detail-category');
  catBadge.textContent = d.category;
  const catColor = CATEGORY_COLORS[d.category];
  catBadge.style.background = catColor + '22';
  catBadge.style.color = catColor;

  document.getElementById('detail-def').textContent = d.definition || 'No definition available.';

  const stats = document.getElementById('detail-stats');
  let html = `<div><strong>Connections:</strong> ${d.relatedCount || 0}</div>`;
  html += `<div><strong>Spec refs:</strong> ${d.specRefCount || 0}</div>`;

  if (d.specs && d.specs.length > 0) {
    html += `<div><strong>In specs:</strong></div>`;
    for (const spec of d.specs) {
      html += `<span style="white-space:normal">📋 ${spec}</span>`;
    }
  }
  stats.innerHTML = html;

  panel.classList.add('visible');
}

// ─── Drag handlers ───
function dragStart(event, d) {
  if (!event.active) simulation.alphaTarget(0.3).restart();
  draggedNode = d;
  dragTargetX = d.x;
  dragTargetY = d.y;
  isDragging = true;
}

function dragged(event, d) {
  if (!draggedNode) return;
  dragTargetX = event.x;
  dragTargetY = event.y;
}

function dragEnded(event, d) {
  if (!event.active) simulation.alphaTarget(0);
  draggedNode = null;
  dragStarted = false;

  // Settle the dragged node
  simulation
    .alpha(0.1)
    .velocityDecay(SETTLE_FRICTION)
    .alphaTarget(0)
    .restart();

  simulation.on('end.dragSettle', () => {
    d.fx = d.x;
    d.fy = d.y;
    simulation.alphaTarget(0.3);
    simulation.velocityDecay(DRAG_FRICTION);
    simulation.on('end.dragSettle', null);
  });
}

// ─── Controls ───
function toggleLabels() {
  showLabels = !showLabels;
  document.getElementById('btn-labels').classList.toggle('active', showLabels);
  labelsG.selectAll('text')
    .transition().duration(200)
    .style('opacity', showLabels ? 0.7 : 0);
}

function toggleSpecs() {
  showSpecs = !showSpecs;
  document.getElementById('btn-specs').classList.toggle('active', showSpecs);
  applyFilters();
}

function reheatSimulation() {
  // Unpin all nodes
  graphData.nodes.forEach(d => {
    d.fx = null;
    d.fy = null;
  });

  // Reheat simulation
  simulation
    .alpha(Math.max(simulation.alpha(), 0.3))
    .restart();

  // Stop after settling
  simulation.on('end.reheat', () => {
    graphData.nodes.forEach(d => {
      d.fx = d.x;
      d.fy = d.y;
    });
    simulation.on('end.reheat', null);
  });
}

function resetZoom() {
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
}

