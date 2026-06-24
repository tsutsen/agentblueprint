import { useRef, useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { applyTheme } from '@/lib/themes'
import { getConfig } from '@/lib/config'

// ─── Bridge Interface ───
// Everything the parent app can command or query via the bridge ref.
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
  // Graph data (required)
  data: any

  // Bridge ref (parent gets bridge via this ref)
  bridgeRef?: React.Ref<IGraphBridge | null>

  // Events (canvas → parent)
  onNodeSelect?: (node: any) => void
  onNodeDeselect?: () => void

  // Called when graph is fully initialized and ready
  onReady?: () => void

  // Optional className for the container
  className?: string
}

declare global {
  interface Window {
    __GRAPH_WRAPPER__: any
    __GRAPH_READY__: Promise<any>
  }
}

/**
 * GraphCanvas — Self-contained D3 canvas graph component.
 *
 * Manages its own internal state (theme, size metric, labels, simulation).
 * Parent app syncs via the bridge ref:
 *   - Read state: bridge.getTheme(), bridge.getSizeMetric(), etc.
 *   - Set state: bridge.setTheme(), bridge.setSizeMetric(), etc.
 *   - Commands: bridge.selectNodeById(), bridge.deselectNode(), etc.
 *
 * The parent app is responsible for:
 *   - Sidebar UI (checkboxes, search, node list)
 *   - Detail panel UI (node info, connections)
 *   - Control bar UI (zoom, simulate, metric, theme)
 *   - URL state sync
 */
