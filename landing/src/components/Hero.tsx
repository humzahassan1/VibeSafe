import gsap from 'gsap'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { GITHUB_URL, HLS_VIDEO_URL } from '../lib/constants'
import { useHlsVideo } from '../hooks/useHlsVideo'
import { Navbar } from './Navbar'

const DESCRIPTORS = ['audited', 'hardened', 'protected', 'secured'] as const

interface HeroProps {
  activeSection?: string
}

export function Hero({ activeSection }: HeroProps) {
  const videoRef = useHlsVideo(HLS_VIDEO_URL)
  const [descriptorIndex, setDescriptorIndex] = useState(0)

  useEffect(() => {
    const interval = window.setInterval(() => {
      setDescriptorIndex((i) => (i + 1) % DESCRIPTORS.length)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } })
    tl.fromTo(
      '.name-reveal',
      { opacity: 0, y: 50 },
      { opacity: 1, y: 0, duration: 1.2, delay: 0.1 },
    )
    tl.fromTo(
      '.blur-in',
      { opacity: 0, filter: 'blur(10px)', y: 20 },
      { opacity: 1, filter: 'blur(0px)', y: 0, duration: 1, stagger: 0.1 },
      0.3,
    )
    return () => {
      tl.kill()
    }
  }, [])

  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden">
      <div className="absolute inset-0 overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          muted
          loop
          playsInline
          className="absolute left-1/2 top-1/2 min-h-full min-w-full -translate-x-1/2 -translate-y-1/2 object-cover"
        />
        <div className="absolute inset-0 bg-black/40" />
        <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-bg to-transparent" />
      </div>

      <Navbar activeSection={activeSection} />

      <div className="relative z-10 flex flex-col items-center px-6 pt-32 text-center">
        <p className="blur-in mb-8 text-xs uppercase tracking-[0.3em] text-muted">
          AI-POWERED SECURITY SCANNING
        </p>

        <h1 className="name-reveal mb-6 font-display text-6xl italic leading-[0.9] tracking-tight text-text-primary md:text-8xl lg:text-9xl">
          Ship code
          <br />
          <span className="italic">fearlessly.</span>
        </h1>

        <p className="blur-in mb-4 text-lg text-muted md:text-xl">
          Your codebase{' '}
          <span
            key={DESCRIPTORS[descriptorIndex]}
            className="animate-role-fade-in inline-block font-display italic text-text-primary"
          >
            {DESCRIPTORS[descriptorIndex]}
          </span>
          .
        </p>

        <p className="blur-in mb-12 max-w-md text-sm text-muted md:text-base">
          51 security rules. 10 vulnerability categories. 3-tier AI scanning pipeline. One
          command to audit your entire codebase.
        </p>

        <div className="blur-in inline-flex flex-wrap justify-center gap-4">
          <Link
            to="/scan"
            className="group relative rounded-full bg-text-primary px-7 py-3.5 text-sm text-bg transition-transform hover:scale-105"
          >
            <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
            <span className="relative rounded-full px-1 group-hover:bg-bg group-hover:text-text-primary">
              Start Scanning
            </span>
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group relative rounded-full border-2 border-stroke bg-bg px-7 py-3.5 text-sm text-text-primary transition-transform hover:scale-105 hover:border-transparent"
          >
            <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
            <span className="relative flex items-center gap-2 rounded-full px-1">
              <GitHubIcon />
              View on GitHub
            </span>
          </a>
        </div>
      </div>
    </section>
  )
}

function GitHubIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}
