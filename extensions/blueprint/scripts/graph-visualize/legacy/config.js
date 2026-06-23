// ─── Configuration Constants ───

// Node type colors — read from CSS custom properties for theme support
// Maps type abbreviations to their CSS variable names
const TYPE_VAR_MAP = {
  REQ: '--technical', NFR: '--technical',
  CON: '--ui', FN: '--spec',
  IS: '--security', TST: '--domain',
  GL: '--security', UJ: '--ui',
  US: '--ui', UXAC: '--ui',
  DG: '--technical', SC: '--technical',
  Entity: '--spec', Enum: '--technical',
  API: '--domain', EP: '--security',
  TASK: '--security', ISSUE: '--domain',
  spec: '--spec',
};

let _typeColorCache = new Map();
export function getTypeColor(type) {
  const cssVar = TYPE_VAR_MAP[type];
  if (!cssVar) return null;
  let color = _typeColorCache.get(type);
  if (!color) {
    try {
      color = getComputedStyle(document.documentElement)
        .getPropertyValue(cssVar).trim();
    } catch { /* fallback */ }
    _typeColorCache.set(type, color || '#94a3b8');
  }
  return color || '#94a3b8';
}
export function resetTypeColorCache() {
  _typeColorCache.clear();
}

// Category colors — read from CSS custom properties for theme support
const CAT_VAR_MAP = {
  domain: '--domain', technical: '--technical', security: '--security',
  ui: '--ui', spec: '--spec',
  req: '--technical', nfr: '--technical',
  con: '--ui', fn: '--spec',
  test: '--domain', gl: '--security',
  design: '--ui', data: '--spec',
  api: '--domain', plan: '--security',
  other: null,
};

let _catColorCache = new Map();
export function getCategoryColor(cat) {
  const cssVar = CAT_VAR_MAP[cat];
  if (!cssVar) return '#94a3b8';
  let color = _catColorCache.get(cat);
  if (color === undefined) {
    try {
      color = getComputedStyle(document.documentElement)
        .getPropertyValue(cssVar).trim();
    } catch { /* fallback */ }
    _catColorCache.set(cat, color || '#94a3b8');
  }
  return color || '#94a3b8';
}
export function resetCategoryColorCache() {
  _catColorCache.clear();
}

// Edge color — reads from CSS custom property so it respects themes.
// Cached after first read; call resetEdgeColorCache() after theme switch.
let _edgeColorCache = null;
export function getEdgeColor() {
  if (_edgeColorCache) return _edgeColorCache;
  try {
    const val = getComputedStyle(document.documentElement)
      .getPropertyValue('--edge-color').trim();
    if (val) { _edgeColorCache = val; return val; }
  } catch { /* fallback below */ }
  _edgeColorCache = 'rgba(148, 163, 184, 0.4)';
  return _edgeColorCache;
}
export function resetEdgeColorCache() {
  _edgeColorCache = null;
}


