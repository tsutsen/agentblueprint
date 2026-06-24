import { useRef, useEffect, useState, useCallback, useImperativeHandle } from 'react'
import * as d3 from 'd3'

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

function getNodeColor(d: any): string {
  const cat = d.typeCat || d.category || d.type || 'other'
  let hash = 0
  for (let i = 0; i < cat.length; i++) hash = cat.charCodeAt(i) + ((hash << 5) - hash)
  const idx = Math.abs(hash) % 12
  const cssVar = `--node-color-${idx}`
  try {
    const color = getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
    if (color) return color
  } catch { /* fallback */ }
  return '#94a3b8'
}

function getEdgeColor(): string {
  try {
    const val = getComputedStyle(document.documentElement).getPropertyValue('--edge-color').trim()
    if (val) return val
  } catch { /* fallback */ }
  return 'rgba(148, 163, 184, 0.4)'
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

  // Internal state (managed by the graph)
  const [theme] = useState(() => localStorage.getItem('graph-theme') || 'default')
  const [sizeMetric, setSizeMetricState] = useState('degree')
  const [showLabels, setShowLabelsState] = useState(true)
  const [simulating, setSimulatingState] = useState(false)

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
  const widthRef = useRef(800)
  const heightRef = useRef(600)
  const resizeRAFRef = useRef<number | null>(null)

  // ─── Build label set (progressive disclosure) ───
  function buildLabelSet() {
    const z = zoomRef.current
    const zoomDelta = Math.abs(z.k - lastLabelZoomRef.current)
    if (zoomDelta < LABEL_HYSTERESIS && labelVisibleSetRef.current !== null) return
    lastLabelZoomRef.current = z.k

    if (!showLabels || z.k < LABEL_MIN_ZOOM || !data) {
      labelVisibleSetRef.current = null
      return
    }

    const candidates: any[] = []
    for (const n of data.nodes) {
      if (!n.visible) continue
      if (z.k < LABEL_MAX_ZOOM) {
        const screenRadius = getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current) * z.k
        if (screenRadius < LABEL_NODE_RADIUS_THRESHOLD) continue
      }
      candidates.push(n)
    }

    candidates.sort((a, b) => getNodeRadius(b, sizeMetric, sizeRangeRef.current, connectedSetRef.current) - getNodeRadius(a, sizeMetric, sizeRangeRef.current, connectedSetRef.current))

    const fontSize = 13 / z.k
    const cellSize = fontSize * 2
    const occupied = new Map<string, true>()

    const cellKey = (wx: number, wy: number) => `${Math.floor(wx / cellSize)},${Math.floor(wy / cellSize)}`

    const labelBBox = (n: any) => {
      const r = getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current)
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
      const r = getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSet)
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

    const w = widthRef.current
    const h = heightRef.current
    const z = zoomRef.current

    // Clear full canvas (canvas has w*dpr x h*dpr pixels)
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Scale context for DPR so all drawing uses CSS coordinates (matching node positions)
    const dpr = window.devicePixelRatio || 1
    ctx.scale(dpr, dpr)
    ctx.save()
    ctx.translate(z.x, z.y)
    ctx.scale(z.k, z.k)

    // Build connected set
    connectedSetRef.current = null
    let connectedEdges: Set<any> | null = null
    if (selectedNodeRef.current) {
      connectedSetRef.current = new Set([selectedNodeRef.current.id])
      connectedEdges = new Set()
      for (const e of validEdgesRef.current) {
        if (e.source.id === selectedNodeRef.current.id || e.target.id === selectedNodeRef.current.id) {
          connectedSetRef.current.add(e.source.id)
          connectedSetRef.current.add(e.target.id)
          connectedEdges.add(e)
        }
      }
    }

    recalcSizeRange()
    buildLabelSet()

    const edgeColor = getEdgeColor()
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
      const r = n._animRadius !== undefined ? Math.max(0, n._animRadius) : getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current)
      const color = getNodeColor(n)
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

      const cs = getComputedStyle(document.documentElement)
      const strokeColor = isSelected
        ? cs.getPropertyValue('--node-stroke-selected').trim() || '#fff'
        : (cs.getPropertyValue('--node-stroke').trim() || d3.color(color).darker(0.8).formatHex())
      ctx.strokeStyle = strokeColor
      const strokeWidth = parseFloat(cs.getPropertyValue('--node-stroke-width')) || 1
      ctx.lineWidth = (isSelected ? strokeWidth * 2 : strokeWidth) / z.k
      ctx.stroke()

      if (isHovered && !isSelected) {
        ctx.strokeStyle = cs.getPropertyValue('--node-stroke-hover').trim() || '#fff'
        ctx.lineWidth = strokeWidth * 2 / z.k
        ctx.stroke()
      }
    }

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
      oldRadii.set(n.id, n._animRadius ?? getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current))
    }

    // Build connected set for correct target radii
    connectedSetRef.current = null
    if (selectedNodeRef.current) {
      connectedSetRef.current = new Set([selectedNodeRef.current.id])
      for (const e of validEdgesRef.current) {
        if (e.source.id === selectedNodeRef.current.id || e.target.id === selectedNodeRef.current.id) {
          connectedSetRef.current.add(e.source.id)
          connectedSetRef.current.add(e.target.id)
        }
      }
    }
    recalcSizeRange()

    animScaleStartRadiiRef.current = new Map()
    animScaleTargetsRef.current = new Map()
    for (const n of data.nodes) {
      if (!n.visible) continue
      const startRadius = oldRadii.get(n.id) ?? getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current)
      const targetRadius = getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current)
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
        const r = getNodeRadius(n, sizeMetric, sizeRangeRef.current, connectedSetRef.current) + 5
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
              .on('tick', () => render())
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
    const cs = document.documentElement.style
    const themeColors: Record<string, Record<string, string>> = {
      default: {
        '--node-color-0': '#60a5fa', '--node-color-1': '#34d399', '--node-color-2': '#f472b6',
        '--node-color-3': '#a78bfa', '--node-color-4': '#fb923c', '--node-color-5': '#2dd4bf',
        '--node-color-6': '#f87171', '--node-color-7': '#818cf8', '--node-color-8': '#22d3ee',
        '--node-color-9': '#fbbf24', '--node-color-10': '#4ade80', '--node-color-11': '#e879f9',
        '--node-stroke': '#1e293b', '--node-stroke-selected': '#fff', '--node-stroke-hover': '#94a3b8',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(148, 163, 184, 0.4)',
      },
      ocean: {
        '--node-color-0': '#0ea5e9', '--node-color-1': '#06b6d4', '--node-color-2': '#0284c7',
        '--node-color-3': '#0891b2', '--node-color-4': '#0d9488', '--node-color-5': '#14b8a6',
        '--node-color-6': '#38bdf8', '--node-color-7': '#7dd3fc', '--node-color-8': '#bae6fd',
        '--node-color-9': '#e0f2fe', '--node-color-10': '#0c4a6e', '--node-color-11': '#0369a1',
        '--node-stroke': '#0c4a6e', '--node-stroke-selected': '#7dd3fc', '--node-stroke-hover': '#38bdf8',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(14, 165, 233, 0.3)',
      },
      forest: {
        '--node-color-0': '#22c55e', '--node-color-1': '#16a34a', '--node-color-2': '#15803d',
        '--node-color-3': '#166534', '--node-color-4': '#84cc16', '--node-color-5': '#65a30d',
        '--node-color-6': '#a3e635', '--node-color-7': '#4ade80', '--node-color-8': '#86efac',
        '--node-color-9': '#bbf7d0', '--node-color-10': '#052e16', '--node-color-11': '#14532d',
        '--node-stroke': '#052e16', '--node-stroke-selected': '#86efac', '--node-stroke-hover': '#4ade80',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(34, 197, 94, 0.3)',
      },
      sunset: {
        '--node-color-0': '#f97316', '--node-color-1': '#ef4444', '--node-color-2': '#ec4899',
        '--node-color-3': '#f59e0b', '--node-color-4': '#fb7185', '--node-color-5': '#f43f5e',
        '--node-color-6': '#fbbf24', '--node-color-7': '#fb923c', '--node-color-8': '#fde68a',
        '--node-color-9': '#fecaca', '--node-color-10': '#7c2d12', '--node-color-11': '#881337',
        '--node-stroke': '#7c2d12', '--node-stroke-selected': '#fecaca', '--node-stroke-hover': '#fbbf24',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(249, 115, 22, 0.3)',
      },
      purple: {
        '--node-color-0': '#8b5cf6', '--node-color-1': '#a855f7', '--node-color-2': '#7c3aed',
        '--node-color-3': '#6d28d9', '--node-color-4': '#c084fc', '--node-color-5': '#e879f9',
        '--node-color-6': '#d946ef', '--node-color-7': '#f0abfc', '--node-color-8': '#c4b5fd',
        '--node-color-9': '#ddd6fe', '--node-color-10': '#3b0764', '--node-color-11': '#581c87',
        '--node-stroke': '#3b0764', '--node-stroke-selected': '#ddd6fe', '--node-stroke-hover': '#c084fc',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(139, 92, 246, 0.3)',
      },
      monochrome: {
        '--node-color-0': '#64748b', '--node-color-1': '#475569', '--node-color-2': '#334155',
        '--node-color-3': '#1e293b', '--node-color-4': '#94a3b8', '--node-color-5': '#cbd5e1',
        '--node-color-6': '#e2e8f0', '--node-color-7': '#f1f5f9', '--node-color-8': '#0f172a',
        '--node-color-9': '#475569', '--node-color-10': '#1e293b', '--node-color-11': '#64748b',
        '--node-stroke': '#0f172a', '--node-stroke-selected': '#e2e8f0', '--node-stroke-hover': '#94a3b8',
        '--node-stroke-width': '1.5', '--edge-color': 'rgba(100, 116, 139, 0.4)',
      },
      neon: {
        '--node-color-0': '#00ff88', '--node-color-1': '#00ccff', '--node-color-2': '#ff00ff',
        '--node-color-3': '#ffff00', '--node-color-4': '#ff6600', '--node-color-5': '#ff0088',
        '--node-color-6': '#00ffcc', '--node-color-7': '#cc00ff', '--node-color-8': '#88ff00',
        '--node-color-9': '#0088ff', '--node-color-10': '#000000', '--node-color-11': '#ffffff',
        '--node-stroke': '#000000', '--node-stroke-selected': '#00ff88', '--node-stroke-hover': '#00ccff',
        '--node-stroke-width': '2', '--edge-color': 'rgba(0, 204, 255, 0.3)',
      },
    }

    const colors = themeColors[theme] || themeColors.default
    for (const [key, value] of Object.entries(colors)) {
      cs.setProperty(key, value)
    }
    render()
  }, [theme]) // eslint-disable-line react-hooks/exhaustive-deps

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
    getTheme: () => theme,
    setTheme: (newTheme: string) => {
      localStorage.setItem('graph-theme', newTheme)
      // Re-render will apply new theme via useEffect
    },
    updateTheme: () => {
      render()
    },

    // Size metric
    getSizeMetric: () => sizeMetric,
    setSizeMetric: (metric: string) => {
      setSizeMetricState(metric)
      startAnimation(null)
      render()
    },

    // Labels
    getLabels: () => showLabels,
    setLabels: (show: boolean) => {
      setShowLabelsState(show)
      render()
    },

    // Simulation
    isSimulating: () => simulating,
    startSimulation: () => {
      setSimulatingState(true)
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
      setSimulatingState(false)
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
  }), [data, theme, sizeMetric, showLabels, simulating, onNodeSelect, onNodeDeselect])

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
