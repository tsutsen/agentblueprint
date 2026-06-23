# Graph Visualization — Simplification Analysis

**File:** `legacy/graph.js` (~750 lines, 32 KB)
**Date:** 2026-06-23
**Status:** Issue #4 (console.log removal) resolved — June 23, 2026

---

## 1. Dead / No-op Code

| Code | Location | Simplification |
|------|----------|----------------|
| `onClick` handler | `graph.js:368` | Pure no-op — comment says "Handled in onMouseUp". **Delete entirely.** |
| `_pendingNodeId` | `ui.js:14` | Declared, `_pendingNodeId = loadURLState()` is called, but **never used**. **Delete.** |
| `DRAG_FRICTION`, `DRAG_SMOOTHING`, `SETTLE_FRICTION` | `config.js:42-44` | Exported but **never imported or used** anywhere. **Delete.** |
| `isSimulating` flag | `graph.js` | Declared but **never read or written** (the real state is in `simulation` variable). **Delete.** |

---

## 2. Redundant Animation Systems

There are **two separate `requestAnimationFrame` loops** that both call `render()` every frame:

- **`startScaleAnimation()` / `scaleAnimStep()`** — animates node radii (350ms, ease-out cubic)
- **`animateDim()`** — animates the dim opacity (400ms, ease-out cubic)

Both use the exact same easing curve (`1 - Math.pow(1-progress, 3)`). They can be merged into a **single unified animation engine** that tracks all active animations in a map and drives one `rAF` loop. This eliminates the risk of both loops running simultaneously and double-calling `render()`.

---

## 3. Overly Complex Connected-Set / Size Range Logic

`recalcSizeRange()` (100+ lines) has duplicated logic for connected vs. full-set cases:
- `_connected` / `_fullRanges` dual-state tracking
- `sizeRange._connected === true` with zero-value special-casing that returns `maxRadius`
- The same metrics loop runs twice in different branches

**Simplify**: Compute one set of ranges. When a node is selected, compute connected ranges from `connectedSet`. Use a single `sizeRange` object with computed `min`/`max` properties. The zero-value special case is an edge case that could be handled in `scaleValue()` directly.

---

## 4. Debug `console.log` Statements ✅ **RESOLVED**

All 12 `console.log` statements have been **removed** from the render path:
- `buildLabelSet()` — removed zoom/candidates/labelSet logging
- `recalcSizeRange()` — removed connected set and visible count logging
- `getNodeRadius()` — removed radius calculation logging
- `ui.js` — removed size metric and filter logging
- `app.js` — removed graph data load logging
- `public/legacy/graph.js` — same 8 removals applied

Legitimate `console.error` calls for genuine error conditions were preserved.

---

## 5. `initGraph()` Does Too Much

`initGraph()` (120+ lines) handles:
1. Canvas setup
2. Edge pre-resolution (converting string IDs to node objects)
3. Size range initialization
4. Static force-directed layout (200 ticks!)
5. Event listener registration
6. Initial render
7. Loading overlay removal

**Simplify**: Split into `initCanvas()`, `initLayout()`, `initEvents()`. The 200-tick static layout is expensive for large graphs — consider reducing to 100 or making it configurable.

---

## 6. `settleAfterDrag()` Tick Cap Hack

The 60-tick hard cap is implemented by monkey-patching `simulation.tick` with a closure that increments a counter. This is fragile.

**Simplify**: Use `simulation.alpha(0.15).alphaDecay(0.15)` with higher decay so it naturally cools faster, or use a `setTimeout` to call `simulation.stop()` after a fixed duration instead of the tick-counting hack.

---

## 7. `SIZE_METRIC_KEYS` Mapping Is Unnecessary

```js
const SIZE_METRIC_KEYS = {
  degree: 'degree',        // same key
  blast: 'blastRadius',    // different
  risk: 'risk',            // same
  centrality: 'centrality', // same
  responsibility: 'responsibility',
  interfacePressure: 'interfacePressure',
};
```

4 out of 6 map to themselves. **Simplify**: Use inline logic or a shorter map. Better yet, normalize the node data so the property names match the metric names directly.

---

## 8. Type-Based Size Lookup Is a Magic Dictionary

```js
const typeSizes = {
  CON: 6, FN: 5, REQ: 4.5, NFR: 4.5, US: 4.5,
  SC: 4, Entity: 4, GL: 3.5, TST: 2.5, Enum: 2.5,
  API: 4, EP: 5, TASK: 3, ISSUE: 4, DG: 3, UJ: 4,
  UXAC: 4, IS: 4, spec: 5,
};
const value = typeSizes[d.type] || 1;
return scaleValue(value, 1, 6, 8, 40);
```

This 20-entry magic dictionary with hardcoded sizes could be replaced by a type-to-category mapping + category-to-size mapping, making it easier to maintain.

---

## 9. Label Placement — `console.log` in Every Rebuild ✅ **RESOLVED**

Removed — covered by the comprehensive console.log cleanup in #4.

---

## 10. `startScaleAnimation()` Recomputes Everything

