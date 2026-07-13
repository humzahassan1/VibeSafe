import { useCallback, useState } from 'react'
import type { ScanMode } from '../../types/scan'

interface ScanInputProps {
  disabled: boolean
  onSubmitGithub: (repo: string, token?: string) => void
  onSubmitZip: (file: File, name: string) => void
}

export function ScanInput({ disabled, onSubmitGithub, onSubmitZip }: ScanInputProps) {
  const [mode, setMode] = useState<ScanMode>('github')
  const [repo, setRepo] = useState('')
  const [token, setToken] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped?.name.endsWith('.zip')) setFile(dropped)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (mode === 'github' && repo.trim()) {
      onSubmitGithub(repo.trim(), token.trim() || undefined)
    } else if (mode === 'zip' && file) {
      onSubmitZip(file, file.name.replace(/\.zip$/i, ''))
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="inline-flex rounded-full border border-stroke bg-surface p-1">
        {(['github', 'zip'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            disabled={disabled}
            onClick={() => setMode(tab)}
            className={`rounded-full px-4 py-2 text-sm transition-colors ${
              mode === tab
                ? 'bg-stroke/60 text-text-primary'
                : 'text-muted hover:text-text-primary'
            }`}
          >
            {tab === 'github' ? 'GitHub repo' : 'Upload zip'}
          </button>
        ))}
      </div>

      {mode === 'github' ? (
        <div className="space-y-3">
          <input
            type="text"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            disabled={disabled}
            placeholder="owner/repo or https://github.com/owner/repo"
            className="w-full rounded-xl border border-stroke bg-bg px-4 py-3 text-sm text-text-primary placeholder:text-muted focus:border-emerald-500/50 focus:outline-none"
          />
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            disabled={disabled}
            placeholder="GitHub token (optional, for private repos)"
            className="w-full rounded-xl border border-stroke bg-bg px-4 py-3 text-sm text-text-primary placeholder:text-muted focus:border-emerald-500/50 focus:outline-none"
          />
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
            dragOver
              ? 'border-emerald-500/60 bg-emerald-500/5'
              : 'border-stroke bg-surface/30'
          }`}
        >
          <input
            type="file"
            accept=".zip"
            disabled={disabled}
            className="hidden"
            id="zip-upload"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <label htmlFor="zip-upload" className="cursor-pointer">
            <p className="mb-2 text-text-primary">
              {file ? file.name : 'Drop a .zip or click to browse'}
            </p>
            <p className="text-xs text-muted">Max 25 MB · Tier 1 + 2 only</p>
          </label>
        </div>
      )}

      <button
        type="submit"
        disabled={disabled || (mode === 'github' ? !repo.trim() : !file)}
        className="group relative w-full rounded-full bg-text-primary py-3.5 text-sm font-medium text-bg transition-transform hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-40"
      >
        <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100 group-disabled:opacity-0" />
        <span className="relative">
          {disabled ? 'Scanning…' : 'Run security scan'}
        </span>
      </button>
    </form>
  )
}
