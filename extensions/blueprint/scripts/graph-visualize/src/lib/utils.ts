import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { GraphData } from '@/lib/graph-types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Extract clean short ID: PREFIX-NNN (handles TST-NNN-xxx, TST-xxx-NNN, CON-NNN-xxx, FLW-NNN-xxx, and slug-style IDs) */
export function extractShortId(id: string): string {
  const parts = id.split('-')
  const numIdx = parts.findIndex(p => /^\d+$/.test(p))
  if (numIdx >= 0) {
    return `${parts[0]}-${parts[numIdx]}`
  }
  // Slug-style IDs (e.g. "citation-network-builder") — show first two segments
  return parts.slice(0, 2).join('-')
}

/** Hash a string to a stable index in [0, bucketCount) */
export function hashToIndex(str: string, bucketCount = 12): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash)
  return Math.abs(hash) % bucketCount
}

/** Map a value from one range to another, with a slight power curve for better visual spread */
export function scaleValue(value: number, minVal: number, maxVal: number, minOut = 8, maxOut = 40): number {
  if (maxVal === minVal) return minVal === 0 && maxVal === 0 ? maxOut : minOut
  const normalized = Math.max(0, Math.min(1, (value - minVal) / (maxVal - minVal)))
  return minOut + Math.pow(normalized, 1.5) * (maxOut - minOut)
}

/** Filter visible node IDs by category and search term */
export function getVisibleNodeIds(
  data: GraphData,
  activeCategories: Set<string>,
  searchTerm: string,
): Set<string> {
  const searchLower = searchTerm.toLowerCase()
  const ids = new Set<string>()
  for (const node of data.nodes) {
    if (!activeCategories.has(node.category)) continue
    if (searchLower) {
      const name = (node.name || node.id).toLowerCase()
      if (!name.includes(searchLower)) continue
    }
    ids.add(node.id)
  }
  return ids
}

/** Extract connected neighbors for a node from the edge list */
export function getNodeConnections(
  data: GraphData,
  nodeId: string,
): { id: string; label: string; type: string; edgeType: string }[] {
  const nodeMap = new Map(data.nodes.map((n) => [n.id, n]))
  const seen = new Map<string, { id: string; label: string; type: string; edgeType: string }>()
  for (const e of data.edges) {
    const srcId = e.source
    const tgtId = e.target
    if (srcId !== nodeId && tgtId !== nodeId) continue
    const neighborId = srcId === nodeId ? tgtId : srcId
    const neighbor = nodeMap.get(neighborId)
    if (!neighbor) continue
    if (!seen.has(neighborId)) {
      seen.set(neighborId, {
        id: neighbor.id,
        label: neighbor.name || neighbor.id,
        type: neighbor.category,
        edgeType: e.type || 'related',
      })
    }
  }
  return [...seen.values()].sort((a, b) => a.type.localeCompare(b.type))
}
