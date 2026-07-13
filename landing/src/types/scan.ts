export type Severity = 'critical' | 'warning' | 'info'

export interface ScanFix {
  description: string
  code: string
  file_path: string
  fix_type: string
}

export interface ScanFinding {
  rule_id: string
  severity: Severity
  category: string
  title: string
  description: string
  file_path: string
  tier: number
  line_start?: number | null
  line_end?: number | null
  code_snippet?: string | null
  confidence?: number
  fix?: ScanFix
}

export interface ScanSummary {
  total: number
  critical: number
  warning: number
  info: number
}

export interface ScanInfo {
  framework: string
  language: string
  files_scanned: number
  scan_time: string
  project_path: string
  tiers_run: string
}

export interface ScanReport {
  summary: ScanSummary
  scan_info: ScanInfo
  findings: ScanFinding[]
}

export type ScanMode = 'github' | 'zip'

export interface TerminalLine {
  id: string
  level: 'info' | 'success' | 'warn' | 'error' | 'finding'
  text: string
  timestamp: string
}
