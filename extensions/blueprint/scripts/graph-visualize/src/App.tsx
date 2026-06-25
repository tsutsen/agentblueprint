import { useState, useRef, useEffect, useCallback } from 'react'
import { GraphCanvas, type IGraphBridge } from '@/components/GraphCanvas'
import { Sidebar, type SidebarHandle } from '@/components/Sidebar'
import { DetailPanel, type ConnectionInfo } from '@/components/DetailPanel'
import { Controls } from '@/components/Controls'
import type { GraphData, GraphNode } from '@/lib/graph-types'
import { getVisibleNodeIds, getNodeConnections, hashToIndex } from '@/lib/utils'
import { TooltipProvider } from '@/components/ui/tooltip'

// Module-level fetch — runs once, survives StrictMode double-mount
const graphDataPromise = fetch('/graph-data.json')
  .then((res) => res.json())
  .then((data: GraphData) => data)
  .catch((err) => { console.error('Failed to load graph data:', err); return null })

function App() {
  // ─── State ───
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set())
  const [categories, setCategories] = useState<Record<string, { count: number; color: string }>>({})
  const [sortBy, setSortBy] = useState<'name' | 'degree'>('name')
  const [sidebarWidth, setSidebarWidth] = useState(300)
  const [sizeMetric, setSizeMetricState] = useState('degree')
  const [currentTheme, setCurrentTheme] = useState('default')

  const bridgeRef = useRef<IGraphBridge | null>(null)
  const resizeRef = useRef<HTMLDivElement>(null)
  const sidebarWidthRef = useRef(sidebarWidth)
  sidebarWidthRef.current = sidebarWidth // keep ref in sync

  // ─── Sync canvas state → parent UI on mount ───
  useEffect(() => {
    if (!bridgeRef.current) return
    setCurrentTheme(bridgeRef.current.getTheme())
    setSizeMetricState(bridgeRef.current.getSizeMetric())
  }, [graphData])

  // ─── Load graph data (module-level promise, fetched once) ───
  useEffect(() => {
    graphDataPromise.then((data) => {
      if (!data) return
      setGraphData(data)

      // Compute categories
      const catCounts: Record<string, { count: number; color: string }> = {}
      for (const node of data.nodes) {
        const cat = node.category
        if (!catCounts[cat]) {
          catCounts[cat] = { count: 0, color: `var(--node-color-${hashToIndex(cat)})` }
        }
        catCounts[cat].count++
      }
      setCategories(catCounts)

      // Restore state from URL
      const params = new URLSearchParams(window.location.search)
      const catsParam = params.get('cats')
      if (catsParam) {
        const cats = new Set(catsParam.split(',').map(c => c.trim()).filter(Boolean))
        setActiveCategories(cats)
      } else {
        setActiveCategories(new Set(Object.keys(catCounts)))
      }
      const qParam = params.get('q')
      if (qParam) {
        setSearchTerm(qParam)
      }
    })
  }, [])

  // ─── Debounced search ───
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 250)
    return () => clearTimeout(timer)
  }, [searchTerm])

  // ─── Sync parent state → graph via bridge ───
  useEffect(() => {
    if (!bridgeRef.current || !graphData) return
    const ids = getVisibleNodeIds(graphData, activeCategories, debouncedSearch)
    bridgeRef.current.setVisibility(ids)
  }, [activeCategories, debouncedSearch, graphData])

  useEffect(() => {
    if (!bridgeRef.current) return
    bridgeRef.current.setSearchTerm(searchTerm)
  }, [searchTerm])

  // ─── Category toggle ───
  const handleCategoryChange = useCallback((cat: string, checked: boolean) => {
    if (cat === '__toggle_all__') {
      setActiveCategories((prev) => {
        const allCats = Object.keys(categories)
        return prev.size === allCats.length ? new Set() : new Set(allCats)
      })
      return
    }
    setActiveCategories((prev) => {
      const next = new Set(prev)
      checked ? next.add(cat) : next.delete(cat)
      return next
    })
  }, [categories])

  // ─── Sync URL on user interaction (categories/search) ───
  useEffect(() => {
    if (!graphData) return
    const params = new URLSearchParams(window.location.search)
    if (activeCategories.size > 0 && activeCategories.size < Object.keys(categories).length) {
      params.set('cats', [...activeCategories].sort().join(','))
    } else {
      params.delete('cats')
    }
    if (searchTerm) {
      params.set('q', searchTerm)
    } else {
      params.delete('q')
    }
    history.replaceState(null, '', `?${params.toString()}`)
  }, [activeCategories, searchTerm, categories, graphData])

  // ─── Node selection ───
  const handleNodeSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node)
    const params = new URLSearchParams(window.location.search)
    params.set('node', node.id)
    history.replaceState(null, '', `?${params.toString()}`)
  }, [])

  const handleNodeDeselect = useCallback(() => {
    setSelectedNode(null)
    const params = new URLSearchParams(window.location.search)
    params.delete('node')
    history.replaceState(null, '', `?${params.toString()}`)
  }, [])

  // ─── Sidebar node selection (stable callback for memoized items) ───
  const handleSidebarSelect = useCallback((id: string) => {
    bridgeRef.current?.selectNodeById(id)
  }, [])

  // ─── Keyboard shortcuts ───
  const sidebarRef = useRef<SidebarHandle>(null)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (selectedNode) {
          bridgeRef.current?.deselectNode()
        } else if (searchTerm) {
          setSearchTerm('')
        }
      }
      if ((e.key === 'k' || e.key === 'K') && !selectedNode) {
        const target = e.target as HTMLElement
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault()
          sidebarRef.current?.focusSearch()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedNode, searchTerm])

  // ─── Sidebar resize ───
  useEffect(() => {
    const handle = resizeRef.current
    if (!handle) return

    let startX: number, startWidth: number

    const onMouseMove = (e: MouseEvent) => {
      const diff = e.clientX - startX
      const newWidth = Math.max(200, Math.min(800, startWidth + diff))
      setSidebarWidth(newWidth)
    }

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    const onMouseDown = (e: MouseEvent) => {
      startX = e.clientX
      startWidth = sidebarWidthRef.current
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      e.preventDefault()
    }

    handle.addEventListener('mousedown', onMouseDown)
    return () => handle.removeEventListener('mousedown', onMouseDown)
  }, [])

  // ─── Visible + sorted nodes ───
  const visibleIds = graphData ? getVisibleNodeIds(graphData, activeCategories, debouncedSearch) : new Set()

  const sortedNodes = graphData?.nodes
    .filter((n: GraphNode) => visibleIds.has(n.id))
    .sort((a: GraphNode, b: GraphNode) => {
      if (sortBy === 'degree') return b.metrics.degree - a.metrics.degree
      return a.name.localeCompare(b.name)
    }) || []

  // ─── Connections for selected node ───
  const connections: ConnectionInfo[] = selectedNode && graphData
    ? getNodeConnections(graphData, selectedNode.id)
    : []

  return (
    <TooltipProvider delayDuration={500}>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
        {/* Sidebar */}
        <aside style={{ width: sidebarWidth, minWidth: 200, maxWidth: 800 }} className="flex flex-col border-r border-border bg-muted/30">
          <Sidebar
            ref={sidebarRef}
            graphData={graphData}
            selectedNode={selectedNode}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            categories={categories}
            activeCategories={activeCategories}
            onCategoryChange={handleCategoryChange}
            sortedNodes={sortedNodes}
            sortBy={sortBy}
            onSortChange={setSortBy}
            debouncedSearch={debouncedSearch}
            onSelectNode={handleSidebarSelect}
          />
        </aside>

        {/* Resize Handle */}
        <div
          ref={resizeRef}
          className="w-[4px] cursor-col-resize hover:bg-primary/20 active-primary/40 transition-colors flex-shrink-0"
        />

        {/* Main Canvas Area */}
        <main className="flex-1 relative overflow-hidden">
          <Controls
            bridgeRef={bridgeRef}
            sizeMetric={sizeMetric}
            onSizeMetricChange={setSizeMetricState}
            currentTheme={currentTheme}
            onThemeChange={setCurrentTheme}
          />

          {/* Graph Canvas */}
          {graphData && (
            <GraphCanvas
              data={graphData}
              bridgeRef={bridgeRef}
              onNodeSelect={handleNodeSelect}
              onNodeDeselect={handleNodeDeselect}
            />
          )}
        </main>

        {/* Detail Panel */}
        {selectedNode && (
          <DetailPanel
            node={selectedNode}
            connections={connections}
            onClose={() => bridgeRef.current?.deselectNode()}
            onSelectNode={handleSidebarSelect}
          />
        )}
      </div>
    </TooltipProvider>
  )
}

export default App
