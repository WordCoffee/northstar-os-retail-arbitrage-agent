import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from './Icon.jsx'
import { useSession } from '../foundation/session.jsx'

export default function TopNav({ role, paletteOpen, setPaletteOpen }) {
  const navigate = useNavigate()
  const session = useSession()

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
        {session.authenticated && (
          <div className="top-nav-role">
            <Icon name="user" size={14} />
            <span>{role === 'platform_admin' ? 'Admin' : role === 'customer' ? 'Customer' : 'Operator'}</span>
          </div>
        )}
        <div className="top-nav-avatar" title={session.authenticated ? session.userId : 'Guest'}>
          {session.authenticated && session.userId ? session.userId[0].toUpperCase() : '?'}
        </div>
      </div>
    </header>
  )
}
