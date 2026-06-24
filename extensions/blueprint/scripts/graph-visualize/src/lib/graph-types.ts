/**
 * Graph data types — single source of truth for graph node/edge shapes.
 */

/** Metric values for a node — extendable, keyed by metric identifier. */
export interface NodeMetrics {
  degree: number
  blast: number
  risk: number
}

/** A node in the graph, including D3 simulation properties and internal state. */
export interface GraphNode {
  id: string
  name: string
  description?: string
  category: string
  metrics: NodeMetrics

  // Runtime state (mutated by graph component)
  visible: boolean
  _animRadius?: number
  _colorIdx?: number
  _cachedColor?: string
  _cachedStroke?: string

  // D3 simulation properties
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
  index?: number
}

/** An edge in the graph — raw form from JSON (string references). */
export interface RawGraphEdge {
  source: string
  target: string
  type?: string
}

/** An edge in the graph — resolved form (object references). */
export interface GraphEdge {
  source: GraphNode
  target: GraphNode
  type?: string

  // Runtime state
  visible: boolean
}

/** Full graph data payload — raw form from JSON. */
export interface GraphData {
  project: string
  version: string
  summary: Record<string, unknown>
  nodes: GraphNode[]
  edges: RawGraphEdge[]
}

/** Size range for a metric — nested so full/connected share the same shape. */
export interface SizeRange {
  full?: { min: number; max: number }
  connected?: { min: number; max: number }
}

/** Map of metric key → size range. */
export type SizeRangeMap = Record<string, SizeRange>
