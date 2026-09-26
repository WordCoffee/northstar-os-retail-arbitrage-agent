// Help / tour registry foundation.
// Per-service tours with skip / next / back / "don't show again", replay from
// Help, per-user completion persisted via foundation UI-preferences.
import { useState } from 'react'
import foundationApi from './api.js'
import { useSession } from './session.jsx'

export const TOUR_REGISTRY = {
  hub: [
    { title: 'Command center', body: 'Portfolio health, pipeline, and alerts in one place.' },
    { title: 'Approval queue', body: 'Review pending approvals with cost and change preview.' },
    { title: 'Drill down', body: 'Open any service from the sidebar or command palette (Ctrl+K).' },
  ],
  prospector: [
    { title: 'Candidate universe', body: 'Build and normalize candidates before scoring.' },
    { title: 'Evidence', body: 'Every value shows provenance — unknown stays unknown.' },
  ],
  // Other services registered in Phase 1C when their pages are implemented.
}

const PREF_PREFIX = 'tour_done_'

export function useTour(serviceId) {
  const { userId } = useSession()
  const steps = TOUR_REGISTRY[serviceId] || []
  return {
    steps,
    available: steps.length > 0,
    async isDone() {
      if (!userId) return true
      try {
        const r = await foundationApi.getPref(`${PREF_PREFIX}${serviceId}`)
        return !!(r.value && r.value.done)
      } catch { return true }
    },
    async markDone() {
      if (!userId) return
      try { await foundationApi.setPref(`${PREF_PREFIX}${serviceId}`, { done: true }) } catch { /* ignore */ }
    },
  }
}

export function TourOverlay({ steps, onClose }) {
  const [i, setI] = useState(0)
  if (!steps || steps.length === 0) return null
  const step = steps[i]
  const last = i === steps.length - 1
  return (
    <div className="fs-tour-backdrop" role="dialog" aria-modal="true" aria-label="Tour">
      <div className="fs-tour">
        <div className="fs-tour-step">Step {i + 1} of {steps.length}</div>
        <h3>{step.title}</h3>
        <p className="text-mid">{step.body}</p>
        <div className="fs-tour-actions">
          <button className="btn btn-ghost" onClick={onClose}>Skip</button>
          <button className="btn btn-ghost" onClick={onClose}>Don’t show again</button>
          <span style={{ flex: 1 }} />
          {i > 0 && <button className="btn" onClick={() => setI(i - 1)}>Back</button>}
          {!last
            ? <button className="btn btn-primary" onClick={() => setI(i + 1)}>Next</button>
            : <button className="btn btn-primary" onClick={onClose}>Done</button>}
        </div>
      </div>
    </div>
  )
}