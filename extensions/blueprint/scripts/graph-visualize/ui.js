// ─── UI Logic ───
// This file contains all UI-related code: search, filters, sidebar, detail panel, controls

import {
  graphData,
  validEdges,
  selectedNode,
  showLabels,
  activeCategories,
  searchTerm,
  zoom,
  isDragging,
  sizeMetric,
  recalcSizeRange,
  startScaleAnimation,
  renderGraph,
  toggleSimulation,
  updateThemeColors,
  animateDim,
  updateHtmlLabels,
  setNodeSelectCallbacks,
  selectNode as graphSelectNode,
  deselectNode as graphDeselectNode,
} from './graph.js';

let _pendingNodeId = null;

// ─── URL State Sync ───
function updateURL() {
  const params = new URLSearchParams();
  params.set('cats', [...activeCategories].sort().join(','));
  if (searchTerm) {
    params.set('q', searchTerm);
  }
  const newURL = `?${params.toString()}`;
  history.replaceState(null, '', newURL);
}

function loadURLState() {
  const params = new URLSearchParams(window.location.search);
  const catsParam = params.get('cats');
  if (catsParam) {
    activeCategories.clear();
    catsParam.split(',').forEach(c => {
      const trimmed = c.trim();
      if (trimmed) activeCategories.add(trimmed);
    });
  }
  const qParam = params.get('q');
  if (qParam) {
    window.searchTerm = qParam;
  }
  return params.get('node');
}

// ─── Init UI ───
export function initUI() {
  // Register node select/deselect callbacks with graph.js
  setNodeSelectCallbacks(handleNodeSelected, handleNodeDeselected);

  // Load state from URL before building filters
  _pendingNodeId = loadURLState();

  document.getElementById('project-name').textContent =
    `${graphData.project} · v${graphData.version}`;

  // Category/type filters
  const catContainer = document.getElementById('category-filters');
  const categoryCounts = {};
  for (const n of graphData.nodes) {
    const cat = n.typeCat || n.category || 'other';
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  }
  for (const [cat, count] of Object.entries(categoryCounts).sort((a, b) => b[1] - a[1])) {
    const div = document.createElement('div');
    div.className = 'filter-item';
    const label = cat.charAt(0).toUpperCase() + cat.slice(1);
    div.innerHTML = `
      <input type="checkbox" data-category="${cat}">
      <span>${label}</span>
      <div class="filter-dot filter-dot-${cat}"></div>
      <span class="filter-count">${count}</span>`;
    const cb = div.querySelector('input');
    cb.checked = activeCategories.has(cat);
    if (cb.checked) activeCategories.add(cat);
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      applyFilters();
      updateURL();
    });

    // Single click: toggle checkbox
    div.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      }
    });

    // Double click: select only this category
    div.addEventListener('dblclick', (e) => {
      e.preventDefault();
      document.querySelectorAll('#category-filters .filter-item input').forEach(inp => {
        inp.checked = false;
      });
      activeCategories.clear();
      activeCategories.add(cat);
      cb.checked = true;
      applyFilters();
      updateURL();
    });

    catContainer.appendChild(div);
  }

  // ── Node List ──
  const termList = document.getElementById('term-list');
  const sortedNodes = [...graphData.nodes]
    .sort((a, b) => {
      const aSpec = (a.type === 'spec' || a.category === 'spec') ? 1 : 0;
      const bSpec = (b.type === 'spec' || b.category === 'spec') ? 1 : 0;
      if (aSpec !== bSpec) return bSpec - aSpec;
      return (a.term || a.label || a.id).localeCompare(b.term || b.label || b.id);
    });

  sortedNodes.forEach(n => {
    const div = document.createElement('div');
    div.className = 'term-list-item';
    div.dataset.nodeId = n.id;
    const idDisplay = (n.type === 'spec' || n.category === 'spec') ? 'SPEC' : n.id.split('-').slice(0, 2).join('-');
    const catDisplay = n.typeLabel || n.type || n.category || 'unknown';
    div.innerHTML = `
      <div class="item-id">${idDisplay}</div>
      <div class="item-name">${n.term || n.label || n.id}</div>
      <div class="item-cat">${catDisplay}</div>`;
    div.addEventListener('click', (e) => {
      e.stopPropagation();
      const node = graphData.nodes.find(nd => nd.id === n.id);
      if (node) graphSelectNode(e, node);
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
      updateURL();
    }, 200);
  });

  // Controls
  document.getElementById('btn-zoom-reset').addEventListener('click', resetZoom);
  document.getElementById('btn-simulate').addEventListener('click', toggleSimulation);
  document.getElementById('btn-labels').addEventListener('click', toggleLabels);

  // Size metric dropdown (native <details>)
  const sizeMetricDropdown = document.getElementById('size-metric-dropdown');
  const sizeMetricMenu = document.getElementById('size-metric-menu');
  const sizeMetricItems = sizeMetricMenu.querySelectorAll('.dropdown-item');

  sizeMetricItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      sizeMetric = item.dataset.metric;
      const labels = {
        degree: 'Size: Degree',
        blast: 'Size: Blast Radius',
        risk: 'Size: Risk Score',
      };
      sizeMetricDropdown.querySelector('summary').textContent = labels[sizeMetric];
      sizeMetricItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      sizeMetricDropdown.open = false;
      console.log('Size metric changed to:', sizeMetric);
      recalcSizeRange();
      startScaleAnimation();
      renderGraph();
    });
  });

  // Theme dropdown (native <details>)
  const themeDropdown = document.getElementById('theme-dropdown');
  const themeMenu = document.getElementById('theme-menu');
  const themeSheets = document.querySelectorAll('[id^="theme-"]');
  let currentTheme = localStorage.getItem('glossary-theme') || 'default';
  applyTheme(currentTheme);
  updateThemeMenu();

  themeMenu.addEventListener('click', (e) => {
    const item = e.target.closest('.dropdown-item');
    if (!item) return;
    currentTheme = item.dataset.theme;
    applyTheme(currentTheme);
    localStorage.setItem('glossary-theme', currentTheme);
    themeDropdown.open = false;
    updateThemeMenu();
  });

  function applyTheme(theme) {
    themeSheets.forEach(sheet => {
      sheet.disabled = sheet.id !== `theme-${theme}`;
    });
    // Wait for stylesheet to apply before updating colors
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        updateThemeColors();
      });
    });
  }

  function updateThemeMenu() {
    themeMenu.querySelectorAll('.dropdown-item').forEach(el => {
      el.classList.toggle('active', el.dataset.theme === currentTheme);
    });
  }

  // Close detail panel
  document.getElementById('close-detail').addEventListener('click', graphDeselectNode);

  // Prevent clicks on detail panel from deselecting node
  document.getElementById('detail-panel').addEventListener('click', (e) => {
    e.stopPropagation();
  });
}

