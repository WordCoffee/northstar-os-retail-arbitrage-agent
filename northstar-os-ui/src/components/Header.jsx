import Icon from './Icon.jsx'
import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Header({ theme, onToggleTheme, toast, rightSlot }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)

  const submit = (e) => {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    toast(`Search: "${q}" — no global index yet`, 'ok')
    setQuery('')
    inputRef.current && inputRef.current.blur()
  }

  return (
    <header className="header">
      <div className="brand" onClick={() => navigate('/hub')}>
        <Icon name="star" size={30} />
        <span className="brand-title">
          Northstar<span className="accent">OS</span>
          <span className="brand-sub">RETAIL ARBITRAGE SUITE</span>
        </span>
      </div>

      <div className="header-center">
        <form className="search" onSubmit={submit}>
          <Icon name="search" size={15} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Global search — services, SKUs, terms…"
            aria-label="Global search"
            autoComplete="off"
            spellCheck="false"
          />
        </form>
        <span className="plan-chip">
          <span className="plan-name">Plan</span>
          <span className="plan-tier">AutothinK (live)</span>
        </span>
        <span className="engine-chip">
          <span className="dot" />
          local · T2 · northstar-qwen3:rev1
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div className="select-wrap">
          <select aria-label="AI engine provider" defaultValue="local" onChange={(e) => toast(`Engine provider → ${e.target.value}`, 'ok')}>
            <option value="local">Local</option>
            <option value="cloud">Cloud</option>
          </select>
          <Icon name="caret" size={13} />
        </div>
        <div className="select-wrap">
          <select aria-label="AI tier" defaultValue="t2" onChange={(e) => toast(`AI tier → ${e.target.value.toUpperCase()}`, 'ok')}>
            <option value="t1">T1 Fast</option>
            <option value="t2">T2 Core</option>
            <option value="t3">T3 Seam</option>
          </select>
          <Icon name="caret" size={13} />
        </div>
        <button
          className="icon-btn"
          aria-label="Toggle light or dark theme"
          data-active={theme === 'light'}
          title="Toggle theme"
          onClick={onToggleTheme}
        >
          <Icon name={theme === 'light' ? 'sun' : 'moon'} size={17} />
        </button>
        <button className="btn" onClick={() => navigate('/account')}>Account</button>
        {rightSlot}
      </div>
    </header>
  )
}