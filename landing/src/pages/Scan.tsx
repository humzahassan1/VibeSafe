import { useCallback, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { FindingsPanel } from '../components/scan/FindingsPanel'
import { ScanInput } from '../components/scan/ScanInput'
import { ScanTerminal } from '../components/scan/ScanTerminal'
import { Navbar } from '../components/Navbar'
import { isApiConfigured, scanGithub, scanZip } from '../lib/api'
import { formatTime, SCAN_PHASES } from '../lib/scanLogs'
import type { ScanReport, TerminalLine } from '../types/scan'

let lineCounter = 0
function nextLineId() {
  lineCounter += 1
  return `line-${lineCounter}`
}

function pushLine(
  setLines: React.Dispatch<React.SetStateAction<TerminalLine[]>>,
  level: TerminalLine['level'],
  text: string,
) {
  setLines((prev) => [
    ...prev,
    { id: nextLineId(), level, text, timestamp: formatTime() },
  ])
}

export function Scan() {
  const [lines, setLines] = useState<TerminalLine[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [report, setReport] = useState<ScanReport | null>(null)
  const phaseTimerRef = useRef<number[]>([])

  const clearTimers = () => {
    phaseTimerRef.current.forEach((id) => window.clearTimeout(id))
    phaseTimerRef.current = []
  }

  const runPhasedLogs = useCallback((targetName: string) => {
    clearTimers()
    setLines([])
    setReport(null)
    pushLine(setLines, 'info', `vibesafe scan ${targetName} --skip-tier3`)

    let elapsed = 0
    SCAN_PHASES.forEach((phase) => {
      elapsed += phase.delay
      const id = window.setTimeout(() => {
        pushLine(setLines, 'info', phase.text)
      }, elapsed)
      phaseTimerRef.current.push(id)
    })
  }, [])

  const finishScan = useCallback((result: ScanReport) => {
    clearTimers()
    const info = result.scan_info
    pushLine(
      setLines,
      'success',
      `Detected ${info.framework} (${info.language}) — ${info.files_scanned} files`,
    )
    pushLine(
      setLines,
      'success',
      `Scan complete in ${info.scan_time} — ${result.summary.total} findings (${result.summary.critical} critical)`,
    )

    const critical = result.findings.filter((f) => f.severity === 'critical')
    const warnings = result.findings.filter((f) => f.severity === 'warning')

    critical.slice(0, 5).forEach((f) => {
      pushLine(setLines, 'error', `[CRITICAL] ${f.rule_id} ${f.title} — ${f.file_path}`)
    })
    warnings.slice(0, 3).forEach((f) => {
      pushLine(setLines, 'warn', `[WARNING] ${f.rule_id} ${f.title}`)
    })

    if (result.findings.length > 8) {
      pushLine(setLines, 'info', `… and ${result.findings.length - 8} more (see findings below)`)
    } else if (result.findings.length === 0) {
      pushLine(setLines, 'success', 'No security issues found. Clean scan.')
    }

    setReport(result)
    setIsRunning(false)
  }, [])

  const handleError = useCallback((err: unknown) => {
    clearTimers()
    const message = err instanceof Error ? err.message : 'Scan failed'
    pushLine(setLines, 'error', message)
    if (!isApiConfigured()) {
      pushLine(
        setLines,
        'info',
        'Tip: run the API locally with uvicorn saas.app:app --reload and npm run dev',
      )
    }
    setIsRunning(false)
  }, [])

  const runGithub = async (repo: string, token?: string) => {
    setIsRunning(true)
    runPhasedLogs(repo)
    try {
      const result = await scanGithub(repo, token)
      finishScan(result)
    } catch (err) {
      handleError(err)
    }
  }

  const runZip = async (file: File, name: string) => {
    setIsRunning(true)
    runPhasedLogs(name)
    try {
      const result = await scanZip(file, name)
      finishScan(result)
    } catch (err) {
      handleError(err)
    }
  }

  return (
    <div className="min-h-screen bg-bg">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(52,211,153,0.08)_0%,_transparent_50%)]" />

      <Navbar />

      <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-28 md:px-10">
        <div className="mb-10">
          <Link to="/" className="text-xs uppercase tracking-[0.3em] text-muted hover:text-text-primary">
            ← Back
          </Link>
          <h1 className="mt-4 font-display text-4xl italic text-text-primary md:text-5xl">
            Live security scan
          </h1>
          <p className="mt-3 max-w-xl text-sm text-muted md:text-base">
            Paste a public GitHub repo or upload a zip. Tier 1 pattern matching + Tier 2
            framework analysis — no API key required.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-[minmax(0,340px)_1fr]">
          <div className="rounded-3xl border border-stroke bg-surface/40 p-6 backdrop-blur-sm">
            <ScanInput
              disabled={isRunning}
              onSubmitGithub={runGithub}
              onSubmitZip={runZip}
            />
            <p className="mt-4 text-xs text-muted">
              Scans run on the VibeSafe API. Locally:{' '}
              <code className="rounded bg-bg px-1 py-0.5">uvicorn saas.app:app --reload</code>
            </p>
          </div>

          <ScanTerminal lines={lines} isRunning={isRunning} />
        </div>

        {report && (
          <div className="mt-10">
            <h2 className="mb-4 font-display text-2xl italic text-text-primary">
              Findings
            </h2>
            <FindingsPanel findings={report.findings} summary={report.summary} />
          </div>
        )}
      </div>
    </div>
  )
}
