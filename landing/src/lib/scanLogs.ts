export const SCAN_PHASES = [
  { text: 'Loading configuration...', delay: 400 },
  { text: 'Phase 1: Discovery — detecting framework and file manifest', delay: 600 },
  { text: 'Phase 2: Tier 1 scan — pattern matching (51 rules)', delay: 800 },
  { text: 'Phase 3: Tier 2 scan — framework config analysis', delay: 700 },
  { text: 'Phase 4: Skipped (Tier 3 requires API key)', delay: 300 },
  { text: 'Phase 5: Generating report...', delay: 500 },
] as const

export function formatTime(date = new Date()): string {
  return date.toLocaleTimeString('en-US', { hour12: false })
}
