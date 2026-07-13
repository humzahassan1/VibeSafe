import { motion } from 'framer-motion'
import type { ScanFinding } from '../../types/scan'

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-red-500/40 bg-red-500/10 text-red-400',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-400',
  info: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
}

interface FindingsPanelProps {
  findings: ScanFinding[]
  summary?: { total: number; critical: number; warning: number }
}

export function FindingsPanel({ findings, summary }: FindingsPanelProps) {
  if (findings.length === 0) return null

  return (
    <div className="space-y-4">
      {summary && (
        <div className="flex flex-wrap gap-3 text-sm">
          <span className="rounded-full border border-stroke bg-surface px-3 py-1 text-muted">
            {summary.total} findings
          </span>
          {summary.critical > 0 && (
            <span className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-red-400">
              {summary.critical} critical
            </span>
          )}
          {summary.warning > 0 && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-amber-400">
              {summary.warning} warning
            </span>
          )}
        </div>
      )}

      <div className="grid gap-3">
        {findings.map((finding, i) => (
          <motion.article
            key={`${finding.rule_id}-${finding.file_path}-${finding.line_start}-${i}`}
            className="rounded-xl border border-stroke bg-surface/50 p-4"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.35 }}
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                  SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info
                }`}
              >
                {finding.severity}
              </span>
              <span className="font-mono text-[10px] text-muted">{finding.rule_id}</span>
              <span className="text-[10px] uppercase tracking-wider text-muted">
                {finding.category}
              </span>
            </div>
            <h3 className="mb-1 font-medium text-text-primary">{finding.title}</h3>
            <p className="mb-2 text-sm text-muted">{finding.description}</p>
            <p className="truncate font-mono text-xs text-muted/80">
              {finding.file_path}
              {finding.line_start ? `:${finding.line_start}` : ''}
            </p>
            {finding.code_snippet && (
              <pre className="mt-2 overflow-x-auto rounded-lg bg-bg p-3 font-mono text-xs text-muted">
                {finding.code_snippet}
              </pre>
            )}
            {finding.fix?.code && (
              <div className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
                <p className="mb-1 text-xs text-emerald-400">Suggested fix</p>
                <pre className="overflow-x-auto font-mono text-xs text-muted">
                  {finding.fix.code}
                </pre>
              </div>
            )}
          </motion.article>
        ))}
      </div>
    </div>
  )
}