export function GraphCanvas({
  data,
  bridgeRef,
  onNodeSelect,
  onNodeDeselect,
  onReady,
  className,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Store data in a ref so bridge functions always reference current data
  const dataRef = useRef(data)
  useEffect(() => {
    dataRef.current = data
  }, [data])

  // Internal state managed by the graph
  const [theme, setThemeState] = useState(getConfig().defaultTheme)
  const [sizeMetric, setSizeMetricState] = useState(getConfig().defaultSizeMetric)
  const [showLabels, setShowLabelsState] = useState(getConfig().defaultShowLabels)
  const [simulating, setSimulatingState] = useState(getConfig().defaultSimulating)

  // Initialize graph once on mount
  useEffect(() => {
    let cancelled = false
    setReady(false)

    ;(async () => {
      const wrapper = await window.__GRAPH_READY__
      if (cancelled || !wrapper) {
        if (!cancelled) setError('Graph wrapper failed to load. Check console.')
        return
      }

      // Set data and callbacks
      wrapper.setGraphData(dataRef.current)
      wrapper.setNodeSelectCallbacks(
        (_event: any, node: any) => onNodeSelect?.(node),
        () => onNodeDeselect?.()
      )

      // Initialize the graph
      wrapper.initGraph()
      if (cancelled) return

      // Handle container resize (throttled via rAF)
      const container = containerRef.current
      if (!container) return

      let resizeRAF: number | null = null
      const resizeObserver = new ResizeObserver(() => {
        if (cancelled || resizeRAF !== null) return
        resizeRAF = requestAnimationFrame(() => {
          resizeRAF = null
          if (cancelled) return
          const { clientWidth: w, clientHeight: h } = container!
          wrapper.setWidth(w)
          wrapper.setHeight(h)
          wrapper.renderGraph()
        })
      })
      resizeObserver.observe(container)

      // Create and expose the bridge
      const bridge: IGraphBridge = {
        // ── Visibility ──
        setVisibility: (visibleIds: Set<string>) => {
          for (const n of dataRef.current.nodes) {
            n.visible = visibleIds.has(n.id)
          }
          wrapper.startAnimation(null)
          if (wrapper.hasSimulation()) {
            wrapper.stopSimulation()
            wrapper.startSimulation()
          }
        },
        setSearchTerm: (term: string) => {
          wrapper.setSearchTerm(term)
          wrapper.startAnimation(null)
        },

        // ── Theme ──
        getTheme: () => theme,
        setTheme: (newTheme: string) => {
          setThemeState(newTheme)
          applyTheme(newTheme)
          wrapper.updateThemeColors()
        },
        updateTheme: () => {
          wrapper.updateThemeColors()
        },

        // ── Size metric ──
        getSizeMetric: () => sizeMetric,
        setSizeMetric: (metric: string) => {
          setSizeMetricState(metric)
          wrapper.setSizeMetric(metric)
          wrapper.recalcSizeRange()
          wrapper.startAnimation(null)
          wrapper.renderGraph()
        },

        // ── Labels ──
        getLabels: () => showLabels,
        setLabels: (show: boolean) => {
          setShowLabelsState(show)
          wrapper.setShowLabels(show)
          wrapper.renderGraph()
        },

        // ── Simulation ──
        isSimulating: () => simulating,
        startSimulation: () => {
          setSimulatingState(true)
          wrapper.startSimulation()
        },
        stopSimulation: () => {
          setSimulatingState(false)
          wrapper.stopSimulation()
        },

        // ── Selection ──
        selectNodeById: (id: string) => {
          const node = dataRef.current.nodes.find((n: any) => n.id === id)
          if (node) {
            wrapper.setSelectedNode(node)
            wrapper.startAnimation(0.15)
            onNodeSelect?.(node)
          }
        },
        deselectNode: () => {
          wrapper.deselectNode()
        },
        getSelectedNode: () => wrapper.getSelectedNode(),

        // ── Zoom ──
        zoomIn: () => {
          const w = wrapper.getWidth() || 800
          const h = wrapper.getHeight() || 600
          const z = wrapper.getZoom()
          const centerX = w / 2
          const centerY = h / 2
          const newK = Math.min(z.k * 1.3, 10)
          const newX = centerX - (centerX - z.x) * (newK / z.k)
          const newY = centerY - (centerY - z.y) * (newK / z.k)
          wrapper.setZoom(newX, newY, newK)
          wrapper.renderGraph()
        },
        zoomOut: () => {
          const w = wrapper.getWidth() || 800
          const h = wrapper.getHeight() || 600
          const z = wrapper.getZoom()
          const centerX = w / 2
          const centerY = h / 2
          const newK = Math.max(z.k / 1.3, 0.1)
          const newX = centerX - (centerX - z.x) * (newK / z.k)
          const newY = centerY - (centerY - z.y) * (newK / z.k)
          wrapper.setZoom(newX, newY, newK)
          wrapper.renderGraph()
        },
        resetZoom: () => {
          const w = wrapper.getWidth() || 800
          const h = wrapper.getHeight() || 600
          const k = 0.3
          wrapper.setZoom(-w / 2 * k + w / 2, -h / 2 * k + h / 2, k)
          wrapper.renderGraph()
        },
        getZoom: () => wrapper.getZoom(),

        // ── Render ──
        triggerRender: () => wrapper.renderGraph(),
      }

      // Attach bridge to ref if provided
      if (bridgeRef) {
        if (typeof bridgeRef === 'function') {
          bridgeRef(bridge)
        } else {
          bridgeRef.current = bridge
        }
      }

      setReady(true)
      onReady?.()

      // Cleanup on unmount
      return () => {
        resizeObserver.disconnect()
        if (resizeRAF !== null) cancelAnimationFrame(resizeRAF)
      }
    })()

    // Cleanup
    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-background">
        <div className="text-center space-y-2 text-sm">
          <p className="text-destructive">⚠ {error}</p>
          <p className="text-muted-foreground">Check console for details</p>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      id="graph-container"
      className={cn('w-full h-full relative', className || '')}
    >
      <canvas
        id="graph-canvas"
        className="absolute inset-0"
      />
      <div
        id="labels-container"
        className="absolute inset-0 pointer-events-none"
      />
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
          <div className="text-center space-y-2">
            <div className="animate-spin h-6 w-6 border-2 border-primary border-t-transparent rounded-full mx-auto" />
            <p className="text-sm text-muted-foreground">Loading graph...</p>
          </div>
        </div>
      )}
    </div>
  )
}
