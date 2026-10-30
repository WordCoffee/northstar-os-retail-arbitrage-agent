import { useCallback, useRef } from 'react'

/**
 * Hover-intent prefetch (item 8).
 *
 * A pointer crossing a menu should not download four route chunks, and a
 * deliberate 90 ms pause should. That delay is the whole feature: it is long
 * enough to exclude a sweep and short enough to feel instant.
 *
 * `preload` must be idempotent (a dynamic import call is); this hook does not
 * cache results, it just decides WHEN to call.
 */
export function useHoverIntent(preload, { delayMs = 90, once = true } = {}) {
  const timer = useRef(null)
  const fired = useRef(false)

  const start = useCallback(() => {
    if (once && fired.current) return
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      fired.current = true
      try {
        const result = preload()
        if (result && typeof result.catch === 'function') result.catch(() => {})
      } catch { /* a failed prefetch is never user-visible */ }
    }, delayMs)
  }, [preload, delayMs, once])

  const cancel = useCallback(() => clearTimeout(timer.current), [])

  return {
    onPointerEnter: start,
    onPointerLeave: cancel,
    onFocus: start,          // keyboard users get the same head start
    onBlur: cancel,
  }
}

export default useHoverIntent
