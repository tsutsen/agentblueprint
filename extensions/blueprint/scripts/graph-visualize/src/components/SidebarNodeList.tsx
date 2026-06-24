import { memo } from 'react'
import type { GraphNode } from '@/lib/graph-types'
import { extractShortId } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

export type SortBy = 'name' | 'degree'

export interface SidebarNodeListProps {
  nodes: GraphNode[]
  selectedNodeId: string | null
  sortBy: SortBy
  onSortChange: (by: SortBy) => void
  debouncedSearch: string
  onSelectNode: (id: string) => void
}

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

export function SidebarNodeList({
  nodes,
  selectedNodeId,
  sortBy,
  onSortChange,
  debouncedSearch,
  onSelectNode,
}: SidebarNodeListProps) {
  const isEmpty = nodes.length === 0

  return (
    <>
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
        {isEmpty ? (
          <p className="px-3 py-4 text-sm text-muted-foreground text-center">
            {debouncedSearch
              ? `No matches for "${debouncedSearch}"`
              : 'No nodes to display'}
          </p>
        ) : (
          <div className="space-y-0.5">
            {nodes.map((node) => (
              <SidebarNodeItem
                key={node.id}
                node={node}
                isSelected={selectedNodeId === node.id}
                onSelectNodeId={onSelectNode}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </>
  )
}
