import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from './Icon.jsx'
import { useSession } from '../foundation/session.jsx'
import ShellModeToggle from './ShellModeToggle.jsx'

export default function TopNav({ role, paletteOpen, setPaletteOpen }) {
  const navigate = useNavigate()
  const session = useSession()
  const [menu, setMenu] = useState('') // '' | 'notifications' | 'create'

  const toggle = (name) => setMenu((m) => (m === name ? '' : name))

  const QUICK_CREATE = [
    { id: 'create-listing', label: 'Listing Forge — New Listing', to: '/listingforge?view=editor' },
    { id: 'create-campaign', label: 'AdPilot — New Campaign', to: '/adpilot?view=planner' },
    { id: 'create-research', label: 'AutothinK — New Research Run', to: '/autothink?view=composer' },
  ]

  return (
    <header className="top-nav">
      <div className="top-nav-brand" onClick={() => navigate('/home')}>
        <Icon name="star" size={22} />
        <span className="top-nav-brand-name">NorthstarOS</span>
      </div>
      <div className="top-nav-right">
        <div className="top-nav-search">
          <Icon name="search" size={15} />
          <input
            type="search"
            placeholder="Search the Northstar Index…"
            onKeyDown={(e) => { if (e.key === 'Enter') setPaletteOpen(true) }}
            aria-label="Search"
          />
        </div>

        <ShellModeToggle />

        <div className="top-nav-action">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-label="Quick create"
            aria-haspopup="menu"
            aria-expanded={menu === 'create'}
            onClick={() => toggle('create')}
          >
            <Icon name="plus" size={15} />
          </button>
          {menu === 'create' && (
            <div className="top-nav-menu" role="menu" aria-label="Quick create">
              {QUICK_CREATE.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="menuitem"
                  className="top-nav-menu-item"
                  onClick={() => { navigate(item.to); setMenu('') }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="top-nav-action">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-label="Notifications"
            aria-haspopup="menu"
            aria-expanded={menu === 'notifications'}
            onClick={() => toggle('notifications')}
          >
            <Icon name="bell" size={15} />
          </button>
          {menu === 'notifications' && (
            <div className="top-nav-menu" role="menu" aria-label="Notifications">
              <div className="top-nav-menu-empty">
                No notifications. Delivery is not wired yet — status UNKNOWN.
              </div>
            </div>
          )}
        </div>

        {session.authenticated && (
          <button
            type="button"
            className="top-nav-role top-nav-account-btn"
            aria-label="Account"
            onClick={() => navigate('/account')}
          >
            <Icon name="user" size={14} />
            <span>{role === 'platform_admin' ? 'Admin' : role === 'customer' ? 'Customer' : 'Operator'}</span>
          </button>
        )}
        <button
          type="button"
          className="top-nav-avatar"
          aria-label="Account"
          title={session.authenticated ? session.userId : 'Guest'}
          onClick={() => navigate(session.authenticated ? '/account' : '/sign-in')}
        >
          {session.authenticated && session.userId ? session.userId[0].toUpperCase() : '?'}
        </button>
      </div>
    </header>
  )
}
