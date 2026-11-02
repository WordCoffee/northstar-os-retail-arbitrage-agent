// When does a service switch earn the warp animation? Pure so it can be tested
// without a DOM, and reduced-motion always wins.

export const SHIFT_MS = 600

export function shouldAnimateShift(prevThemeId, nextThemeId, reducedMotion = false) {
  if (!prevThemeId || !nextThemeId) return false
  if (prevThemeId === nextThemeId) return false
  return !reducedMotion
}

export function prefersReducedMotion(win = typeof window !== 'undefined' ? window : null) {
  try {
    return !!(win && win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches)
  } catch {
    return false
  }
}
