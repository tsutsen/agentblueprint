import type { GraphNode } from '@/lib/graph-types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { X } from 'lucide-react'

export interface ConnectionInfo {
  id: string
  label: string
  type: string
  edgeType: string
}

export interface DetailPanelProps {
  node: GraphNode
  connections: ConnectionInfo[]
  onClose: () => void
  onSelectNode: (id: string) => void
}

export function DetailPanel({ node, connections, onClose, onSelectNode }: DetailPanelProps) {
  return (
    <div data-testid="detail-panel" className="absolute top-4 right-4 w-[360px] max-h-[calc(100%-2rem)] bg-card border border-border rounded-xl shadow-lg z-40 flex flex-col overflow-hidden">
      {/* Header */}
      <div data-testid="detail-header" className="flex items-start justify-between p-4 border-b border-border">
        <div data-testid="detail-header-text" className="flex flex-col gap-1 pr-2 min-w-0 flex-1">
          <span data-testid="detail-node-name" className="text-base font-semibold break-words overflow-wrap-anywhere">{node.name || node.id}</span>
          <div className="flex items-center gap-2">
            <Badge data-testid="detail-type-badge" variant="secondary" className="text-[10px] uppercase">
              {node.category}
            </Badge>
            <span data-testid="detail-node-id" className="text-xs text-muted-foreground font-mono">
              {node.id.split('-').slice(0, 2).join('-')}
            </span>
          </div>
        </div>
        <Button
          data-testid="detail-close-btn"
          variant="ghost"
          size="sm"
          className="h-7 w-7 p-0 shrink-0"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Scrollable content */}
      <div data-testid="detail-scroll" className="flex-1 overflow-y-auto overflow-x-hidden">
        <div data-testid="detail-body" className="p-4 w-full">
          <p data-testid="detail-description" className="text-sm leading-relaxed text-muted-foreground break-words overflow-wrap-anywhere max-w-full">
            {node.description || node.name || 'No description available.'}
          </p>

          <Separator className="my-3" />

          {/* Stats */}
          <div data-testid="detail-stats" className="space-y-1.5 text-sm">
            <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
              <Label className="text-muted-foreground">Connections</Label>
              <span data-testid="detail-stat-degree" className="font-mono text-right">{node.metrics.degree ?? 0}</span>
            </div>
            <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
              <Label className="text-muted-foreground">Blast Radius</Label>
              <span data-testid="detail-stat-blast-radius" className="font-mono text-right">{node.metrics.blast}</span>
            </div>
            <div className="grid grid-cols-[1fr_auto] items-center gap-x-3">
              <Label className="text-muted-foreground">Risk Score</Label>
              <span data-testid="detail-stat-risk" className="font-mono text-right">{node.metrics.risk}</span>
            </div>
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
                  {connections.map((conn) => (
                    <button
                      data-testid={`detail-connection-${conn.id}`}
                      key={conn.id}
                      onClick={() => onSelectNode(conn.id)}
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
  )
}
