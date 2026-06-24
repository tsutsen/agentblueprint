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
import { Search, RotateCcw, ChevronDown, ZoomIn, ZoomOut } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Switch } from '@/components/ui/switch'
import { themes } from '@/lib/themes'
import { SIZE_METRICS } from '@/lib/metrics'

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

function App() {
  const [graphData, setGraphData] = useState<any>(null)
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeCategories, setActiveCategories] = useState<Set<string>>(new Set())
  const [categories, setCategories] = useState<Record<string, { count: number; color: string }>>({})
  const [sortBy, setSortBy] = useState<'name' | 'degree'>('name')
  const [sidebarWidth, setSidebarWidth] = useState(300)
  const [isSimulating, setIsSimulating] = useState(false)
  const [showLabels, setShowLabels] = useState(true)
  const [sizeMetric, setSizeMetricState] = useState('degree')
  const [currentTheme, setCurrentTheme] = useState('default')

  const bridgeRef = useRef<IGraphBridge | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const resizeRef = useRef<HTMLDivElement>(null)

  // ─── Load graph data ───
  useEffect(() => {
    fetch('/graph-data.json')
      .then((res) => res.json())
      .then((data) => {
        setGraphData(data)

        // Compute categories
        const catCounts: Record<string, { count: number; color: string }> = {}
        function getCatColor(cat: string): string {
          let hash = 0
          for (let i = 0; i < cat.length; i++) hash = cat.charCodeAt(i) + ((hash << 5) - hash)
          const idx = Math.abs(hash) % 12
          return `var(--node-color-${idx})`
        }
        for (const node of data.nodes) {
          const cat = node.typeCat || node.category || node.type || 'other'
          if (!catCounts[cat]) {
            catCounts[cat] = { count: 0, color: getCatColor(cat) }
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
      .catch((err) => console.error('Failed to load graph data:', err))
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
    const ids = new Set(graphData.nodes.filter((node: any) => {
      const cat = node.typeCat || node.category || 'other'
      const catVisible = activeCategories.has(cat)
      const searchMatch = !debouncedSearch ||
        (node.term || node.label || node.id).toLowerCase().includes(debouncedSearch.toLowerCase())
      return catVisible && searchMatch
    }).map((n: any) => n.id))
    bridgeRef.current.setVisibility(ids)
  }, [activeCategories, debouncedSearch, graphData])

  useEffect(() => {
    if (!bridgeRef.current) return
    bridgeRef.current.setSearchTerm(searchTerm)
  }, [searchTerm])

  // ─── Sync URL on user interaction ───
  const handleCategoryChange = (cat: string, checked: boolean) => {
    setActiveCategories((prev) => {
      const next = new Set(prev)
      checked ? next.add(cat) : next.delete(cat)
      return next
    })
  }

  // Sync URL on user interaction (categories/search)
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
  const handleNodeSelect = useCallback((node: any) => {
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

  // ─── Keyboard shortcuts ───
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

  // ─── Visible + sorted nodes (for sidebar) ───
  const visibleIds = new Set(graphData?.nodes.filter((node: any) => {
    const cat = node.typeCat || node.category || 'other'
    const catVisible = activeCategories.has(cat)
    const searchMatch = !debouncedSearch ||
      (node.term || node.label || node.id).toLowerCase().includes(debouncedSearch.toLowerCase())
    return catVisible && searchMatch
  }).map((n: any) => n.id) || [])

  const sortedNodes = graphData?.nodes
    .filter((n: any) => visibleIds.has(n.id))
    .sort((a: any, b: any) => {
      if (sortBy === 'degree') return (b.degree || 0) - (a.degree || 0)
      return (a.term || a.label || a.id).localeCompare(b.term || b.label || b.id)
    }) || []

  // ─── Connections for selected node ───
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
    <TooltipProvider delayDuration={500}>
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
                      onCheckedChange={(checked) => handleCategoryChange(cat, checked === true)}
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
                  <Tooltip key={node.id}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => bridgeRef.current?.selectNodeById(node.id)}
                        className={`w-full min-w-0 max-w-full text-left rounded transition-colors px-2 py-1 ${
                          selectedNode?.id === node.id
                            ? 'bg-primary/10 text-primary'
                            : 'hover:bg-muted/50'
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
                            {idShort}
                          </span>
                          <span className="text-[10px] text-muted-foreground/60 flex-shrink-0">·</span>
                          <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
                            {catDisplay}
                          </span>
                        </div>
                        <span className="text-sm text-foreground truncate block min-w-0">
                          {node.term || node.label || node.id}
                        </span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-[300px]">
                      {node.term || node.label || node.id}
                    </TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </aside>

      {/* Resize Handle */}
      <div
        ref={resizeRef}
        className="w-[4px] cursor-col-resize hover:bg-primary/20 active-primary/40 transition-colors flex-shrink-0"
      />

      {/* Main Canvas Area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Controls */}
        <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
          <Tooltip>
            <TooltipTrigger asChild>
              <label className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2 h-8 text-xs font-medium bg-background/90 backdrop-blur border border-input cursor-pointer graph-control-btn">
                Simulation
                <Switch
                  checked={isSimulating}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      bridgeRef.current?.startSimulation()
                    } else {
                      bridgeRef.current?.stopSimulation()
                    }
                    setIsSimulating(checked)
                  }}
                />
              </label>
            </TooltipTrigger>
          </Tooltip>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs bg-background backdrop-blur graph-control-btn">
                Size: {SIZE_METRICS.find((m) => m.key === sizeMetric)?.label}
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {SIZE_METRICS.map((m) => (
                <DropdownMenuItem
                  key={m.key}
                  onClick={() => {
                    bridgeRef.current?.setSizeMetric(m.key)
                    setSizeMetricState(m.key)
                  }}
                >
                  {m.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs bg-background backdrop-blur graph-control-btn">
                Theme: {themes.find((t) => t.key === currentTheme)?.label || 'Default'}
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {themes.map((t) => (
                <DropdownMenuItem
                  key={t.key}
                  onClick={() => {
                    bridgeRef.current?.setTheme(t.key)
                    setCurrentTheme(t.key)
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
                className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
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
                className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
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
                className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
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
            bridgeRef={bridgeRef}
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
