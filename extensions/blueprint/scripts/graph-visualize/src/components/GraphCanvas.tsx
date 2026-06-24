import { useRef, useEffect, useState, useCallback, useImperativeHandle } from 'react'
import * as d3 from 'd3'
import { themes } from '@/lib/themes'

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

  // ── Selection (parent commands, canvas fires events) ──
  selectNodeById(id: string): void
  deselectNode(): void
  getSelectedNode(): any | null

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
  data: any
  bridgeRef?: React.Ref<IGraphBridge | null>
  onNodeSelect?: (node: any) => void
  onNodeDeselect?: () => void
  className?: string
}

/** Extract clean short ID: PREFIX-NNN */
function extractShortId(id: string, type?: string): string {
  const parts = id.split('-')
  const numIdx = parts.findIndex(p => /^\d+$/.test(p))
  if (numIdx >= 0) return `${parts[0]}-${parts[numIdx]}`
  if (type) return type.toUpperCase()
  return parts.slice(0, 2).join('-')
}

// ─── Constants ───
const LABEL_MIN_ZOOM = 0.5
const LABEL_MAX_ZOOM = 2.0
const LABEL_NODE_RADIUS_THRESHOLD = 8
const LABEL_CHAR_WIDTH = 0.62
const LABEL_PAD_X = 4
const LABEL_PAD_Y = 2
const LABEL_HYSTERESIS = 0.2
const ANIM_DURATION = 400
const HOVER_LABEL_DELAY = 300

// ─── Helpers ───
function scaleValue(value: number, minVal: number, maxVal: number, minRadius = 8, maxRadius = 40): number {
  if (maxVal === minVal) return minVal === 0 && maxVal === 0 ? maxRadius : minRadius
  const normalized = Math.max(0, Math.min(1, (value - minVal) / (maxVal - minVal)))
  return minRadius + Math.pow(normalized, 1.5) * (maxRadius - minRadius)
}

function getNodeColor(d: any, colors: Record<string, string>): string {
  const cat = d.typeCat || d.category || d.type || 'other'
  let hash = 0
  for (let i = 0; i < cat.length; i++) hash = cat.charCodeAt(i) + ((hash << 5) - hash)
  const idx = Math.abs(hash) % 12
  const cssVar = `--node-color-${idx}`
  return colors[cssVar] || '#94a3b8'
}

function getEdgeColor(colors: Record<string, string>): string {
  return colors['--edge-color'] || 'rgba(148, 163, 184, 0.4)'
}

function getNodeRadius(d: any, sizeMetric: string, sizeRange: any, connectedSet: Set<string> | null, type?: string): number {
  if (d.type === 'spec' || d.category === 'spec') return 15

  if (sizeMetric === 'type') {
    const typeSizes: Record<string, number> = {
      CON: 6, FN: 5, REQ: 4.5, NFR: 4.5, US: 4.5, SC: 4, Entity: 4, GL: 3.5,
      TST: 2.5, Enum: 2.5, API: 4, EP: 5, TASK: 3, ISSUE: 4, DG: 3, UJ: 4, UXAC: 4, IS: 4, spec: 5,
    }
    const value = typeSizes[d.type] || 1
    return scaleValue(value, 1, 6, 8, 40)
  }

  const rangeKey = sizeMetric ?? 'degree'
  const range = sizeRange[rangeKey]
  let minVal: number, maxVal: number
  if (range?.connected && connectedSet?.has(d.id)) {
    minVal = range.connected.min
    maxVal = range.connected.max
  } else {
    minVal = range?.full?.min ?? range?.min ?? 0
    maxVal = range?.full?.max ?? range?.max ?? 0
  }

  const nodeKey = rangeKey === 'blast' ? 'blastRadius' : rangeKey
  const value = d[nodeKey] ?? 0
  return scaleValue(value, minVal, maxVal, 8, 40)
}

