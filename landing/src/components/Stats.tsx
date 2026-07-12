import { motion, useInView } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

const STATS = [
  { value: 51, suffix: '', label: 'Rules Checked' },
  { value: 10, suffix: '', label: 'Vulnerability Categories' },
  { value: 3, suffix: '', label: 'Scanning Tiers' },
  { value: 2, suffix: 'min', label: 'Average Scan Time', prefix: '<' },
] as const

export function Stats() {
  return (
    <section className="bg-bg py-16 md:py-24">
      <div className="mx-auto max-w-[1200px] px-6 md:px-10 lg:px-16">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4 md:gap-12">
          {STATS.map((stat, i) => (
            <StatItem key={stat.label} stat={stat} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}

function StatItem({
  stat,
  index,
}: {
  stat: (typeof STATS)[number]
  index: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!inView) return
    const duration = 1200
    const start = performance.now()

    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(stat.value * eased))
      if (progress < 1) requestAnimationFrame(tick)
    }

    const frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [inView, stat.value])

  return (
    <motion.div
      ref={ref}
      className="text-center"
      initial={{ opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.8, delay: index * 0.1, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <p className="animate-stat-count-up font-display text-5xl text-text-primary md:text-6xl lg:text-7xl">
        {'prefix' in stat ? stat.prefix : ''}
        {display}
        {stat.suffix}
      </p>
      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-muted md:text-sm">
        {stat.label}
      </p>
    </motion.div>
  )
}