`startScaleAnimation()` independently recomputes `connectedSet`, calls `recalcSizeRange()`, and calls `buildLabelSet()` — all of which `render()` also does. When called from `selectNode()` → `startScaleAnimation()`, then each `scaleAnimStep` frame calls `render()` which does the same work again.

**Simplify**: `startScaleAnimation()` should only capture start/target radii and kick off the animation. Let `render()` handle connected-set computation, size range recalculation, and label building. This eliminates the duplicate work.

---

## 11. `public/legacy/graph-wrapper.js` Is a Thin Re-export

The wrapper just re-exports every function from `graph.js` with getter/setter wrappers for mutable state. It adds ~60 lines of boilerplate. Consider whether this indirection is worth it or if the React component could access the module exports directly.

---

## 12. CSS Theme System

Five separate CSS files (`theme-default-light.css`, `theme-gruvbox.css`, etc.) with disabled/enabled stylesheet toggling is brittle. **Simplify**: Use CSS custom properties on `:root` and toggle a single class on `<body>` (e.g., `<body class="theme-gruvbox">`). One CSS file with all themes as class-scoped overrides.

---

## Summary — Highest-Impact Simplifications

| Priority | Change | Impact |
|----------|--------|--------|
| ~~**1**~~ ✅ | Merge the two animation systems into one | Eliminates double-rAF, prevents double-render |
| ~~**2**~~ ✅ | Move connected-set/size-range out of `startScaleAnimation()` into `render()` only | Eliminates duplicate computation per frame |
| ~~**3**~~ ✅ | Simplify connected-set / size-range logic | Removed `_connected`/`_fullRanges` dual-state; single `sizeRange` with `{min, max}`; eliminated 40+ lines |
| **4** | Delete dead code (`onClick`, `_pendingNodeId`, unused config, `isSimulating`) | ~20 lines, dead weight |
| **5** ✅ | Split `initGraph()` into smaller functions | Better testability, readability |

---

## 5. `initGraph()` Does Too Much — ✅ **RESOLVED**

Split `initGraph()` into four focused functions:

| Function | Responsibility |
|----------|---------------|
| `initCanvas()` | Canvas sizing, DPI scaling, context setup. Returns `false` on missing canvas. |
| `initLayout(maxStaticTicks?)` | Edge pre-resolution, size range init, circular node placement, static force-directed layout. |
| `initEvents()` | Registers `mousedown`, `mousemove`, `mouseup`, `wheel` listeners. |
| `initGraph(options?)` | Orchestrator — calls the three above, then `render()` and hides the loading overlay. |

**Additional improvements:**
- Static layout ticks reduced from 200 → 100 (configurable via `options.staticLayoutTicks`)
- Removed duplicate `render()` call that was in the original
- `initCanvas()` returns a boolean so `initGraph()` can bail early on missing canvas
- Backward compatible — `initGraph()` with no args works exactly as before
- TypeScript compiles cleanly, ESLint passes, `vite build` succeeds

---

## 3. Overly Complex Connected-Set / Size Range Logic — ✅ **RESOLVED**

Simplified `recalcSizeRange()` and `getNodeRadius()` to use a single `sizeRange` object with `{ min, max }` properties per metric, eliminating the `_connected` flag and `_fullRanges` backup dictionary.

**Changes:**

| Before | After |
|--------|-------|
| `sizeRange[rangeKey] = [0, maxVal]` (array) | `sizeRange[rangeKey] = { min: 0, max: maxVal }` (object) |
| `sizeRange._connected` flag | Removed — active range is always in `sizeRange[rangeKey]` |
| `sizeRange._fullRanges` backup dict | Removed — full ranges computed on demand in `recalcSizeRange()` |
| `SIZE_METRIC_KEYS` with 6 entries | `SIZE_METRIC_KEYS = { blast: 'blastRadius' }` (only 1 non-trivial mapping) |
| `getNodeRadius()` had 3-way range lookup | Single lookup: `sizeRange[rangeKey]` |
| ~60 lines in `recalcSizeRange()` | ~50 lines — cleaner branching, no duplicated metrics loop |

**How it works now:**
1. `recalcSizeRange()` computes full visible-set ranges first
2. If a node is selected, it computes connected-set ranges and overwrites `sizeRange` entries
3. If no selection (or all neighbors filtered), full ranges are restored
4. `getNodeRadius()` simply reads `sizeRange[rangeKey]` — always the correct active range
5. The zero-value special case (`{min:0, max:0}` → `maxRadius`) is handled by `scaleValue()` directly

**Benefits:**
- No stale state — `sizeRange` always reflects the current selection context
- No dual-state tracking (`_connected` / `_fullRanges`)
- `getNodeRadius()` is 15 lines shorter with no conditional branching on range source
- `vite build` succeeds cleanly
| **6** | Replace theme CSS files with single file + class toggling | One file instead of five, less brittle |
| **7** | Replace `settleAfterDrag` tick cap with `setTimeout` | Simpler, less fragile |
| ~~**8**~~ ✅ | Replace `SIZE_METRIC_KEYS` with inline logic | 6 lines → 1 line (merged into #3 resolution) |
