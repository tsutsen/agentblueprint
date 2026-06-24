# Glossary Link Graph

Visualize glossary term relationships and cross-specification references as an interactive force-directed graph.

## Features

- **Force-directed graph** — nodes are glossary terms, edges are related-term links and spec references
- **Category filtering** — toggle term categories (domain, technical, security, ui) on/off
- **Edge type filtering** — toggle related-term links, spec references, and cross-spec links
- **Search** — filter terms by name or ID
- **Node highlighting** — click a term to highlight its connections and dim everything else
- **Detail panel** — see term definition, related terms count, and which specs reference it
- **Draggable nodes** — rearrange the layout by dragging
- **Zoom & pan** — scroll to zoom, drag background to pan
- **Spec nodes** — toggle visibility of specification nodes that connect to terms
- **Labels toggle** — show/hide term labels
- **7 themes** — Default Light, Dark, Gruvbox Dark, Gruvbox Light, Neon Dark, Retro Light, Netrunner

## Quick Start

### Generate graph data

```bash
cd artifacts/glossary-graph
node extract-graph-data.js
```

This reads all `*.json` spec files and `Glossary.json` from the `artifacts/` directory and produces `graph-data.json`.

### Serve the visualization

```bash
npm install
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

### Build for production

```bash
npm run build
```

Output goes to `dist/`. Serve with `npm run preview` or any static file server.

## Architecture

This is a **React shell + Canvas isolate** architecture:

- **React + Vite + shadcn/ui** — sidebar, detail panel, controls, themes (polished UI)
- **D3.js v7 + Canvas 2D** (`public/legacy/`) — force-directed layout, rendering, animations (preserved as-is)
- **Bridge** — `window.__GRAPH_WRAPPER__` exposes minimal API between React and the canvas

The D3 canvas rendering is loaded as native browser ES modules, completely untouched by the React build.

## How it works

1. **`extract-graph-data.js`** scans the glossary and all spec JSON files
2. It extracts `relatedTerms` links from glossary terms
3. It extracts `glossaryRefs` from every spec section (recursively)
4. It builds cross-spec edges showing which specs share glossary references
5. The output `graph-data.json` is consumed by the React app, which passes it to the D3 canvas
6. The canvas runs a force-directed layout (200 ticks, static) and renders at 60fps

## Graph data structure

| Field | Description |
|-------|-------------|
| `nodes[].id` | GL-NNN term ID or SPEC:SpecName |
| `nodes[].term` | Term name |
| `nodes[].category` | domain, technical, security, ui, or spec |
| `nodes[].specRefCount` | How many specs reference this term |
| `nodes[].specs` | List of spec names that reference this term |
| `edges[].type` | relatedTerms, specRef, or crossSpec |
| `edges[].sharedTerms` | (crossSpec only) List of shared GL IDs |
