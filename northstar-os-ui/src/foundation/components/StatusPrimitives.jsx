// Status & provenance primitives (foundation).
import Icon from '../../components/Icon.jsx'

const PROVENANCE_TONE = {
  live: 'pill-live',
  cached: 'pill-warn',
  imported: 'pill-info',
  benchmark: 'pill-mute',
  computed: 'pill-ok',
  estimated: 'pill-info',
  mocked: 'pill-mute',
  stale: 'pill-warn',
  unavailable: 'pill-off',
}

export function ProvenanceBadge({ kind = 'unavailable', title }) {
  const cls = PROVENANCE_TONE[kind] || 'pill-mute'
  return <span className={`fs-pill ${cls}`} title={title || `provenance: ${kind}`}>{kind}</span>
}

export function ConfidenceChip({ value }) {
  if (value === null || value === undefined) {
    return <span className="fs-pill pill-off">confidence: unknown</span>
  }
  const label = value >= 0.8 ? 'high' : value >= 0.5 ? 'medium' : 'low'
  const cls = value >= 0.8 ? 'pill-live' : value >= 0.5 ? 'pill-warn' : 'pill-off'
  return <span className={`fs-pill ${cls}`} title={`confidence ${value}`}>{label}</span>
}

export function LastUpdated({ at }) {
  if (!at) return <span className="fs-muted">never updated</span>
  const d = new Date(at)
  return <span className="fs-muted">updated {isNaN(d) ? String(at) : d.toLocaleString()}</span>
}

// Standard state messages: loading / error / empty / stale / partial / denied
export function StateMessage({ state, title, detail, onRetry, onAction, actionLabel }) {
  const map = {
    loading: { icon: 'sync', label: 'Loading…' },
    error: { icon: 'alert', label: 'Something went wrong' },
    empty: { icon: 'star', label: 'Nothing here yet' },
    stale: { icon: 'clock', label: 'Data is stale' },
    partial: { icon: 'alert', label: 'Partial data' },
    denied: { icon: 'lock', label: 'Permission required' },
  }
  const m = map[state] || map.empty
  return (
    <div className={`fs-state fs-state-${state}`} role="status" aria-live="polite">
      <div className="fs-state-label"><Icon name={m.icon} size={15} /> {title || m.label}</div>
      {detail && <div className="fs-state-detail">{detail}</div>}
      {(onRetry || onAction) && (
        <div className="fs-state-actions">
          {onRetry && <button className="btn" onClick={onRetry}>Retry</button>}
          {onAction && <button className="btn btn-primary" onClick={onAction}>{actionLabel || 'Continue'}</button>}
        </div>
      )}
    </div>
  )
}