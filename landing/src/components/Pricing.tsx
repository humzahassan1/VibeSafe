import { motion } from 'framer-motion'
import { GITHUB_URL } from '../lib/constants'

const PLANS = [
  {
    name: 'Open Source',
    price: 'Free',
    period: 'forever',
    features: [
      'CLI scanning',
      'All 51 security rules',
      'GitHub Actions integration',
      'Markdown & JSON output',
      '3-tier pipeline (Tier 3 needs API key)',
    ],
    cta: 'Get Started',
    href: GITHUB_URL,
    primary: false,
  },
  {
    name: 'SaaS Pro',
    price: '$29',
    period: '/mo',
    features: [
      'Everything in Open Source',
      'Scan history dashboard',
      'REST API access',
      'GitHub repo scanning',
      '500 scans/month + Tier 3 AI',
      'Stripe billing',
    ],
    cta: 'Start Free Trial',
    href: GITHUB_URL,
    primary: true,
  },
] as const

export function Pricing() {
  return (
    <section id="pricing" className="bg-bg py-16 md:py-24">
      <div className="mx-auto max-w-[1000px] px-6 md:px-10">
        <motion.div
          className="mb-12 text-center md:mb-16"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <div className="mb-4 flex items-center justify-center gap-3">
            <div className="h-px w-8 bg-stroke" />
            <span className="text-xs uppercase tracking-[0.3em] text-muted">
              Simple pricing
            </span>
            <div className="h-px w-8 bg-stroke" />
          </div>
          <h2 className="text-3xl text-text-primary md:text-4xl">
            Open-source core.{' '}
            <span className="font-display italic">Pay only if you want SaaS.</span>
          </h2>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2">
          {PLANS.map((plan, i) => (
            <motion.article
              key={plan.name}
              className={`relative rounded-3xl p-[1px] ${
                plan.primary ? 'accent-gradient' : 'bg-stroke'
              }`}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.7, delay: i * 0.1 }}
            >
              <div className="h-full rounded-3xl bg-surface p-8">
                <h3 className="mb-1 text-lg font-medium text-text-primary">{plan.name}</h3>
                <p className="mb-6 font-display text-4xl text-text-primary">
                  {plan.price}
                  <span className="text-base font-body text-muted">{plan.period}</span>
                </p>
                <ul className="mb-8 space-y-3">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-muted">
                      <span className="mt-1 text-accent">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href={plan.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`group relative inline-flex rounded-full px-7 py-3.5 text-sm transition-transform hover:scale-105 ${
                    plan.primary
                      ? 'bg-text-primary text-bg'
                      : 'border-2 border-stroke bg-bg text-text-primary'
                  }`}
                >
                  {!plan.primary && (
                    <span className="absolute inset-[-2px] rounded-full opacity-0 accent-gradient transition-opacity group-hover:opacity-100" />
                  )}
                  <span className="relative">{plan.cta}</span>
                </a>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}
