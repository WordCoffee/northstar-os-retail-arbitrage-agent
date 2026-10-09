import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { NAV_GROUPS, canUseRole } from '../data/nav-config.js'
import { fromBackendRole } from '../data/roles.js'
import { useSession } from '../foundation/session.jsx'

export default function SuiteRail({ onNavigate }) {
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()
  const [collapsed, setCollapsed] = useState({})

  // nav-config lists sections by UI display role, so the backend role the
  // session carries has to be translated before it gates nav. Comparing the
  // two vocabularies directly matched nothing and silently emptied the rail for
  // every signed-in user - see data/roles.js.
  const role = session.authenticated
    ? (fromBackendRole(session.role) ||
       (session.permissions?.includes('platform_admin') ? 'platform_admin' : 'operator'))
    : 'invitee'

  const toggle = (id) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }))

  const filtered = NAV_GROUPS
    .filter(g => g.sections.some(s => canUseRole(s, role)))
    .map(g => ({ ...g, sections: g.sections.filter(s => canUseRole(s, role)) }))
    .filter(g => g.sections.length > 0)

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

      {filtered.length === 0 ? (
        <div className="suite-rail-signin">
          <div className="suite-rail-signin-title">Sign in to open your workspace</div>
          <button className="btn btn-sm" onClick={() => navigate('/sign-in')}>Sign In</button>
        </div>
      ) : filtered.map(g => {
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
                        <span
                          className={`pill pill-${s.statusTone || 'muted'} suite-rail-status`}
                          title={s.readinessTitle || ''}
                        >{s.status}</span>
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
