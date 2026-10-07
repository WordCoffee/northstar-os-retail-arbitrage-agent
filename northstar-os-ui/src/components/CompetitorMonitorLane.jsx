import { useEffect, useState } from 'react'
import { DataNotice, EmptyState } from './Shared.jsx'

// Competitor Monitor — local watch desk. Add competitor entries, record
// snapshots (price/title/rank), and see exactly what changed. No scraping and no
// provider: the operator supplies the observations and the monitor computes deltas.

const API = '/api/competitor-monitor'

export default function CompetitorMonitorLane() {
  const [entries, setEntries] = useState([])
  const [overview, setOverview] = useState([])
  const [add, setAdd] = useState({ name: '', asin: '' })
  const [snap, setSnap] = useState({})
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  async function load() {
    try {
      const j = await (await fetch(`${API}/watchlist`)).json()
      setEntries(j.entries || [])
      setOverview(j.overview || [])
    } catch (e) {
      setNotice({ tone: 'error', text: `Watch desk unavailable (${e.message}).` })
    }
  }
  useEffect(() => { load() }, [])

  async function addEntry() {
    if (!add.name.trim()) { setNotice({ tone: 'warn', text: 'Give the competitor a name.' }); return }
    setBusy(true)
    try {
      const r = await fetch(`${API}/watchlist`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: add.name, asin: add.asin }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setAdd({ name: '', asin: '' })
      setNotice({ tone: 'ok', text: `Watching ${j.entry.name}.` })
      await load()
    } catch (e) { setNotice({ tone: 'error', text: e.message }) } finally { setBusy(false) }
  }

  async function recordSnapshot(id) {
    const s = snap[id] || {}
    if ([s.price, s.rank, s.title].every((v) => v === undefined || v === '')) {
      setNotice({ tone: 'warn', text: 'Enter at least one observed field (price/title/rank).' }); return
    }
    try {
      const data = {}
      if (s.price !== undefined && s.price !== '') data.price = Number(s.price)
      if (s.rank !== undefined && s.rank !== '') data.rank = Number(s.rank)
      if (s.title) data.title = s.title
      const r = await fetch(`${API}/watchlist/${id}/snapshot`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setNotice({ tone: 'ok', text: `Snapshot recorded (${j.deltas.count} change(s)).` })
      setSnap({ ...snap, [id]: {} })
      await load()
    } catch (e) { setNotice({ tone: 'error', text: e.message }) }
  }

  async function remove(id) {
    await fetch(`${API}/watchlist/${id}`, { method: 'DELETE' })
    await load()
  }

  const ov = (id) => overview.find((o) => o.id === id)

  return (
    <div className="subview ns-lane fade-in">
      <DataNotice tone="internal" title="Local watch desk — operator-supplied observations">
        Add competitors and record snapshots you observe. The monitor computes exact
        deltas between your snapshots. It performs no scraping and never invents
        competitor data.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3 className="card-title">Add competitor</h3></div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ minWidth: 200 }}>
            <label htmlFor="cm-name">Name</label>
            <input id="cm-name" type="text" value={add.name} onChange={(e) => setAdd({ ...add, name: e.target.value })} />
          </div>
          <div style={{ minWidth: 160 }}>
            <label htmlFor="cm-asin">ASIN (optional)</label>
            <input id="cm-asin" type="text" value={add.asin} onChange={(e) => setAdd({ ...add, asin: e.target.value })} />
          </div>
          <button className="btn btn-primary" disabled={busy} onClick={addEntry}>Add to watchlist</button>
        </div>
        {notice && (
          <div className={`alert${notice.tone === 'error' ? ' alert-error' : notice.tone === 'warn' ? ' alert-warn' : ''}`} style={{ marginTop: 12 }}>
            <div className="alert-text">{notice.text}</div>
          </div>
        )}
      </div>

      {entries.length === 0 && (
        <div className="card">
          <EmptyState icon="👁" title="No competitors on watch">
            Add a competitor above, then record snapshots to see price/rank/title deltas.
          </EmptyState>
        </div>
      )}

      {entries.map((e) => {
        const o = ov(e.id) || {}
        const s = snap[e.id] || {}
        return (
          <div key={e.id} className="card" style={{ marginBottom: 14 }}>
            <div className="card-head">
              <h3 className="card-title">{e.name}{e.asin ? ` · ${e.asin}` : ''}</h3>
              <span className="pill pill-muted">{o.snapshots || 0} snapshot(s) · {o.changes || 0} change(s)</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ width: 110 }}>
                <label htmlFor={`p-${e.id}`}>Price</label>
                <input id={`p-${e.id}`} type="text" value={s.price || ''} onChange={(ev) => setSnap({ ...snap, [e.id]: { ...s, price: ev.target.value } })} />
              </div>
              <div style={{ width: 110 }}>
                <label htmlFor={`r-${e.id}`}>Rank</label>
                <input id={`r-${e.id}`} type="text" value={s.rank || ''} onChange={(ev) => setSnap({ ...snap, [e.id]: { ...s, rank: ev.target.value } })} />
              </div>
              <div style={{ minWidth: 220, flex: 1 }}>
                <label htmlFor={`t-${e.id}`}>Title (optional)</label>
                <input id={`t-${e.id}`} type="text" value={s.title || ''} onChange={(ev) => setSnap({ ...snap, [e.id]: { ...s, title: ev.target.value } })} />
              </div>
              <button className="btn btn-primary" onClick={() => recordSnapshot(e.id)}>Record snapshot</button>
              <button className="btn btn-ghost" onClick={() => remove(e.id)}>Remove</button>
            </div>
            {o.latest_change && (
              <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>
                latest change: {o.latest_change.field} {String(o.latest_change.from)} → {String(o.latest_change.to)}
                {o.latest_change.delta !== null && o.latest_change.delta !== undefined ? ` (Δ ${o.latest_change.delta})` : ''}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
