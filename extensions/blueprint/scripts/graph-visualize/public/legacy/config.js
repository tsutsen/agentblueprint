// ─── Configuration Constants ───

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
