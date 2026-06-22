import { useState, useRef, useEffect, useCallback } from 'react'
import { GraphCanvas, type IGraphBridge } from '@/components/GraphCanvas'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuCheckboxItem } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Search, RotateCcw, Play, Settings, ChevronDown, Eye, EyeOff } from 'lucide-react'

// ─── Size Metrics ───
const SIZE_METRICS = [
  { key: 'degree', label: 'Degree' },
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
  const [showLabels, setShowLabels] = useState(true)
  const [showDetail, setShowDetail] = useState(false)
  const [sortBy, setSortBy] = useState<'name' | 'degree'>('name')

  const bridgeRef = useRef<IGraphBridge | null>(null)

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

  // Apply filters when search/categories change
  const applyFilters = useCallback(() => {
    if (!graphData || !bridgeRef.current) return

    const visibleIds = new Set<string>()
    for (const node of graphData.nodes) {
      const cat = node.typeCat || node.category || 'other'
      const catVisible = activeCategories.size === 0 || activeCategories.has(cat)
      const searchMatch = !searchTerm ||
        (node.term || node.label || node.id).toLowerCase().includes(searchTerm.toLowerCase()) ||
        node.id.toLowerCase().includes(searchTerm.toLowerCase())
      if (catVisible && searchMatch) {
        visibleIds.add(node.id)
      }
    }
    bridgeRef.current.setVisibility(visibleIds)
  }, [graphData, activeCategories, searchTerm])

  // Re-apply filters when dependencies change
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
    setShowDetail(true)
  }, [])

  const handleNodeDeselect = useCallback(() => {
    setSelectedNode(null)
    setShowDetail(false)
  }, [])

  // Compute sorted nodes
  const sortedNodes = graphData?.nodes
    .filter((n: any) => n.visible !== false)
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
              placeholder="Search nodes..."
              className="pl-9 h-8 text-sm"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
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
          <ScrollArea className="h-[120px]">
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
          </ScrollArea>
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
        </ScrollArea>
      </aside>

      {/* Main Canvas Area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Controls */}
        <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs bg-background/90 backdrop-blur"
            onClick={() => bridgeRef.current?.resetZoom()}
          >
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset Zoom
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs bg-background/90 backdrop-blur"
            onClick={() => bridgeRef.current?.toggleSimulation()}
          >
            <Play className="h-3.5 w-3.5 mr-1" />
            Simulate
          </Button>
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
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-xs bg-background/90 backdrop-blur"
            onClick={() => {
              setShowLabels((prev) => !prev)
              bridgeRef.current?.setLabels(!showLabels)
            }}
          >
            {showLabels ? <EyeOff className="h-3.5 w-3.5 mr-1" /> : <Eye className="h-3.5 w-3.5 mr-1" />}
            Labels
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs bg-background/90 backdrop-blur">
                <Settings className="h-3.5 w-3.5 mr-1" />
                Theme
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Dark</DropdownMenuItem>
              <DropdownMenuItem>Light</DropdownMenuItem>
              <DropdownMenuItem>Gruvbox</DropdownMenuItem>
              <DropdownMenuItem>Neon</DropdownMenuItem>
              <DropdownMenuItem>Retro</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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

      {/* Detail Panel (Sheet) */}
      <Sheet open={showDetail} onOpenChange={(open) => {
        if (!open) {
          bridgeRef.current?.deselectNode()
        }
      }}>
        <SheetContent side="right" className="w-[380px] sm:w-[380px]">
          {selectedNode && (
            <>
              <SheetHeader>
                <SheetTitle className="text-base">
                  <div className="flex flex-col gap-1.5">
                    <span className="text-lg">{selectedNode.term || selectedNode.label || selectedNode.id}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-[10px] uppercase">
                        {selectedNode.typeLabel || selectedNode.type || selectedNode.category || 'unknown'}
                      </Badge>
                      <span className="text-xs text-muted-foreground font-mono">
                        {selectedNode.id.split('-').slice(0, 2).join('-')}
                      </span>
                    </div>
                  </div>
                </SheetTitle>
                <SheetDescription className="text-sm leading-relaxed mt-2">
                  {selectedNode.description || 'No description available.'}
                </SheetDescription>
              </SheetHeader>
              <Separator className="my-3" />

              {/* Stats */}
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <Label className="text-muted-foreground">Connections</Label>
                  <span className="font-mono">{selectedNode.degree ?? 0}</span>
                </div>
                {selectedNode.blastRadius !== undefined && (
                  <div className="flex justify-between">
                    <Label className="text-muted-foreground">Blast Radius</Label>
                    <span className="font-mono">{selectedNode.blastRadius}</span>
                  </div>
                )}
                {selectedNode.risk !== undefined && (
                  <div className="flex justify-between">
                    <Label className="text-muted-foreground">Risk Score</Label>
                    <span className="font-mono">{selectedNode.risk}</span>
                  </div>
                )}
                {selectedNode.centrality !== undefined && (
                  <div className="flex justify-between">
                    <Label className="text-muted-foreground">Centrality</Label>
                    <span className="font-mono">{selectedNode.centrality?.toFixed(4)}</span>
                  </div>
                )}
              </div>

              {/* Specs */}
              {selectedNode.specs && selectedNode.specs.length > 0 && (
                <>
                  <Separator className="my-3" />
                  <div>
                    <Label className="text-xs text-muted-foreground mb-1.5 block">Specs</Label>
                    <div className="space-y-1">
                      {selectedNode.specs.map((spec: string, i: number) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {spec}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Connections */}
              {connections.length > 0 && (
                <>
                  <Separator className="my-3" />
                  <div>
                    <Label className="text-xs text-muted-foreground mb-1.5 block">
                      Connections ({connections.length})
                    </Label>
                    <ScrollArea className="max-h-[300px]">
                      <div className="space-y-0.5">
                        {connections.map((conn: any) => (
                          <button
                            key={conn.id}
                            onClick={() => bridgeRef.current?.selectNodeById(conn.id)}
                            className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-muted/50 text-left"
                          >
                            <Badge variant="secondary" className="text-[10px] flex-shrink-0">
                              {conn.type}
                            </Badge>
                            <span className="truncate flex-1">{conn.label}</span>
                            <span className="text-[10px] text-muted-foreground flex-shrink-0">
                              ({conn.edgeType})
                            </span>
                          </button>
                        ))}
                      </div>
                    </ScrollArea>
                  </div>
                </>
              )}
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

export default App
