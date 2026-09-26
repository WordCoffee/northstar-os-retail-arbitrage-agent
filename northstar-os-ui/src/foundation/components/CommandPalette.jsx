// Command palette (Ctrl+K) + help entry point.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../../components/Icon.jsx'
import { SERVICES } from '../../data/services.js'
import { useSession } from '../session.jsx'

export default function CommandPalette({ open, onClose, onToggle }) {
  const navigate = useNavigate()
  const session = useSession()
  const [q, setQ] = useState('')

  const commands = useMemo(() => {
    const items = []
    SERVICES.forEach((g) => g.items.forEach((it) =>
      items.push({ id: it.route, label: `${g.group} · ${it.label}`, run: () => navigate(it.route) })))
    items.push({ id: 'help', label: 'Help · Show tour for this screen', run: () => alert('Tour registry: foundational stub (Phase 1C mounts tours).') })
    items.push({ id: 'docs', label: 'Help · Documentation', run: () => window.open('/reference/index.html', '_blank') })
    items.push({ id: 'refresh', label: 'Reload foundation context', run: () => session.refresh() })
    return items
  }, [navigate, session])

  const filtered = commands.filter((c) => c.label.toLowerCase().includes(q.toLowerCase()))

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); onToggle()
      }
      if (e.key === 'Escape' && open) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose, onToggle])

  if (!open) return null
  return (
    <div className="fs-palette-backdrop" onClick={onClose} role="presentation">
      <div className="fs-palette" role="dialog" aria-modal="true" aria-label="Command palette"
           onClick={(e) => e.stopPropagation()}>
        <div className="fs-palette-input">
          <Icon name="search" size={15} />
          <input autoFocus placeholder="Jump to a service or run a command…" value={q}
                 onChange={(e) => setQ(e.target.value)} aria-label="Command input" />
          <span className="kbd">Esc</span>
        </div>
        <div className="fs-palette-list">
          {filtered.length === 0 && <div className="fs-muted" style={{ padding: 12 }}>No matches</div>}
          {filtered.map((c) => (
            <button key={c.id} className="fs-palette-item"
                    onClick={() => { c.run(); onClose() }}>{c.label}</button>
          ))}
        </div>
      </div>
    </div>
  )
}