// ─── Filters ───
export function applyFilters() {
  // Apply category/type filter
  const filteredIds = new Set();
  console.log('applyFilters: activeCategories =', activeCategories, 'size =', activeCategories.size);
  for (const n of graphData.nodes) {
    // Initialize visible if not set
    if (n.visible === undefined) n.visible = true;
    // New format: use typeCat or category
    const cat = n.typeCat || n.category || 'other';
    const catVisible = activeCategories.size === 0 || activeCategories.has(cat);
    const name = n.term || n.label || n.id;
    const searchMatch = searchTerm ? name.toLowerCase().includes(searchTerm) ||
      n.id.toLowerCase().includes(searchTerm) : true;
    n.visible = catVisible && searchMatch;
    if (n.visible) filteredIds.add(n.id);
  }
  console.log('applyFilters: visible nodes =', filteredIds.size);

  // Apply edge filter (only source/target visibility matters now)
  for (const e of validEdges) {
    const srcVisible = filteredIds.has(e.source.id);
    const tgtVisible = filteredIds.has(e.target.id);
    e.visible = srcVisible && tgtVisible;
  }

  // Update term list
  document.querySelectorAll('.term-list-item').forEach(el => {
    const nodeId = el.dataset.nodeId;
    const node = graphData.nodes.find(n => n.id === nodeId);
    el.style.display = node && node.visible ? 'block' : 'none';
  });

  // Trigger scale animation (it internally calls recalcSizeRange and computes connectedSet)
  startScaleAnimation();
  // Ensure immediate render after filters
  renderGraph();
}

// ─── Zoom ───
function resetZoom() {
  zoom.x = 0;
  zoom.y = 0;
  zoom.k = 1;
  renderGraph();
}

