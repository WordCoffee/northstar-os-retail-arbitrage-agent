// Global notifications surface (foundation).
// Phase 1B: renders foundation context errors/notices; richer delivery is Phase 1C.
import { useSession } from '../session.jsx'

export default function Notifications() {
  const { error, loaded } = useSession()
  const count = error ? 1 : 0
  return (
    <div className="fs-notifications" title={error ? `foundation error: ${error.message}` : 'no notifications'}>
      <span className="fs-bell" aria-hidden="true">🔔</span>
      {count > 0 && <span className="fs-badge-count">{count}</span>}
      {!loaded && <span className="fs-muted" style={{ marginLeft: 6 }}>…</span>}
    </div>
  )
}