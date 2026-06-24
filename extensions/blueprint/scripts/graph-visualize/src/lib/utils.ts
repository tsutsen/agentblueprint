import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

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
