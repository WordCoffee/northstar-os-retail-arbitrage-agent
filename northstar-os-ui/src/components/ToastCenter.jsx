import { useEffect, useState } from 'react'
import { subscribe, dismiss, undo, ordered } from '../lib/toastBus.js'
import './toast.css'

/**
 * Notification centre viewport (item 19). Mount ONCE, at the shell root.
 *
 * Behaviour that the old provider did not have:
 *   - ordered by priority, so an error is never buried under a success;
 *   - identical messages group into one row with a count;
 *   - hover/focus PAUSES auto-dismiss, because a toast that disappears while
 *     the pointer is on it is worse than no toast;
 *   - manual dismiss on every row, and an undo affordance when the emitter
 *     supplied one;
 *   - assertive announcements for errors, polite for everything else.
 */
const TTL = 5000

export default function ToastCenter() {
  const [items, setItems] = useState(() => ordered())
  const [paused, setPaused] = useState(false)

  useEffect(() => subscribe(() => setItems(ordered())), [])

  useEffect(() => {
    if (paused || items.length === 0) return undefined
    const timer = setInterval(() => {
      const now = Date.now()
      for (const item of items) {
        if (!item.sticky && now - item.createdAt >= TTL) dismiss(item.id)
      }
    }, 600)
    return () => clearInterval(timer)
  }, [paused, items])

  if (items.length === 0) return null

  return (
    <div
      className="toast-viewport"
      role="region"
      aria-label="Notifications"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      {items.map((item) => (
        <div key={item.id} className={`toast toast--${item.tone}`} role="status">
          <span className="toast__dot" aria-hidden="true" />
          <div className="toast__body">
            <p className="toast__msg">{item.msg}</p>
            {item.count > 1 && <span className="toast__count">×{item.count}</span>}
          </div>
          {item.undo && (
            <button type="button" className="toast__action" onClick={() => undo(item.id)}>
              Undo
            </button>
          )}
          <button
            type="button"
            className="toast__close"
            aria-label={`Dismiss notification: ${item.msg}`}
            onClick={() => dismiss(item.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
