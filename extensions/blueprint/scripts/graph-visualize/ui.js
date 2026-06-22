// ─── UI Logic ───
// This file contains all UI-related code: search, filters, sidebar, detail panel, controls

let _pendingNodeId = null;

// Double-click detection: require clicks within 300ms of each other, per element
const DOUBLE_CLICK_TIMEOUT = 300;

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

function getCategoryCounts() {
  const counts = {};
  for (const n of graphData.nodes) {
    const cat = n.typeCat || n.category || 'other';
    counts[cat] = (counts[cat] || 0) + 1;
  }
  return counts;
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
    searchTerm = qParam;
  }
  return params.get('node');
}

function clearURLState() {
  const params = new URLSearchParams(window.location.search);
  if (params.toString()) {
    history.replaceState(null, '', window.location.pathname);
  }
}

// ─── Init UI ───
function initUI() {
  // Load state from URL before building filters
  _pendingNodeId = loadURLState();

  document.getElementById('project-name').textContent =
    `${graphData.project} · v${graphData.version}`;

  // Category/type filters
  const catContainer = document.getElementById('category-filters');
  const categoryCounts = {};
  for (const n of graphData.nodes) {
    // New format: use typeCat, legacy: use category
    const cat = n.typeCat || n.category || 'other';
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  }
  for (const [cat, count] of Object.entries(categoryCounts).sort((a, b) => b[1] - a[1])) {
    const div = document.createElement('div');
    div.className = 'filter-item';
    const label = cat.charAt(0).toUpperCase() + cat.slice(1);
    div.innerHTML = `
      <input type="checkbox" data-category="${cat}">
      <div class="filter-dot filter-dot-${cat}"></div>
      <span>${label}</span>
      <span class="filter-count">${count}</span>`;
    const cb = div.querySelector('input');
    cb.checked = activeCategories.has(cat);
    if (cb.checked) activeCategories.add(cat);
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      applyFilters();
      updateURL();
    });
    div.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        const cb = div.querySelector('input');
        const now = Date.now();
        const lastClick = div._lastClick || 0;
        const elapsed = now - lastClick;
        div._lastClick = now;

        if (elapsed < DOUBLE_CLICK_TIMEOUT) {
          // Double click: select only this category
          clearTimeout(div._clickTimer);
          delete div._clickTimer;
          document.querySelectorAll('#category-filters .filter-item input').forEach(inp => {
            inp.checked = false;
          });
          activeCategories.clear();
          activeCategories.add(cat);
          cb.checked = true;
          applyFilters();
          updateURL();
        } else {
          // Single click: toggle this category (delayed to avoid conflict with double-click)
          div._clickTimer = setTimeout(() => {
            delete div._lastClick;
            delete div._clickTimer;
            cb.checked = !cb.checked;
            cb.dispatchEvent(new Event('change'));
          }, DOUBLE_CLICK_TIMEOUT);
        }
      }
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
      updateURL();
    }, 200);
  });

  // Controls
  document.getElementById('btn-zoom-reset').addEventListener('click', resetZoom);
  document.getElementById('btn-simulate').addEventListener('click', toggleSimulation);
  document.getElementById('btn-labels').addEventListener('click', toggleLabels);

  // Size metric dropdown
  const sizeMetricBtn = document.getElementById('btn-size-metric');
  const sizeMetricMenu = document.getElementById('size-metric-menu');
  const sizeMetricItems = sizeMetricMenu.querySelectorAll('.dropdown-item');
  
  // Toggle dropdown
  sizeMetricBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    sizeMetricMenu.classList.toggle('open');
  });
  
  // Handle item selection
  sizeMetricItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      sizeMetric = item.dataset.metric;
      const labels = {
        degree: 'Size: Degree',
        blast: 'Size: Blast Radius',
        risk: 'Size: Risk Score',
        centrality: 'Size: Centrality',
        type: 'Size: Type',
      };
      sizeMetricBtn.textContent = labels[sizeMetric];
      sizeMetricItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      sizeMetricMenu.classList.remove('open');
      console.log('Size metric changed to:', sizeMetric);
      if (typeof recalcSizeRange === 'function') recalcSizeRange();
      if (typeof startScaleAnimation === 'function') startScaleAnimation();
      if (typeof render === 'function') render();
    });
  });

  // Theme dropdown
  const btnTheme = document.getElementById('btn-theme');
  const themeMenu = document.getElementById('theme-menu');
  const themeSheets = document.querySelectorAll('[id^="theme-"]');
  let currentTheme = localStorage.getItem('glossary-theme') || 'default';
  applyTheme(currentTheme);
  updateThemeMenu();

  btnTheme.addEventListener('click', (e) => {
    e.stopPropagation();
    themeMenu.classList.toggle('open');
  });

  themeMenu.addEventListener('click', (e) => {
    const item = e.target.closest('.dropdown-item');
    if (!item) return;
    currentTheme = item.dataset.theme;
    applyTheme(currentTheme);
    localStorage.setItem('glossary-theme', currentTheme);
    themeMenu.classList.remove('open');
    updateThemeMenu();
  });

  function applyTheme(theme) {
    themeSheets.forEach(sheet => {
      sheet.disabled = sheet.id !== `theme-${theme}`;
      console.log('Theme sheet:', sheet.id, 'disabled:', sheet.disabled);
    });
    // Wait for stylesheet to apply before updating colors
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (window.updateThemeColors) window.updateThemeColors();
      });
    });
  }

  document.addEventListener('click', () => {
    themeMenu.classList.remove('open');
    sizeMetricMenu.classList.remove('open');
  });

  function updateThemeMenu() {
    document.querySelectorAll('.dropdown-item').forEach(el => {
      el.classList.toggle('active', el.dataset.theme === currentTheme);
    });
  }

  // Close detail panel
  document.getElementById('close-detail').addEventListener('click', deselectNode);

  // Prevent clicks on detail panel from deselecting node
  document.getElementById('detail-panel').addEventListener('click', (e) => {
    e.stopPropagation();
  });
}

