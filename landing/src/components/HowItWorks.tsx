import { motion } from 'framer-motion'
import { DOCS_URL } from '../lib/constants'

const STEPS = [
  {
    number: '01',
    title: 'Install',
    command: 'pip install vibesafe',
    icon: PackageIcon,
  },
  {
    number: '02',
    title: 'Scan',
    command: 'vibesafe scan ./your-project',
    icon: TerminalIcon,
  },
  {
    number: '03',
    title: 'Review',
    command: 'AI-prioritized findings with severity + code fixes',
    icon: ReportIcon,
  },
  {
    number: '04',
    title: 'Ship',
    command: 'Integrate into CI and ship with confidence',
    icon: RocketIcon,
  },
] as const

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-bg py-16 md:py-24">
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
                How it works
              </span>
            </div>
            <h2 className="text-3xl text-text-primary md:text-4xl lg:text-5xl">
              Four steps to{' '}
              <span className="font-display italic">secure code</span>
            </h2>
            <p className="mt-4 max-w-lg text-sm text-muted md:text-base">
              From install to CI integration — get production-ready security in minutes.
            </p>
          </div>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group relative hidden rounded-full px-6 py-3 text-sm md:inline-flex"
          >
            <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
            <span className="relative flex items-center gap-2 rounded-full border border-stroke bg-surface px-4 py-2 text-text-primary">
              View docs <span aria-hidden>→</span>
            </span>
          </a>
        </motion.div>

        <div className="flex flex-col gap-4">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.number}
              className="flex flex-col items-start gap-4 rounded-[40px] border border-stroke bg-surface/30 p-4 transition-colors hover:bg-surface sm:flex-row sm:items-center sm:gap-6 sm:rounded-full sm:p-4"
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
            >
              <div className="accent-gradient flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-bg">
                {step.number}
              </div>
              <step.icon />
              <div className="min-w-0 flex-1">
                <h3 className="mb-1 font-medium text-text-primary">{step.title}</h3>
                <p className="truncate font-mono text-sm text-muted">{step.command}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

function PackageIcon() {
  return (
    <svg className="h-6 w-6 shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  )
}

function TerminalIcon() {
  return (
    <svg className="h-6 w-6 shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" />
    </svg>
  )
}

function ReportIcon() {
  return (
    <svg className="h-6 w-6 shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  )
}

function RocketIcon() {
  return (
    <svg className="h-6 w-6 shrink-0 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
    </svg>
  )
}
