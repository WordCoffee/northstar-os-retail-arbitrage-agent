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
        <div className="suite-rail-context" style={{ marginTop: 0, textTransform: 'uppercase', letterSpacing: '0.14em', fontSize: 10.5, opacity: 0.7 }}>
          Workspace
        </div>
        <div className="suite-rail-context" style={{ fontWeight: 600, marginTop: 2 }}>
          {session.authenticated
            ? (session.role === 'internal_platform_admin' ? 'Platform Admin' : (session.role || 'Operator'))
            : 'Invitee'}
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
                          className={`nav-dot nav-dot-${s.statusTone || 'muted'}`}
                          title={`${s.status} — ${s.readinessTitle || ''}`}
                          aria-label={s.status}
                        />
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
        <span className="suite-rail-system" title={`Build ${__BUILD_INFO__.commit} · ${__BUILD_INFO__.time}`}>
          v2.0 · build {__BUILD_INFO__.commit}
        </span>
      </div>
    </aside>
  )
}
