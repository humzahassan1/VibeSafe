import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

const WORDS = ['Scan', 'Detect', 'Secure'] as const
const DURATION_MS = 2700

interface LoadingScreenProps {
  onComplete: () => void
}

export function LoadingScreen({ onComplete }: LoadingScreenProps) {
  const [count, setCount] = useState(0)
  const [wordIndex, setWordIndex] = useState(0)
  const startRef = useRef<number | null>(null)
  const completedRef = useRef(false)

  useEffect(() => {
    let frame: number

    const tick = (now: number) => {
      if (startRef.current === null) startRef.current = now
      const elapsed = now - startRef.current
      const next = Math.min(100, Math.round((elapsed / DURATION_MS) * 100))
      setCount(next)

      if (next >= 100 && !completedRef.current) {
        completedRef.current = true
        window.setTimeout(onComplete, 400)
        return
      }

      frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [onComplete])

  useEffect(() => {
    const interval = window.setInterval(() => {
      setWordIndex((i) => (i + 1) % WORDS.length)
    }, 900)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="fixed inset-0 z-[9999] flex flex-col bg-bg">
      <motion.div
        className="absolute left-6 top-6 text-xs uppercase tracking-[0.3em] text-muted md:left-10 md:top-10"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
      >
        VibeSafe
      </motion.div>

      <div className="flex flex-1 items-center justify-center px-6">
        <AnimatePresence mode="wait">
          <motion.span
            key={WORDS[wordIndex]}
            className="font-display text-4xl italic text-text-primary/80 md:text-6xl lg:text-7xl"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -20, opacity: 0 }}
            transition={{ duration: 0.35, ease: 'easeInOut' }}
          >
            {WORDS[wordIndex]}
          </motion.span>
        </AnimatePresence>
      </div>

      <div className="absolute bottom-24 right-6 md:bottom-32 md:right-10">
        <span className="font-display text-6xl tabular-nums text-text-primary md:text-8xl lg:text-9xl">
          {String(count).padStart(3, '0')}
        </span>
      </div>

      <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-stroke/50">
        <div
          className="h-full origin-left accent-gradient transition-transform duration-75"
          style={{
            transform: `scaleX(${count / 100})`,
            boxShadow: '0 0 8px rgba(52, 211, 153, 0.35)',
          }}
        />
      </div>
    </div>
  )
}
