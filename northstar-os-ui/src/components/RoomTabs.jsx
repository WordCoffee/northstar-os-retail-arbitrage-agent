import { useNavigate, useLocation } from 'react-router-dom'

// Service-local navigation — drives subviews through a `view` search param so
// every room is deep-linkable (e.g. /listingforge?view=editor) while staying
// inside the service room. Replaces dashboard-style single pages.
export default function RoomTabs({ tabs, base, param = 'view', onNavigate }) {
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get(param) || ''
  const active = tabs.some(t => t.id === requested) ? requested : tabs[0].id

  const select = (id) => {
    const params = new URLSearchParams(location.search)
    params.set(param, id)
    const search = params.toString()
    navigate(`${base}${search ? `?${search}` : ''}`)
    if (onNavigate) onNavigate()
  }

  return (
    <nav className="room-tabs" aria-label="Service navigation">
      {tabs.map(t => {
        const isActive = t.id === active
        return (
          <button
            key={t.id}
            className={`room-tab ${isActive ? 'active' : ''}`}
            onClick={() => select(t.id)}
          >
            <span className="room-tab-label">{t.label}</span>
            {t.count !== undefined && (
              <span className={`room-tab-count ${isActive ? 'active' : ''}`}>{t.count}</span>
            )}
            {t.status && <span className={`pill pill-${t.statusTone || 'muted'}`}>{t.status}</span>}
          </button>
        )
      })}
    </nav>
  )
}