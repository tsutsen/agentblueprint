/**
 * Size metric definitions — single source of truth for graph node sizing.
 * Each metric has a key (used internally) and a label (shown in UI).
 */

export interface SizeMetric {
  key: string
  label: string
  // The property name on graph nodes that holds the metric value
  nodeProperty: string
}

export const SIZE_METRICS: SizeMetric[] = [
  { key: 'degree', label: 'Degree', nodeProperty: 'degree' },
  { key: 'blast', label: 'Blast Radius', nodeProperty: 'blastRadius' },
  { key: 'risk', label: 'Risk Score', nodeProperty: 'risk' },
]

/** Get a metric by key */
export function getSizeMetric(key: string): SizeMetric | undefined {
  return SIZE_METRICS.find((m) => m.key === key)
}

/** Default metric key */
export const DEFAULT_SIZE_METRIC = 'degree'
