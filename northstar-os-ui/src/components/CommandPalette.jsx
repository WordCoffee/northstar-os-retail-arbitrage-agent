import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from './Icon.jsx'
import { NAV_GROUPS } from '../data/nav-config.js'

const NAV_MAP = {}
NAV_GROUPS.forEach(g => g.sections.forEach(s => NAV_MAP[s.route] = s))

export default function CommandPalette({ onClose }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(0)
  const inputRef = useRef(null)

  const matches = NAV_GROUPS.flatMap(g =>
    g.sections.map(s => ({ ...s, group: g.label, groupIcon: g.icon }))
  ).filter(item =>
    query === '' ||
    item.label.toLowerCase().includes(query.toLowerCase()) ||
    item.route.toLowerCase().includes(query.toLowerCase())
  )

  useEffect(() => { inputRef.current?.focus() }, [])

  return (
    <div className="cmd-backdrop" onClick={onClose}>
      <div className="cmd-box" onClick={e => e.stopPropagation()}>
        <div className="cmd-input-row">
          <Icon name="search" size={16} />
          <input
            ref={inputRef}
            type="text"
            aria-label="Search rooms and services"
            placeholder="Search rooms, services…"
            value={query}
            onChange={e => { setQuery(e.target.value); setFocused(0) }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setFocused(f => Math.min(f + 1, matches.length - 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setFocused(f => Math.max(f - 1, 0)) }
              if (e.key === 'Enter' && matches[focused]) { navigate(matches[focused].route) }
              if (e.key === 'Escape') onClose()
            }}
          />
        </div>
        <div className="cmd-list">
          {matches.length === 0 && (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--ink-soft)', fontSize: 13 }}>No matches</div>
          )}
          {matches.map((item, i) => (
            <button
              key={item.id}
              className={`cmd-item ${i === focused ? 'focused' : ''}`}
              onClick={() => navigate(item.route)}
            >
              <span className="cmd-label">{item.label}</span>
              <span className="cmd-hint">{item.group}</span>
            </button>
          ))}
        </div>
        <div className="cmd-footer">
          <span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span>
          <span><kbd>Enter</kbd> Open</span>
          <span><kbd>Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  )
}