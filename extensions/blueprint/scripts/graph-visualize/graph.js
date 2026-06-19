
// ─── Graph State ───
let graphData = null;
let simulation = null;
let validEdges = null;
let svg, g, linkGroup, nodeGroup, labelsG;
let link, node, labelText;
let selectedNode = null;
let showLabels = true;
let showSpecs = true;
let tickCount = 0;
let startTime = 0;
let activeCategories = new Set();
let activeEdgeTypes = new Set();
let searchTerm = '';
let width, height;
let draggedNode = null;
let dragTargetX = 0, dragTargetY = 0;
let dragStartX = 0, dragStartY = 0;
let isDragging = false;

// ─── Zoom ───
let zoom;

// ─── Init graph ───
function initGraph() {

  const container = document.getElementById('graph-container');
  width = container.clientWidth;
  height = container.clientHeight;


  svg = d3.select('#graph-svg')
    .attr('width', width)
    .attr('height', height);



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
      console.warn(`Skipping edge: ${srcId} -> ${tgtId} (missing node)`);
      continue;
    }
    e.source = srcNode;
    e.target = tgtNode;
    validEdges.push(e);
  }


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
  function getEdgeColor(type) {
    const map = { relatedTerms: '--edge-related', specRef: '--edge-spec', crossSpec: '--edge-cross' };
    const val = getComputedStyle(document.documentElement).getPropertyValue(map[type]).trim();
    if (!val) console.warn('Missing CSS var:', map[type]);
    return val;
  }
  linkGroup = g.append('g').attr('class', 'links');
  link = linkGroup.selectAll('line')
    .data(validEdges)
    .join('line')
    .attr('stroke', d => getEdgeColor(d.type))
    .attr('stroke-width', d => d.type === 'crossSpec' ? 1.5 : d.type === 'relatedTerms' ? 1 : 0.5)
    .attr('stroke-dasharray', d => d.type === 'specRef' ? '3,4' : d.type === 'crossSpec' ? '5,4' : 'none')
    .attr('opacity', 1);

  // ── Nodes ──
  nodeGroup = g.append('g').attr('class', 'nodes');
  node = nodeGroup.selectAll('g')
    .data(graphData.nodes)
    .join('g')
    .attr('class', 'node')
    .call(d3.drag()
      .clickDistance(20)
      .on('start', dragStart)
      .on('drag', dragged)
      .on('end', dragEnded));

  function getNodeColor(d) {
    // New format: use TYPE_COLORS for node types
    if (d.type && TYPE_COLORS[d.type]) return TYPE_COLORS[d.type];
    // Legacy format: use CATEGORY_COLORS
    return getComputedStyle(document.documentElement).getPropertyValue(`--${d.category || 'other'}`).trim() || '#94a3b8';
  }

  function getNodeRadius(d) {
    if (d.type === 'spec' || d.category === 'spec') return 10;
    const totalConn = (d.specRefCount || 0) + (d.relatedCount || 0);
    return Math.max(4, Math.min(12, 3 + totalConn * 0.6));
  }

  node.append('circle')
    .attr('r', d => getNodeRadius(d))
    .attr('fill', d => getNodeColor(d))
    .attr('stroke', d => d3.color(getNodeColor(d)).darker(0.8).formatHex())
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
      .attr('stroke', d3.color(getNodeColor(d)).darker(0.8).formatHex())
      .attr('stroke-width', 1);
  });

  // ── Labels ──
  labelsG.selectAll('text')
    .data(graphData.nodes)
    .join('text')
    .text(d => d.term || d.label || d.id)
    .attr('font-size', d => (d.type === 'spec' || d.category === 'spec') ? 10 : 9)
    .attr('fill', d => d3.color(getNodeColor(d)).darker(0.8).formatHex())
    .attr('dy', d => (d.type === 'spec' || d.category === 'spec') ? -14 : -12)
    .attr('text-anchor', 'middle')
    .style('opacity', showLabels ? 0.7 : 0)
    .style('font-weight', d => (d.type === 'spec' || d.category === 'spec') ? 600 : 400)
    .attr('class', 'node-label');

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
        if (d.type === 'crossSpec') return 350;
        if (d.type === 'specRef') return 200;
        return 80;
      })
      .strength(d => {
        if (d.type === 'crossSpec') return 0.1;
        if (d.type === 'specRef') return 0.15;
        return 0.5;
      }))
    .force('charge', d3.forceManyBody()
      .strength(-250)
      .distanceMax(500))
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
}

// ─── Drag handlers ───
// clickDistance(20) on the drag behavior suppresses click only if pointer
// moves >= 20px between mousedown and mouseup. Pure clicks pass through.

function dragStart(event, d) {
  // Pin the node at its current position — don't restart simulation yet.
  // Neighbors only react once actual movement happens (see dragged()).
  d.fx = d.x;
  d.fy = d.y;
  draggedNode = d;
  dragTargetX = event.x;
  dragTargetY = event.y;
  isDragging = false;
}

function dragged(event, d) {
  if (!draggedNode) return;
  dragTargetX = event.x;
  dragTargetY = event.y;

  // Wake the simulation so neighbors react.
  // All nodes are pinned (fx/fy set) at rest — pinned nodes are immune
  // to forces in d3. Release everyone EXCEPT the dragged node so forces
  // can actually move them during this gesture.
  if (!isDragging) {
    // Only wake up if movement exceeds threshold (ignore micro-shakes from clicks)
    const dx = event.x - dragStartX;
    const dy = event.y - dragStartY;
    if (dx * dx + dy * dy < 100) return; // < 10px threshold
    isDragging = true;
    graphData.nodes.forEach(n => {
      if (n !== d) {
        n.fx = null;
        n.fy = null;
      }
    });
    // Keep simulation running with steady alpha during drag
    simulation.alphaTarget(0.3).restart();
  }
}

function dragEnded(event, d) {
  isDragging = false;
  draggedNode = null;
  delete d._dragStartX;
  delete d._dragStartY;

  // Pin the dragged node at its current position
  d.fx = d.x;
  d.fy = d.y;

  // Let all other nodes coast with momentum — don't pin yet.
  // Set alphaTarget(0) so alpha decays naturally, giving nodes
  // time to settle into their new positions with smooth momentum.
  simulation.alphaTarget(0);
  simulation.velocityDecay(DRAG_FRICTION);

  // Once settled, pin everything for a stable resting state
  simulation.on('end.dragSettle', () => {
    graphData.nodes.forEach(n => {
      n.fx = n.x;
      n.fy = n.y;
    });
    simulation.on('end.dragSettle', null);
  });
}

// ─── Theme Update ───
function updateThemeColors() {
  if (link) {
    link.attr('stroke', d => {
      const map = { relatedTerms: '--edge-related', specRef: '--edge-spec', crossSpec: '--edge-cross', architecture: '--edge-architecture' };
      const cssVar = map[d.type] || '--edge-architecture';
      return getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim();
    });
  }
  if (node) {
    node.select('circle').attr('fill', d => getNodeColor(d)).attr('stroke', d => d3.color(getNodeColor(d)).darker(0.8).formatHex());
  }
  if (labelsG) {
    labelsG.selectAll('text').attr('fill', d => d3.color(getNodeColor(d)).darker(0.8).formatHex());
  }
}

window.updateThemeColors = updateThemeColors;



