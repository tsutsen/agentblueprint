# Handoff: Blast Radius Sizing Regression

## Symptom
When "Blast Radius" is selected as the size metric (no node selected), **all nodes with `blastRadius: 0` render at maximum size (~30px radius)** while nodes with high blast values (12-21) render tiny. The sizing is effectively **inverted**.

This is **not** present in the legacy vanilla version — it appears only in the shadcn migration.

## Data
- 571 total nodes, **457 have `blastRadius: 0`** (80%), 114 have values 1-21
- The `SIZE_METRIC_KEYS` mapping is correct: `blast → blastRadius`
- `recalcSizeRange` filters out 0 values for the full range: `[0, Math.max(...nonZeroValues)]` → should be `[0, 21]`
- With range `[0, 21]`, `scaleValue(0, 0, 21, 4, 30)` should return `~4` (min radius), but blast=0 nodes are huge

## What's NOT the cause
- **Bridge flow is correct**: `setSizeMetric('blast')` → `recalcSizeRange()` → `startScaleAnimation()` → `renderGraph()`
- **graph.js is unchanged** from legacy (diff shows only setter functions added, no logic changes)
- **`recalcSizeRange()` is identical** between `legacy/graph.js` and `public/legacy/graph.js`
- **Not the connected-set bug**: user confirmed this happens with **no node selected**, so `sizeRange._connected` should be `false` and all nodes use the full range

## Suspected areas (requires inspecting graph.js)
1. **`sizeRange._fullRanges` not being set** in some code path, causing `getNodeRadius` to fall back to stale/wrong values
2. **`scaleValue` receiving swapped min/max** from some edge case in range computation
3. **Animation state** (`_animRadius`) retaining stale values from a previous metric and not converging
4. **`visible` flag** set incorrectly by the bridge's `setVisibility()`, causing `recalcSizeRange` to compute ranges from a filtered subset

## Commands to debug
```js
// In browser console after loading the graph:
// Check current size ranges
console.log(sizeRange);
console.log(sizeRange._fullRanges);
console.log(sizeRange._connected);

// Check what range a specific node uses
const node = graphData.nodes.find(n => n.blastRadius === 20);
console.log('node radius:', getNodeRadius(node), 'blast:', node.blastRadius);
```

## Constraint
User explicitly said: **don't edit `graph.js` without permission**. Any fix that requires changes to `recalcSizeRange`, `getNodeRadius`, or `scaleValue` needs approval first.
