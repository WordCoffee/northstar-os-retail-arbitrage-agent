// Ty's eyes are on — a cobalt ring around the screen.
//
// Two rules shape this component:
//
// 1. **It only claims what the server says.** The ring appears when
//    `/api/admin/tys/switches` reports `vision: true`. It is never inferred from
//    a local toggle or a guess, so a ring on screen means the eyes are really armed.
// 2. **It is nearly free.** One fixed div, one CSS opacity animation on the
//    compositor, no canvas, no requestAnimationFrame, no timers per frame. Polling
//    is 15 s, pauses while the tab is hidden, and stops for good on 401/403/404
//    (a customer surface has no admin API and must not poll forever).
import { useEffect, useState } from 'react'
import { getDevSession } from '../foundation/api.js'

const POLL_MS = 15000

function devHeaders() {
  if (!import.meta.env.DEV) return {}
  try {
    const s = getDevSession()
    if (!s || !s.userId) return {}
    return { 'X-User-Id': s.userId, 'X-Org-Id': s.orgId || 'org-t2',
             'X-Role': s.role || 'operator' }
  } catch { return {} }
}

export default function VisionRing() {
  const [armed, setArmed] = useState(false)

  useEffect(() => {
    let alive = true
    let stopped = false
    let timer = null

    const tick = async () => {
      if (stopped || document.visibilityState === 'hidden') return
      try {
        const res = await fetch('/api/admin/tys/switches', {
          credentials: 'include',
          headers: { Accept: 'application/json', ...devHeaders() },
        })
        if (!res.ok) {
          if ([401, 403, 404].includes(res.status)) {
            stopped = true
            if (alive) setArmed(false)
            return
          }
          return
        }
        const data = await res.json()
        if (alive) setArmed(Boolean(data && data.switches && data.switches.vision))
      } catch {
        // A network blip keeps the last known state: the ring must not flap.
      }
    }

    tick()
    timer = setInterval(tick, POLL_MS)
    const onVisible = () => { if (document.visibilityState === 'visible') tick() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive = false
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  if (!armed) return null
  return (
    <div className="vision-ring" data-testid="vision-ring" aria-hidden="true">
      <span className="vision-ring-line" />
      <span className="vision-ring-glow" />
    </div>
  )
}
