import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { rank } from '../lib/fuzzy.js'
import { announce } from '../lib/announce.js'
import { NAV_GROUPS } from '../data/nav-config.js'

/**
 * Command palette (item 17).
 *
 * The repo shipped two CommandPalette components that nothing imported and no
 * Cmd/Ctrl+K listener anywhere, so "there is a palette" was never true. This one
 * is mounted, keyboard-first and ranked with the tested fuzzy scorer.
 *
 * Recents are the point of a palette: after ten jumps, the top of the list is
 * your working set rather than an alphabetical room index.
 */
const RECENTS_KEY = 'northstar.cmdk.recents'
const MAX_RECENTS = 5

function readRecents() {
  try {
    const raw = JSON.parse(localStorage.getItem(RECENTS_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter((r) => typeof r === 'string') : []
  } catch {
    return []
  }
}

function writeRecents(routes) {
  try { localStorage.setItem(RECENTS_KEY, JSON.stringify(routes.slice(0, MAX_RECENTS))) } catch { /* non-fatal */ }
}

export default function CommandMenu({ open, onClose }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(0)
  const inputRef = useRef(null)
  const returnTo = useRef(null)

  const items = useMemo(
    () => NAV_GROUPS.flatMap((g) => g.sections.map((s) => ({
      id: s.id, label: s.label, route: s.route, group: g.label,
    }))),
    [],
  )

  const results = useMemo(() => {
    const q = query.trim()
    if (q) return rank(q, items, 'label').slice(0, 12)
    const recentRoutes = readRecents()
    const recentItems = recentRoutes
      .map((r) => items.find((i) => i.route === r))
      .filter(Boolean)
      .map((i) => ({ ...i, group: `${i.group} · recent` }))
    const rest = items.filter((i) => !recentRoutes.includes(i.route))
    return [...recentItems, ...rest].slice(0, 12)
  }, [query, items])

  useEffect(() => {
    if (!open) return undefined
    returnTo.current = document.activeElement
    setQuery('')
    setFocused(0)
    const t = setTimeout(() => inputRef.current?.focus(), 0)
    return () => clearTimeout(t)
  }, [open])

  useEffect(() => {
    if (open) return
    // Return focus where the user left it - a palette that dumps focus on <body>
    // breaks keyboard flow.
    if (returnTo.current && typeof returnTo.current.focus === 'function') returnTo.current.focus()
  }, [open])

  if (!open) return null

  const choose = (item) => {
    if (!item) return
    writeRecents([item.route, ...readRecents().filter((r) => r !== item.route)])
    announce(`Opening ${item.label}`)
    onClose()
    navigate(item.route)
  }

  return (
    <div className="cmd-backdrop" onMouseDown={onClose}>
      <div
        className="cmd-box glass"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="cmd-input-row">
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Jump to a room, service or setting"
            aria-expanded="true"
            aria-controls="cmdk-list"
            aria-activedescendant={results[focused] ? `cmdk-${results[focused].id}` : undefined}
            placeholder="Jump to a room, service or setting…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setFocused(0) }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setFocused((f) => Math.min(f + 1, results.length - 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setFocused((f) => Math.max(f - 1, 0)) }
              if (e.key === 'Enter') { e.preventDefault(); choose(results[focused]) }
              if (e.key === 'Escape') { e.preventDefault(); onClose() }
            }}
          />
        </div>
        <div className="cmd-list" id="cmdk-list" role="listbox" aria-label="Results">
          {results.length === 0 && <div className="cmd-empty">No matches</div>}
          {results.map((item, i) => (
            <button
              key={item.route}
              id={`cmdk-${item.id}`}
              type="button"
              role="option"
              aria-selected={i === focused}
              className={`cmd-item ${i === focused ? 'focused' : ''}`}
              onMouseEnter={() => setFocused(i)}
              onClick={() => choose(item)}
            >
              <span className="cmd-label">{item.label}</span>
              <span className="cmd-hint">{item.group}</span>
            </button>
          ))}
        </div>
        <div className="cmd-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span>
          <span><kbd>Enter</kbd> Open</span>
          <span><kbd>Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  )
}
