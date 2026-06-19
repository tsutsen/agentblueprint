// ─── Configuration Constants ───

// Node type colors (new format - full architecture graph)
const TYPE_COLORS = {
  REQ: '#38bdf8', NFR: '#7dd3fc',
  CON: '#a78bfa', FN: '#34d399',
  IS: '#fb923c', TST: '#f87171',
  GL: '#fbbf24', UJ: '#c084fc',
  US: '#a78bfa', UXAC: '#8b5cf6',
  DG: '#60a5fa', SC: '#38bdf8',
  Entity: '#4ade80', Enum: '#22d3ee',
  API: '#f472b6', EP: '#facc15',
  TASK: '#f59e0b', ISSUE: '#ef4444',
  spec: '#34d399',
};

// Category colors (legacy glossary format)
const CATEGORY_COLORS = {
  domain: '#f472b6',
  technical: '#38bdf8',
  security: '#fbbf24',
  ui: '#a78bfa',
  spec: '#34d399',
  req: '#38bdf8', nfr: '#7dd3fc',
  con: '#a78bfa', fn: '#34d399',
  test: '#f87171', gl: '#fbbf24',
  design: '#c084fc', data: '#4ade80',
  api: '#f472b6', plan: '#facc15',
  other: '#94a3b8',
};

const EDGE_COLORS = {
  relatedTerms: 'rgba(100, 110, 160, 0.25)',
  specRef: 'rgba(56, 189, 248, 0.15)',
  crossSpec: 'rgba(251, 191, 36, 0.15)',
  architecture: 'rgba(148, 163, 184, 0.15)',
};

// Drag physics constants
const DRAG_FRICTION = 0.6;
const DRAG_SMOOTHING = 0.3;
const SETTLE_FRICTION = 0.8;
