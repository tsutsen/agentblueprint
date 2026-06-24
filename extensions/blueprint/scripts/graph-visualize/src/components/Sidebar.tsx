import { forwardRef, useImperativeHandle, useRef, memo } from 'react'
import type { GraphData, GraphNode } from '@/lib/graph-types'
import { extractShortId } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Search } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

export interface SidebarHandle {
  focusSearch: () => void
}

export interface SidebarProps {
  graphData: GraphData | null
  selectedNode: GraphNode | null
  searchTerm: string
  onSearchChange: (value: string) => void
  categories: Record<string, { count: number; color: string }>
  activeCategories: Set<string>
  onCategoryChange: (cat: string, checked: boolean) => void
  sortedNodes: GraphNode[]
  sortBy: 'name' | 'degree'
  onSortChange: (by: 'name' | 'degree') => void
  debouncedSearch: string
  onSelectNode: (id: string) => void
}

// ─── Memoized sidebar node item ───
const SidebarNodeItem = memo(function SidebarNodeItem({
  node,
  isSelected,
  onSelectNodeId,
}: {
  node: GraphNode
  isSelected: boolean
  onSelectNodeId: (id: string) => void
}) {
  const idShort = extractShortId(node.id)
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={() => onSelectNodeId(node.id)}
          className={`w-full min-w-0 max-w-full text-left rounded transition-colors px-2 py-1 ${
            isSelected ? 'bg-primary/10 text-primary' : 'hover:bg-muted/50'
          }`}
        >
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
              {idShort}
            </span>
            <span className="text-[10px] text-muted-foreground/60 flex-shrink-0">·</span>
            <span className="text-[10px] text-muted-foreground font-mono flex-shrink-0 whitespace-nowrap">
              {node.category}
            </span>
          </div>
          <span className="text-sm text-foreground truncate block min-w-0">
            {node.name || node.id}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-[300px]">
        {node.name || node.id}
      </TooltipContent>
    </Tooltip>
  )
})

function SidebarContent({
  graphData,
  selectedNode,
  searchTerm,
  onSearchChange,
  categories,
  activeCategories,
  onCategoryChange,
  sortedNodes,
  sortBy,
  onSortChange,
  debouncedSearch,
  onSelectNode,
  searchInputRef,
}: SidebarProps & { searchInputRef: React.RefObject<HTMLInputElement | null> }) {
  return (
    <>
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
            onChange={(e) => onSearchChange(e.target.value)}
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
                onCategoryChange('__toggle_all__', false)
              } else {
                onCategoryChange('__toggle_all__', true)
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
                    onCheckedChange={(checked) => onCategoryChange(cat, checked === true)}
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
            <DropdownMenuItem onClick={() => onSortChange('name')}>Name</DropdownMenuItem>
            <DropdownMenuItem onClick={() => onSortChange('degree')}>Degree</DropdownMenuItem>
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
            {sortedNodes.map((node) => (
              <SidebarNodeItem
                key={node.id}
                node={node}
                isSelected={selectedNode?.id === node.id}
                onSelectNodeId={onSelectNode}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </>
  )
}

export const Sidebar = forwardRef<SidebarHandle, SidebarProps>(function Sidebar(props, ref) {
  const searchInputRef = useRef<HTMLInputElement>(null)

  useImperativeHandle(ref, () => ({
    focusSearch: () => searchInputRef.current?.focus(),
  }))

  return (
    <SidebarContent
      {...props}
      searchInputRef={searchInputRef as React.RefObject<HTMLInputElement | null>}
    />
  )
})
