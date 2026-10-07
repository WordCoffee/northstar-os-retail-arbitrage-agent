import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Real local memory entries (read-only) ═══
function MemoryEntries() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncSessions()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const items = v && Array.isArray(v.items) ? v.items : []
  const byType = v && v.summary && v.summary.by_type ? v.summary.by_type : {}
  return (
    <div className="card" data-testid="mb-entries" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Knowledge entries</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${items.length} entries · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Memory read unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        <>
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {Object.entries(byType).map(([k, n]) => <span key={k} className="pill pill-muted" style={{ fontSize: 10 }}>{k}: {n}</span>)}
          </div>
          {items.length > 0 ? (
            <DataTable columns={[
              { key: 'entry_type', label: 'Type', render: (x) => <span className="pill pill-muted">{x || 'UNKNOWN'}</span> },
              { key: 'content', label: 'Content', render: (x) => <span title={x}>{x && x.length > 70 ? x.slice(0, 69) + '…' : x}</span> },
              { key: 'source', label: 'Source', render: (x) => x || 'UNKNOWN' },
              { key: 'confidence', label: 'Conf.', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{x}</span> },
            ]} rows={items} />
          ) : <p data-testid="mb-entries-empty" style={{ fontSize: 13 }}>No memory entries. Honest empty state.</p>}
        </>
      )}
    </div>
  )
}

// ═══ Real knowledge search + distilled playbooks (local reads) ═══
function MemoryLive() {
  const [intent, setIntent] = useState('')
  const [st, setSt] = useState({ phase: 'loading' })
  const [books, setBooks] = useState({ phase: 'loading' })
  const run = (q) => {
    setSt({ phase: 'loading' })
    settle(signals.memorySearch(q)).then(r => {
      if (r.ok) setSt({ phase: 'loaded', value: r.value.data || r.value })
      else setSt({ phase: 'error', error: r.error })
    })
  }
  useEffect(() => {
    run('')
    settle(signals.learningPlaybooks()).then(r => {
      if (r.ok) setBooks({ phase: 'loaded', value: r.value.data || r.value })
      else setBooks({ phase: 'error', error: r.error })
    })
  }, [])
  const results = st.value && Array.isArray(st.value.results) ? st.value.results : []
  const pbMap = books.value && books.value.playbooks && typeof books.value.playbooks === 'object' ? books.value.playbooks : {}
  const pbEntries = Object.entries(pbMap)
  return (
    <>
      <div className="card" data-testid="mb-live" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <h3 className="card-title">Knowledge search</h3>
          <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${results.length} match${results.length === 1 ? '' : 'es'} · local`}</span>
        </div>
        <div className="inline-flex" style={{ gap: 8, marginBottom: 12 }}>
          <input className="field" style={{ maxWidth: 320 }} value={intent} onChange={e => setIntent(e.target.value)} placeholder="Search intent (keyword)…" onKeyDown={e => { if (e.key === 'Enter') run(intent) }} />
          <button className="btn btn-sm" onClick={() => run(intent)}>Search</button>
        </div>
        {st.phase === 'error' && <p style={{ fontSize: 13 }}>Memory search unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
        {st.phase === 'loaded' && (results.length > 0 ? (
          <DataTable columns={[
            { key: 'content', label: 'Entry' },
            { key: 'entry_type', label: 'Type', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
            { key: 'confidence', label: 'Confidence', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{v}</span> },
            { key: 'source', label: 'Source', render: (v) => v || 'UNKNOWN' },
          ]} rows={results} />
        ) : <p data-testid="mb-live-empty" style={{ fontSize: 13 }}>No memory entries matched. Honest empty state.</p>)}
      </div>

      <div className="card" data-testid="mb-playbooks" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <h3 className="card-title">Learning playbooks</h3>
          <span className={`pill pill-${books.phase === 'error' ? 'unknown' : 'muted'}`}>{books.phase === 'loading' ? 'Loading…' : books.phase === 'error' ? 'unavailable' : `${pbEntries.length} distilled`}</span>
        </div>
        {books.phase === 'error' && <p style={{ fontSize: 13 }}>Playbook read unavailable{books.error && books.error.code ? ` (${books.error.code})` : ''}.</p>}
        {books.phase === 'loaded' && (pbEntries.length > 0 ? (
          <div className="stack" style={{ gap: 8 }}>
            {pbEntries.map(([sig, p]) => (
              <div key={sig} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{sig}</div>
                <span className="pill pill-muted" title="Playbooks are distilled, reviewable guidance — not automatic actions">{p && p.account_id ? `account: ${p.account_id}` : 'distilled'}</span>
              </div>
            ))}
          </div>
        ) : <p data-testid="mb-playbooks-empty" style={{ fontSize: 13 }}>No distilled playbooks yet. Honest empty state.</p>)}
      </div>
    </>
  )
}

export default function MemoryBank() {
  return (
    <PageLayout
      title="Memory Bank"
      subtitle="Per-account knowledge store — facts, preferences, experiences, and AI-derived learnings. All local, no live calls."
    >
      <DataNotice tone="internal" title="Live local knowledge store">
        Entries, search, and playbooks are live local reads (no external provider call). Unlearning (a write) is not activated in this beta.
      </DataNotice>
      <MemoryLive />
      <MemoryEntries />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Revision &amp; Unlearn</h3>
          <span className="pill pill-muted">disabled · write not activated</span>
        </div>
        <p style={{ fontSize: 13 }}>Unlearning a playbook is a real, audited write (<span style={{ fontFamily: 'var(--font-mono)' }}>POST /api/v1/learning/unlearn</span>) and is not activated in this beta.</p>
      </div>
    </PageLayout>
  )
}
