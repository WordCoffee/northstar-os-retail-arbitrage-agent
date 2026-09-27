import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from './Icon.jsx'

export default function MobileBottomNav({ active, onToolsClick }) {
  const navigate = useNavigate()
  const navItems = [
    { id: 'home', label: 'Home', icon: 'home', route: '/home' },
    { id: 'sourcescout', label: 'SourceScout', icon: 'search', route: '/product-finder' },
    { id: 'goose', label: 'Goose', icon: 'goose', route: '/golden-goose' },
    { id: 'profitability', label: 'Profit', icon: 'coin', route: '/profitability' },
    { id: 'tools', label: 'Tools', icon: 'more', route: '/home', onToolsClick },
  ]

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
      {navItems.map(item => (
        <button
          key={item.id}
          className={`mobile-bottom-nav-item ${active === item.id ? 'active' : ''}`}
          onClick={() => {
            if (item.onToolsClick) {
              item.onToolsClick()
            } else {
              navigate(item.route)
            }
          }}
        >
          <Icon name={item.icon} size={20} />
          {item.label}
        </button>
      ))}
    </nav>
  )
}