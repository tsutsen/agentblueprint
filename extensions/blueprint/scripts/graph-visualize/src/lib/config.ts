/**
 * Global configuration — single source of truth for graph defaults.
 * Can be overridden at runtime via URL params or init function.
 */

import { themes } from './themes'
import { DEFAULT_SIZE_METRIC } from './metrics'

export interface GraphConfig {
  // Theme
  defaultTheme: string
  
  // Size metrics
  defaultSizeMetric: string
  
  // Labels
  defaultShowLabels: boolean
  
  // Simulation
  defaultSimulating: boolean
  
  // Zoom
  defaultZoom: { x: number; y: number; k: number }
  
  // Sidebar
  defaultSidebarWidth: number
  
  // Available themes (subset of all themes)
  availableThemes: string[]
}

/** Default configuration */
export const DEFAULT_CONFIG: GraphConfig = {
  defaultTheme: 'default',
  defaultSizeMetric: DEFAULT_SIZE_METRIC,
  defaultShowLabels: false,
  defaultSimulating: false,
  defaultZoom: { x: 0, y: 0, k: 0.3 },
  defaultSidebarWidth: 300,
  availableThemes: themes.map((t) => t.key),
}

/** Runtime configuration — can be overridden */
let runtimeConfig: Partial<GraphConfig> = {}

/** Merge runtime overrides into defaults */
export function mergeConfig(overrides: Partial<GraphConfig>): void {
  runtimeConfig = { ...runtimeConfig, ...overrides }
}

/** Get the current config (defaults + runtime overrides) */
export function getConfig(): GraphConfig {
  return { ...DEFAULT_CONFIG, ...runtimeConfig }
}

/** Get config value with a default */
export function getConfigValue<T extends keyof GraphConfig>(key: T): GraphConfig[T] {
  const config = getConfig()
  return config[key]
}
