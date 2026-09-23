import { useState } from 'react'
import Icon from './Icon.jsx'

export default function RightRail({ toast }) {
  const [pinned, setPinned] = useState([])
  const [note, setNote] = useState('')

  const addNote = () => {
    const t = note.trim()
    if (!t) return
    setPinned((prev) => [...prev, t])
    setNote('')
    toast('Pinned to board', 'ok')
  }

  const remove = (idx) => setPinned((prev) => prev.filter((_, i) => i !== idx))

  return (
    <aside className="rail" aria-label="Bulletin board">
      <div className="rail-head">
        <h3>Pinned</h3>
        <span className="count">{pinned.length} pinned</span>
      </div>

      {pinned.length === 0 ? (
        <div className="rail-empty">
          Pin a row (♡) or hit “Pinned” notes here to keep deals on the board.
        </div>
      ) : (
        pinned.map((p, i) => (
          <div key={i} className="list-row" style={{ alignItems: 'center' }}>
            <span style={{ flex: 1, fontSize: 12 }}>{p}</span>
            <button className="btn btn-ghost" style={{ padding: '3px 8px' }} onClick={() => remove(i)} aria-label="Unpin">✕</button>
          </div>
        ))
      )}

      <div className="stack" style={{ marginTop: 4 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            className="field"
            placeholder="Pin a note…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addNote()}
          />
          <button className="btn btn-primary" onClick={addNote}>Pin</button>
        </div>
      </div>

      <div className="rail-note">
        <Icon name="alert" size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
        Estimates only. Live actions require a fresh named operator approval.
      </div>
    </aside>
  )
}