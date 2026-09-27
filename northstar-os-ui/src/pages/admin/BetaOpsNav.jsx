import { NavLink } from 'react-router-dom'

const TABS = [
  { to: '/beta-ops', label: 'Overview', end: true },
  { to: '/beta-ops/orgs', label: 'Organizations' },
  { to: '/beta-ops/invites', label: 'Invites' },
  { to: '/beta-ops/cohorts', label: 'Cohorts' },
  { to: '/beta-ops/support', label: 'Support' },
  { to: '/beta-ops/lifecycle', label: 'Lifecycle' },
  { to: '/beta-ops/audit', label: 'Audit' },
  { to: '/beta-ops/reports', label: 'Reports' },
]

export default function BetaOpsNav() {
  return (
    <nav className="room-tabs" aria-label="Beta Operations navigation" style={{ marginBottom: 20 }}>
      {TABS.map(t => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) => `room-tab ${isActive ? 'active' : ''}`}
        >
          <span className="room-tab-label">{t.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
