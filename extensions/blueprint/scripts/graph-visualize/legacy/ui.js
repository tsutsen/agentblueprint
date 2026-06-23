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
  startAnimation,
  renderGraph,
  toggleSimulation,
  updateThemeColors,
  updateHtmlLabels,
  setNodeSelectCallbacks,
  selectNode as graphSelectNode,
  deselectNode as graphDeselectNode,
} from './graph.js';
import { getCategoryColor } from './config.js';

// ─── Init UI ───
export function initUI() {
  // Register node select/deselect callbacks with graph.js
  setNodeSelectCallbacks(handleNodeSelected, handleNodeDeselected);

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
      <div class="filter-dot" style="background: ${getCategoryColor(cat)}"></div>
      <span class="filter-count">${count}</span>`;
    const cb = div.querySelector('input');
    cb.checked = activeCategories.has(cat);
    if (cb.checked) activeCategories.add(cat);
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      applyFilters();
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
    }, 200);
  });

  // Controls
  document.getElementById('btn-zoom-reset').addEventListener('click', resetZoom);
  document.getElementById('btn-simulate').addEventListener('click', toggleSimulation);

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

      recalcSizeRange();
      startAnimation(null);
      renderGraph();
    });
  });

  // Theme definitions (single source of truth — matches src/lib/themes.ts)
  const THEME_DATA = {
    'default-light': {
      '--bg': '#ffffff', '--surface': '#f5f5f5', '--surface2': '#e8e8e8',
      '--btn-text': '#1a1a1a', '--border': '#d0d0d0',
      '--text': '#1a1a1a', '--text-dim': '#666666', '--text-bright': '#000000',
      '--text-secondary': '#666666', '--accent': '#000000', '--accent-text': '#ffffff',
      '--accent-glow': 'rgba(0, 0, 0, 0.1)',
      '--domain': '#c62828', '--technical': '#1565c0', '--security': '#e65100',
      '--ui': '#6a1b9a', '--spec': '#00695c',
      '--edge-color': 'rgba(148, 163, 184, 0.4)', '--edge-related': 'rgba(148, 163, 184, 0.4)',
      '--edge-spec': 'rgba(52, 211, 153, 0.4)', '--edge-cross': 'rgba(255, 170, 0, 0.3)',
    },
    gruvbox: {
      '--bg': '#1d2021', '--surface': '#3c3836', '--surface2': '#504945',
      '--btn-text': '#e0e0e0', '--border': '#665c54',
      '--text': '#c3b89a', '--text-dim': '#a89984', '--text-bright': '#d5c4a1',
      '--text-secondary': '#a89984', '--accent': '#fabd2f', '--accent-text': '#1a1a1a',
      '--accent-glow': 'rgba(250, 189, 47, 0.15)',
      '--domain': '#ff6b6b', '--technical': '#5c93d6', '--security': '#d4943a',
      '--ui': '#d3869b', '--spec': '#ce93d8',
      '--edge-color': 'rgba(121, 134, 203, 0.3)', '--edge-related': 'rgba(121, 134, 203, 0.3)',
      '--edge-spec': 'rgba(77, 182, 172, 0.3)', '--edge-cross': 'rgba(255, 183, 77, 0.3)',
    },
    'gruvbox-light': {
      '--bg': '#fbf1c7', '--surface': '#ebdbb2', '--surface2': '#d5c4a1',
      '--btn-text': '#504945', '--border': '#bdae93',
      '--text': '#504945', '--text-dim': '#7c6f64', '--text-bright': '#282828',
      '--text-secondary': '#7c6f64', '--accent': '#d79921', '--accent-text': '#1a1a1a',
      '--accent-glow': 'rgba(215, 153, 33, 0.15)',
      '--domain': '#9d0006', '--technical': '#0d47a1', '--security': '#bf360c',
      '--ui': '#4a148c', '--spec': '#01579b',
      '--edge-color': 'rgba(121, 134, 203, 0.3)', '--edge-related': 'rgba(21, 101, 192, 0.3)',
      '--edge-spec': 'rgba(0, 77, 64, 0.3)', '--edge-cross': 'rgba(216, 67, 21, 0.3)',
    },
    'neon-dark': {
      '--bg': '#0d0221', '--surface': '#1a0a2e', '--surface2': '#2d1b4e',
      '--btn-text': '#00ffcc', '--border': '#4a2c7a',
      '--text': '#00ffcc', '--text-dim': '#a09cff', '--text-bright': '#ff80ff',
      '--text-secondary': '#a09cff', '--accent': '#00ffcc', '--accent-text': '#0d0221',
      '--accent-glow': 'rgba(0, 255, 204, 0.2)',
      '--domain': '#ff4081', '--technical': '#00bcd4', '--security': '#ff8a50',
      '--ui': '#7c4dff', '--spec': '#9fa8da',
      '--edge-color': 'rgba(68, 138, 255, 0.3)', '--edge-related': 'rgba(68, 138, 255, 0.3)',
      '--edge-spec': 'rgba(0, 229, 255, 0.3)', '--edge-cross': 'rgba(255, 193, 7, 0.3)',
    },
    'retro-light': {
      '--bg': '#fff0f5', '--surface': '#ffe4e1', '--surface2': '#ffdab9',
      '--btn-text': '#4b0082', '--border': '#dda0dd',
      '--text': '#4b0082', '--text-dim': '#9b1b9b', '--text-bright': '#1a0030',
      '--text-secondary': '#9b1b9b', '--accent': '#d6357f', '--accent-text': '#1a1a1a',
      '--accent-glow': 'rgba(255, 105, 180, 0.2)',
      '--domain': '#c62828', '--technical': '#1565c0', '--security': '#bf360c',
      '--ui': '#6a1b9a', '--spec': '#00695c',
      '--edge-color': 'rgba(155, 89, 182, 0.3)', '--edge-related': 'rgba(155, 89, 182, 0.3)',
      '--edge-spec': 'rgba(52, 211, 153, 0.3)', '--edge-cross': 'rgba(255, 105, 180, 0.3)',
    },
    netrunner: {
      '--bg': '#0a0a12', '--surface': '#12121f', '--surface2': '#1a1a2e',
      '--btn-text': '#fcee0a', '--border': '#2a2a4a',
      '--text': '#e0e0ff', '--text-dim': '#8888aa', '--text-bright': '#ffffff',
      '--text-secondary': '#8888aa', '--accent': '#fcee0a', '--accent-text': '#0a0a12',
      '--accent-glow': 'rgba(252, 238, 10, 0.2)',
      '--domain': '#ff003c', '--technical': '#00f0ff', '--security': '#ff6600',
      '--ui': '#b026ff', '--spec': '#00ff9d',
      '--edge-color': 'rgba(0, 240, 255, 0.4)', '--edge-related': 'rgba(0, 240, 255, 0.3)',
      '--edge-spec': 'rgba(0, 255, 157, 0.3)', '--edge-cross': 'rgba(255, 0, 60, 0.3)',
    },
    'netrunner-light': {
      '--bg': '#f0f0f5', '--surface': '#e8e8f0', '--surface2': '#d8d8e8',
      '--btn-text': '#1a1a2e', '--border': '#c0c0d0',
      '--text': '#1a1a2e', '--text-dim': '#5a5a7a', '--text-bright': '#0a0a12',
      '--text-secondary': '#5a5a7a', '--accent': '#fcee0a', '--accent-text': '#0a0a12',
      '--accent-glow': 'rgba(252, 238, 10, 0.15)',
      '--domain': '#cc0030', '--technical': '#0099aa', '--security': '#cc5500',
      '--ui': '#7a1acc', '--spec': '#00aa66',
      '--edge-color': 'rgba(0, 153, 170, 0.4)', '--edge-related': 'rgba(0, 153, 170, 0.3)',
      '--edge-spec': 'rgba(0, 170, 102, 0.3)', '--edge-cross': 'rgba(204, 0, 48, 0.3)',
    },
  };

  // Theme dropdown (native <details>)
  const themeDropdown = document.getElementById('theme-dropdown');
  const themeMenu = document.getElementById('theme-menu');
  let currentTheme = localStorage.getItem('glossary-theme') || 'default-light';
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
    // Set CSS variables directly on :root — no themes.css needed
    const vars = THEME_DATA[theme];
    const root = document.documentElement;
    // Clear all theme vars first
    for (const key of Object.keys(vars)) {
      root.style.removeProperty(key);
    }
    // Set new theme vars
    for (const [key, value] of Object.entries(vars)) {
      root.style.setProperty(key, value);
    }
    // Wait for CSS to apply before updating canvas colors
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

  // Trigger animation (it internally calls recalcSizeRange and computes connectedSet)
  startAnimation(null);
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