// ─── Component Loader ───
async function loadComponent(id, path) {
  const container = document.getElementById(id);
  const response = await fetch(path);
  const html = await response.text();
  container.insertAdjacentHTML('beforeend', html);
}

// ─── App Initialization ───
async function initApp() {
  try {
    await Promise.all([
      loadComponent('sidebar-container', 'components/sidebar.html'),
      loadComponent('canvas-container', 'components/canvas.html'),
    ]);

    // Detail and debug panels are inside canvas-container now

    // Start the app — wait for styles to apply
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        loadGraphData();
      });
    });

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
        // Skip if a drag actually occurred
        if (isDragging) return;
        // Canvas click is handled in onMouseUp
      });
    }

    // Global error handler
    window.addEventListener('error', (e) => {
      console.error('Global error:', e.message, 'at', e.filename, ':', e.lineno);
      const overlay = document.getElementById('loading-overlay');
      if (overlay) {
        overlay.innerHTML = `<div style="color:#f44;font-size:14px;padding:20px;text-align:center;">
          <strong>JavaScript Error</strong><br><br>
          <code style="font-size:11px;word-break:break-all;">${e.message}</code><br><br>
          <span style="font-size:11px;color:#888;">${e.filename}:${e.lineno}</span><br><br>
          <span style="font-size:11px;color:#f80;">Check browser console (F12) for details</span>
        </div>`;
      }
    });

    window.addEventListener('unhandledrejection', (e) => {
      console.error('Unhandled promise rejection:', e.reason);
    });

    // Resize handler
    window.addEventListener('resize', () => {
      const container = document.getElementById('graph-container');
      width = container.clientWidth;
      height = container.clientHeight;
      if (canvas) {
        canvas.width = width * window.devicePixelRatio;
        canvas.height = height * window.devicePixelRatio;
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        render();
      }
    });

    // Escape to deselect
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && selectedNode) {
        deselectNode();
      }
    });
  } catch (e) {
    console.error('Failed to load components:', e);
  }
}

// ─── Start ───
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// ─── Load Graph Data ───
async function loadGraphData() {
  try {
    const resp = await fetch('graph-data.json');
    graphData = await resp.json();
  } catch (e) {
    try {
      const resp = await fetch('./graph-data.json');
      graphData = await resp.json();
    } catch (e2) {
      document.getElementById('loading-text').textContent =
        'Could not load graph-data.json. Run `node extract-graph-data.js` first.';
      return;
    }
  }
  initUI();
  startTime = performance.now();
  tickCount = 0;

  // Compute actual data ranges for size normalization
  let maxRelated = 0, maxDegree = 0;
  for (const n of graphData.nodes) {
    const rc = n.relatedCount || 0;
    const deg = n.degree || 0;
    if (rc > maxRelated) maxRelated = rc;
    if (deg > maxDegree) maxDegree = deg;
  }
  sizeRange.relatedCount = [0, Math.max(1, maxRelated)];
  sizeRange.degree = [0, Math.max(1, maxDegree)];
  console.log('Size ranges:', sizeRange);

  initGraph();
}
