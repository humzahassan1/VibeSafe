import { useEffect, useRef } from 'react'
import type { TerminalLine } from '../../types/scan'

const LEVEL_STYLES: Record<TerminalLine['level'], string> = {
  info: 'text-muted',
  success: 'text-emerald-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
  finding: 'text-text-primary',
}

interface ScanTerminalProps {
  lines: TerminalLine[]
  isRunning: boolean
}

export function ScanTerminal({ lines, isRunning }: ScanTerminalProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div className="flex h-full min-h-[320px] flex-col overflow-hidden rounded-2xl border border-stroke bg-[#0c0c0c] font-mono text-xs shadow-2xl md:min-h-[420px] md:text-sm">
      <div className="flex items-center gap-2 border-b border-stroke/80 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-500/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <span className="ml-2 text-muted">vibesafe — tier 1 + 2</span>
        {isRunning && (
          <span className="ml-auto animate-scan-pulse text-emerald-400">● scanning</span>
        )}
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto p-4">
        {lines.length === 0 && (
          <p className="text-muted">
            Paste a GitHub URL or drop a zip to start a live security scan.
          </p>
        )}
        {lines.map((line) => (
          <div key={line.id} className="flex gap-3 leading-relaxed">
            <span className="shrink-0 text-muted/60">{line.timestamp}</span>
            <span className={LEVEL_STYLES[line.level]}>{line.text}</span>
          </div>
        ))}
        {isRunning && (
          <div className="flex gap-3">
            <span className="text-muted/60">{/* live */}</span>
            <span className="animate-pulse text-emerald-400">▌</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
