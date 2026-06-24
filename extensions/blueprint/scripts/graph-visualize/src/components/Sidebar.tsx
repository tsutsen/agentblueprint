import { forwardRef, useImperativeHandle, useRef } from 'react'
import type { GraphData, GraphNode } from '@/lib/graph-types'
import { SidebarSearch } from './SidebarSearch'
import { SidebarFilters } from './SidebarFilters'
import { SidebarNodeList } from './SidebarNodeList'

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

export const Sidebar = forwardRef<SidebarHandle, SidebarProps>(function Sidebar(props, ref) {
  const searchInputRef = useRef<HTMLInputElement>(null)

  useImperativeHandle(ref, () => ({
    focusSearch: () => searchInputRef.current?.focus(),
  }))

  const {
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
  } = props

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
      <SidebarSearch
        ref={searchInputRef}
        value={searchTerm}
        onChange={onSearchChange}
      />

      {/* Category Filters */}
      <SidebarFilters
        categories={categories}
        activeCategories={activeCategories}
        onCategoryChange={onCategoryChange}
      />

      {/* Node List */}
      <SidebarNodeList
        nodes={sortedNodes}
        selectedNodeId={selectedNode?.id ?? null}
        sortBy={sortBy}
        onSortChange={onSortChange}
        debouncedSearch={debouncedSearch}
        onSelectNode={onSelectNode}
      />
    </>
  )
})
