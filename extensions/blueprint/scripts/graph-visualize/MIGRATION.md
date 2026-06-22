# shadcn/ui Migration Strategy

## Current Architecture

| Layer | Technology |
|-------|-----------|
| UI | Vanilla JS, hand-built HTML/CSS components |
| Graph | D3.js v7 (force-directed, Canvas 2D) |
| Styling | CSS custom properties (`:root` vars), 5 theme CSS files |
| Build | None — served raw via `node server.js` |
| Components | Inline HTML in `index.html`, custom `<details>` dropdowns |

**What's working well and should stay:**
- D3 force-directed layout + Canvas rendering (graph.js ~700 lines, battle-tested)
- Progressive label disclosure system (spatial grid, hysteresis)
- Scale/dim animation engine
- Data extraction pipeline (`extract-graph-data.js`)
- Graph data format (`graph-data.json`)

**What's being replaced:**
- Sidebar (category filters, search, node list)
- Detail panel (node info overlay)
- Canvas controls (zoom reset, simulate, size metric dropdown, theme dropdown)
- Loading/error overlays
- All 5 theme CSS files + `graph.css` UI chrome styles
- URL state sync logic (rewrite in React hooks)

---

## Architecture Decision: React Shell + Canvas Isolation

### Recommendation: **Vite + React + shadcn/ui, Canvas preserved as-is**

The D3 canvas rendering in `graph.js` is the core intellectual property of this tool. Rewriting it to an SVG-based or React-Fullscreen approach would be high-risk with little visual benefit. Instead:

```
┌─────────────────────────────────────────────────────┐
│ React App (Vite + shadcn/ui)                        │
│                                                     │
│  ┌──────────┐  ┌────────────────────────────────┐   │
│  │ Sidebar  │  │ Canvas Container               │   │
│  │ (shadcn) │  │ (vanilla D3 Canvas, isolated)  │   │
│  │          │  │                                │   │
│  │ - Search │  │  ┌──────────────────────────┐  │   │
│  │ - Filters│  │  │ D3 Canvas (graph.js)     │  │   │
│  │ - Node   │  │  │                          │  │   │
│  │   List   │  │  │ ┌──────────────────────┐ │  │   │
│  │          │  │  │ │ Detail Sheet         │ │  │   │
│  │          │  │  │ │ (shadcn Sheet)       │ │  │   │
│  │          │  │  │ └──────────────────────┘ │  │   │
│  │          │  │  │                          │  │   │
│  └──────────┘  │  │ Controls (shadcn bar)    │  │   │
│                │  └──────────────────────────┘  │   │
│  ┌──────────┐  └────────────────────────────────┘   │
│  │ Toast/   │                                       │
│  │ Loading  │                                       │
│  └──────────┘                                       │
└─────────────────────────────────────────────────────┘
```

### Why this approach:

1. **Zero risk to graph rendering** — `graph.js` stays as a vanilla module
2. **Minimal state bridging** — only ~6 values flow React ↔ Canvas (see below)
3. **Best of both worlds** — polished shadcn UI + battle-tested D3 canvas
4. **Theming via Tailwind CSS variables** — shadcn's built-in theming replaces the 5 theme files

### Canvas isolation via `useRef` + `useEffect`

The canvas is mounted into a React `<div ref>` and initialized/teardown via effects. Communication is one-way React→Canvas for commands, and Canvas→React for selection events.

---

## State Bridge: React ↔ Canvas

Minimal bidirectional bridge — avoid coupling:

```typescript
// Canvas exposes this interface
interface GraphBridge {
  // React calls these to command the canvas
  setVisibility(nodeIds: Set<string>): void;
  setSizeMetric(metric: 'degree' | 'blast' | 'risk'): void;
  resetZoom(): void;
  simulate(): void;

  // Canvas calls these to report events
  onNodeSelect: (node: GraphNode) => void;
  onNodeDeselect: () => void;
}
```

**React state that drives the canvas:**
- `activeCategories` → `setVisibility()`
- `searchTerm` → `setVisibility()`
- `sizeMetric` → `setSizeMetric()`

**Canvas events that drive React UI:**
- node click → show shadcn `Sheet` (detail panel)
- node deselect → close `Sheet`

---

## Component Mapping

| Current (vanilla) | shadcn/ui replacement | Notes |
|---|---|---|
| `#sidebar` (div) | `Sheet` (side=left) or fixed `<aside>` | Sheet is dismissable; fixed aside is more graph-tool-like |
| `#search-input` | `Input` + `Search` icon (Lucide) | |
| Category checkboxes | `Checkbox` + `Popover` for overflow | |
| `#term-list` | `ScrollArea` + custom list items | |
| `<details>` dropdowns | `DropdownMenu` | Direct replacement |
| `#detail-panel` | `Sheet` (side=right) | Slide-in panel, accessible |
| `#controls` buttons | `Button` variants | |
| Theme switcher | `DropdownMenu` inside `DropdownMenu` (Settings) | |
| Loading spinner | `Skeleton` + `Spinner` (custom) | |
| Error overlay | `AlertDialog` or `Toast` | |
| All theme CSS files | Tailwind CSS variables (`@theme`) | shadcn's native theming |

