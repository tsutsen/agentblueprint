import { useRef, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export interface IGraphBridge {
  setVisibility: (visibleIds: Set<string>) => void
  setSizeMetric: (metric: string) => void
  selectNodeById: (id: string) => void
  deselectNode: () => void
  resetZoom: () => void
  startSimulation: () => void
  stopSimulation: () => void
  zoomIn: () => void
  zoomOut: () => void
  updateTheme: () => void
  setLabels: (show: boolean) => void
  getSelectedNode: () => any | null
  getZoom: () => { x: number; y: number; k: number }
  triggerRender: () => void
}

declare global {
  interface Window {
    __GRAPH_WRAPPER__: any
    __GRAPH_READY__: Promise<any>
  }
}

export interface GraphCanvasProps {
  data: any
  bridge: React.MutableRefObject<IGraphBridge | null>
  onNodeSelect?: (node: any) => void
  onNodeDeselect?: () => void
  className?: string
}

/**
 * GraphCanvas — Uses the pre-loaded legacy D3 graph via window.__GRAPH_WRAPPER__.
 * The bootstrap.js script loads D3 + graph.js + config.js as native ES modules
 * before the React app mounts, so the wrapper is ready synchronously.
 */
export function GraphCanvas({ data, bridge, onNodeSelect, onNodeDeselect, className }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Store data in a ref so bridge functions always reference current data
  const dataRef = useRef(data)
  useEffect(() => { dataRef.current = data }, [data])
  // Mark as ready once data is available (no re-run on data changes)
  useEffect(() => {
    if (data) setReady(true)
  }, [data])

  useEffect(() => {
    if (!data) return

    let cancelled = false
    setReady(false)

    // Wait for the legacy modules to be ready, then initialize
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
      bridge.current = {
        setVisibility: (visibleIds: Set<string>) => {
          for (const n of dataRef.current.nodes) {
            n.visible = visibleIds.has(n.id)
          }
          wrapper.startAnimation(null)
          // Restart simulation so newly visible nodes are included
          if (wrapper.hasSimulation()) {
            wrapper.stopSimulation()
            wrapper.startSimulation()
          }
        },
        setSizeMetric: (metric: string) => {
          wrapper.setSizeMetric(metric)
          wrapper.recalcSizeRange()
          wrapper.startAnimation(null)
          wrapper.renderGraph()
        },
        selectNodeById: (id: string) => {
          const node = dataRef.current.nodes.find((n: any) => n.id === id)
          if (node) {
            wrapper.setSelectedNode(node)
            wrapper.startAnimation(0.15)
            // Trigger the selection callback so React detail panel updates
            onNodeSelect?.(node)
          }
        },
        deselectNode: () => {
          wrapper.deselectNode()
        },
        resetZoom: () => {
          wrapper.setZoom(0, 0, 1)
          wrapper.renderGraph()
        },
        startSimulation: () => {
          wrapper.startSimulation()
        },
        stopSimulation: () => {
          wrapper.stopSimulation()
        },
        zoomIn: () => {
          const z = wrapper.getZoom()
          const newK = Math.min(z.k * 1.3, 10)
          wrapper.setZoom(z.x, z.y, newK)
          wrapper.renderGraph()
        },
        zoomOut: () => {
          const z = wrapper.getZoom()
          const newK = Math.max(z.k / 1.3, 0.1)
          wrapper.setZoom(z.x, z.y, newK)
          wrapper.renderGraph()
        },
        updateTheme: () => {
          wrapper.updateThemeColors()
        },
        setLabels: (show: boolean) => {
          wrapper.setShowLabels(show)
          wrapper.renderGraph()
        },
        getSelectedNode: () => wrapper.getSelectedNode(),
        getZoom: () => wrapper.getZoom(),
        triggerRender: () => wrapper.renderGraph(),
      }

      setReady(true)

      // Cleanup on unmount (don't null bridge.current — App.tsx needs it)
      return () => {
        resizeObserver.disconnect()
        if (resizeRAF !== null) cancelAnimationFrame(resizeRAF)
      }
    })()

    // Cleanup
    return () => {
      cancelled = true
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
