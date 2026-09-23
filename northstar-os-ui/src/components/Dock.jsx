import { useLocation, useNavigate } from 'react-router-dom'
import { DOCK_ACTIONS } from '../data/services.js'
import Icon from './Icon.jsx'

export default function Dock() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <nav className="dock" aria-label="Action dock">
      {DOCK_ACTIONS.map((a) => (
        <button
          key={a.id}
          className={`dock-item ${location.pathname === a.route ? 'active' : ''}`}
          onClick={() => navigate(a.route)}
          aria-label={a.label}
        >
          <Icon name={a.icon} size={19} />
          <span>{a.label}</span>
        </button>
      ))}
    </nav>
  )
}