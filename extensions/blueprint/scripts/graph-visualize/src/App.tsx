import { useState, useRef, useEffect, useCallback } from 'react'
import { GraphCanvas, type IGraphBridge } from '@/components/GraphCanvas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { X } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Search, RotateCcw, Settings, ChevronDown, ZoomIn, ZoomOut } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Switch } from '@/components/ui/switch'
import { themes, applyTheme } from '@/lib/themes'

/** Extract clean short ID: PREFIX-NNN (handles TST-NNN-xxx, TST-xxx-NNN, CON-NNN-xxx, FLW-NNN-xxx, and slug-style IDs) */
function extractShortId(id: string, type?: string): string {
  const parts = id.split('-')
  const numIdx = parts.findIndex(p => /^\d+$/.test(p))
  if (numIdx >= 0) {
    return `${parts[0]}-${parts[numIdx]}`
  }
  // Slug-style IDs (e.g. "citation-network-builder") — use type prefix
  if (type) return type.toUpperCase()
  return parts.slice(0, 2).join('-')
}

// ─── Size Metrics ───
const SIZE_METRICS = [
  { key: 'degree', label: 'Degree' },
  { key: 'type', label: 'Type' },
  { key: 'blast', label: 'Blast Radius' },
  { key: 'risk', label: 'Risk Score' },
  { key: 'centrality', label: 'Centrality' },
]

