/**
 * Wrapper around vanilla graph.js that exposes mutable state via getter/setter functions.
 * Provides a `window.__GRAPH_WRAPPER__` interface for the React shell to use.
 */

import * as graph from './graph.js';

window.__GRAPH_WRAPPER__ = {
  // Functions
  initGraph: graph.initGraph,
  renderGraph: graph.renderGraph,
  recalcSizeRange: graph.recalcSizeRange,
  startScaleAnimation: graph.startScaleAnimation,
  startSimulation: graph.startSimulation,
  stopSimulation: graph.stopSimulation,
  hasSimulation: graph.hasSimulation,
  updateThemeColors: graph.updateThemeColors,
  animateDim: graph.animateDim,
  updateHtmlLabels: graph.updateHtmlLabels,
  setNodeSelectCallbacks: graph.setNodeSelectCallbacks,
  selectNode: graph.selectNode,
  deselectNode: graph.deselectNode,
  settleAfterDrag: graph.settleAfterDrag,

  // Mutable state accessors
  getGraphData: graph.getGraphData,
  setGraphData: graph.setGraphData,
  getSelectedNode: () => graph.selectedNode,
  setSelectedNode: graph.setSelectedNode,
  getShowLabels: () => graph.showLabels,
  setShowLabels: graph.setShowLabels,
  getActiveCategories: () => graph.activeCategories,
  setActiveCategories: graph.setActiveCategories,
  getSearchTerm: () => graph.searchTerm,
  setSearchTerm: graph.setSearchTerm,
  getSizeMetric: () => graph.sizeMetric,
  setSizeMetric: graph.setSizeMetric,
  getZoom: () => graph.zoom,
  setZoom: graph.setZoom,
  getWidth: () => graph.width,
  setWidth: graph.setWidth,
  getHeight: () => graph.height,
  setHeight: graph.setHeight,
  getValidEdges: () => graph.validEdges,
  setValidEdges: graph.setValidEdges,
  getTickCount: () => graph.tickCount,
};
