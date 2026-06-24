# Graph Visualization Suite — Agent Handoff

## Overview

This is a **two-tier architecture** for visualizing architecture graphs derived from
AgentBlueprint specification artifacts. It consists of:

1. **Python backend** — builds a unified graph from spec JSON files and computes 10
   architecture quality metrics
2. **JavaScript frontend** — renders the graph as an interactive D3.js canvas visualization
   with filtering, selection, and dynamic node sizing

**Root directory:** `extensions/blueprint/scripts/`

```
scripts/
├── graph_metrics.py              # Python: graph builder + 10 metrics
├── graph-visualize.py            # Python: orchestrator (runs metrics, serves frontend)
├── generate_tests.py             # (unrelated)
├── json_uml_convert.py           # (unrelated)
└── graph-visualize/              # JavaScript frontend (static files, served by HTTP server)
    ├── public/
    │   └── legacy/               # Vanilla D3 canvas (loaded as native ES modules)
    │       ├── graph.js          # Core: force-directed layout, canvas rendering, selection
    │       ├── config.js         # Constants (colors, physics)
    │       ├── graph-wrapper.js  # React ↔ Canvas bridge
    │       ├── bootstrap.js      # Loads D3 + graph modules before React mounts
    │       └── ui.js             # UI helpers
    ├── src/                      # React + shadcn/ui frontend
    │   ├── App.tsx               # Root layout
    │   ├── components/           # React components
    │   ├── lib/                  # Utils, themes
    │   └── index.css             # Tailwind + shadcn base + canvas styles
    ├── extract-graph-data.js     # Node.js data extractor
    ├── graph-data.json           # Generated intermediate output
    ├── package.json              # Vite + React + shadcn dependencies
    ├── vite.config.ts            # Vite configuration
    ├── tsconfig.json             # TypeScript config
    ├── README.md
    └── HANDOFF.md
```

---

## Data Flow

```
Artifacts (JSON specs)
        │
        ▼
┌─────────────────────┐
│  graph_metrics.py   │  ← Python: builds unified graph + computes metrics
│  --dump-graph       │     • Loads 7 spec files (GoalSpec, DesignSpec, etc.)
│                     │     • Resolves node types from ID prefixes + DataSpec
│                     │     • Computes: orphans, traceability, blast radius,
│                     │       risk scores, responsibility load, interface pressure,
│                     │       test density, epic coherence, layer violations,
│                     │       health index
└─────────┬───────────┘
          │ JSON stdout (nodes + edges)
          ▼
┌─────────────────────┐
│ graph-visualize.py  │  ← Python: orchestrator
│ build_graph_data()  │     • Runs graph_metrics.py --dump-graph
│                     │     • Enriches nodes with glossary metadata
│                     │     • Computes degree/centrality/blast/risk metrics
│                     │     • Writes graph-data.json
└─────────┬───────────┘
          │ graph-data.json
          ▼
┌─────────────────────┐
│  graph-visualize/   │  ← JavaScript frontend
│  (browser)          │     • Fetches graph-data.json
│                     │     • D3.js force-directed layout (200 ticks, static)
│                     │     • Canvas 2D rendering (60fps via requestAnimationFrame)
│                     │     • Sidebar filters, search, detail panel
│                     │     • Dynamic node sizing based on selection context
└─────────────────────┘
```

---

## Python Backend

### graph_metrics.py

**Entry:** `python3 graph_metrics.py --artifacts <dir> [--dump-graph] [--format json]`

#### Graph Construction (`load_graph()`)

1. Parses 7 spec JSON files from the artifacts directory:
   - `GoalSpec.json` — REQ, NFR, US, SC nodes + glossary refs
   - `Glossary.json` — GL nodes + relatedTerms edges
   - `ArchitectureSpec.json` — CON nodes + req/nfr/glossary refs
   - `ApiSpec.json` — FN nodes + entity refs + glossary refs
   - `TestSpec.json` — TST nodes + fnRef + glossary refs
   - `DesignSpec.json` — UJ, UXAC, DG nodes + glossary refs
   - `DataSpec.json` — Entity/Enum nodes + relationships + glossary refs

2. Resolves node types via prefix matching (`REQ-` → REQ, `GL-` → GL, etc.)
   and PascalCase entity/enum detection from DataSpec.json.

3. Builds adjacency lists (`adj` = outgoing, `radj` = incoming).

4. Post-processes: ensures all referenced GL IDs have nodes.

#### Metrics (10 total)