// ─── Component ───
export function GraphCanvas({ data, bridgeRef, onNodeSelect, onNodeDeselect, className }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const labelsContainerRef = useRef<HTMLDivElement>(null)

  // Internal state (managed by the graph) — refs for live bridge access
  const themeRef = useRef(localStorage.getItem('graph-theme') || 'default')
  const sizeMetricRef = useRef('degree')
  const showLabelsRef = useRef(true)
  const simulatingRef = useRef(false)
  // Also keep state for theme useEffect (triggers re-apply)
  const [themeState, setThemeState] = useState(themeRef.current)
  const [sizeMetricState, setSizeMetricState] = useState(sizeMetricRef.current)
  // Live theme colors for render (avoids getComputedStyle staleness)
  const themeColorsRef = useRef<Record<string, string>>({})

  // Mutable refs (avoid re-renders during animation)
  const zoomRef = useRef({ x: 0, y: 0, k: 0.3 })
  const selectedNodeRef = useRef<any>(null)
  const hoveredNodeRef = useRef<any>(null)
  const hoveredLabelNodeRef = useRef<any>(null)
  const connectedSetRef = useRef<Set<string> | null>(null)
  const sizeRangeRef = useRef<any>({})
  const simulationRef = useRef<d3.Simulation<any, any> | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const validEdgesRef = useRef<any[]>([])
  const nodeMapRef = useRef<Map<string, any>>(new Map())
  const labelElementsRef = useRef<Map<string, HTMLDivElement>>(new Map())
  const labelVisibleSetRef = useRef<Set<string> | null>(null)
  const lastLabelZoomRef = useRef(0)
  const hoverLabelTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const currentDimRef = useRef(1)
  const animDimRef = useRef(1)
  const animDimTargetRef = useRef<number | null>(null)
  const animScaleStartRadiiRef = useRef<Map<string, number>>(new Map())
  const animScaleTargetsRef = useRef<Map<string, number>>(new Map())
  const animStartRef = useRef(0)
  const isPanningRef = useRef(false)
  const panStartRef = useRef({ x: 0, y: 0 })
  const zoomStartRef = useRef({ x: 0, y: 0 })
  const isMouseDownRef = useRef(false)
  const draggedNodeRef = useRef<any>(null)
  const isDraggingRef = useRef(false)
  const renderPendingRef = useRef(false)
  const rafIdRef = useRef<number | null>(null)
  // Cached connected set — only updated on selection change
  const connectedEdgesRef = useRef<Set<any> | null>(null)

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
  const widthRef = useRef(800)
  const heightRef = useRef(600)
  const resizeRAFRef = useRef<number | null>(null)

  // ─── Build label set (progressive disclosure) ───
  function buildLabelSet() {
    const z = zoomRef.current
    const zoomDelta = Math.abs(z.k - lastLabelZoomRef.current)
    if (zoomDelta < LABEL_HYSTERESIS && labelVisibleSetRef.current !== null) return
    lastLabelZoomRef.current = z.k

    if (!showLabelsRef.current || z.k < LABEL_MIN_ZOOM || !data) {
      labelVisibleSetRef.current = null
      return
    }

    const candidates: any[] = []
    for (const n of data.nodes) {
      if (!n.visible) continue
      if (z.k < LABEL_MAX_ZOOM) {
        const screenRadius = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current) * z.k
        if (screenRadius < LABEL_NODE_RADIUS_THRESHOLD) continue
      }
      candidates.push(n)
    }

    candidates.sort((a, b) => getNodeRadius(b, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current) - getNodeRadius(a, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current))

    const fontSize = 13 / z.k
    const cellSize = fontSize * 2
    const occupied = new Map<string, true>()

    const cellKey = (wx: number, wy: number) => `${Math.floor(wx / cellSize)},${Math.floor(wy / cellSize)}`

    const labelBBox = (n: any) => {
      const r = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      const fs = n.type === 'spec' ? 14 : 13
      const text = n.term || n.label || n.id || ''
      const tw = text.length * fs * LABEL_CHAR_WIDTH + LABEL_PAD_X * 2
      const th = fs
      return {
        x: n.x - tw / 2,
        y: n.y - r - 4 / z.k - th,
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
    if (!container || !data) return

    const z = zoomRef.current
    const selectedNode = selectedNodeRef.current
    const connectedSet = connectedSetRef.current

    for (const n of data.nodes) {
      if (!n.visible) continue

      const labelX = z.x + n.x * z.k
      const r = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSet)
      const labelY = z.y + n.y * z.k - r * z.k - 8

      let labelEl = labelElementsRef.current.get(n.id)
      if (!labelEl) {
        labelEl = document.createElement('div')
        labelEl.className = 'graph-label'
        labelEl.textContent = n.term || n.label || n.id
        container.appendChild(labelEl)
        labelElementsRef.current.set(n.id, labelEl)
      }

      labelEl.style.left = `${labelX}px`
      labelEl.style.top = `${labelY}px`
      labelEl.style.fontSize = `${n.type === 'spec' ? 14 : 13}px`

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
    const visibleIds = new Set(data.nodes.filter((n: any) => n.visible).map((n: any) => n.id))
    for (const [id, el] of labelElementsRef.current) {
      if (!visibleIds.has(id)) {
        el.remove()
        labelElementsRef.current.delete(id)
      }
    }
  }

  // ─── Recalculate size ranges ───
  function recalcSizeRange() {
    const visibleNodes = data.nodes.filter((n: any) => n.visible !== false)
    if (visibleNodes.length === 0) return

    const metrics = [
      { nodeKey: 'blastRadius', rangeKey: 'blast' },
      { nodeKey: 'degree', rangeKey: 'degree' },
      { nodeKey: 'risk', rangeKey: 'risk' },
      { nodeKey: 'centrality', rangeKey: 'centrality' },
    ]

    const fullRanges: any = {}
    for (const m of metrics) {
      const values = visibleNodes.map((n: any) => n[m.nodeKey] || 0).filter((v: number) => v > 0)
      if (values.length > 0) fullRanges[m.rangeKey] = { min: 0, max: Math.max(...values) }
    }

    for (const m of metrics) {
      if (fullRanges[m.rangeKey]) {
        sizeRangeRef.current[m.rangeKey] = { full: fullRanges[m.rangeKey] }
      }
    }

    // Connected-set ranges
    if (selectedNodeRef.current && connectedSetRef.current) {
      const connectedNodes = visibleNodes.filter((n: any) => connectedSetRef.current!.has(n.id))
      if (connectedNodes.length > 0) {
        for (const m of metrics) {
          const values = connectedNodes.map((n: any) => n[m.nodeKey] || 0)
          const maxVal = Math.max(...values)
          sizeRangeRef.current[m.rangeKey] = {
            full: sizeRangeRef.current[m.rangeKey]?.full ?? { min: 0, max: maxVal },
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
    const nCount = data?.nodes?.length ?? 0
    const vCount = data?.nodes?.filter((n: any) => n.visible !== false)?.length ?? 0
    if (nCount > 0 && vCount === 0) console.warn('[render] ALL NODES INVISIBLE!')

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

    // Always recompute — dirty flags are broken
    recalcSizeRange()

    const edgeColor = getEdgeColor(themeColorsRef.current)
    const currentDim = currentDimRef.current

    // Draw edges
    ctx.globalAlpha = 0.3
    for (const e of validEdgesRef.current) {
      if (!e.visible || !e.source.visible || !e.target.visible) continue
      ctx.beginPath()
      ctx.moveTo(e.source.x, e.source.y)
      ctx.lineTo(e.target.x, e.target.y)
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
    for (const n of data.nodes) {
      if (!n.visible) continue
      const r = n._animRadius !== undefined ? Math.max(0, n._animRadius) : getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      const color = getNodeColor(n, themeColorsRef.current)
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
        : (c['--node-stroke'] || d3.color(color)!.darker(0.8).formatHex())
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

    // Always update label positions — they follow nodes during pan/drag/sim
    updateHtmlLabels()
    ctx.globalAlpha = 1
    ctx.restore()
    ctx.globalAlpha = 1
  }

  // ─── Animation ───
  function startAnimation(dimTarget: number | null) {
    if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current)

    animStartRef.current = performance.now()
    animDimRef.current = currentDimRef.current
    animDimTargetRef.current = dimTarget

    const oldRadii = new Map<string, number>()
    for (const n of data.nodes) {
      if (!n.visible) continue
      oldRadii.set(n.id, n._animRadius ?? getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current))
    }

    // Build connected set for correct target radii
    connectedSetRef.current = null
    connectedEdgesRef.current = null
    if (selectedNodeRef.current) {
      connectedSetRef.current = new Set([selectedNodeRef.current.id])
      connectedEdgesRef.current = new Set()
      for (const e of validEdgesRef.current) {
        if (e.source.id === selectedNodeRef.current.id || e.target.id === selectedNodeRef.current.id) {
          connectedSetRef.current.add(e.source.id)
          connectedSetRef.current.add(e.target.id)
          connectedEdgesRef.current!.add(e)
        }
      }
    }
    recalcSizeRange()

    animScaleStartRadiiRef.current = new Map()
    animScaleTargetsRef.current = new Map()
    for (const n of data.nodes) {
      if (!n.visible) continue
      const startRadius = oldRadii.get(n.id) ?? getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      const targetRadius = getNodeRadius(n, sizeMetricRef.current, sizeRangeRef.current, connectedSetRef.current)
      animScaleStartRadiiRef.current.set(n.id, startRadius)
      animScaleTargetsRef.current.set(n.id, targetRadius)
      n._animRadius = startRadius
    }

    animFrameRef.current = requestAnimationFrame(animStep)
  }

  function animStep(now: number) {
    const elapsed = now - animStartRef.current
    const progress = Math.min(elapsed / ANIM_DURATION, 1)
    const ease = 1 - Math.pow(1 - progress, 3)

    if (animDimTargetRef.current !== null) {
      currentDimRef.current = animDimRef.current + (animDimTargetRef.current - animDimRef.current) * ease
    }

    if (animScaleStartRadiiRef.current.size > 0) {
      for (const n of data.nodes) {
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
      for (const n of data.nodes) {
        if (!n.visible) continue
        n._animRadius = undefined
      }
      if (animDimTargetRef.current !== null) {
        currentDimRef.current = animDimTargetRef.current
      }
      animFrameRef.current = null
    }
  }

  // ─── Initialize graph ───
  useEffect(() => {
    if (!data) return

    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    // Clear previous labels
    labelElementsRef.current.clear()
    labelVisibleSetRef.current = null

    // Compute size ranges
    const metrics = ['blastRadius', 'degree', 'risk', 'volume', 'centrality']
    const rangeKeys = ['blast', 'degree', 'risk', 'volume', 'centrality']
    for (let i = 0; i < metrics.length; i++) {
      const key = metrics[i]
      const rkey = rangeKeys[i]
      const values = data.nodes.map((n: any) => n[key] || 0).filter((v: number) => v > 0)
      if (values.length > 0) sizeRangeRef.current[rkey] = { min: 0, max: Math.max(...values) }
    }

    // Build node map
    nodeMapRef.current = new Map()
    for (const n of data.nodes) {
      n.visible = true
      n._animRadius = undefined
      nodeMapRef.current.set(n.id, n)
    }

    // Pre-resolve edges
    validEdgesRef.current = []
    for (const e of data.edges) {
      e.visible = true
      const srcId = typeof e.source === 'object' ? e.source.id : e.source
      const tgtId = typeof e.target === 'object' ? e.target.id : e.target
      const srcNode = nodeMapRef.current.get(srcId)
      const tgtNode = nodeMapRef.current.get(tgtId)
      if (!srcNode || !tgtNode) continue
      e.source = srcNode
      e.target = tgtNode
      validEdgesRef.current.push(e)
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
    data.nodes.forEach((n: any, i: number) => {
      const angle = (2 * Math.PI * i) / data.nodes.length
      const radius = 200 + Math.random() * 200
      n.x = w / 2 + radius * Math.cos(angle)
      n.y = h / 2 + radius * Math.sin(angle)
      n.vx = 0
      n.vy = 0
    })

    // Initial static layout
    const initSim = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(validEdgesRef.current).distance(120).strength(0.05))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(w / 2, h / 2).strength(0.02))
      .force('collision', d3.forceCollide().radius(25))
      .alpha(0.3)
      .alphaDecay(0.1)
      .velocityDecay(0.4)

    for (let i = 0; i < 200; i++) initSim.tick()
    initSim.stop()

    // Initial render
    render()

    // ─── Manual wheel zoom (replaces d3-zoom to avoid double transform) ───
    function onWheel(event: WheelEvent) {
      event.preventDefault()
      const rect = canvas.getBoundingClientRect()
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

    // ─── Mouse Events (left-click: node drag, pan, select) ───
    function getMousePos(event: MouseEvent) {
      const rect = canvas.getBoundingClientRect()
      const z = zoomRef.current
      return {
        x: (event.clientX - rect.left - z.x) / z.k,
        y: (event.clientY - rect.top - z.y) / z.k,
      }
    }

    function findNodeAt(pos: { x: number; y: number }) {
      for (let i = data.nodes.length - 1; i >= 0; i--) {
        const n = data.nodes[i]
        if (!n.visible) continue
        const dx = pos.x - n.x
        const dy = pos.y - n.y
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
        canvas.style.cursor = node ? 'pointer' : 'grab'
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
            onNodeSelect?.(node)
          } else {
            selectedNodeRef.current = null
            startAnimation(1)
            onNodeDeselect?.()
          }
        } else {
          isDraggingRef.current = false
          const node = draggedNodeRef.current
          if (simulationRef.current) {
            node.fx = null
            node.fy = null
          } else {
            node.fx = node.x
            node.fy = node.y
            // Settle after drag
            if (simulationRef.current) simulationRef.current.stop()
            const visibleNodes = data.nodes.filter((n: any) => n.visible)
            const visibleEdges = validEdgesRef.current.filter((e: any) => e.visible)
            simulationRef.current = d3.forceSimulation(visibleNodes)
              .force('link', d3.forceLink(visibleEdges).distance(120).strength(0.08))
              .force('charge', d3.forceManyBody().strength(-350).distanceMax(300))
              .force('collision', d3.forceCollide().radius(25).strength(0.7))
              .alpha(0.15)
              .alphaDecay(0.12)
              .velocityDecay(0.7)
              .on('tick', () => {
                render()
              })
              .on('end', () => {
                node.fx = null
                node.fy = null
                simulationRef.current = null
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
      } else if (!wasPanning) {
        selectedNodeRef.current = null
        startAnimation(1)
        onNodeDeselect?.()
      }
    }

    canvas.addEventListener('mousedown', onMouseDown, { capture: true })
    canvas.addEventListener('mousemove', onMouseMove, { capture: true })
    canvas.addEventListener('mouseup', onMouseUp, { capture: true })
    canvas.addEventListener('wheel', onWheel, { passive: false })

    // ─── Resize observer ───
    const resizeObserver = new ResizeObserver(() => {
      if (resizeRAFRef.current !== null) return
      resizeRAFRef.current = requestAnimationFrame(() => {
        resizeRAFRef.current = null
        const w = container.clientWidth
        const h = container.clientHeight
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

    // ─── Cleanup ───
    return () => {
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('wheel', onWheel)
      resizeObserver.disconnect()
      if (resizeRAFRef.current !== null) cancelAnimationFrame(resizeRAFRef.current)
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
    // Don't call deferRender — CSS vars update instantly, graph re-renders on next interaction
    // This avoids the freeze that occurs when idle callback fires synchronously
  }, [themeState]) // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Bridge ───
  useImperativeHandle(bridgeRef, () => ({
    // Visibility
    setVisibility: (visibleIds: Set<string>) => {
      for (const n of data.nodes) {
        n.visible = visibleIds.has(n.id)
      }
      startAnimation(null)
      if (simulationRef.current) {
        simulationRef.current.stop()
        startSimulation()
      }
    },
    setSearchTerm: (term: string) => {
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
      setShowLabelsState(show)
      deferRender()
    },

    // Simulation
    isSimulating: () => simulatingRef.current,
    startSimulation: () => {
      simulatingRef.current = true
      if (simulationRef.current) simulationRef.current.stop()
      const visibleNodes = data.nodes.filter((n: any) => n.visible)
      const visibleEdges = validEdgesRef.current.filter((e: any) => e.visible)
      simulationRef.current = d3.forceSimulation(visibleNodes)
        .force('link', d3.forceLink(visibleEdges).distance(120).strength(0.05))
        .force('charge', d3.forceManyBody().strength(-150))
        .force('center', d3.forceCenter(widthRef.current / 2, heightRef.current / 2).strength(0.02))
        .force('collision', d3.forceCollide().radius(25))
        .alpha(0.3)
        .alphaDecay(0)
        .alphaMin(0)
        .on('tick', () => render())
    },
    stopSimulation: () => {
      simulatingRef.current = false
      if (simulationRef.current) {
        simulationRef.current.stop()
        simulationRef.current = null
      }
    },

    // Selection
    selectNodeById: (id: string) => {
      const node = data.nodes.find((n: any) => n.id === id)
      if (node) {
        selectedNodeRef.current = node
        startAnimation(0.15)
        onNodeSelect?.(node)
      }
    },
    deselectNode: () => {
      selectedNodeRef.current = null
      startAnimation(1)
      onNodeDeselect?.()
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
  }), [data, onNodeSelect, onNodeDeselect])

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
