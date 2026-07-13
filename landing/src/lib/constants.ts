export const HLS_VIDEO_URL =
  'https://stream.mux.com/Aa02T7oM1wH5Mk5EEVDYhbZ1ChcdhRsS2m1NYyx4Ua1g.m3u8'

export const GITHUB_URL = 'https://github.com/humzahassan1/VibeSafe'
export const DOCS_URL = `${GITHUB_URL}#readme`
export const PYPI_URL = 'https://pypi.org/project/vibesafe/'

/**
 * Fallback production API URL when VITE_API_URL is not set at build time.
 * Update after Railway deploy, or set VITE_API_URL in Vercel env (preferred).
 */
export const PRODUCTION_API_URL = 'https://vibesafe-production-1044.up.railway.app'

export const NAV_LINKS = [
  { label: 'Features', href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Pricing', href: '#pricing' },
] as const
