import { motion } from 'framer-motion'
import { DOCS_URL } from '../lib/constants'

const FEATURES = [
  {
    title: '3-Tier Scanning Pipeline',
    description:
      'Regex → framework config parsing → Claude-powered deep analysis. Each tier escalates intelligently.',
    span: 'md:col-span-7',
    icon: 'terminal',
    aspect: 'aspect-[16/10]',
  },
  {
    title: '51 Rules, 10 Categories',
    description:
      'Injection, secrets exposure, auth flaws, prompt injection, XSS, SSRF, and more — out of the box.',
    span: 'md:col-span-5',
    icon: 'shield',
    aspect: 'aspect-[4/5]',
  },
  {
    title: 'GitHub Actions CI',
    description:
      'Auto-scan every PR. Findings posted as comments. CI fails on critical vulnerabilities. Zero config.',
    span: 'md:col-span-5',
    icon: 'github',
    aspect: 'aspect-[4/5]',
  },
  {
    title: 'Agentic Investigation',
    description:
      'Claude reads files, follows data flows, and generates context-aware fix suggestions beyond static pattern matching.',
    span: 'md:col-span-7',
    icon: 'brain',
    aspect: 'aspect-[16/10]',
  },
] as const

export function Features() {
  return (
    <section id="features" className="bg-bg py-12 md:py-16">
      <div className="mx-auto max-w-[1200px] px-6 md:px-10 lg:px-16">
        <motion.div
          className="mb-12 flex flex-col gap-6 md:mb-16 md:flex-row md:items-end md:justify-between"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <div>
            <div className="mb-4 flex items-center gap-3">
              <div className="h-px w-8 bg-stroke" />
              <span className="text-xs uppercase tracking-[0.3em] text-muted">
                Core Features
              </span>
            </div>
            <h2 className="text-3xl text-text-primary md:text-4xl lg:text-5xl">
              Why teams trust{' '}
              <span className="font-display italic">VibeSafe</span>
            </h2>
            <p className="mt-4 max-w-lg text-sm text-muted md:text-base">
              From regex matching to LLM-powered deep analysis — every layer of your code,
              covered.
            </p>
          </div>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group relative hidden rounded-full px-6 py-3 text-sm text-text-primary md:inline-flex"
          >
            <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
            <span className="relative flex items-center gap-2 rounded-full border border-stroke bg-surface px-4 py-2">
              Read the docs <span aria-hidden>→</span>
            </span>
          </a>
        </motion.div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-12 md:gap-6">
          {FEATURES.map((feature, i) => (
            <motion.article
              key={feature.title}
              className={`group relative overflow-hidden rounded-3xl border border-stroke bg-surface ${feature.span} ${feature.aspect}`}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.7, delay: i * 0.08, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <FeatureBackground type={feature.icon} />
              <div className="relative flex h-full flex-col justify-between p-6 md:p-8">
                <FeatureIcon type={feature.icon} />
                <div>
                  <h3 className="mb-2 text-lg font-medium text-text-primary md:text-xl">
                    {feature.title}
                  </h3>
                  <p className="text-sm leading-relaxed text-muted">{feature.description}</p>
                </div>
              </div>
              <div className="absolute inset-0 flex items-end justify-start p-6 opacity-0 backdrop-blur-lg transition-opacity group-hover:bg-bg/70 group-hover:opacity-100">
                <span className="relative rounded-full bg-white px-4 py-2 text-xs text-bg">
                  <span className="absolute inset-[-2px] rounded-full accent-gradient" />
                  <span className="relative">
                    Learn more →{' '}
                    <span className="font-display italic">{feature.title}</span>
                  </span>
                </span>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}

function FeatureBackground({ type }: { type: string }) {
  if (type === 'terminal') {
    return (
      <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-[0.05]">
        <pre className="animate-[scroll-down_20s_linear_infinite] p-4 font-mono text-[10px] leading-relaxed text-text-primary">
          {Array.from({ length: 20 }, (_, i) => (
            <div key={i}>
              $ vibesafe scan ./app --skip-tier3
              <br />
              [INFO] Tier 1 found 13 issues
              <br />
              [CRITICAL] SEC-001 hardcoded API key
            </div>
          ))}
        </pre>
      </div>
    )
  }
  if (type === 'brain') {
    return (
      <div className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              'radial-gradient(circle at 1px 1px, hsl(var(--stroke)) 1px, transparent 0)',
            backgroundSize: '24px 24px',
          }}
        />
      </div>
    )
  }
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-[0.04]">
      <div className="h-48 w-48 rounded-full border border-stroke" />
    </div>
  )
}

function FeatureIcon({ type }: { type: string }) {
  const base = 'mb-6 flex h-12 w-12 items-center justify-center rounded-2xl border border-stroke bg-bg/50 text-accent'
  if (type === 'terminal') {
    return (
      <div className={base}>
        <span className="font-mono text-lg">&gt;_</span>
      </div>
    )
  }
  if (type === 'shield') {
    return (
      <div className={base}>
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
          />
        </svg>
      </div>
    )
  }
  if (type === 'github') {
    return (
      <div className={base}>
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
        </svg>
      </div>
    )
  }
  return (
    <div className={base}>
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
        />
      </svg>
    </div>
  )
}
