import { useRef, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export interface IGraphBridge {
  setVisibility: (visibleIds: Set<string>) => void
  setSizeMetric: (metric: string) => void
  selectNodeById: (id: string) => void
  deselectNode: () => void
  resetZoom: () => void
  toggleSimulation: () => void
  updateTheme: () => void
  setLabels: (show: boolean) => void
  setSpecs: (show: boolean) => void
  getSelectedNode: () => any | null
  getZoom: () => { x: number; y: number; k: number }
  triggerRender: () => void
}

declare global {
  interface Window {
    __GRAPH_WRAPPER__: any
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

  useEffect(() => {
    if (!data) return

    const wrapper = window.__GRAPH_WRAPPER__
    if (!wrapper) {
      setError('Graph wrapper not loaded. Check /legacy/bootstrap.js')
      return
    }

    let cancelled = false
    setReady(false)

    // Set data and callbacks
    wrapper.setGraphData(data)
    wrapper.setNodeSelectCallbacks(
      (_event: any, node: any) => onNodeSelect?.(node),
      () => onNodeDeselect?.()
    )

    // Initialize the graph
    wrapper.initGraph()

    if (cancelled) return

    // Handle container resize
    const container = containerRef.current
    if (!container) return

    const resizeObserver = new ResizeObserver(() => {
      if (cancelled) return
      const { clientWidth: w, clientHeight: h } = container
      wrapper.setWidth(w)
      wrapper.setHeight(h)
      wrapper.renderGraph()
    })
    resizeObserver.observe(container)

    // Create and expose the bridge
    bridge.current = {
      setVisibility: (visibleIds: Set<string>) => {
        for (const n of data.nodes) {
          n.visible = visibleIds.has(n.id)
        }
        wrapper.startScaleAnimation()
      },
      setSizeMetric: (metric: string) => {
        wrapper.setSizeMetric(metric)
        wrapper.recalcSizeRange()
        wrapper.startScaleAnimation()
        wrapper.renderGraph()
      },
      selectNodeById: (id: string) => {
        const node = data.nodes.find((n: any) => n.id === id)
        if (node) {
          wrapper.setSelectedNode(node)
          wrapper.animateDim(0.15)
          wrapper.startScaleAnimation()
        }
      },
      deselectNode: () => {
        wrapper.deselectNode()
      },
      resetZoom: () => {
        wrapper.setZoom(0, 0, 1)
        wrapper.renderGraph()
      },
      toggleSimulation: () => {
        wrapper.toggleSimulation()
      },
      updateTheme: () => {
        wrapper.updateThemeColors()
      },
      setLabels: (show: boolean) => {
        wrapper.setShowLabels(show)
        wrapper.renderGraph()
      },
      setSpecs: (show: boolean) => {
        wrapper.setShowSpecs(show)
        wrapper.renderGraph()
      },
      getSelectedNode: () => wrapper.getSelectedNode(),
      getZoom: () => wrapper.getZoom(),
      triggerRender: () => wrapper.renderGraph(),
    }

    setReady(true)

    // Cleanup
    return () => {
      resizeObserver.disconnect()
      bridge.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

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