### Recommended component list to install:

```bash
npx shadcn@latest add button checkbox dropdown-menu input popover scroll-area sheet skeleton toast separator badge
```

Plus Lucide icons: `search`, `x`, `rotate-ccw`, `play`, `settings`, `zoom-in`, `zoom-out`

---

## Theming Strategy

### Current: 5 separate CSS files with `:root` variable overrides

### New: shadcn's CSS variable theming (single source of truth)

shadcn/ui uses CSS variables on `:root` mapped to Tailwind semantic tokens:

```css
@theme {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  /* ... standard shadcn tokens ... */
}
```

**Migration plan for themes:**
1. Convert the 5 existing themes to shadcn's CSS variable format
2. Store theme configs as JS objects (OKLCH values)
3. Switch themes by setting CSS variables on `document.documentElement`
4. The D3 canvas already reads `--edge-color` from computed styles — keep this pattern
5. Node type colors (`TYPE_COLORS` in config.js) stay as-is — they're data-driven, not UI theming

**Preserve the existing color palettes** — just reformat the variable names.

---

## Current Progress

### Phase 1: Scaffold ✅ DONE
- Vite + React + TypeScript + Tailwind CSS v3 scaffolded
- 12 shadcn/ui components created manually (Badge, Button, Checkbox, DropdownMenu, Input, Label, Popover, ScrollArea, Separator, Sheet, Skeleton, Toast)
- TypeScript path aliases configured (`@/*` → `src/*`)
- App.tsx layout skeleton with Sidebar, Canvas, Controls, Detail Panel, Search
- Legacy files preserved in `legacy/` directory
- Build passes cleanly

### Phase 2: Canvas Bridge ✅ DONE
- **Strategy**: Native browser ES modules via `public/legacy/`
  - `graph.js`, `config.js`, `graph-wrapper.js` moved to `public/legacy/`
  - `bootstrap.js` loads D3 from CDN + graph modules before React mounts
  - `window.__GRAPH_WRAPPER__` exposes getter/setter functions for mutable state
- **Why this approach**: Both Vite 8 (rolldown) and Vite 7 dev server (esbuild) enforce strict ESM immutability on `let` exports. By loading graph.js as a native browser ES module, the `let` reassignments work naturally.
- GraphCanvas.tsx uses `window.__GRAPH_WRAPPER__` via `useEffect` + `ResizeObserver`
- `IGraphBridge` interface provides typed bridge to React shell
- Critical canvas CSS extracted from `legacy/graph.css` into `src/index.css`
- Build and dev server both pass cleanly

**Key decisions:**
- Downgraded Vite 8 → Vite 7 (rollup bundler) — Vite 8 uses rolldown which has no escape hatch for ESM immutability
- Native browser ES modules for legacy code — avoids bundler analysis entirely
- `graph.js` remains completely untouched — no modifications needed

### Phase 3: Sidebar & Controls ✅ DONE
- [x] Graph renders correctly via blob URL loader + bridge
- [x] Debounced search (250ms) → `setVisibility()`
- [x] Category filters → `activeCategories` → `setVisibility()`
- [x] Node list (click → `selectNodeById()` → detail panel)
- [x] Controls wired: zoom reset, simulate toggle, size metric dropdown
- [x] Labels toggle fixed (stale closure) + Specs toggle added
- [x] `selectNodeById` fires `onNodeSelect` callback for detail panel
- [x] `deselectNode` fires `onNodeDeselect` callback to close detail panel
- [x] End-to-end tested: canvas click, sidebar click, search, filters

### Phase 4: Detail Panel & Controls Polish ✅ DONE
- [x] Detail panel replaced `Sheet` → non-modal fixed panel (canvas remains interactive)
- [x] Close button (X) on detail panel
- [x] Keyboard shortcut: Escape to deselect
- [x] Keyboard shortcut: K to focus search
- [x] Zoom in/out buttons (+/−) added
- [x] Simulation state indicator ("Running" vs "Simulate")
- [x] Theme switcher wired — 5 themes (Default Light, Dark, Gruvbox, Neon, Retro)
- [x] `src/lib/themes.ts` — theme definitions with hex→HSL conversion
- [x] `applyTheme()` sets shadcn CSS variables + canvas-specific edge colors

---

## Implementation Phases

### Phase 1: Scaffold (1-2 hours)

- [ ] `npm create vite@latest . -- --template react` (or parallel `ui/` directory)
- [ ] Install shadcn/ui: `npx shadcn@latest init`
- [ ] Add required components via `npx shadcn@latest add ...`
- [ ] Configure Tailwind with shadcn's CSS variable approach
- [ ] Move existing files to `legacy/` subdirectory for reference
- [ ] Copy `graph-data.json`, `config.js`, `extract-graph-data.js`, `server.js` unchanged

