import { useLocation, useNavigate } from 'react-router-dom'
import { SERVICES, routeToId } from '../data/services.js'
import Icon from './Icon.jsx'
import { useState } from 'react'

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const activeId = routeToId(location.pathname)

  // Collapsed groups: defaults open
  const [collapsed, setCollapsed] = useState(() => {
    const map = {}
    SERVICES.forEach((g) => (map[g.group] = false))
    return map
  })

  const toggleGroup = (name) => setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }))

  return (
    <aside className="sidebar" aria-label="Service drawer">
      {SERVICES.map((group) => {
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

      <div className="sidebar-demo">
        <strong>Live posture</strong> — local engine connected, real catalog data.
        Money gates (purchases, listing, publish) stay closed until explicitly approved.
      </div>
    </aside>
  )
}