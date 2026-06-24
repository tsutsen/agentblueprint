/**
 * Size metric definitions — single source of truth for graph node sizing.
 * Each metric key corresponds to a key in GraphNode.metrics.
 */

import type { NodeMetrics } from './graph-types'

export interface SizeMetric {
  key: keyof NodeMetrics
  label: string
}

export const SIZE_METRICS: SizeMetric[] = [
  { key: 'degree', label: 'Degree' },
  { key: 'blast', label: 'Blast Radius' },
  { key: 'risk', label: 'Risk Score' },
]

/** Get a metric by key */
export function getSizeMetric(key: string): SizeMetric | undefined {
  return SIZE_METRICS.find((m) => m.key === key)
}

/** Default metric key */
export const DEFAULT_SIZE_METRIC: keyof NodeMetrics = 'degree'
