import { useCallback, useEffect, useState } from 'react'

// HITL queue: the local approval records created by agent_kernel.hitl. The
// Matrix/AgentTeams bridge is not installed, so this panel is the operator's
// current command surface. It never invents a request or an approval.
export default function HitlQueue({ bus }) {
  const [requests, setRequests] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/hitl/pending', {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const body = await response.json()
      const rows = body?.data?.requests || body?.requests || []
      setRequests(Array.isArray(rows) ? rows : [])
      setError('')
    } catch (failure) {
      setError(String(failure?.message || failure))
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [load])

  const decide = async (request, action) => {
    setBusy(request.id)
    try {
      const response = await fetch(`/api/v1/hitl/${encodeURIComponent(request.id)}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ operator: 'operator', note: '' }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      bus?.publish(`hitl.${action}`, { request: request.id, action: request.action }, {
        severity: action === 'approve' ? 'ok' : 'warn', source: 'ui',
      })
      await load()
    } catch (failure) {
      setError(String(failure?.message || failure))
      bus?.publish('hitl.decision_failed', { request: request.id, error: String(failure?.message || failure) }, {
        severity: 'error', source: 'ui',
      })
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="gx-hitl">
      <div className="gx-hitl-head">
        <span className="gx-eyebrow">Human in the loop</span>
        <span className="gx-hitl-count">{requests.length} pending</span>
      </div>
      {error && <p className="gx-hitl-error" role="status">Queue unavailable: {error}</p>}
      {!error && loaded && requests.length === 0 && (
        <p className="gx-empty">No pending approvals.</p>
      )}
      <ul className="gx-hitl-list" aria-live="polite">
        {requests.map((request) => (
          <li className="gx-hitl-item" key={request.id}>
            <div className="gx-hitl-body">
              <strong>{request.action}</strong>
              <span>
                {request.requested_by || 'agent'} · {request.created_at || '—'}
              </span>
            </div>
            <div className="gx-hitl-actions">
              <button
                type="button"
                className="gx-btn"
                disabled={busy === request.id}
                onClick={() => decide(request, 'approve')}
              >
                Approve
              </button>
              <button
                type="button"
                className="gx-btn gx-btn--ghost"
                disabled={busy === request.id}
                onClick={() => decide(request, 'deny')}
              >
                Deny
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