// ─── Controls ───
function toggleLabels() {
  showLabels = !showLabels;
  document.getElementById('btn-labels').classList.toggle('active', showLabels);
  renderGraph();
}

// ─── Node selection callbacks (registered with graph.js) ───
function handleNodeSelected(event, d) {
  showDetail(d);
  document.querySelectorAll('.term-list-item').forEach(el => {
    el.classList.toggle('active', el.dataset.nodeId === d.id);
  });
}

function handleNodeDeselected() {
  document.querySelectorAll('.term-list-item').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-panel').classList.remove('visible');
}

export function showDetail(d) {
  const panel = document.getElementById('detail-panel');
  const shortId = (d.type === 'spec' || d.category === 'spec') ? 'SPEC' : d.id.split('-').slice(0, 2).join('-');
  const displayName = d.term || d.label || d.id;
  document.getElementById('detail-name').textContent = displayName;
  document.getElementById('detail-id').textContent = `\u00a0[${shortId}]`;
  document.getElementById('detail-id').style.display = 'inline';

  const catBadge = document.getElementById('detail-category');
  const displayType = d.typeLabel || d.type || d.category || 'unknown';
  catBadge.textContent = displayType.charAt(0).toUpperCase() + displayType.slice(1);
  catBadge.className = `category-badge category-badge-${d.typeCat || d.category || 'other'}`;

  // Build stats section using <details>/<summary> for connections
  const statsDiv = document.getElementById('detail-stats');
  statsDiv.innerHTML = '';

  // Basic info
  const infoDiv = document.createElement('div');
  infoDiv.innerHTML = `<strong>Connections:</strong> ${d.degree || 0}`;
  statsDiv.appendChild(infoDiv);

  if (d.blastRadius) {
    const blastDiv = document.createElement('div');
    blastDiv.innerHTML = `<strong>Blast Radius:</strong> ${d.blastRadius}`;
    statsDiv.appendChild(blastDiv);
  }
  if (d.risk) {
    const riskDiv = document.createElement('div');
    riskDiv.innerHTML = `<strong>Risk Score:</strong> ${d.risk}`;
    statsDiv.appendChild(riskDiv);
  }
  if (d.centrality) {
    const centDiv = document.createElement('div');
    centDiv.innerHTML = `<strong>Centrality:</strong> ${d.centrality.toFixed(4)}`;
    statsDiv.appendChild(centDiv);
  }

  // Specs list (if any)
  if (d.specs && d.specs.length > 0) {
    const specsDiv = document.createElement('div');
    specsDiv.style.marginTop = '8px';
    specsDiv.innerHTML = `<strong>Specs:</strong>`;
    const specsList = document.createElement('ul');
    specsList.className = 'specs-list';
    d.specs.forEach(spec => {
      const li = document.createElement('li');
      li.textContent = spec;
      specsList.appendChild(li);
    });
    specsDiv.appendChild(specsList);
    statsDiv.appendChild(specsDiv);
  }

  // Connections section (collapsible via <details>/<summary>)
  const connections = [];
  for (const e of validEdges) {
    const neighbor = e.source.id === d.id ? e.target : e.source;
    connections.push({
      id: neighbor.id,
      type: neighbor.typeLabel || neighbor.type || neighbor.category || 'unknown',
      edgeType: e.type || 'related',
      label: neighbor.term || neighbor.label || neighbor.id,
    });
  }
  connections.sort((a, b) => a.type.localeCompare(b.type));

  if (connections.length > 0) {
    const details = document.createElement('details');
    details.className = 'connections-toggle';
    const summary = document.createElement('summary');
    summary.textContent = `Connections (${connections.length})`;
    details.appendChild(summary);

    const list = document.createElement('ul');
    list.className = 'connections-list';
    connections.forEach(conn => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="conn-type">[${conn.type}]</span> <span class="conn-label">${conn.label}</span> <span class="conn-edge">(${conn.edgeType})</span>`;
      li.addEventListener('click', () => {
        const targetNode = graphData.nodes.find(n => n.id === conn.id);
        if (targetNode) graphSelectNode(new Event('click'), targetNode);
      });
      list.appendChild(li);
    });
    details.appendChild(list);
    statsDiv.appendChild(details);
  }

  panel.classList.add('visible');
}