| Metric | What it measures | Key logic |
|--------|-----------------|-----------|
| **Orphans** | Nodes disconnected from expected types | REQ→CON, FN→TST, GL→1 spec, CON→REQ |
| **Traceability** | REQ→CON→FN→TST→IS chain completeness | Bidirectional BFS per hop |
| **Blast Radius** | Reachable descendants from REQ/GL nodes | BFS out, count by type |
| **Risk Score** | `(volume × centrality) / (tests + 1)` | Top 10 by risk |
| **Responsibility Load** | REQ/FN/Entity/IS count per component | God component detection (3× mean) |
| **Interface Pressure** | FN count per component / total FNs | Flags > 30% pressure |
| **Test Density** | TST / (FN + REQ) ratio | Per scope or global |
| **Epic Coherence** | Intra-epic vs cross-epic GL edges | Flags coherence < 50% |
| **Layer Violations** | Edges not in ALLOWED_EDGES matrix | 50+ allowed type pairs |
| **Health Index** | Weighted composite (0–100) | 30% coverage + 20% verifiability + 20% traceability + 15% (1-orphan_rate) + 15% layer_ok |

#### Output Formats

- `--dump-graph`: JSON with `{ nodes: [{id, type, label, source}], edges: [{source, target}] }`
- `--format json`: Full metrics report as JSON
- `--format text`: Human-readable report with bars and severity flags

### graph-visualize.py

**Entry:** `python3 graph-visualize.py [artifacts-dir] [--port PORT] [--no-server] [--no-open]`

#### `build_graph_data(artifacts_dir)`

1. Runs `graph_metrics.py --dump-graph` to get raw nodes/edges
2. Loads `Glossary.json` for term metadata
3. Enriches each node with:
   - `term`, `definition`, `category` (from glossary, GL nodes only)
   - `relatedCount` (from glossary relatedTerms)
   - `degree` (computed from all edges)
   - `centrality` (degree / (total_nodes - 1))
   - `blastRadius` (from blast_radius metric)
   - `risk`, `volume`, `tests` (from risk_scores metric)
   - `responsibility`, `interfacePressure` (from component metrics)
   - `isOrphan` (boolean)
4. Writes `graph-data.json` to `graph-visualize/` directory

#### `serve_graph(artifacts_dir, port, no_server, open_browser)`

1. Calls `build_graph_data()`, writes `graph-data.json`
2. Kills any process on the port (lsof/fuser)
3. Starts detached HTTP server serving `graph-visualize/` directory
4. Verifies server is running
5. Optionally opens browser
6. Main process exits; server continues running

---

## JavaScript Frontend

### Architecture

The frontend is a **single-page app** loaded in the browser. It uses:
- **D3.js v7** (CDN) — force-directed layout
- **Canvas 2D API** — custom rendering (not D3 SVG)
- **Lazy-loaded components** — sidebar and canvas HTML loaded via fetch

#### File Responsibilities

| File | Role | Key Functions |
|------|------|--------------|
| `index.html` | Entry point | Loads CSS, D3, JS files |
| `config.js` | Constants | `TYPE_COLORS`, `CATEGORY_COLORS`, `EDGE_COLOR`, physics constants |
| `app.js` | Bootstrap | `initApp()` — loads components, sets up event listeners, fetches data |
| `graph.js` | Core engine | `initGraph()`, `render()`, `getNodeRadius()`, `getNodeAnimatedRadius()`, `startScaleAnimation()`, `scaleValue()`, mouse/zoom, simulation |
| `ui.js` | UI logic | `initUI()`, `selectNode()`, `deselectNode()`, `applyFilters()`, `showDetail()` |

### Global State (graph.js)

```javascript
let graphData = null;       // Full graph-data.json parsed
let validEdges = null;      // Edge list with resolved node references
let selectedNode = null;    // Currently selected node (or null)
let connectedSet = null;    // Set of node IDs in the connected neighborhood
let showLabels = false;     // Toggle label visibility
let activeCategories = Set; // Visible category set
let searchTerm = '';        // Current search string
let zoom = { x, y, k };    // Pan/zoom transform
let sizeRange = { ... };    // Per-metric [min, max] ranges for node sizing
let sizeMetric = 'degree';  // Active sizing metric (from dropdown)
let hoveredNode = null;     // Node under cursor
let currentDim = 1;         // Dim opacity (1 = full, 0.15 = dimmed)
let isDragging = false;     // Whether mouse drag occurred
let isScaleAnimating = false; // Whether scale animation is in progress
let scaleAnimTargets = null;  // Map<nodeId, targetRadius>
let scaleAnimStartRadii = null; // Map<nodeId, startRadius>
const SCALE_ANIM_DURATION = 350; // ms — scale transition duration
```

