import { useState } from 'react'
import { useScrollSpy } from '../hooks/useScrollSpy'
import { Features } from '../components/Features'
import { Footer } from '../components/Footer'
import { Hero } from '../components/Hero'
import { HowItWorks } from '../components/HowItWorks'
import { LoadingScreen } from '../components/LoadingScreen'
import { Pricing } from '../components/Pricing'
import { Stats } from '../components/Stats'
import { TerminalPreview } from '../components/TerminalPreview'

const SECTION_IDS = ['features', 'how-it-works', 'pricing']

export function Index() {
  const [isLoading, setIsLoading] = useState(true)
  const activeSection = useScrollSpy(SECTION_IDS)

  return (
    <>
      {isLoading && <LoadingScreen onComplete={() => setIsLoading(false)} />}
      <main className={isLoading ? 'invisible h-0 overflow-hidden' : ''}>
        <Hero activeSection={activeSection} />
        <Features />
        <HowItWorks />
        <TerminalPreview />
        <Stats />
        <Pricing />
        <Footer />
      </main>
    </>
  )
}