// ─── Filters ───
function applyFilters() {
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
  if (typeof startScaleAnimation === 'function') startScaleAnimation();
  // Ensure immediate render after filters
  if (typeof render === 'function') render();
}

// ─── Zoom ───
function resetZoom() {
  zoom = { x: 0, y: 0, k: 1 };
  if (typeof render === 'function') render();
}

// ─── Controls ───
function toggleLabels() {
  showLabels = !showLabels;
  document.getElementById('btn-labels').classList.toggle('active', showLabels);
  if (typeof render === 'function') render();
}

// ─── Node selection ───
function selectNode(event, d) {
  event.stopPropagation();
  if (selectedNode && selectedNode.id === d.id) {
    deselectNode();
    return;
  }
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

  // Canvas rendering handles highlighting in render()
  animateDim(0.15); // Animate to dimmed state

  // Update label opacity immediately (not waiting for node animation)
  if (typeof updateHtmlLabels === 'function') updateHtmlLabels();

  // Trigger scale animation for node size transitions
  if (typeof startScaleAnimation === 'function') startScaleAnimation();

  showDetail(d);

  document.querySelectorAll('.term-list-item').forEach(el => {
    el.classList.toggle('active', el.dataset.nodeId === d.id);
  });
}

function deselectNode() {
  selectedNode = null;
  document.querySelectorAll('.term-list-item').forEach(el => el.classList.remove('active'));
  document.getElementById('detail-panel').classList.remove('visible');
  animateDim(1); // Animate to full opacity

  // Update label opacity immediately (not waiting for node animation)
  if (typeof updateHtmlLabels === 'function') updateHtmlLabels();

  if (typeof startScaleAnimation === 'function') startScaleAnimation();
}

function showDetail(d) {
  const panel = document.getElementById('detail-panel');
  const shortId = (d.type === 'spec' || d.category === 'spec') ? 'SPEC' : d.id.split('-').slice(0, 2).join('-');
  const displayName = d.term || d.label || d.id;
  document.getElementById('detail-name').textContent = displayName;
  document.getElementById('detail-id').textContent = `\u00a0[${shortId}]`;
  document.getElementById('detail-id').style.display = 'inline';

  const catBadge = document.getElementById('detail-category');
  // Show typeLabel for new format, category for legacy
  const displayType = d.typeLabel || d.type || d.category || 'unknown';
  catBadge.textContent = displayType;
  catBadge.className = `category-badge category-badge-${d.type || d.category || 'other'}`;

  document.getElementById('detail-def').textContent = d.definition || 'No definition available.';

  const stats = document.getElementById('detail-stats');
  let html = `<div><strong>Connections:</strong> ${d.relatedCount || 0}</div>`;
  html += `<div><strong>Type:</strong> ${d.type || d.category || 'unknown'}</div>`;

  if (d.specs && d.specs.length > 0) {
    html += `<div><strong>In specs:</strong></div>`;
    html += `<ul style="list-style: none; padding: 4px 0 0 0; margin: 0;">`;
    for (const spec of d.specs) {
      html += `<li style="padding: 2px 0; font-size: 11px;">${spec}</li>`;
    }
    html += '</ul>';
  }
  stats.innerHTML = html;

  panel.classList.add('visible');

  // Sync selected node to URL
  const params = new URLSearchParams(window.location.search);
  params.set('node', d.id);
  const newURL = `?${params.toString()}`;
  history.replaceState(null, '', newURL);
}

function restoreNodeFromURL() {
  if (!_pendingNodeId) return;
  const node = graphData.nodes.find(n => n.id === _pendingNodeId);
  if (!node) return;
  // Create a minimal event object
  const fakeEvent = { stopPropagation: () => {}, clientX: 0, clientY: 0 };
  selectNode(fakeEvent, node);
  _pendingNodeId = null;
}
