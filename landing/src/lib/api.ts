import type { ScanReport } from '../types/scan'
import { PRODUCTION_API_URL } from './constants'

function resolveApiBase(): string {
  const fromEnv = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
  if (fromEnv) return fromEnv
  if (import.meta.env.PROD && PRODUCTION_API_URL) return PRODUCTION_API_URL
  return ''
}

const API_BASE = resolveApiBase()

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

export function getApiBase(): string {
  return API_BASE
}

export async function scanZip(file: File, name: string): Promise<ScanReport> {
  const form = new FormData()
  form.append('project', file)
  form.append('name', name)

  const res = await fetch(apiUrl('/api/demo/scan'), {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Scan failed (${res.status})`)
  }

  return res.json()
}

export async function scanGithub(repo: string, token?: string): Promise<ScanReport> {
  const form = new FormData()
  form.append('repo', repo)
  if (token) form.append('github_token', token)

  const res = await fetch(apiUrl('/api/demo/scan/github'), {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Scan failed (${res.status})`)
  }

  return res.json()
}

export function isApiConfigured(): boolean {
  return API_BASE !== '' || import.meta.env.DEV
}
