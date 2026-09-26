import { useLocation, useNavigate } from 'react-router-dom'
import { SERVICES, routeToId } from '../data/services.js'
import Icon from './Icon.jsx'
import { useState } from 'react'
import { useSession, hasPerm } from '../foundation/session.jsx'

export default function Sidebar({ betaOnly = false }) {
  const location = useLocation()
  const navigate = useNavigate()
  const session = useSession()
  const activeId = routeToId(location.pathname)

  // Private-beta mode: show ONLY the beta groups (Private Beta, Beta Operations).
  // The legacy analyst groups (Workspace, Sourcing, Listings, Social, Advertising,
  // AutothinK, Monitoring, Internal, ...) are hidden in this mode.
  const BETA_GROUPS = ['Private Beta', 'Beta Operations']
  const groups = betaOnly ? SERVICES.filter((g) => BETA_GROUPS.includes(g.group)) : SERVICES

  // Role-aware: hide items whose permission the session lacks.
  const visibleServices = groups.map((g) => ({
    ...g,
    items: g.items.filter((it) => !it.perm || hasPerm(session, it.perm)),
  })).filter((g) => g.items.length > 0)

  // Collapsed groups: defaults open
  const [collapsed, setCollapsed] = useState(() => {
    const map = {}
    SERVICES.forEach((g) => (map[g.group] = false))
    return map
  })

  const toggleGroup = (name) => setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }))

  return (
    <aside className="sidebar" aria-label="Service drawer">
      {visibleServices.map((group) => {
        const open = !collapsed[group.group]
        return (
          <div key={group.group} className="nav-group">
            <button
              className={`nav-group-head ${open ? 'open' : ''}`}
              onClick={() => toggleGroup(group.group)}
              aria-expanded={open}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <Icon name={group.icon} size={15} />
                <span className="nav-label">{group.group}</span>
              </span>
              <span className="caret"><Icon name="caret" size={13} /></span>
            </button>
            {open && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {group.items.map((item) => {
                  const active = item.id === activeId
                  return (
                    <button
                      key={item.id}
                      className={`nav-item ${active ? 'active' : ''}`}
                      onClick={() => navigate(item.route)}
                      aria-current={active ? 'true' : 'false'}
                    >
                      <Icon name={item.icon} size={15} />
                      <span className="nav-label">{item.label}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}

      {!betaOnly && (
        <div className="sidebar-demo">
          <strong>Live posture</strong> — local engine connected, real catalog data.
          Money gates (purchases, listing, publish) stay closed until explicitly approved.
        </div>
      )}
    </aside>
  )
}