import { useRef, useEffect, useState, useImperativeHandle } from 'react'
import * as d3 from 'd3'
import { themes } from '@/lib/themes'
import { SIZE_METRICS } from '@/lib/metrics'
import { hashToIndex, scaleValue } from '@/lib/utils'
import type { GraphNode, GraphEdge, GraphData, SizeRangeMap } from '@/lib/graph-types'

// ─── Bridge Interface ───
export interface IGraphBridge {
  // ── Visibility (parent commands) ──
  setVisibility(visibleIds: Set<string>): void
  setSearchTerm(term: string): void

  // ── Theme (graph manages, parent syncs via bridge) ──
  getTheme(): string
  setTheme(theme: string): void
  updateTheme(): void

  // ── Size metric (graph manages, parent syncs via bridge) ──
  getSizeMetric(): string
  setSizeMetric(metric: string): void

  // ── Labels (graph manages, parent syncs via bridge) ──
  getLabels(): boolean
  setLabels(show: boolean): void

  // ── Simulation (graph manages, parent syncs via bridge) ──
  isSimulating(): boolean
  startSimulation(): void
  stopSimulation(): void
  tighten(): void

  // ── Selection (parent commands, canvas fires events) ──
  selectNodeById(id: string): void
  deselectNode(): void
  getSelectedNode(): GraphNode | null

  // ── Zoom ──
  zoomIn(): void
  zoomOut(): void
  resetZoom(): void
  getZoom(): { x: number; y: number; k: number }

  // ── Render ──
  triggerRender(): void
}

// ─── Props ───
export interface GraphCanvasProps {
  data: GraphData
  bridgeRef?: React.Ref<IGraphBridge | null>
  onNodeSelect?: (node: GraphNode) => void
  onNodeDeselect?: () => void
  className?: string
}


// ─── Constants ───
const LABEL_MIN_ZOOM = 0.5
const LABEL_MAX_ZOOM = 2.0
const LABEL_NODE_RADIUS_THRESHOLD = 8
const LABEL_CHAR_WIDTH = 0.62
const LABEL_PAD_X = 4
const LABEL_HYSTERESIS = 0.2
const ANIM_DURATION = 400
const HOVER_LABEL_DELAY = 300

// ─── Helpers ───
function getNodeColor(n: GraphNode, colors: Record<string, string>): string {
  const cssVar = `--node-color-${n._colorIdx}`
  return colors[cssVar] || '#94a3b8'
}

function getEdgeColor(colors: Record<string, string>): string {
  return colors['--edge-color'] || 'rgba(148, 163, 184, 0.4)'
}

function getNodeRadius(d: GraphNode, sizeMetric: string, sizeRange: SizeRangeMap, connectedSet: Set<string> | null): number {
  const metric = SIZE_METRICS.find((m) => m.key === sizeMetric) || SIZE_METRICS[0]
  const range = sizeRange[metric.key]
  let minVal: number, maxVal: number
  if (range?.connected && connectedSet?.has(d.id)) {
    minVal = range.connected.min
    maxVal = range.connected.max
  } else {
    minVal = range?.full?.min ?? 0
    maxVal = range?.full?.max ?? 0
  }

  const value = d.metrics[metric.key] ?? 0
  return scaleValue(value, minVal, maxVal, 8, 40)
}