function App() {
  const [graphData, setGraphData] = useState<any>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set())
  const [categories, setCategories] = useState<Record<string, { count: number; color: string }>>({})
  const [sizeMetric, setSizeMetric] = useState('degree')
  const [sortBy, setSortBy] = useState<'name' | 'degree'>('name')
  const [bridgeReady, setBridgeReady] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(300)

  const bridgeRef = useRef<IGraphBridge | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const resizeRef = useRef<HTMLDivElement>(null)

  // Sidebar resize handler
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

    handle.addEventListener('mousedown', (e) => {
      startX = e.clientX
      startWidth = sidebarWidth
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      e.preventDefault()
    })
  }, [sidebarWidth])

  // Load graph data
  useEffect(() => {
    fetch('/graph-data.json')
      .then((res) => res.json())
      .then((data) => {
        setGraphData(data)

        // Compute categories
        const catCounts: Record<string, { count: number; color: string }> = {}
        const defaultColors: Record<string, string> = {
          domain: '#f472b6', technical: '#38bdf8', security: '#fbbf24',
          ui: '#a78bfa', spec: '#34d399', req: '#38bdf8', nfr: '#7dd3fc',
          con: '#a78bfa', fn: '#34d399', test: '#f87171', gl: '#fbbf24',
          design: '#c084fc', data: '#4ade80', api: '#f472b6', plan: '#facc15',
          other: '#94a3b8',
        }
        for (const node of data.nodes) {
          const cat = node.typeCat || node.category || 'other'
          if (!catCounts[cat]) {
            catCounts[cat] = { count: 0, color: defaultColors[cat] || '#94a3b8' }
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
          // Activate all categories by default
          setActiveCategories(new Set(Object.keys(catCounts)))
        }
        const qParam = params.get('q')
        if (qParam) {
          setSearchTerm(qParam)
        }
      })
      .catch((err) => console.error('Failed to load graph data:', err))
  }, [])

  // Debounced search term + URL sync
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 250)
    return () => clearTimeout(timer)
  }, [searchTerm])

  // Sync URL on state changes (after initial load)
  useEffect(() => {
    if (!graphData) return
    const params = new URLSearchParams(window.location.search)
    // cats
    if (activeCategories.size > 0 && activeCategories.size < Object.keys(categories).length) {
      params.set('cats', [...activeCategories].sort().join(','))
    } else {
      params.delete('cats')
    }
    // q
    if (searchTerm) {
      params.set('q', searchTerm)
    } else {
      params.delete('q')
    }
    // node (only if different from current)
    // (node param is handled in handleNodeSelect/handleNodeDeselect)
    const newURL = `?${params.toString()}`
    history.replaceState(null, '', newURL)
  }, [activeCategories, searchTerm, categories, graphData])

  // Apply filters when search/categories change (only after bridge is ready)
  const applyFilters = useCallback(() => {
    if (!graphData || !bridgeRef.current || !bridgeReady) return

    const visibleIds = new Set<string>()
    for (const node of graphData.nodes) {
      const cat = node.typeCat || node.category || 'other'
      const catVisible = activeCategories.has(cat)
      const searchMatch = !debouncedSearch ||
        (node.term || node.label || node.id).toLowerCase().includes(debouncedSearch.toLowerCase())
      if (catVisible && searchMatch) {
        visibleIds.add(node.id)
      }
    }
    bridgeRef.current.setVisibility(visibleIds)
  }, [graphData, activeCategories, debouncedSearch, bridgeReady])

  useEffect(() => {
    applyFilters()
  }, [applyFilters])

  // Handle size metric change
  const handleSizeMetricChange = useCallback((metric: string) => {
    setSizeMetric(metric)
    bridgeRef.current?.setSizeMetric(metric)
  }, [])

  // Handle node selection — sync to URL
  const handleNodeSelect = useCallback((node: any) => {
    setSelectedNode(node)
    const params = new URLSearchParams(window.location.search)
    params.set('node', node.id)
    history.replaceState(null, '', `?${params.toString()}`)
  }, [])

  // Handle node deselection — sync to URL
  const handleNodeDeselect = useCallback(() => {
    setSelectedNode(null)
    const params = new URLSearchParams(window.location.search)
    params.delete('node')
    history.replaceState(null, '', `?${params.toString()}`)
  }, [])

  // Keyboard shortcuts: Escape to deselect/clear search, K to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (selectedNode) {
          bridgeRef.current?.deselectNode()
        } else if (searchTerm) {
          setSearchTerm('')
          searchInputRef.current?.blur()
        }
      }
      if ((e.key === 'k' || e.key === 'K') && !selectedNode) {
        const target = e.target as HTMLElement
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          e.preventDefault()
          searchInputRef.current?.focus()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedNode, searchTerm])

  // Mark bridge as ready once data is loaded
  useEffect(() => {
    if (graphData) setBridgeReady(true)
  }, [graphData])

  // Restore selected node from URL after bridge is ready
  useEffect(() => {
    if (!graphData || !bridgeReady) return
    const params = new URLSearchParams(window.location.search)
    const nodeId = params.get('node')
    if (!nodeId) return
    const node = graphData.nodes.find((n: any) => n.id === nodeId)
    if (!node) return
    // Select the node
    bridgeRef.current?.selectNodeById(nodeId)
  }, [graphData, bridgeReady])

  // Compute visible node IDs (same logic as applyFilters)
  const visibleIds = new Set(graphData?.nodes.filter((node: any) => {
    const cat = node.typeCat || node.category || 'other'
    const catVisible = activeCategories.has(cat)
    const searchMatch = !debouncedSearch ||
      (node.term || node.label || node.id).toLowerCase().includes(debouncedSearch.toLowerCase())
    return catVisible && searchMatch
  }).map((n: any) => n.id) || [])

  // Compute sorted + filtered nodes (sidebar)
  const sortedNodes = graphData?.nodes
    .filter((n: any) => visibleIds.has(n.id))
    .sort((a: any, b: any) => {
      if (sortBy === 'degree') return (b.degree || 0) - (a.degree || 0)
      return (a.term || a.label || a.id).localeCompare(b.term || b.label || b.id)
    }) || []

  // Compute connections for selected node (deduplicated by neighbor id)
  const connections = selectedNode
    ? (() => {
        const seen = new Map<string, any>()
        graphData?.edges
          ?.filter((e: any) => e.source?.id === selectedNode.id || e.target?.id === selectedNode.id)
          .forEach((e: any) => {
            const neighbor = e.source?.id === selectedNode.id ? e.target : e.source
            const key = neighbor.id
            if (!seen.has(key)) {
              seen.set(key, {
                id: neighbor.id,
                label: neighbor.term || neighbor.label || neighbor.id,
                type: neighbor.typeLabel || neighbor.type || neighbor.category || 'unknown',
                edgeType: e.type || 'related',
              })
            }
          })
        return [...seen.values()].sort((a: any, b: any) => a.type.localeCompare(b.type))
      })()
    : []

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside style={{ width: sidebarWidth, minWidth: 200, maxWidth: 800 }} className="flex flex-col border-r border-border bg-muted/30">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <h1 className="text-sm font-bold text-foreground">
            {graphData ? `${graphData.project} · v${graphData.version}` : 'Glossary Graph'}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {graphData ? `${graphData.nodes.length} nodes, ${graphData.edges.length} edges` : 'Loading...'}
          </p>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-border">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search nodes... (K)"
              className="pl-9 h-8 text-sm"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              ref={searchInputRef}
            />
          </div>
        </div>

        {/* Filters */}
        <div className="p-3 border-b border-border">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground">Categories</h3>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 px-1.5 text-[10px]"
              onClick={() => {
                if (activeCategories.size === Object.keys(categories).length) {
                  setActiveCategories(new Set())
                } else {
                  setActiveCategories(new Set(Object.keys(categories)))
                }
              }}
            >
              {activeCategories.size === Object.keys(categories).length ? 'Deselect all' : 'Select all'}
            </Button>
          </div>
          <div>
            <div className="space-y-0.5">
              {Object.entries(categories)
                .sort((a, b) => b[1].count - a[1].count)
                .map(([cat, { count, color }]) => (
                  <label
                    key={cat}
                    className="flex items-center gap-2 p-1 rounded cursor-pointer hover:bg-muted/50 text-sm"
                  >
                    <Checkbox
                      id={`cat-${cat}`}
                      checked={activeCategories.has(cat)}
                      onCheckedChange={(checked) => {
                        setActiveCategories((prev) => {
                          const next = new Set(prev)
                          checked ? next.add(cat) : next.delete(cat)
                          return next
                        })
                      }}
                    />
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="flex-1 truncate">{cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
                    <span className="text-xs text-muted-foreground font-mono">{count}</span>
                  </label>
                ))}
            </div>
          </div>
        </div>

        {/* Node List */}
        <div className="px-3 py-1.5 border-b border-border flex items-center gap-1">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground">Nodes</h3>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-5 px-1.5 text-[10px] ml-auto">
                Sort: {sortBy}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => setSortBy('name')}>Name</DropdownMenuItem>
              <DropdownMenuItem onClick={() => setSortBy('degree')}>Degree</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <ScrollArea className="flex-1 p-1">
          {sortedNodes.length === 0 && debouncedSearch ? (
            <p className="px-3 py-4 text-sm text-muted-foreground text-center">No matches for "{debouncedSearch}"</p>
          ) : sortedNodes.length === 0 && activeCategories.size === 0 ? (
            <p className="px-3 py-4 text-sm text-muted-foreground text-center">No categories selected</p>
          ) : sortedNodes.length === 0 ? (
            <p className="px-3 py-4 text-sm text-muted-foreground text-center">All categories hidden</p>
          ) : (
            <div className="space-y-0.5">
              {sortedNodes.map((node: any) => {
                const idShort = (node.type === 'spec' || node.category === 'spec')
                  ? 'SPEC'
                  : extractShortId(node.id, node.type);
                const catDisplay = node.typeLabel || node.type || node.category || 'unknown';
                return (
                  <button
                    key={node.id}
                    onClick={() => bridgeRef.current?.selectNodeById(node.id)}
                    className={`w-full min-w-0 max-w-full flex items-center gap-2 px-2 py-1 rounded text-left transition-colors ${
                      selectedNode?.id === node.id
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted/50'
                    }`}
                  >
                    <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
                      {idShort}
                    </span>
                    <span className="text-sm text-foreground flex-1 min-w-0 truncate">
                      {node.term || node.label || node.id}
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
                      {catDisplay}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </aside>

      {/* Resize Handle */}
      <div
        ref={resizeRef}
        className="w-[4px] cursor-col-resize hover:bg-primary/20 active:bg-primary/40 transition-colors flex-shrink-0"
      />

      {/* Main Canvas Area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Controls */}
        <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
          <Tooltip>
            <TooltipTrigger asChild>
              <label className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2 h-8 text-xs font-medium bg-background/90 backdrop-blur border border-input cursor-pointer hover:bg-accent hover:text-accent-foreground">
                Simulation
                <Switch
                  checked={simulating}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      bridgeRef.current?.startSimulation()
                    } else {
                      bridgeRef.current?.stopSimulation()
                    }
                    setSimulating(checked)
                  }}
                />
              </label>
            </TooltipTrigger>
          </Tooltip>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs bg-background/90 backdrop-blur">
                Size: {SIZE_METRICS.find((m) => m.key === sizeMetric)?.label}
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {SIZE_METRICS.map((m) => (
                <DropdownMenuItem
                  key={m.key}
                  onClick={() => handleSizeMetricChange(m.key)}
                >
                  {m.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs bg-background/90 backdrop-blur">
                <Settings className="h-3.5 w-3.5 mr-1" />
                Theme
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {themes.map((t) => (
                <DropdownMenuItem
                  key={t.key}
                  onClick={() => {
                    applyTheme(t.key)
                    bridgeRef.current?.updateTheme()
                  }}
                >
                  {t.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Zoom Controls — bottom left */}
        <div className="absolute bottom-3 left-3 flex items-center gap-1 z-10">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 bg-background/90 backdrop-blur"
                onClick={() => bridgeRef.current?.zoomIn()}
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Zoom in</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 bg-background/90 backdrop-blur"
                onClick={() => bridgeRef.current?.zoomOut()}
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Zoom out</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-8 w-8 p-0 bg-background/90 backdrop-blur"
                onClick={() => bridgeRef.current?.resetZoom()}
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Reset zoom</TooltipContent>
          </Tooltip>
        </div>

        {/* Graph Canvas */}
        {graphData && (
          <GraphCanvas
            data={graphData}
            bridge={bridgeRef}
            onNodeSelect={handleNodeSelect}
            onNodeDeselect={handleNodeDeselect}
          />
        )}
      </main>

      {/* Detail Panel — floating card, auto-height with max-height scroll */}
      {selectedNode && (
        <div data-testid="detail-panel" className="absolute top-4 right-4 w-[360px] max-h-[calc(100%-2rem)] bg-card border border-border rounded-xl shadow-lg z-40 flex flex-col overflow-hidden">
          {/* Header */}
          <div data-testid="detail-header" className="flex items-start justify-between p-4 border-b border-border">
            <div data-testid="detail-header-text" className="flex flex-col gap-1 pr-2 min-w-0 flex-1">
              <span data-testid="detail-node-name" className="text-base font-semibold break-words overflow-wrap-anywhere">{selectedNode.term || selectedNode.label || selectedNode.id}</span>
              <div className="flex items-center gap-2">
                <Badge data-testid="detail-type-badge" variant="secondary" className="text-[10px] uppercase">
                  {selectedNode.typeLabel || selectedNode.type || selectedNode.category || 'unknown'}
                </Badge>
                <span data-testid="detail-node-id" className="text-xs text-muted-foreground font-mono">
                  {selectedNode.id.split('-').slice(0, 2).join('-')}
                </span>
              </div>
            </div>
            <Button
              data-testid="detail-close-btn"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 shrink-0"
              onClick={() => bridgeRef.current?.deselectNode()}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Scrollable content */}
          <div data-testid="detail-scroll" className="flex-1 overflow-y-auto overflow-x-hidden">
            <div data-testid="detail-body" className="p-4 w-full">
              <p data-testid="detail-description" className="text-sm leading-relaxed text-muted-foreground break-words overflow-wrap-anywhere max-w-full">
                {selectedNode.definition || selectedNode.term || selectedNode.label || 'No description available.'}
              </p>

              <Separator className="my-3" />

              {/* Stats */}
              <div data-testid="detail-stats" className="space-y-1.5 text-sm">
                <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
                  <Label className="text-muted-foreground">Connections</Label>
                  <span data-testid="detail-stat-degree" className="font-mono text-right">{selectedNode.degree ?? 0}</span>
                </div>
                {selectedNode.blastRadius !== undefined && (
                  <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
                    <Label className="text-muted-foreground">Blast Radius</Label>
                    <span data-testid="detail-stat-blast-radius" className="font-mono text-right">{selectedNode.blastRadius}</span>
                  </div>
                )}
                {selectedNode.risk !== undefined && (
                  <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
                    <Label className="text-muted-foreground">Risk Score</Label>
                    <span data-testid="detail-stat-risk" className="font-mono text-right">{selectedNode.risk}</span>
                  </div>
                )}
                {selectedNode.centrality !== undefined && (
                  <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
                    <Label className="text-muted-foreground">Centrality</Label>
                    <span data-testid="detail-stat-centrality" className="font-mono text-right">{selectedNode.centrality?.toFixed(4)}</span>
                  </div>
                )}
              </div>

              {/* Connections */}
              {connections.length > 0 && (
                <>
                  <Separator className="my-3" />
                  <div data-testid="detail-connections" className="w-full">
                    <Label className="text-xs text-muted-foreground mb-1.5 block">
                      Connections ({connections.length})
                    </Label>
                    <div className="space-y-0.5">
                        {connections.map((conn: any) => (
                          <button
                            data-testid={`detail-connection-${conn.id}`}
                            key={conn.id}
                            onClick={() => bridgeRef.current?.selectNodeById(conn.id)}
                            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-muted/50 text-left"
                          >
                            <span data-testid={`detail-conn-label-${conn.id}`} className="truncate flex-1 min-w-0">{conn.label}</span>
                            <Badge variant="secondary" className="text-[10px] flex-shrink-0">
                              {conn.type}
                            </Badge>
                          </button>
                        ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
    </TooltipProvider>
  )
}

export default App
