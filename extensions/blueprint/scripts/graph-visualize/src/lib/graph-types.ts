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
  originSpec?: string
  metrics: NodeMetrics

  // Runtime state (mutated by graph component)
  visible: boolean
  _animRadius?: number

  // D3 simulation properties
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

/** An edge in the graph — source/target are strings before resolution, GraphNode after. */
export interface GraphEdge {
  source: string | GraphNode
  target: string | GraphNode
  type?: string

  // Runtime state
  visible: boolean
}

/** Full graph data payload. */
export interface GraphData {
  summary: Record<string, unknown>
  nodes: GraphNode[]
  edges: GraphEdge[]
}

/** Size range for a metric. */
export interface SizeRange {
  min: number
  max: number
  full?: SizeRange
  connected?: SizeRange
}

/** Map of metric key → size range. */
export type SizeRangeMap = Record<string, SizeRange>
