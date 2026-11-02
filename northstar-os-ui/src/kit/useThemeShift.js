import { useEffect, useRef, useState } from 'react'
import { SHIFT_MS, shouldAnimateShift, prefersReducedMotion } from '../lib/themeShift.js'

/**
 * True for the length of one service-switch transition. The shell adds
 * `is-shifting` so the cockpit visibly reconfigures; reduced-motion users never
 * see it, and the first paint never animates (there is nothing to shift from).
 */
export function useThemeShift(themeId) {
  const [shifting, setShifting] = useState(false)
  const previous = useRef(themeId)

  useEffect(() => {
    const animate = shouldAnimateShift(previous.current, themeId, prefersReducedMotion())
    previous.current = themeId
    if (!animate) return undefined
    setShifting(true)
    const timer = setTimeout(() => setShifting(false), SHIFT_MS)
    return () => clearTimeout(timer)
  }, [themeId])

  return shifting
}
