// ─── UI Logic ───
// This file contains all UI-related code: search, filters, sidebar, detail panel, controls

// ─── Init UI ───
function initUI() {
  document.getElementById('project-name').textContent =
    `${graphData.project} · v${graphData.version}`;

  // Category filters
  const catContainer = document.getElementById('category-filters');
  const categoryCounts = {};
  for (const n of graphData.nodes) {
    categoryCounts[n.category] = (categoryCounts[n.category] || 0) + 1;
  }
  for (const [cat, count] of Object.entries(categoryCounts)) {
    const div = document.createElement('div');
    div.className = 'filter-item';
    div.innerHTML = `
      <input type="checkbox" checked data-category="${cat}">
      <div class="filter-dot filter-dot-${cat}"></div>
      <span>${cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
      <span class="filter-count">${count}</span>`;
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeCategories.add(cat) : activeCategories.delete(cat);
      applyFilters();
    });
    div.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        const cb = div.querySelector('input');
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      }
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
      <div class="edge-line edge-line-${type}"></div>
      <span>${edgeLabels[type] || type}</span>`;
    div.querySelector('input').addEventListener('change', (e) => {
      e.target.checked ? activeEdgeTypes.add(type) : activeEdgeTypes.delete(type);
      applyFilters();
    });
    div.addEventListener('click', (e) => {
      if (e.target.tagName !== 'INPUT') {
        const cb = div.querySelector('input');
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event('change'));
      }
    });
    activeEdgeTypes.add(type);
    edgeContainer.appendChild(div);
  }

  // ── Term List ──
  const termList = document.getElementById('term-list');
  const sortedNodes = [...graphData.nodes]
    .sort((a, b) => {
      if (a.category === 'spec' && b.category !== 'spec') return -1;
      if (a.category !== 'spec' && b.category === 'spec') return 1;
      return a.term.localeCompare(b.term);
    });

  sortedNodes.forEach(n => {
    const div = document.createElement('div');
    div.className = 'term-list-item';
    div.dataset.nodeId = n.id;
    div.innerHTML = `
      <div class="item-id">${n.category === 'spec' ? 'SPEC' : n.id}</div>
      <div class="item-name">${n.term}</div>
      <div class="item-cat">${n.category === 'spec' ? 'Spec' : n.category}</div>`;
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

  // Update label opacity
  labelsG.selectAll('text')
    .transition().duration(200)
    .style('opacity', n => {
      if (!showLabels) return 0;
      return n.visible ? 0.7 : 0.02;
    });

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

// ─── Controls ───
function toggleLabels() {
  showLabels = !showLabels;
  document.getElementById('btn-labels').classList.toggle('active', showLabels);
  labelsG.selectAll('text')
    .transition().duration(200)
    .style('opacity', showLabels ? 0.7 : 0);
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

  node.classed('highlighted', n => connectedIds.has(n.id))
      .classed('dimmed', n => !connectedIds.has(n.id));

  link.classed('highlighted', e => connectedEdgeSet.has(e))
      .classed('dimmed', e => !connectedEdgeSet.has(e));

  labelsG.selectAll('text')
    .transition().duration(200)
    .style('opacity', n => {
      if (!showLabels) return 0;
      return connectedIds.has(n.id) ? 0.9 : 0.02;
    });

  showDetail(d);

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
  document.getElementById('detail-id').textContent = d.category === 'spec' ? 'SPEC' : d.id;
  document.getElementById('detail-name').textContent = d.term;

  const catBadge = document.getElementById('detail-category');
  catBadge.textContent = d.category;
  catBadge.className = `category-badge category-badge-${d.category}`;

  document.getElementById('detail-def').textContent = d.definition || 'No definition available.';

  const stats = document.getElementById('detail-stats');
  let html = `<div><strong>Connections:</strong> ${d.relatedCount || 0}</div>`;
  html += `<div><strong>Spec refs:</strong> ${d.specRefCount || 0}</div>`;

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
}
