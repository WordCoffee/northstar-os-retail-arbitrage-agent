// Collapsible Pinned drawer (replaces the persistent right rail).
// Preference persisted per user via the foundation UI-preferences API.
import { useEffect, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import foundationApi from '../api.js'
import { useSession } from '../session.jsx'

const KEY = 'pinned_drawer'

export default function PinnedDrawer({ toast }) {
  const { userId } = useSession()
  const [open, setOpen] = useState(false)
  const [pins, setPins] = useState([])
  const [note, setNote] = useState('')

  // Load persisted open/closed preference
  useEffect(() => {
    if (!userId) return
    foundationApi.getPref(KEY)
      .then((r) => { if (r.value && typeof r.value.open === 'boolean') setOpen(r.value.open) })
      .catch(() => { /* preference unavailable; default closed */ })
  }, [userId])

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (userId) foundationApi.setPref(KEY, { open: next }).catch(() => {})
  }

  const addNote = () => {
    const t = note.trim()
    if (!t) return
    setPins((prev) => [...prev, t])
    setNote('')
    toast('Pinned to board', 'ok')
  }

  return (
    <>
      <button className="fs-pin-toggle" onClick={toggle}
              aria-expanded={open} aria-controls="fs-pinned-drawer"
              title="Pinned drawer">
        <Icon name="star" size={16} /> Pinned
      </button>
      {open && (
        <aside id="fs-pinned-drawer" className="fs-drawer" aria-label="Pinned items">
          <div className="fs-drawer-head">
            <h3>Pinned</h3>
            <button className="btn btn-ghost" onClick={toggle} aria-label="Close pinned drawer">
              <Icon name="caret" size={14} />
            </button>
          </div>
          {pins.length === 0 ? (
            <div className="fs-drawer-empty">Pin products, opportunities, or notes to keep them here.</div>
          ) : (
            pins.map((p, i) => (
              <div key={i} className="fs-drawer-row">
                <span style={{ flex: 1 }}>{p}</span>
                <button className="btn btn-ghost" onClick={() => setPins((prev) => prev.filter((_, j) => j !== i))}
                        aria-label="Unpin">✕</button>
              </div>
            ))
          )}
          <div className="fs-drawer-add">
            <input className="field" aria-label="Pin a note" placeholder="Pin a note…" value={note}
                   onChange={(e) => setNote(e.target.value)}
                   onKeyDown={(e) => e.key === 'Enter' && addNote()} />
            <button className="btn btn-primary" onClick={addNote}>Pin</button>
          </div>
          <div className="fs-drawer-note">
            Pins are per-user. Estimates only — live actions require approval.
          </div>
        </aside>
      )}
    </>
  )
}