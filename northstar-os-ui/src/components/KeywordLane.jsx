import { useEffect, useState } from 'react'
import { DataNotice, EmptyState } from './Shared.jsx'
import foundationApi from '../foundation/api.js'

// Keyword Tracker — live foundation lane. Reads the existing foundation
// /keywords routes (search, gaps). Honest states: it shows the exact backend
// error (e.g. missing org context) rather than inventing keyword data.

function rows(items) {
  return Array.isArray(items) ? items : []
}

function labelOf(it) {
  if (!it || typeof it !== 'object') return String(it ?? '')
  return it.keyword || it.term || it.text || it.query || it.name || it.id || JSON.stringify(it)
}

export default function KeywordLane() {
  const [q, setQ] = useState('turmeric')
  const [items, setItems] = useState(null)
  const [mode, setMode] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function search() {
    setBusy(true); setErr(''); setItems(null); setMode('search')
    try {
      const j = await foundationApi.keywordSearch(q, 50)
      setItems(rows(j.items))
    } catch (e) { setErr(e.message || String(e)) } finally { setBusy(false) }
  }

  async function gaps() {
    setBusy(true); setErr(''); setItems(null); setMode('gaps')
    try {
      const j = await foundationApi.keywordGaps()
      setItems(rows(j.items))
    } catch (e) { setErr(e.message || String(e)) } finally { setBusy(false) }
  }

  const cols = items && items[0] && typeof items[0] === 'object'
    ? Object.keys(items[0]).slice(0, 6) : []

  return (
    <div className="subview ns-lane fade-in">
      <DataNotice tone="cached" title="Live foundation read — real keyword records">
        This lane reads the foundation keyword store through the authenticated API.
        If the backend reports a missing organization context or an error, it is shown
        verbatim — no keyword data is fabricated.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3 className="card-title">Keyword search</h3></div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <label htmlFor="kl-q">Query</label>
            <input id="kl-q" type="text" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <button className="btn btn-primary" disabled={busy} onClick={search}>{busy && mode === 'search' ? 'Searching…' : 'Search'}</button>
          <button className="btn btn-ghost" disabled={busy} onClick={gaps}>{busy && mode === 'gaps' ? 'Loading…' : 'Coverage gaps'}</button>
        </div>
      </div>

      {err && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <div className="alert-title">Backend reported</div>
          <div className="alert-text">{err}</div>
        </div>
      )}

      <div className="card">
        <div className="card-head">
          <h3 className="card-title">{mode === 'gaps' ? 'Coverage gaps' : 'Results'}</h3>
          {items && <span className="pill pill-muted">{items.length} record(s)</span>}
        </div>
        {!items && !err && <EmptyState icon="🔎" title="No query yet">Search keywords or load coverage gaps.</EmptyState>}
        {items && items.length === 0 && !err && (
          <EmptyState icon="∅" title="No records returned">The foundation store has no matching rows for this query.</EmptyState>
        )}
        {items && items.length > 0 && (
          <table className="table">
            <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c} className="text-low" style={{ fontSize: 12 }}>
                      {typeof it[c] === 'object' ? JSON.stringify(it[c]) : String(it[c] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {items && items.length > 0 && (
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
            first record: {labelOf(items[0])}
          </div>
        )}
      </div>
    </div>
  )
}
