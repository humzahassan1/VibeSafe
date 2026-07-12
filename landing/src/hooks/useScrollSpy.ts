import { useEffect, useState } from 'react'

export function useScrollSpy(sectionIds: string[], offset = 120) {
  const [active, setActive] = useState(sectionIds[0] ?? '')

  useEffect(() => {
    const handleScroll = () => {
      let current = sectionIds[0] ?? ''
      for (const id of sectionIds) {
        const el = document.getElementById(id)
        if (el && el.getBoundingClientRect().top <= offset) {
          current = id
        }
      }
      setActive(current)
    }

    handleScroll()
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [sectionIds, offset])

  return active
}
