import gsap from 'gsap'
import { useEffect, useRef, useState } from 'react'
import { DOCS_URL, GITHUB_URL, HLS_VIDEO_URL, PYPI_URL } from '../lib/constants'
import { useHlsVideo } from '../hooks/useHlsVideo'

const FOOTER_LINKS = [
  { label: 'Documentation', href: DOCS_URL },
  { label: 'GitHub', href: GITHUB_URL },
  { label: 'PyPI', href: PYPI_URL },
  { label: 'Changelog', href: `${GITHUB_URL}/releases` },
] as const

const MARQUEE_TEXT = 'SECURE YOUR CODE • '

export function Footer() {
  const videoRef = useHlsVideo(HLS_VIDEO_URL)
  const marqueeRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const el = marqueeRef.current
    if (!el) return

    const tween = gsap.to(el, {
      xPercent: -50,
      duration: 40,
      ease: 'none',
      repeat: -1,
    })

    return () => {
      tween.kill()
    }
  }, [])

  const copyInstall = async () => {
    await navigator.clipboard.writeText('pip install vibesafe')
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <footer className="relative overflow-hidden bg-bg pt-16 md:pt-20">
      <div className="absolute inset-0 overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          muted
          loop
          playsInline
          className="absolute left-1/2 top-1/2 min-h-full min-w-full -translate-x-1/2 -translate-y-1/2 scale-y-[-1] object-cover"
        />
        <div className="absolute inset-0 bg-black/60" />
      </div>

      <div className="relative z-10 overflow-hidden border-y border-stroke/30 py-6">
        <div ref={marqueeRef} className="flex whitespace-nowrap">
          {Array.from({ length: 10 }, (_, i) => (
            <span
              key={i}
              className="px-4 font-display text-4xl italic text-text-primary/20 md:text-6xl"
            >
              {MARQUEE_TEXT}
            </span>
          ))}
        </div>
      </div>

      <div className="relative z-10 px-6 py-16 text-center md:py-24">
        <h2 className="mb-8 font-display text-4xl italic text-text-primary md:text-5xl lg:text-6xl">
          Get started in 30 seconds
        </h2>

        <button
          type="button"
          onClick={copyInstall}
          className="group relative mx-auto mb-8 flex max-w-md items-center justify-between rounded-2xl border border-accent/40 bg-bg/80 px-6 py-4 font-mono text-sm text-text-primary backdrop-blur-sm transition-colors hover:border-accent"
        >
          <span>pip install vibesafe</span>
          <span className="text-xs text-muted">{copied ? 'Copied!' : 'Copy'}</span>
        </button>

        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="group relative inline-flex rounded-full px-7 py-3.5 text-sm text-text-primary transition-transform hover:scale-105"
        >
          <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
          <span className="relative flex items-center gap-2 rounded-full border border-stroke bg-surface/80 px-4 py-2 backdrop-blur-sm">
            ★ Star on GitHub
          </span>
        </a>
      </div>

      <div className="relative z-10 flex flex-col items-center justify-between gap-4 border-t border-stroke/30 px-6 py-8 text-sm text-muted md:flex-row md:px-10">
        <div className="flex flex-wrap justify-center gap-6">
          {FOOTER_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="transition-colors hover:text-text-primary"
            >
              {link.label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          Open source &amp; actively maintained
        </div>
      </div>
    </footer>
  )
}
