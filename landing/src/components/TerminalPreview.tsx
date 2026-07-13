import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'

gsap.registerPlugin(ScrollTrigger)

const LEFT_CARDS = [
  {
    severity: 'CRITICAL',
    color: 'text-red-400 border-red-400/30 bg-red-400/10',
    title: 'Hardcoded API Key',
    rule: 'SEC-001',
    snippet: 'const KEY = "sk_live_abc123..."',
    category: 'secrets',
  },
  {
    severity: 'CRITICAL',
    color: 'text-red-400 border-red-400/30 bg-red-400/10',
    title: 'SQL Injection',
    rule: 'SEC-020',
    snippet: 'db.query("SELECT * FROM u WHERE id = " + id)',
    category: 'injection',
  },
  {
    severity: 'HIGH',
    color: 'text-orange-400 border-orange-400/30 bg-orange-400/10',
    title: 'Missing Helmet',
    rule: 'SEC-038',
    snippet: 'Express app without security headers',
    category: 'infrastructure',
  },
] as const

const RIGHT_CARDS = [
  {
    severity: 'HIGH',
    color: 'text-orange-400 border-orange-400/30 bg-orange-400/10',
    title: 'Permissive CORS',
    rule: 'SEC-039',
    snippet: "cors({ origin: '*' })",
    category: 'infrastructure',
  },
  {
    severity: 'MEDIUM',
    color: 'text-yellow-400 border-yellow-400/30 bg-yellow-400/10',
    title: 'Unpinned Dependency',
    rule: 'SEC-049',
    snippet: '"express": "*"',
    category: 'dependencies',
  },
  {
    severity: 'LOW',
    color: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
    title: 'Fix Suggestion',
    rule: 'SEC-020',
    snippet: "cursor.execute('SELECT * FROM u WHERE id = ?', (id,))",
    category: 'fix',
  },
] as const

export function TerminalPreview() {
  const sectionRef = useRef<HTMLElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const leftColRef = useRef<HTMLDivElement>(null)
  const rightColRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const section = sectionRef.current
    const content = contentRef.current
    const leftCol = leftColRef.current
    const rightCol = rightColRef.current
    if (!section || !content || !leftCol || !rightCol) return

    const pin = ScrollTrigger.create({
      trigger: content,
      start: 'top top',
      end: () => `+=${section.offsetHeight - window.innerHeight}`,
      pin: content,
      pinSpacing: false,
    })

    const leftCards = leftCol.querySelectorAll('[data-parallax]')
    const rightCards = rightCol.querySelectorAll('[data-parallax]')

    leftCards.forEach((card, i) => {
      gsap.to(card, {
        y: -120 - i * 40,
        ease: 'none',
        scrollTrigger: {
          trigger: section,
          start: 'top bottom',
          end: 'bottom top',
          scrub: true,
        },
      })
    })

    rightCards.forEach((card, i) => {
      gsap.to(card, {
        y: 80 + i * 50,
        ease: 'none',
        scrollTrigger: {
          trigger: section,
          start: 'top bottom',
          end: 'bottom top',
          scrub: true,
        },
      })
    })

    return () => {
      pin.kill()
      ScrollTrigger.getAll().forEach((t) => {
        if (t.trigger === section) t.kill()
      })
    }
  }, [])

  return (
    <section ref={sectionRef} className="relative min-h-[300vh] bg-bg">
      <div
        ref={contentRef}
        className="relative z-10 flex h-screen flex-col items-center justify-center px-6 text-center"
      >
        <div className="mb-4 flex items-center justify-center gap-3">
          <div className="h-px w-8 bg-stroke" />
          <span className="text-xs uppercase tracking-[0.3em] text-muted">
            See It In Action
          </span>
          <div className="h-px w-8 bg-stroke" />
        </div>
        <h2 className="mb-4 font-display text-4xl italic text-text-primary md:text-5xl lg:text-6xl">
          Real scan, real results
        </h2>
        <p className="mb-8 max-w-md text-sm text-muted md:text-base">
          Watch VibeSafe audit a vulnerable Express app in seconds.
        </p>
        <Link
          to="/scan"
          className="group relative rounded-full px-7 py-3.5 text-sm text-text-primary transition-transform hover:scale-105"
        >
          <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
          <span className="relative rounded-full border border-stroke bg-surface px-4 py-2">
            Try it yourself →
          </span>
        </Link>
      </div>

      <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-6">
        <div className="grid w-full max-w-[1400px] grid-cols-2 gap-12 md:gap-40">
          <div ref={leftColRef} className="flex flex-col items-end gap-16 pt-[20vh]">
            {LEFT_CARDS.map((card) => (
              <FindingCard key={card.rule + card.title} card={card} />
            ))}
          </div>
          <div ref={rightColRef} className="flex flex-col items-start gap-16 pt-[40vh]">
            {RIGHT_CARDS.map((card) => (
              <FindingCard key={card.rule + card.title} card={card} />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function FindingCard({
  card,
}: {
  card: {
    severity: string
    color: string
    title: string
    rule: string
    snippet: string
    category: string
  }
}) {
  return (
    <div
      data-parallax
      className="aspect-square w-full max-w-[280px] rounded-2xl border border-stroke bg-surface/90 p-4 backdrop-blur-sm animate-scan-pulse md:max-w-[320px]"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${card.color}`}>
          {card.severity}
        </span>
        <span className="font-mono text-[10px] text-muted">{card.rule}</span>
      </div>
      <p className="mb-2 text-sm font-medium text-text-primary">{card.title}</p>
      <pre className="overflow-hidden rounded-lg bg-bg/80 p-2 font-mono text-[10px] leading-relaxed text-muted">
        {card.snippet}
      </pre>
      <p className="mt-2 text-[10px] uppercase tracking-wider text-muted">{card.category}</p>
    </div>
  )
}