### Rendering Pipeline

1. **`initGraph()`** — runs once on load
   - Sets up canvas with device pixel ratio scaling
   - Pre-resolves edges to node references
   - Computes initial size ranges from all nodes
   - Runs force-directed layout (200 ticks, then stops)
   - Calls `render()` and sets up event listeners

2. **`render()`** — called every frame during animation, or on interaction
   - Clears canvas, applies zoom/pan transform
   - Computes `connectedSet` from `selectedNode` (if any)
   - Calls `recalcSizeRange()` to update node size ranges
   - Draws edges (dimmed if not connected to selection)
   - Draws nodes (with selection highlighting, hover effects, labels)

3. **`recalcSizeRange()`** — recalculates size ranges based on context
4. **`startScaleAnimation()`** — triggers smooth scale transitions for all visible nodes
5. **`getNodeAnimatedRadius(n)`** — returns the current animated radius (interpolated value)
6. **`scaleAnimStep(now)`** — animation loop step: interpolates radii with ease-out cubic

### Scale Animation

When a selection changes, metric switches, or filters apply, node radii transition smoothly
over ~350ms using an ease-out cubic curve (same curve as the dim animation).

**How it works:**
1. `startScaleAnimation()` captures each visible node's current `_animRadius` as the start value
2. Computes the new target radius via `getNodeRadius(n)` and stores it in `scaleAnimTargets`
3. `scaleAnimStep()` runs every frame, interpolating each node from start → target
4. `getNodeAnimatedRadius(n)` returns `_animRadius` during animation, falling back to `getNodeRadius()` after
5. The animation loop auto-stops when all nodes reach their targets

**Triggered by:**
- `selectNode()` — when a node is selected (connected-set sizing kicks in)
- `deselectNode()` — when selection is cleared (full-range sizing restored)
- Size metric dropdown change — when the user picks a different metric
- `applyFilters()` — when category/search filters change the visible node set
   - Computes `fullRanges` for all visible nodes (sidebar filters applied)
   - If `selectedNode` is set, computes `connectedNodes` and their ranges
   - Sets `sizeRange._connected = true` when in selection mode
   - **Key fix:** When all connected nodes have metric value 0 for a metric,
     sets range to `[0, 0]` so `scaleValue(0, 0, 0)` returns `maxRadius` (30),
     making isolated/zero-value nodes appear at maximum size.

4. **`getNodeRadius(d)`** — computes node radius for a given node
   - Determines `rangeKey` from `sizeMetric` (degree, blast, risk, etc.)
   - Uses connected-set range if node is in `connectedSet` and `_connected` is true
   - Falls back to full visible-set range or default `[0, 1]`
   - Calls `scaleValue(value, minVal, maxVal, 4, 30)` with sqrt scaling

5. **`scaleValue(value, minVal, maxVal, minRadius=4, maxRadius=30)`**
   - If `maxVal === minVal === 0` and `value === 0`: returns `maxRadius` (30)
   - Otherwise: sqrt-scales value from `[minVal, maxVal]` to `[minRadius, maxRadius]`

### Selection System

1. **`selectNode(event, d)`** in `ui.js`:
   - Sets `selectedNode = d`
   - Computes `connectedIds` (for detail panel stats, not used in rendering)
   - Calls `animateDim(0.15)` — fades non-connected nodes over 400ms
   - Opens detail panel via `showDetail(d)`
   - Highlights node in term list

2. **`deselectNode()`** in `ui.js`:
   - Sets `selectedNode = null`
   - Calls `animateDim(1)` — fades back to full opacity
   - Calls `recalcSizeRange()` + `render()` to restore full-range sizing

3. **Rendering-time highlighting** in `render()`:
   - Builds `connectedSet` from `selectedNode`'s neighbors
   - Builds `connectedEdges` set for edge highlighting
   - Non-connected nodes get `ctx.globalAlpha = currentDim` (animated to 0.15)
   - Selected node gets white stroke, connected nodes stay bright

### Size Metric Dropdown

Users can switch the active sizing metric:
- `relatedCount` — glossary related terms count
- `degree` — total edge connections
- `blast` — blast radius (reachable descendants)
- `risk` — risk score
- `centrality` — normalized degree centrality
- `type` — fixed sizes per node type (CON=6, FN=5, REQ=4.5, etc.)

When changed, calls `recalcSizeRange()` + `render()`.

### Filters

