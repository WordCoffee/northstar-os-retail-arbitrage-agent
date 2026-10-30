/**
 * Screen-reader announcements (work order UI-20, item 12).
 *
 * A tiny event bus, not a context: any module can announce a background
 * completion without being inside a provider. <Announcer /> subscribes once and
 * owns the two live regions.
 *
 * Politeness matters:
 *   polite     queued behind whatever the user is reading (default)
 *   assertive  interrupts - reserve it for errors and destructive results
 */

const EVENT = 'northstar:announce'

export function announce(message, { assertive = false } = {}) {
  const text = String(message ?? '').trim()
  if (!text) return
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { text, assertive } }))
}

export function subscribe(handler) {
  if (typeof window === 'undefined') return () => {}
  const listener = (event) => handler(event.detail)
  window.addEventListener(EVENT, listener)
  return () => window.removeEventListener(EVENT, listener)
}

export const ANNOUNCE_EVENT = EVENT
export default { announce, subscribe, ANNOUNCE_EVENT }
