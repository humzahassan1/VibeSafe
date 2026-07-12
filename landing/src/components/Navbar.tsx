import { useEffect, useState } from 'react'
import { GITHUB_URL, NAV_LINKS } from '../lib/constants'

interface NavbarProps {
  activeSection?: string
}

export function Navbar({ activeSection }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 100)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const sectionMap: Record<string, string> = {
    features: 'features',
    'how-it-works': 'how-it-works',
    pricing: 'pricing',
  }

  return (
    <nav className="fixed left-0 right-0 top-0 z-50 flex justify-center px-4 pt-4 md:pt-6">
      <div
        className={`inline-flex items-center rounded-full border border-white/10 bg-surface px-2 py-2 backdrop-blur-md transition-shadow ${
          scrolled ? 'shadow-md shadow-black/10' : ''
        }`}
      >
        <a href="#" className="group flex items-center" aria-label="VibeSafe home">
          <div className="accent-gradient flex h-9 w-9 items-center justify-center rounded-full p-[2px] transition-transform group-hover:scale-110 group-hover:[background:linear-gradient(270deg,#34D399_0%,#059669_100%)]">
            <div className="flex h-full w-full items-center justify-center rounded-full bg-bg">
              <span className="font-display text-[13px] italic">VS</span>
            </div>
          </div>
        </a>

        <div className="mx-1 hidden h-5 w-px bg-stroke sm:block" />

        <div className="hidden items-center sm:flex">
          {NAV_LINKS.map((link) => {
            const id = link.href.replace('#', '')
            const isActive = activeSection === sectionMap[id]
            return (
              <a
                key={link.href}
                href={link.href}
                className={`rounded-full px-3 py-1.5 text-xs transition-colors sm:px-4 sm:py-2 sm:text-sm ${
                  isActive
                    ? 'bg-stroke/50 text-text-primary'
                    : 'text-muted hover:bg-stroke/50 hover:text-text-primary'
                }`}
              >
                {link.label}
              </a>
            )
          })}
        </div>

        <div className="mx-1 hidden h-5 w-px bg-stroke sm:block" />

        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="group relative rounded-full px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm"
        >
          <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
          <span className="relative flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 backdrop-blur-md text-text-primary">
            Get Started <span aria-hidden>→</span>
          </span>
        </a>
      </div>
    </nav>
  )
}