- **Category filters** — checkboxes for each `typeCat` (req, con, fn, test, gl, design, data, api, plan, other)
- **Search** — debounced (200ms) text search on `term`, `label`, `id`
- Both call `applyFilters()` which sets `n.visible` on each node, then `render()`

### Themes

6 themes via CSS variables: default, default-light, gruvbox, gruvbox-light, neon-dark, retro-light.
Persisted in `localStorage` as `glossary-theme`.

---

## Node Types & Colors

| Type | Label | Color | Category |
|------|-------|-------|----------|
| REQ | Requirement | #38bdf8 | req |
| NFR | Non-Functional Req | #7dd3fc | req |
| CON | Component | #a78bfa | con |
| FN | Function | #34d399 | fn |
| IS | Integration Test | #fb923c | test |
| TST | Test | #f87171 | test |
| GL | Glossary Term | #fbbf24 | gl |
| UJ | User Journey | #c084fc | design |
| US | User Story | #a78bfa | design |
| UXAC | UX Acceptance Criteria | #8b5cf6 | design |
| DG | Design Goal | #60a5fa | design |
| SC | Screen | #38bdf8 | design |
| Entity | Entity | #4ade80 | data |
| Enum | Enum | #22d3ee | data |
| API | API Endpoint | #f472b6 | api |
| EP | Epic | #facc15 | plan |
| TASK | Task | #f59e0b | plan |
| ISSUE | Issue | #ef4444 | plan |

---

## How to Run

### Quick Start (Python orchestrator — recommended)

```bash
cd /home/leon/Projects/AgentBlueprint
python3 extensions/blueprint/scripts/graph-visualize.py /path/to/artifacts --port 3001
```

This runs graph_metrics.py, builds the enriched graph, writes graph-data.json,
and starts an HTTP server at http://localhost:3001.

### Manual (Python backend + Vite frontend)

```bash
# Generate data
python3 extensions/blueprint/scripts/graph_metrics.py --artifacts /path/to/artifacts --dump-graph > graph-visualize/graph-data.json

# Start frontend dev server
cd extensions/blueprint/scripts/graph-visualize
npm run dev
```

### Legacy (Node.js only, no metrics)

```bash
cd extensions/blueprint/scripts/graph-visualize
node extract-graph-data.js /path/to/artifacts  # generates graph-data.json
node server.js 3001  # legacy server (deprecated, use npm run dev)
```

Note: `extract-graph-data.js` only uses Glossary.json and spec glossaryRefs —
it does NOT build the full architecture graph or compute metrics.

---

## Recent Fixes & Known Issues

### Added: Smooth node scale animation
- **Feature:** Node radii now animate smoothly (~350ms, ease-out cubic) when sizes change
- **Triggers:** node selection, deselection, size metric switch, filter changes
- **Mechanism:** `startScaleAnimation()` captures current radii as start values, computes new targets via `getNodeRadius()`, then `scaleAnimStep()` interpolates each frame
- **Files:** `graph.js` — `startScaleAnimation()`, `scaleAnimStep()`, `getNodeAnimatedRadius()`, `render()` calls `getNodeAnimatedRadius()` instead of `getNodeRadius()`

### Fixed: Dynamic sizing for zero-connection nodes
- **Problem:** When a node with 0 connections was selected, its metrics were all 0,
  and `scaleValue(0, 0, 1)` returned min radius (4) instead of max (30).
- **Fix:** In `recalcSizeRange()`, when all connected nodes have metric value 0,
  set range to `[0, 0]` instead of `[0, 1]`. In `scaleValue()`, handle
  `maxVal === minVal === 0` by returning `maxRadius`.
- **Files:** `graph.js` — `recalcSizeRange()`, `scaleValue()`

### Debug logging
All `console.log` statements have been removed. Only `console.error` calls remain for actual error handling in `graph.js`.

### Known limitations
1. **Static layout** — force-directed simulation runs 200 ticks once at init,
   then stops. `toggleSimulation()` can re-run it but it auto-stops after 3s.
2. **No edge labels** — edge types are not displayed on the canvas.
3. **Detail panel incomplete** — shows basic stats but not full metric details
   (blast radius, risk, etc.) or connected node list.
4. **No hot reload for legacy canvas** — changes to `public/legacy/*.js` require
   browser hard-refresh (Ctrl+Shift+R). React code hot-reloads normally via Vite.
5. **Canvas hit detection** — uses squared distance with `+5` padding; may miss
   very small nodes when zoomed out.

---

## Extension Points

