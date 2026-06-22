/**
 * Wrapper around vanilla graph.js that exposes mutable state via getter/setter functions.
 * This file is loaded as a native ES module from public/legacy/ (not bundled by Vite).
 * It provides a `window.__GRAPH_WRAPPER__` interface for the React shell to use.
 */

// Import vanilla graph module
import * as graph from './graph.js'

// Re-export functions directly
window.__GRAPH_WRAPPER__ = {
  // Functions
  initGraph: graph.initGraph,
  renderGraph: graph.renderGraph,
  recalcSizeRange: graph.recalcSizeRange,
  startScaleAnimation: graph.startScaleAnimation,
  toggleSimulation: graph.toggleSimulation,
  updateThemeColors: graph.updateThemeColors,
  animateDim: graph.animateDim,
  updateHtmlLabels: graph.updateHtmlLabels,
  setNodeSelectCallbacks: graph.setNodeSelectCallbacks,
  selectNode: graph.selectNode,
  deselectNode: graph.deselectNode,
  settleAfterDrag: graph.settleAfterDrag,

  // Mutable state accessors
  getGraphData: () => graph.graphData,
  setGraphData: (data) => { graph.graphData = data },

  getSelectedNode: () => graph.selectedNode,
  setSelectedNode: (node) => { graph.selectedNode = node },

  getShowLabels: () => graph.showLabels,
  setShowLabels: (v) => { graph.showLabels = v },

  getShowSpecs: () => graph.showSpecs,
  setShowSpecs: (v) => { graph.showSpecs = v },

  getActiveCategories: () => graph.activeCategories,
  setActiveCategories: (v) => { graph.activeCategories = v },

  getSearchTerm: () => graph.searchTerm,
  setSearchTerm: (v) => { graph.searchTerm = v },

  getSizeMetric: () => graph.sizeMetric,
  setSizeMetric: (v) => { graph.sizeMetric = v },

  getZoom: () => graph.zoom,
  setZoom: (x, y, k) => {
    if (x !== undefined) graph.zoom.x = x
    if (y !== undefined) graph.zoom.y = y
    if (k !== undefined) graph.zoom.k = k
  },

  getWidth: () => graph.width,
  setWidth: (v) => { graph.width = v },

  getHeight: () => graph.height,
  setHeight: (v) => { graph.height = v },

  getValidEdges: () => graph.validEdges,
  setValidEdges: (v) => { graph.validEdges = v },

  getTickCount: () => graph.tickCount,
}
