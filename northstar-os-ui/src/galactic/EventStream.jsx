import { useMemo, useState } from 'react'
import { summarizeEvents } from '../lib/galacticState.js'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'telemetry', label: 'Telemetry' },
  { id: 'ui', label: 'UI' },
  { id: 'warn', label: 'Warnings' },
  { id: 'error', label: 'Errors' },
]

function clock(ts) {
  const n = Number(ts)
  if (!Number.isFinite(n)) return '—'
  try {
    return new Date(n).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return '—'
  }
}

// Unified Event Bus view: the deck publishes UI events and telemetry snapshots
// into one ordered stream. The list is the audit surface, not a toast queue.
export default function EventStream({ events = [], onReplay }) {
  const [filter, setFilter] = useState('all')
  const summary = useMemo(() => summarizeEvents(events), [events])
  const visible = useMemo(() => {
    if (filter === 'all') return events
    if (filter === 'telemetry' || filter === 'ui') {
      return events.filter((event) => event.source === filter)
    }
    return events.filter((event) => event.severity === filter)
  }, [events, filter])

  return (
    <div className="gx-events">
      <div className="gx-events-head">
        <div>
          <span className="gx-eyebrow">Unified event bus</span>
          <strong className="gx-events-count">{summary.total} events</strong>
        </div>
        {onReplay && (
          <button type="button" className="gx-btn gx-btn--ghost" onClick={onReplay}>
            Replay
          </button>
        )}
      </div>
      <div className="gx-filters" role="group" aria-label="Event filters">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`gx-filter ${filter === item.id ? 'is-active' : ''}`}
            aria-pressed={filter === item.id}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <ol className="gx-event-list" aria-live="polite">
        {visible.length === 0 && <li className="gx-empty">No events in this filter.</li>}
        {visible.map((event) => (
          <li className={`gx-event gx-event--${event.severity || 'info'}`} key={event.id}>
            <time dateTime={new Date(Number(event.ts) || 0).toISOString()}>{clock(event.ts)}</time>
            <span className="gx-event-type">{event.type}</span>
            <span className="gx-event-source">{event.source}</span>
            <span className="gx-event-payload">
              {Object.keys(event.payload || {}).length
                ? JSON.stringify(event.payload).slice(0, 120)
                : ''}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