### Adding a new sizing metric
1. Add to `sizeMetric` dropdown in `canvas.html`
2. Add `rangeKey` mapping in `getNodeRadius()` (if not already covered)
3. Add `nodeKey` mapping in `recalcSizeRange()` `_metrics` array
4. Add `value` mapping in `getNodeRadius()` value extraction section

### Adding a new node type
1. Add prefix pattern in `graph_metrics.py` → `node_type()` function
2. Add display info in `graph-visualize.py` → `TYPE_INFO` dict
3. Add color in `config.js` → `TYPE_COLORS`
4. Add size in `getNodeRadius()` → `typeSizes` map (for `sizeMetric === 'type'`)

### Adding a new metric computation
1. Add function in `graph_metrics.py` (follow existing pattern)
2. Call it in `main()` and add to `results` dict
3. In `graph-visualize.py` → `build_graph_data()`, extract from metrics_data
4. Add to node enrichment in the `nodes` loop
5. Add to frontend: `sizeMetric` dropdown option, `rangeKey` mapping, `nodeKey` mapping

### Adding edge types
1. Add in `graph_metrics.py` → `ALLOWED_EDGES` set
2. In `graph-visualize.py` → `edges[].type` from edge data
3. In `config.js` → edge color
4. In `graph.css` → legend styles
5. In `graph.js` → edge rendering with type-specific styling

---

## File Map for Reference

```
Python Backend:
  graph_metrics.py          Lines ~1-100:    Node type registry, Graph class
                            Lines ~100-300:  load_graph() — spec parsing
                            Lines ~300-500:  Metrics functions
                            Lines ~500-700:  Report formatting
                            Lines ~700-end:  main() CLI entry point

  graph-visualize.py        Lines ~1-50:     Imports, debug helper
                            Lines ~50-150:   run_graph_metrics(), load_glossary()
                            Lines ~150-250:  collect_spec_refs(), _extract_glossary_refs()
                            Lines ~250-450:  build_graph_data() — the core pipeline
                            Lines ~450-550:  write_graph_data(), kill_port()
                            Lines ~550-end:  serve_graph(), CLI entry point

JavaScript Frontend:
  graph.js                  Lines ~1-30:     Global state declarations
                            Lines ~30-40:      scaleValue() — radius scaling
                            Lines ~40-130:     initGraph() — setup + layout
                            Lines ~130-190:    recalcSizeRange() — dynamic sizing
                            Lines ~190-280:    render() — canvas draw loop
                            Lines ~280-320:    drawGrid() — background grid
                            Lines ~320-430:    Mouse/zoom event handlers
                            Lines ~430-500:    getNodeRadius() — per-node radius
                            Lines ~500-560:    toggleSimulation(), animateDim()

  ui.js                     Lines ~1-100:    initUI() — sidebar, filters, dropdowns
                            Lines ~100-150:    applyFilters() — category + search
                            Lines ~150-170:    resetZoom(), toggleLabels()
                            Lines ~170-220:    selectNode(), deselectNode(), showDetail()

  app.js                    Lines ~1-30:     loadComponent() — HTML fragment loader
                            Lines ~30-100:     initApp() — bootstrap + event listeners
                            Lines ~100-130:    loadGraphData() — fetch + init

  config.js                 Lines ~1-30:     TYPE_COLORS, CATEGORY_COLORS
                            Lines ~30-40:      EDGE_COLOR, physics constants
```

---

## Quick Reference: Key Interactions

| Action | Effect |
|--------|--------|
| Click node | Select → highlight neighbors, dim others, show detail panel, recalc sizes |
| Click empty space | Deselect → restore full view |
| Press Escape | Deselect |
| Scroll | Zoom in/out |
| Drag background | Pan |
| Drag node | Reposition (physics disabled) |
| Toggle category | Show/hide node types |
| Search | Filter by name/ID |
| Change size metric | Recalculate node sizes based on new metric |
| Toggle simulation | Re-run force layout for 3 seconds |
| Toggle labels | Show/hide node labels |
| Change theme | Switch CSS theme (persisted) |
| Click term list item | Select node |

---

## Debugging Tips

1. **Console logging** — check browser console for `[RECALC]` and `[RADIUS]` logs
   when debugging sizing issues.

2. **Force re-render** — call `render()` from console after state changes.

3. **Check node data** — `graphData.nodes[0]` in console shows full node object
   with all enriched metrics.

4. **Clear cache** — hard-refresh (Ctrl+Shift+R) after JS changes.

5. **Python output** — stderr shows `[DEBUG]` messages from graph-visualize.py.

6. **Port conflicts** — previous server processes may linger; kill them manually
   or wait for auto-cleanup.