// ─── Component ───
export function GraphCanvas({ data, bridgeRef, onNodeSelect, onNodeDeselect, className }: GraphCanvasProps) {
  // ─── DOM refs ───
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const labelsContainerRef = useRef<HTMLDivElement>(null)

  // ─── Graph state (managed by graph, exposed via bridge) ───
  const themeRef = useRef(localStorage.getItem('graph-theme') || 'default')
  const sizeMetricRef = useRef('degree')
  const showLabelsRef = useRef(true)
  const simulatingRef = useRef(false)
  const [themeState, setThemeState] = useState(themeRef.current)
  const [, setSizeMetricState] = useState(sizeMetricRef.current)
  const themeColorsRef = useRef<Record<string, string>>({})

  // ─── Zoom & viewport ───
  const zoomRef = useRef({ x: 0, y: 0, k: 0.3 })
  const widthRef = useRef(800)
  const heightRef = useRef(600)
  const resizeRAFRef = useRef<number | null>(null)

  // ─── Selection & hover ───
  const selectedNodeRef = useRef<GraphNode | null>(null)
  const hoveredNodeRef = useRef<GraphNode | null>(null)
  const hoveredLabelNodeRef = useRef<GraphNode | null>(null)
  const connectedSetRef = useRef<Set<string> | null>(null)
  const connectedEdgesRef = useRef<Set<GraphEdge> | null>(null)

  // ─── Data & layout ───
  const validEdgesRef = useRef<GraphEdge[]>([])
  const nodeMapRef = useRef<Map<string, GraphNode>>(new Map())
  const sizeRangeRef = useRef<SizeRangeMap>({})
  const simulationRef = useRef<d3.Simulation<GraphNode, undefined> | null>(null)
  const initializedRef = useRef(false)
  const currentDimRef = useRef(1)

  // ─── Labels ───
  const labelElementsRef = useRef<Map<string, HTMLDivElement>>(new Map())
  const labelFontSizeRef = useRef(themes.find(t => t.key === (localStorage.getItem('graph-theme') || 'default'))?.labelFontSize ?? 13)
  const labelVisibleSetRef = useRef<Set<string> | null>(null)
  const lastLabelZoomRef = useRef(0)
  const hoverLabelTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ─── Animation (dimension + radius transitions) ───
  const animFrameRef = useRef<number | null>(null)
  const animDimRef = useRef(1)
  const animDimTargetRef = useRef<number | null>(null)
  const animScaleStartRadiiRef = useRef<Map<string, number>>(new Map())
  const animScaleTargetsRef = useRef<Map<string, number>>(new Map())
  const animStartRef = useRef(0)
  const animatingRef = useRef(false)

  // ─── Interaction (mouse, pan, drag) ───
  const isPanningRef = useRef(false)
  const panStartRef = useRef({ x: 0, y: 0 })
  const zoomStartRef = useRef({ x: 0, y: 0 })
  const isMouseDownRef = useRef(false)
  const draggedNodeRef = useRef<GraphNode | null>(null)
  const isDraggingRef = useRef(false)

  // ─── Render batching ───
  const renderPendingRef = useRef(false)
  const rafIdRef = useRef<number | null>(null)
  const labelSetDirtyRef = useRef(false)

  // ─── Data ref — prevents stale closures in render callbacks ───
  const dataRef = useRef(data)
  // Synced in init effect only — dataRef stays bound to the same object
  // that the layout simulation ran on, preventing NaN position collapse.

  // Deferred render — batches rapid calls into a single RAF
  function deferRender() {
    if (renderPendingRef.current) return
    renderPendingRef.current = true
    if (rafIdRef.current !== null) cancelAnimationFrame(rafIdRef.current)
    rafIdRef.current = requestAnimationFrame(() => {
      renderPendingRef.current = false
      render()
    })
  }

  // ─── Simulation factory ───
  function createSimulation(nodes: GraphNode[], edges: GraphEdge[], opts: {
    alpha?: number
    alphaDecay?: number
    alphaMin?: number
    velocityDecay?: number
    chargeStrength?: number
    chargeDistanceMax?: number
    linkDistance?: number
    linkStrength?: number
    linkIdAccessor?: boolean
    collisionRadius?: number
    collisionStrength?: number
    centerX?: number
    centerY?: number
    centerStrength?: number
    tick?: () => void
  }) {
    const linkForce = d3.forceLink(edges)
      .distance(opts.linkDistance ?? 120)
      .strength(opts.linkStrength ?? 0.05)
    if (opts.linkIdAccessor) {
      linkForce.id((d) => (d as GraphNode).id)
    }

    const chargeForce = d3.forceManyBody().strength(opts.chargeStrength ?? -150)
    if (opts.chargeDistanceMax != null) {
      chargeForce.distanceMax(opts.chargeDistanceMax)
    }

    const collideForce = d3.forceCollide().radius(opts.collisionRadius ?? 25)
    if (opts.collisionStrength != null) {
      collideForce.strength(opts.collisionStrength)
    }

    const sim = d3.forceSimulation(nodes)
      .force('link', linkForce)
      .force('charge', chargeForce)
      .force('collision', collideForce)
      .alpha(opts.alpha ?? 0.3)
      .alphaDecay(opts.alphaDecay ?? 0)
      .alphaMin(opts.alphaMin ?? 0)
      .velocityDecay(opts.velocityDecay ?? 0.4)

    if (opts.centerX != null && opts.centerY != null) {
      sim.force('center', d3.forceCenter(opts.centerX, opts.centerY).strength(opts.centerStrength ?? 0.02))
    }

    if (opts.tick) {
      sim.on('tick', opts.tick)
    }

    return sim
  }

  // ─── Build label set (progressive disclosure) ───
  function buildLabelSet() {
    const z = zoomRef.current
    const zoomDelta = Math.abs(z.k - lastLabelZoomRef.current)
    if (!labelSetDirtyRef.current && zoomDelta < LABEL_HYSTERESIS && labelVisibleSetRef.current !== null) return
    labelSetDirtyRef.current = false
    lastLabelZoomRef.current = z.k

    if (!showLabelsRef.current || z.k < LABEL_MIN_ZOOM || !dataRef.current) {
      labelVisibleSetRef.current = null
      return
    }

    // Cache getNodeRadius results — inputs don't change within this call
    const radiusCache = new Map<string, number>()
    const cachedRadius = (n: GraphNode) => {
      const cached = radiusCache.get(n.id)
      if (cached !== undefined) return cached
      const r = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      radiusCache.set(n.id, r)
      return r
    }

    const candidates: GraphNode[] = []
    for (const n of dataRef.current.nodes) {
      if (!n.visible) continue
      if (z.k < LABEL_MAX_ZOOM) {
        const screenRadius = cachedRadius(n) * z.k
        if (screenRadius < LABEL_NODE_RADIUS_THRESHOLD) continue
      }
      candidates.push(n)
    }

    candidates.sort((a, b) => cachedRadius(b) - cachedRadius(a))

    const fontSize = labelFontSizeRef.current / z.k
    const cellSize = fontSize * 2
    const occupied = new Map<string, true>()

    const labelBBox = (n: GraphNode) => {
      const r = cachedRadius(n)
      const fs = labelFontSizeRef.current
      const text = n.name || n.id || ''
      const tw = text.length * fs * LABEL_CHAR_WIDTH + LABEL_PAD_X * 2
      const th = fs
      return {
        x: (n.x ?? 0) - tw / 2,
        y: (n.y ?? 0) - r - 4 / z.k - th,
        w: tw,
        h: th,
      }
    }

    const overlapsOccupied = (bbox: { x: number; y: number; w: number; h: number }) => {
      const x0 = Math.floor(bbox.x / cellSize)
      const x1 = Math.floor((bbox.x + bbox.w) / cellSize)
      const y0 = Math.floor(bbox.y / cellSize)
      const y1 = Math.floor((bbox.y + bbox.h) / cellSize)
      for (let cx = x0; cx <= x1; cx++) {
        for (let cy = y0; cy <= y1; cy++) {
          if (occupied.has(`${cx},${cy}`)) return true
        }
      }
      return false
    }

    const markOccupied = (bbox: { x: number; y: number; w: number; h: number }) => {
      const x0 = Math.floor(bbox.x / cellSize)
      const x1 = Math.floor((bbox.x + bbox.w) / cellSize)
      const y0 = Math.floor(bbox.y / cellSize)
      const y1 = Math.floor((bbox.y + bbox.h) / cellSize)
      for (let cx = x0; cx <= x1; cx++) {
        for (let cy = y0; cy <= y1; cy++) {
          occupied.set(`${cx},${cy}`, true)
        }
      }
    }

    const newVisible = new Set<string>()
    for (const n of candidates) {
      const bbox = labelBBox(n)
      if (!overlapsOccupied(bbox)) {
        newVisible.add(n.id)
        markOccupied(bbox)
      }
    }
    labelVisibleSetRef.current = newVisible
  }

  // ─── Update HTML labels ───
  function updateHtmlLabels() {
    const container = labelsContainerRef.current
    if (!container || !dataRef.current) return

    const z = zoomRef.current
    const connectedSet = connectedSetRef.current

    for (const n of dataRef.current.nodes) {
      if (!n.visible) continue

      const labelX = z.x + (n.x ?? 0) * z.k
      const r = n._animRadius !== undefined ? n._animRadius : getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSet)
      const labelY = z.y + (n.y ?? 0) * z.k - r * z.k - 8

      let labelEl = labelElementsRef.current.get(n.id)
      if (!labelEl) {
        labelEl = document.createElement('div')
        labelEl.className = 'graph-label'
        labelEl.textContent = n.name || n.id
        container.appendChild(labelEl)
        labelElementsRef.current.set(n.id, labelEl)
      }

      labelEl.style.left = `${labelX}px`
      labelEl.style.top = `${labelY}px`
      labelEl.style.fontSize = `${labelFontSizeRef.current}px`

      const isVisible = labelVisibleSetRef.current?.has(n.id) ?? false
      if (isVisible) {
        labelEl.classList.add('visible')
        const isConnected = !connectedSet || connectedSet.has(n.id)
        if (connectedSet && !isConnected) {
          labelEl.classList.add('dimmed')
        } else {
          labelEl.classList.remove('dimmed')
        }
      } else {
        labelEl.classList.remove('visible', 'dimmed')
      }
    }

    // Remove elements for hidden nodes
    const visibleIds = new Set(dataRef.current.nodes.filter((n: GraphNode) => n.visible).map((n: GraphNode) => n.id))
    for (const [id, el] of labelElementsRef.current) {
      if (!visibleIds.has(id)) {
        el.remove()
        labelElementsRef.current.delete(id)
      }
    }
  }

  // ─── Recompute size ranges (called on selection or visibility change) ───
  function recalcSizeRange() {
    const visibleNodes = dataRef.current.nodes.filter((n: GraphNode) => n.visible !== false)
    if (visibleNodes.length === 0) return

    // Full ranges over visible nodes (changes when filters hide nodes)
    for (const m of SIZE_METRICS) {
      let maxVal = 0
      for (const n of visibleNodes) {
        const v = n.metrics[m.key] || 0
        if (v > maxVal) maxVal = v
      }
      if (maxVal > 0) {
        sizeRangeRef.current[m.key] = { full: { min: 0, max: maxVal } }
      }
    }

    // Connected-set ranges
    if (selectedNodeRef.current && connectedSetRef.current) {
      const connectedNodes = visibleNodes.filter((n: GraphNode) => connectedSetRef.current!.has(n.id))
      if (connectedNodes.length > 0) {
        for (const m of SIZE_METRICS) {
          let maxVal = 0
          for (const n of connectedNodes) {
            const v = n.metrics[m.key] || 0
            if (v > maxVal) maxVal = v
          }
          sizeRangeRef.current[m.key] = {
            full: sizeRangeRef.current[m.key]?.full ?? { min: 0, max: maxVal },
            connected: maxVal > 0 ? { min: 0, max: maxVal } : { min: 0, max: 0 },
          }
        }
      }
    }
  }

  // ─── Render ───
  function render() {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const w = widthRef.current
    const h = heightRef.current
    const z = zoomRef.current

    // Reset transform to identity, then clear full canvas
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Scale by DPR so all subsequent transforms are in CSS coords
    const dpr = window.devicePixelRatio || 1
    ctx.scale(dpr, dpr)

    // Apply zoom transform
    ctx.save()
    ctx.translate(z.x, z.y)
    ctx.scale(z.k, z.k)

    // Draw nodes and edges (in CSS coords, scaled by DPR)
    // ...

    // Use cached connected edges (only updated on selection change)
    const connectedEdges = connectedEdgesRef.current

    buildLabelSet()

    const edgeColor = getEdgeColor(themeColorsRef.current)
    const currentDim = currentDimRef.current

    // Draw edges
    ctx.globalAlpha = 0.3
    for (const e of validEdgesRef.current) {
      if (!e.visible || !e.source.visible || !e.target.visible) continue
      ctx.beginPath()
      ctx.moveTo(e.source.x ?? 0, e.source.y ?? 0)
      ctx.lineTo(e.target.x ?? 0, e.target.y ?? 0)
      ctx.strokeStyle = edgeColor
      ctx.lineWidth = 0.6 / z.k
      if (connectedEdges && !connectedEdges.has(e)) {
        ctx.globalAlpha = currentDim * 0.3
      } else {
        ctx.globalAlpha = currentDim * 0.5 + (1 - currentDim) * 0.3
      }
      ctx.stroke()
    }

    ctx.globalAlpha = 1

    // Draw nodes
    for (const n of dataRef.current.nodes) {
      if (!n.visible) continue
      if (n.x == null || n.y == null || isNaN(n.x) || isNaN(n.y)) { n.x = w / 2; n.y = h / 2 }
      const r = n._animRadius !== undefined ? Math.max(0, n._animRadius) : getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      const color = n._cachedColor ?? getNodeColor(n, themeColorsRef.current)
      const isSelected = selectedNodeRef.current && selectedNodeRef.current.id === n.id
      const isHovered = hoveredNodeRef.current && hoveredNodeRef.current.id === n.id
      const isConnected = !connectedSetRef.current || connectedSetRef.current.has(n.id)

      if (connectedSetRef.current && !isConnected) {
        ctx.globalAlpha = currentDim
      } else {
        ctx.globalAlpha = 1
      }

      ctx.beginPath()
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
      ctx.fillStyle = color
      ctx.fill()

      const c = themeColorsRef.current
      const strokeColor = isSelected
        ? (c['--node-stroke-selected'] || '#fff')
        : (n._cachedStroke ?? d3.color(color)!.darker(0.8).formatHex())
      ctx.strokeStyle = strokeColor
      const strokeWidth = parseFloat(c['--node-stroke-width']) || 1
      ctx.lineWidth = (isSelected ? strokeWidth * 2 : strokeWidth) / z.k
      ctx.stroke()

      if (isHovered && !isSelected) {
        ctx.strokeStyle = c['--node-stroke-hover'] || '#fff'
        ctx.lineWidth = strokeWidth * 2 / z.k
        ctx.stroke()
      }
    }

    // Update labels every frame during pan/drag/sim, but skip during radius animation
    // (positions don't change during animation, only radii)
    if (!animatingRef.current) {
      updateHtmlLabels()
    }
    ctx.restore()
  }

  // ─── Simulation helper (used by bridge and animation restore) ───
  function startSimulationInternal() {
    simulatingRef.current = true
    if (simulationRef.current) simulationRef.current.stop()
    const visibleNodes = dataRef.current.nodes.filter((n: GraphNode) => n.visible)
    const visibleNodeSet = new Set(visibleNodes)
    const visibleEdges = validEdgesRef.current
      .filter((e: GraphEdge) => e.visible && visibleNodeSet.has(e.source) && visibleNodeSet.has(e.target))
      .map((e: GraphEdge) => ({ ...e, source: e.source, target: e.target }))
    simulationRef.current = createSimulation(visibleNodes, visibleEdges, {
      alpha: 1, alphaDecay: 0.08, alphaMin: 0, velocityDecay: 0.2,
      chargeStrength: -400,
      tick: () => render(),
    }).on('end', () => {
      simulatingRef.current = false
      render()
    })
  }

  // ─── Tighten: pull nodes closer together ───
  function tightenSimulationInternal() {
    simulatingRef.current = true
    if (simulationRef.current) simulationRef.current.stop()
    const visibleNodes = dataRef.current.nodes.filter((n: GraphNode) => n.visible)
    const visibleNodeSet = new Set(visibleNodes)
    const visibleEdges = validEdgesRef.current
      .filter((e: GraphEdge) => e.visible && visibleNodeSet.has(e.source) && visibleNodeSet.has(e.target))
      .map((e: GraphEdge) => ({ ...e, source: e.source, target: e.target }))
    const cx = widthRef.current / 2
    const cy = heightRef.current / 2
    simulationRef.current = createSimulation(visibleNodes, visibleEdges, {
      alpha: 1, alphaDecay: 0.1, alphaMin: 0, velocityDecay: 0.4,
      chargeStrength: -100,
      linkDistance: 180,
      linkStrength: 0.15,
      centerX: cx, centerY: cy, centerStrength: 0.15,
      tick: () => render(),
    }).on('end', () => {
      simulatingRef.current = false
      render()
    })
  }

  // ─── Animation ───
  function startAnimation(dimTarget: number | null) {
    if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current)
    animatingRef.current = true

    // Stop simulation during selection animation to avoid double-rendering
    if (simulationRef.current) {
      simulationRef.current.stop()
      simulationRef.current = null
      simulatingRef.current = false
    }

    // Snapshot old radii synchronously — cheap, needed before state changes
    const oldRadii = new Map<string, number>()
    for (const n of dataRef.current.nodes) {
      if (!n.visible) continue
      oldRadii.set(n.id, n._animRadius ?? getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current))
    }

    // Defer all heavy work into RAF so the browser can paint the click frame
    animFrameRef.current = requestAnimationFrame((now) => {
      animStartRef.current = now
      animDimRef.current = currentDimRef.current
      animDimTargetRef.current = dimTarget

      // Build connected set for correct target radii
      connectedSetRef.current = null
      connectedEdgesRef.current = null
      labelSetDirtyRef.current = true
      if (selectedNodeRef.current) {
        connectedSetRef.current = new Set([selectedNodeRef.current.id])
        connectedEdgesRef.current = new Set()
        for (const e of validEdgesRef.current) {
          if (e.source.id === selectedNodeRef.current.id || e.target.id === selectedNodeRef.current.id) {
            connectedSetRef.current.add(e.source.id)
            connectedSetRef.current.add(e.target.id)
            connectedEdgesRef.current.add(e)
          }
        }
      }
      recalcSizeRange()

      animScaleStartRadiiRef.current = new Map()
      animScaleTargetsRef.current = new Map()
      for (const n of dataRef.current.nodes) {
        if (!n.visible) continue
        const startRadius = oldRadii.get(n.id) ?? getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
        const targetRadius = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
        animScaleStartRadiiRef.current.set(n.id, startRadius)
        animScaleTargetsRef.current.set(n.id, targetRadius)
        n._animRadius = startRadius
      }

      updateHtmlLabels()
      animStep(now)
    })
  }

  function animStep(now: number) {
    const elapsed = now - animStartRef.current
    const progress = Math.min(elapsed / ANIM_DURATION, 1)
    const ease = 1 - Math.pow(1 - progress, 3)

    if (animDimTargetRef.current !== null) {
      currentDimRef.current = animDimRef.current + (animDimTargetRef.current - animDimRef.current) * ease
    }

    if (animScaleStartRadiiRef.current.size > 0) {
      for (const n of dataRef.current.nodes) {
        if (!n.visible) continue
        const start = animScaleStartRadiiRef.current.get(n.id) ?? 0
        const target = animScaleTargetsRef.current.get(n.id) ?? 0
        n._animRadius = start + (target - start) * ease
      }
    }

    render()

    if (progress < 1) {
      animFrameRef.current = requestAnimationFrame(animStep)
    } else {
      for (const n of dataRef.current.nodes) {
        if (!n.visible) continue
        n._animRadius = undefined
      }
      if (animDimTargetRef.current !== null) {
        currentDimRef.current = animDimTargetRef.current
      }
      animFrameRef.current = null
      animatingRef.current = false
      // Update labels once after animation completes
      updateHtmlLabels()
    }
  }

  // ─── Initialize graph ───
  // ─── Layout init (runs once, StrictMode-safe) ───
  useEffect(() => {
    if (!data) return
    if (initializedRef.current) {
      // StrictMode remount — just render with existing positions
      render()
      return
    }
    initializedRef.current = true
    dataRef.current = data

    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    // Clear previous labels
    labelElementsRef.current.clear()
    labelVisibleSetRef.current = null

    // Reset any D3-mutated state from prior mounts
    for (const n of dataRef.current.nodes) {
      delete n.x
      delete n.y
      delete n.vx
      delete n.vy
      delete n.fx
      delete n.fy
      delete n.index
    }

    // Compute full size ranges (constant — never changes after init)
    for (const m of SIZE_METRICS) {
      let maxVal = 0
      for (const n of dataRef.current.nodes) {
        const v = n.metrics[m.key] || 0
        if (v > maxVal) maxVal = v
      }
      if (maxVal > 0) sizeRangeRef.current[m.key] = { full: { min: 0, max: maxVal } }
    }

    // Build node map + precompute color indices
    nodeMapRef.current = new Map()
    for (const n of dataRef.current.nodes) {
      n.visible = true
      n._animRadius = undefined
      n._colorIdx = hashToIndex(n.category)
      nodeMapRef.current.set(n.id, n)
    }

    // Pre-resolve edges (RawGraphEdge → GraphEdge)
    validEdgesRef.current = []
    for (const raw of dataRef.current.edges) {
      const srcNode = nodeMapRef.current.get(raw.source)
      const tgtNode = nodeMapRef.current.get(raw.target)
      if (!srcNode || !tgtNode) continue
      validEdgesRef.current.push({
        source: srcNode,
        target: tgtNode,
        type: raw.type,
        visible: true,
      })
    }

    // Initial sizing
    const w = container.clientWidth
    const h = container.clientHeight
    widthRef.current = w
    heightRef.current = h

    // Canvas setup with DPR
    const dpr = window.devicePixelRatio || 1
    canvas.width = w * dpr
    canvas.height = h * dpr
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'

    // Center zoom
    const initK = 0.3
    zoomRef.current = { x: -w / 2 * initK + w / 2, y: -h / 2 * initK + h / 2, k: initK }

    // Initial node placement
    dataRef.current.nodes.forEach((n: GraphNode, i: number) => {
      const angle = (2 * Math.PI * i) / dataRef.current.nodes.length
      const radius = 200 + Math.random() * 200
      n.x = w / 2 + radius * Math.cos(angle)
      n.y = h / 2 + radius * Math.sin(angle)
      n.vx = 0
      n.vy = 0
    })

    // Initial static layout
    const initSim = createSimulation(dataRef.current.nodes, validEdgesRef.current, {
      alpha: 0.3, alphaDecay: 0.1, velocityDecay: 0.4,
      chargeStrength: -150,
      linkIdAccessor: true,
      centerX: w / 2, centerY: h / 2, centerStrength: 0.02,
      collisionRadius: 25,
    })
    for (let i = 0; i < 200; i++) initSim.tick()
    initSim.stop()

    // Initial render
    render()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Mouse & wheel event listeners ───
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Manual wheel zoom (replaces d3-zoom to avoid double transform)
    function onWheel(event: WheelEvent) {
      event.preventDefault()
      const rect = canvas!.getBoundingClientRect()
      const mouseX = event.clientX - rect.left
      const mouseY = event.clientY - rect.top

      const delta = event.deltaY > 0 ? 0.9 : 1.1
      const newK = Math.max(0.05, Math.min(8, zoomRef.current.k * delta))

      // Zoom toward mouse position (same formula as original graph.js)
      zoomRef.current.x = mouseX - (mouseX - zoomRef.current.x) * (newK / zoomRef.current.k)
      zoomRef.current.y = mouseY - (mouseY - zoomRef.current.y) * (newK / zoomRef.current.k)
      zoomRef.current.k = newK

      render()
    }

    // Mouse position in world coordinates
    function getMousePos(event: MouseEvent) {
      const rect = canvas!.getBoundingClientRect()
      const z = zoomRef.current
      return {
        x: (event.clientX - rect.left - z.x) / z.k,
        y: (event.clientY - rect.top - z.y) / z.k,
      }
    }

    function findNodeAt(pos: { x: number; y: number }) {
      for (let i = dataRef.current.nodes.length - 1; i >= 0; i--) {
        const n = dataRef.current.nodes[i]
        if (!n.visible) continue
        const dx = pos.x - (n.x ?? 0)
        const dy = pos.y - (n.y ?? 0)
        const r = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current) + 5
        if (dx * dx + dy * dy < r * r) return n
      }
      return null
    }

    function onMouseDown(event: MouseEvent) {
      if (event.button !== 0) return
      event.stopPropagation()
      isMouseDownRef.current = true
      const pos = getMousePos(event)
      const node = findNodeAt(pos)
      if (node) {
        draggedNodeRef.current = node
        panStartRef.current = { x: event.clientX, y: event.clientY }
        isDraggingRef.current = false
      } else {
        isPanningRef.current = false
        panStartRef.current = { x: event.clientX, y: event.clientY }
        zoomStartRef.current = { x: zoomRef.current.x, y: zoomRef.current.y }
      }
    }

    function onMouseMove(event: MouseEvent) {
      event.stopPropagation()
      const pos = getMousePos(event)

      if (draggedNodeRef.current) {
        const dx = event.clientX - panStartRef.current.x
        const dy = event.clientY - panStartRef.current.y
        if (dx * dx + dy * dy < 100) return

        isDraggingRef.current = true
        draggedNodeRef.current.x = pos.x
        draggedNodeRef.current.y = pos.y
        draggedNodeRef.current.vx = 0
        draggedNodeRef.current.vy = 0
        if (simulationRef.current) {
          draggedNodeRef.current.fx = pos.x
          draggedNodeRef.current.fy = pos.y
          simulationRef.current.alpha(0.1)
        }
        render()
        return
      }

      if (!draggedNodeRef.current && !isPanningRef.current && isMouseDownRef.current) {
        const dx = event.clientX - panStartRef.current.x
        const dy = event.clientY - panStartRef.current.y
        if (dx * dx + dy * dy > 25) {
          isPanningRef.current = true
        }
      }

      if (isPanningRef.current) {
        zoomRef.current.x = zoomStartRef.current.x + (event.clientX - panStartRef.current.x)
        zoomRef.current.y = zoomStartRef.current.y + (event.clientY - panStartRef.current.y)
        render()
        return
      }

      const node = findNodeAt(pos)
      if (node !== hoveredNodeRef.current) {
        if (hoverLabelTimeoutRef.current) {
          clearTimeout(hoverLabelTimeoutRef.current)
          hoverLabelTimeoutRef.current = null
        }
        if (hoveredLabelNodeRef.current && hoveredLabelNodeRef.current !== node) {
          hoveredLabelNodeRef.current = null
          render()
        }
        hoveredNodeRef.current = node
        canvas!.style.cursor = node ? 'pointer' : 'grab'
        if (node) {
          hoverLabelTimeoutRef.current = setTimeout(() => {
            hoverLabelTimeoutRef.current = null
            hoveredLabelNodeRef.current = node
            render()
          }, HOVER_LABEL_DELAY)
        }
        render()
      }
    }

    function onMouseUp(event: MouseEvent) {
      event.stopPropagation()
      const wasPanning = isPanningRef.current
      isPanningRef.current = false
      isMouseDownRef.current = false

      if (draggedNodeRef.current) {
        if (!isDraggingRef.current) {
          const pos = getMousePos(event)
          const node = findNodeAt(pos)
          if (node) {
            selectedNodeRef.current = node
            startAnimation(0.15)
            requestAnimationFrame(() => onNodeSelect?.(node))
          } else {
            selectedNodeRef.current = null
            startAnimation(1)
            requestAnimationFrame(() => onNodeDeselect?.())
          }
        } else {
          isDraggingRef.current = false
          const node = draggedNodeRef.current
          if (simulationRef.current) {
            node.fx = null
            node.fy = null
            // Let simulation cool down after drag
            simulationRef.current.alphaTarget(0)
          } else {
            node.fx = node.x
            node.fy = node.y
            // Settle after drag
            const visibleNodes = dataRef.current.nodes.filter((n: GraphNode) => n.visible)
            const visibleEdges = validEdgesRef.current.filter((e: GraphEdge) => e.visible)
            simulationRef.current = createSimulation(visibleNodes, visibleEdges, {
              alpha: 0.15, alphaDecay: 0.12, velocityDecay: 0.7,
              chargeStrength: -350, chargeDistanceMax: 300,
              linkStrength: 0.08,
              collisionRadius: 25, collisionStrength: 0.7,
              tick: () => render(),
            })
              .on('end', () => {
                node.fx = null
                node.fy = null
              })
            setTimeout(() => {
              if (simulationRef.current) {
                node.fx = null
                node.fy = null
                simulationRef.current.stop()
                simulationRef.current = null
                render()
              }
            }, 1000)
          }
        }
        draggedNodeRef.current = null
        isDraggingRef.current = false
      } else if (!wasPanning && selectedNodeRef.current) {
        selectedNodeRef.current = null
        startAnimation(1)
        requestAnimationFrame(() => onNodeDeselect?.())
      }
    }

    canvas.addEventListener('mousedown', onMouseDown, { capture: true })
    canvas.addEventListener('mousemove', onMouseMove, { capture: true })
    canvas.addEventListener('mouseup', onMouseUp, { capture: true })
    canvas.addEventListener('wheel', onWheel, { passive: false })

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown, { capture: true })
      canvas.removeEventListener('mousemove', onMouseMove, { capture: true })
      canvas.removeEventListener('mouseup', onMouseUp, { capture: true })
      canvas.removeEventListener('wheel', onWheel, { capture: true })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Resize observer ───
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const resizeObserver = new ResizeObserver(() => {
      if (resizeRAFRef.current !== null) return
      resizeRAFRef.current = requestAnimationFrame(() => {
        resizeRAFRef.current = null
        const w = container.clientWidth
        const h = container.clientHeight
        // Skip if dimensions haven't actually changed — canvas.width = sameValue resets the bitmap
        if (w === widthRef.current && h === heightRef.current) return
        widthRef.current = w
        heightRef.current = h
        const dpr = window.devicePixelRatio || 1
        canvas.width = w * dpr
        canvas.height = h * dpr
        canvas.style.width = w + 'px'
        canvas.style.height = h + 'px'
        render()
      })
    })
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      if (resizeRAFRef.current !== null) cancelAnimationFrame(resizeRAFRef.current)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Global cleanup (sim, anim frame, hover timeout) ───
  useEffect(() => {
    return () => {
      if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current)
      if (hoverLabelTimeoutRef.current) clearTimeout(hoverLabelTimeoutRef.current)
      if (simulationRef.current) {
        simulationRef.current.stop()
        simulationRef.current = null
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Apply theme ───
  useEffect(() => {
    const theme = themes.find((t) => t.key === themeState)
    if (!theme) return

    const cs = document.documentElement.style
    const colors: Record<string, string> = {}

    // Build colors map from theme definition
    for (let i = 0; i < 12; i++) {
      colors[`--node-color-${i}`] = theme.nodeColors[i]
    }
    colors['--edge-color'] = theme.edgeColor
    colors['--node-stroke-width'] = theme.nodeStrokeWidth.toString()
    colors['--node-stroke-selected'] = theme.nodeStrokeSelectedColor || '#fff'
    colors['--node-stroke-hover'] = theme.nodeStrokeHoverColor || '#fff'
    // Default node stroke to darker version of first node color
    colors['--node-stroke'] = theme.nodeStrokeColor || ''

    // Apply to DOM
    for (const [key, value] of Object.entries(theme.vars)) {
      cs.setProperty(key, value)
    }
    for (const [key, value] of Object.entries(colors)) {
      cs.setProperty(key, value)
    }

    themeColorsRef.current = colors
    labelFontSizeRef.current = theme.labelFontSize

    // Cache resolved color + stroke strings on each node (avoids d3.color per frame)
    for (const n of dataRef.current.nodes) {
      const cssVar = `--node-color-${n._colorIdx ?? 0}`
      const color = colors[cssVar] || '#94a3b8'
      n._cachedColor = color
      n._cachedStroke = d3.color(color)!.darker(0.8).formatHex()
    }

    render()
  }, [themeState]) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Bridge ───
  useImperativeHandle(bridgeRef, () => ({
    // Visibility
    setVisibility: (visibleIds: Set<string>) => {
      for (const n of dataRef.current.nodes) {
        n.visible = visibleIds.has(n.id)
      }
      labelSetDirtyRef.current = true
      // Recalculate sizes for visible nodes
      connectedSetRef.current = null
      connectedEdgesRef.current = null
      recalcSizeRange()
      // Restart simulation with updated visibility (preserves user's simulation preference)
      if (simulatingRef.current) {
        startSimulationInternal()
      }
      render()
    },
    setSearchTerm: (_term: string) => {
      // Search is handled by parent via setVisibility
    },

    // Theme
    getTheme: () => themeRef.current,
    setTheme: (newTheme: string) => {
      themeRef.current = newTheme
      setThemeState(newTheme)
      localStorage.setItem('graph-theme', newTheme)
      // render() is called by the theme useEffect after applying CSS
    },
    updateTheme: () => {
      render()
    },

    // Size metric
    getSizeMetric: () => sizeMetricRef.current,
    setSizeMetric: (metric: string) => {
      sizeMetricRef.current = metric
      setSizeMetricState(metric)
      startAnimation(null)
      deferRender()
    },

    // Labels
    getLabels: () => showLabelsRef.current,
    setLabels: (show: boolean) => {
      showLabelsRef.current = show
      labelSetDirtyRef.current = true
      deferRender()
    },

    // Simulation
    isSimulating: () => simulatingRef.current,
    startSimulation: () => startSimulationInternal(),
    tighten: () => tightenSimulationInternal(),
    stopSimulation: () => {
      simulatingRef.current = false
      if (simulationRef.current) {
        simulationRef.current.stop()
        simulationRef.current = null
        render()
      }
    },

    // Selection
    selectNodeById: (id: string) => {
      const node = dataRef.current.nodes.find((n: GraphNode) => n.id === id)
      if (node) {
        selectedNodeRef.current = node
        startAnimation(0.15)
        requestAnimationFrame(() => onNodeSelect?.(node))
      }
    },
    deselectNode: () => {
      selectedNodeRef.current = null
      startAnimation(1)
      requestAnimationFrame(() => onNodeDeselect?.())
    },
    getSelectedNode: () => selectedNodeRef.current,

    // Zoom
    zoomIn: () => {
      const w = widthRef.current
      const h = heightRef.current
      const z = zoomRef.current
      const centerX = w / 2
      const centerY = h / 2
      const newK = Math.min(z.k * 1.3, 10)
      zoomRef.current = {
        x: centerX - (centerX - z.x) * (newK / z.k),
        y: centerY - (centerY - z.y) * (newK / z.k),
        k: newK,
      }
      render()
    },
    zoomOut: () => {
      const w = widthRef.current
      const h = heightRef.current
      const z = zoomRef.current
      const centerX = w / 2
      const centerY = h / 2
      const newK = Math.max(z.k / 1.3, 0.1)
      zoomRef.current = {
        x: centerX - (centerX - z.x) * (newK / z.k),
        y: centerY - (centerY - z.y) * (newK / z.k),
        k: newK,
      }
      render()
    },
    resetZoom: () => {
      const w = widthRef.current
      const h = heightRef.current
      const k = 0.3
      zoomRef.current = { x: -w / 2 * k + w / 2, y: -h / 2 * k + h / 2, k }
      render()
    },
    getZoom: () => ({ ...zoomRef.current }),

    // Render
    triggerRender: () => render(),
  }), [onNodeSelect, onNodeDeselect]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      ref={containerRef}
      id="graph-container"
      className={`w-full h-full relative ${className || ''}`}
    >
      <canvas id="graph-canvas" className="absolute inset-0" ref={canvasRef} />
      <div id="labels-container" className="absolute inset-0 pointer-events-none" ref={labelsContainerRef} />
    </div>
  )
}
