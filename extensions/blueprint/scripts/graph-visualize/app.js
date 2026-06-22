// ─── Main App ───
import { initGraph, setGraphData, activeCategories } from './graph.js';
import { initUI, applyFilters } from './ui.js';

const DATA_URL = '/graph-data.json';

async function loadGraphData() {
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    showError(error, DATA_URL);
    return null;
  }
}

function showError(error, url) {
  const overlay = document.getElementById('loading-overlay');
  if (!overlay) {
    console.error('Loading overlay not found:', error);
    return;
  }
  overlay.innerHTML = `
    <div class="error-message">
      <p><strong>Error loading graph data</strong></p>
      <p class="error-location">URL: ${url}</p>
      <p class="error-hint">${error.message}</p>
      <p><code>${error.stack}</code></p>
    </div>`;
}

async function init() {
  setGraphData(await loadGraphData());
  if (!graphData) return;

  console.log('Loaded graph data:', graphData);
  console.log('Nodes:', graphData.nodes.length);
  console.log('Edges:', graphData.edges.length);

  initUI();
  initGraph();
  applyFilters();
}

init();