### Phase 2: Canvas Bridge (1-2 hours)

- [ ] Create `lib/graph-bridge.ts` — wrapper around `graph.js` exposing the minimal interface
- [ ] Create `components/GraphCanvas.tsx` — `<div>` ref + `useEffect` to init/teardown canvas
- [ ] Wire `onNodeSelect`/`onNodeDeselect` to React state
- [ ] Verify canvas renders correctly inside React

### Phase 3: Sidebar (1 hour)

- [ ] `components/Sidebar.tsx` with:
  - `Input` for search
  - `Checkbox` list for category filters
  - `ScrollArea` for node list
- [ ] Wire search + filter state to `graphBridge.setVisibility()`
- [ ] URL state sync via `useSearchParams`

### Phase 4: Detail Panel (30 min)

- [ ] `components/DetailPanel.tsx` using `Sheet` (side=right)
- [ ] Display node info: name, category badge (`Badge`), stats
- [ ] Connections list with click-to-navigate

### Phase 5: Controls (30 min)

- [ ] Top control bar with `Button` components
- [ ] `DropdownMenu` for size metric selector
- [ ] `DropdownMenu` for theme selector
- [ ] Reset zoom + simulate buttons

### Phase 6: Polish (1 hour)

- [ ] Loading state with `Skeleton` overlays
- [ ] Error handling with `Toast`
- [ ] Keyboard shortcuts (k for search, escape to deselect)
- [ ] Responsive adjustments (collapsible sidebar on mobile)
- [ ] Convert theme files to shadcn variable format
- [ ] Remove `legacy/` files

### Phase 7: Dev Server (15 min)

- [ ] Replace `server.js` with `npm run dev` (Vite dev server)
- [ ] Update `package.json` scripts
- [ ] Update `README.md` and `HANDOFF.md`

---

## File Structure After Migration

```
graph-visualize/
├── package.json              # Vite + React + shadcn dependencies
├── vite.config.js            # Vite configuration
├── tailwind.config.js        # Tailwind + shadcn theme
├── postcss.config.js         # PostCSS for Tailwind
├── index.html                # Vite entry point
├── tsconfig.json             # TypeScript config
│
├── src/
│   ├── main.tsx              # React entry
│   ├── App.tsx               # Root layout: Sidebar + Canvas + Sheets
│   ├── lib/
│   │   ├── graph-bridge.ts   # Canvas ↔ React bridge
│   │   └── utils.ts          # shadcn cn() helper
│   ├── hooks/
│   │   ├── use-graph.ts      # Graph commands hook
│   │   ├── use-filters.ts    # Category + search state
│   │   └── use-theme.ts      # Theme switching
│   ├── components/
│   │   ├── ui/               # shadcn components (auto-generated)
│   │   ├── GraphCanvas.tsx   # Canvas wrapper
│   │   ├── Sidebar.tsx       # Filters + search + node list
│   │   ├── DetailPanel.tsx   # shadcn Sheet for node details
│   │   ├── ControlBar.tsx    # Zoom, simulate, metric, theme
│   │   └── CategoryFilter.tsx
│   └── styles/
│       ├── index.css         # Tailwind + shadcn base + theme vars
│       └── themes.ts         # Theme color definitions (JS objects)
│
├── graph-data.json           # Unchanged
├── extract-graph-data.js     # Unchanged
├── config.js                 # TYPE_COLORS, CATEGORY_COLORS (unchanged)
├── graph.js                  # D3 canvas rendering (unchanged, loaded as vanilla module)
├── README.md
└── HANDOFF.md
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Canvas z-index conflicts with shadcn Sheets/Popovers | High | Explicit z-index layering; canvas container gets `z-0`, overlays get `z-50+` |
| Tailwind CSS variable theming breaks existing D3 color reads | Medium | Keep `--edge-color` CSS var; test `getEdgeColor()` after migration |
| Node type colors not Tailwind-aware | Low | They're hardcoded hex in config.js — no change needed |
| Performance regression from React re-renders | Medium | Canvas is isolated from React render tree; `React.memo` on expensive components |
| Loss of keyboard navigation | Low | shadcn components are Radix-based — fully accessible by default |
| Build step complexity | Low | Vite is trivial; `npm run dev` replaces `node server.js` |

---

## What NOT to change

- **`graph.js`** — Canvas rendering, force simulation, animations, label disclosure
- **`config.js`** — TYPE_COLORS, CATEGORY_COLORS, edge color logic
- **`graph-data.json`** — Data format
- **`extract-graph-data.js`** — Data pipeline

These files are loaded as vanilla ES modules and work through the bridge. Do not attempt to "React-ify" the graph rendering — it's the least likely part to have bugs and the most expensive to rewrite.
