import { useState, useRef, useEffect, useCallback } from 'react'
import { GraphCanvas, type IGraphBridge } from '@/components/GraphCanvas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { X } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuCheckboxItem } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Search, RotateCcw, Play, Settings, ChevronDown, ZoomIn, ZoomOut } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Switch } from '@/components/ui/switch'
import { themes, applyTheme } from '@/lib/themes'

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

  const bridgeRef = useRef<IGraphBridge | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

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

        // Activate all categories by default
        setActiveCategories(new Set(Object.keys(catCounts)))
      })
      .catch((err) => console.error('Failed to load graph data:', err))
  }, [])

  // Debounced search term
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 250)
    return () => clearTimeout(timer)
  }, [searchTerm])

  // Apply filters when search/categories change (only after bridge is ready)
  const applyFilters = useCallback(() => {
    if (!graphData || !bridgeRef.current || !bridgeReady) return

    const visibleIds = new Set<string>()
    for (const node of graphData.nodes) {
      const cat = node.typeCat || node.category || 'other'
      const catVisible = activeCategories.size === 0 || activeCategories.has(cat)
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

  // Handle node selection
  const handleNodeSelect = useCallback((node: any) => {
    setSelectedNode(node)
  }, [])

  const handleNodeDeselect = useCallback(() => {
    setSelectedNode(null)
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

  // Compute visible node IDs (same logic as applyFilters)
  const visibleIds = new Set(graphData?.nodes.filter((node: any) => {
    const cat = node.typeCat || node.category || 'other'
    const catVisible = activeCategories.size === 0 || activeCategories.has(cat)
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

  // Compute connections for selected node
  const connections = selectedNode
    ? graphData?.edges
        ?.filter((e: any) => e.source?.id === selectedNode.id || e.target?.id === selectedNode.id)
        .map((e: any) => {
          const neighbor = e.source?.id === selectedNode.id ? e.target : e.source
          return {
            id: neighbor.id,
            label: neighbor.term || neighbor.label || neighbor.id,
            type: neighbor.typeLabel || neighbor.type || neighbor.category || 'unknown',
            edgeType: e.type || 'related',
          }
        })
        .sort((a: any, b: any) => a.type.localeCompare(b.type))
    : []

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-[300px] min-w-[300px] flex flex-col border-r border-border bg-muted/30">
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
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-5 px-1.5 text-[10px]">
                  Toggle all
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                {Object.entries(categories).map(([cat, { count }]) => (
                  <DropdownMenuCheckboxItem
                    key={cat}
                    checked={activeCategories.has(cat)}
                    onCheckedChange={(checked) => {
                      setActiveCategories((prev) => {
                        const next = new Set(prev)
                        checked ? next.add(cat) : next.delete(cat)
                        return next
                      })
                    }}
                  >
                    {cat.charAt(0).toUpperCase() + cat.slice(1)} ({count})
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
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
              <Button variant="ghost" size="sm" className="h-5 px-1.5 text-[10px]">
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
          ) : sortedNodes.length === 0 && activeCategories.size > 0 ? (
            <p className="px-3 py-4 text-sm text-muted-foreground text-center">All categories hidden</p>
          ) : (
            <div className="space-y-0.5">
              {sortedNodes.map((node: any) => (
                <button
                  key={node.id}
                  onClick={() => bridgeRef.current?.selectNodeById(node.id)}
                  className={`w-full flex items-center gap-2 px-2 py-1 rounded text-sm text-left transition-colors ${
                    selectedNode?.id === node.id
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-muted/50'
                  }`}
                >
                  <span className="truncate font-medium text-foreground flex-1">
                    {node.term || node.label || node.id}
                  </span>
                  <Badge variant="secondary" className="text-[10px] flex-shrink-0 font-mono">
                    {node.degree ?? 0}
                  </Badge>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </aside>

      {/* Main Canvas Area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Controls */}
        <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
          <Tooltip>
            <TooltipTrigger asChild>
              <label className="flex items-center gap-1 bg-background/90 backdrop-blur rounded-md px-1.5 h-7 text-xs cursor-pointer">
                <Play className="h-3.5 w-3.5" />
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
            <TooltipContent side="bottom">Simulation</TooltipContent>
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
                {selectedNode.definition || 'No description available.'}
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
