
// ─── Graph State ───
let graphData = null;
let validEdges = null;
let svg, g, linkGroup, nodeGroup, labelsG;
let link, node, labelText;
let selectedNode = null;
let showLabels = true;
let showSpecs = true;
let tickCount = 0;
let startTime = 0;
let activeCategories = new Set();
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
  linkGroup = g.append('g').attr('class', 'links');
  link = linkGroup.selectAll('line')
    .data(validEdges)
    .join('line')
    .attr('stroke', EDGE_COLOR)
    .attr('stroke-width', 0.8)
    .attr('opacity', 0.5);

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

  // Static layout — place nodes in concentric circles by category
  const catMap = {};
  const catGroups = [];
  graphData.nodes.forEach(n => {
    const cat = n.typeCat || n.category || 'other';
    if (!catMap[cat]) {
      catMap[cat] = catGroups.length;
      catGroups.push([]);
    }
    catGroups[catMap[cat]].push(n);
  });

  const cx = width / 2;
  const cy = height / 2;
  const maxRadius = Math.min(width, height) * 0.4;
  catGroups.forEach((group, ci) => {
    const radius = group.length > 50 ? maxRadius * 0.7 : maxRadius * 0.4;
    const angleStep = (2 * Math.PI) / group.length;
    group.forEach((n, ni) => {
      const angle = ci * angleStep * 0.5 + ni * angleStep;
      n.x = cx + radius * Math.cos(angle);
      n.y = cy + radius * Math.sin(angle);
    });
  });



  // Run enough ticks synchronously for a stable initial layout.
  // With alphaDecay(0.06), alpha halves roughly every 12 ticks.
  // Render the initial layout
  ticked();

  // Hide overlay — layout is complete
  document.getElementById('loading-overlay').classList.add('hidden');


}

function ticked() {
  // Update positions (only called during drag now)
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
  draggedNode = d;
  dragStartX = event.x;
  dragStartY = event.y;
  isDragging = false;
}

function dragged(event, d) {
  if (!draggedNode) return;

  // Only treat as drag if movement exceeds threshold (ignore clicks)
  const dx = event.x - dragStartX;
  const dy = event.y - dragStartY;
  if (dx * dx + dy * dy < 100) return; // < 10px threshold

  isDragging = true;

  // Move the dragged node
  d.x = event.x;
  d.y = event.y;

  // Update links connected to this node
  link
    .attr('x1', e => e.source === d ? d.x : e.source.x)
    .attr('y1', e => e.source === d ? d.y : e.source.y)
    .attr('x2', e => e.target === d ? d.x : e.target.x)
    .attr('y2', e => e.target === d ? d.y : e.target.y);

  // Update node position
  node.filter(n => n === d).attr('transform', `translate(${d.x},${d.y})`);

  // Update label position
  labelsG.selectAll('text').filter(n => n === d)
    .attr('x', d.x)
    .attr('y', d.y);
}

function dragEnded(event, d) {
  draggedNode = null;
  delete d._dragStartX;
  delete d._dragStartY;
}

// ─── Theme Update ───
function getNodeColor(d) {
  if (d.type && TYPE_COLORS[d.type]) return TYPE_COLORS[d.type];
  return '#94a3b8';
}

function updateThemeColors() {
  if (link) {
    link.attr('stroke', EDGE_COLOR);
  }
  if (node) {
    node.select('circle').attr('fill', d => getNodeColor(d)).attr('stroke', d => d3.color(getNodeColor(d)).darker(0.8).formatHex());
  }
  if (labelsG) {
    labelsG.selectAll('text').attr('fill', d => d3.color(getNodeColor(d)).darker(0.8).formatHex());
  }
}

window.updateThemeColors = updateThemeColors;



