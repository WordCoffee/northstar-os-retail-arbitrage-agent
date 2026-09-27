import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { NAV_GROUPS, canUseRole } from '../data/nav-config.js'
import { useSession } from '../foundation/session.jsx'

export default function SuiteRail({ onNavigate }) {
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()
  const [collapsed, setCollapsed] = useState({})
  const role = session.authenticated
    ? (session.role || (session.permissions?.includes('platform_admin') ? 'platform_admin' : 'operator'))
    : 'invitee'

  const toggle = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const filtered = NAV_GROUPS.filter(g =>
    g.sections.some(s => canUseRole(s, role))
  )

  return (
    <aside className="suite-rail" aria-label="Suite navigation">
      <div className="suite-rail-header">
        <div className="suite-rail-mark">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L3 7 12 12 21 7 21 17 12 22 3 17Z" fill="none"/>
            <circle cx="12" cy="12" r="2" fill="currentColor"/>
          </svg>
          <span className="suite-rail-name">NorthstarOS</span>
        </div>
        <div className="suite-rail-context">
          {session.authenticated ? (session.role || 'Operator') : 'Invitee'}
        </div>
      </div>

      {filtered.map(g => {
        const open = !collapsed[g.id]
        const activeSection = g.sections.find(s => s.route === location.pathname)
        return (
          <div key={g.id} className={`suite-rail-group ${activeSection ? 'has-active' : ''}`}>
            <button className="suite-rail-group-header" onClick={() => toggle(g.id)}>
              <span className="suite-rail-group-label">{g.label}</span>
              <span className={`suite-rail-chevron ${open ? 'open' : ''}`}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
              </span>
            </button>
            {open && (
              <div className="suite-rail-items">
                {g.sections.map(s => {
                  const active = s.route === location.pathname
                  return (
                    <button
                      key={s.id}
                      className={`suite-rail-item ${active ? 'active' : ''}`}
                      onClick={() => {
                        navigate(s.route)
                        if (onNavigate) onNavigate(s.route)
                      }}
                    >
                      <span className="suite-rail-item-label">{s.label}</span>
                      {s.status && (
                        <span className={`suite-rail-status status-${s.status.toLowerCase().replace(/\s/g, '-')}`}>{s.status}</span>
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}

      <div className="suite-rail-footer">
        <span className="suite-rail-system">v2.0 — Internal Use</span>
      </div>
    </aside>
  )
}
