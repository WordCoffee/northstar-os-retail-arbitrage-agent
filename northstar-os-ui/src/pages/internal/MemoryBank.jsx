import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Live Memory Bank search + distilled playbooks (local reads) ═══
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
            { key: 'created_at', label: 'Created', render: (v) => v ? String(v).slice(0, 19).replace('T', ' ') : 'UNKNOWN' },
          ]} rows={results} />
        ) : (
          <p data-testid="mb-live-empty" style={{ fontSize: 13 }}>No memory entries matched. Honest empty state — nothing is fabricated.</p>
        ))}
        <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Local, per-account search. No external provider call is made.</div>
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
        ) : (
          <p data-testid="mb-playbooks-empty" style={{ fontSize: 13 }}>No distilled playbooks yet. Honest empty state.</p>
        ))}
      </div>
    </>
  )
}

const TABS = [
  { id: 'topics', label: 'Topics', count: 14 },
  { id: 'entries', label: 'Recent Entries' },
  { id: 'unlearn', label: 'Revision & Unlearn' },
]

export default function MemoryBank() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'topics'

  return (
    <PageLayout
      title="Memory Bank"
      subtitle="Per-account knowledge store — facts, preferences, experiences, and AI-derived learnings. All local, no live calls."
      actions={<>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Knowledge is indexed by topic and freshness.', 'info')}>View Knowledge</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Unlearn opens revision control — reversible.', 'info')}>Unlearn</button>
      </>}
    >
      <DataNotice tone="internal" title="Live local reads + sample topics">
        “Knowledge search” and “Learning playbooks” are live local reads (no external provider call). The topic/entry views below are sample data.
      </DataNotice>

      <MemoryLive />

      <RoomTabs tabs={TABS} base="/memory-bank" />

      {view === 'topics' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Knowledge Topics</h3>
              <span className="pill pill-muted">sample</span>
            </div>
            <DataTable columns={[
              { key: 'label', label: 'Topic' },
              { key: 'entries', label: 'Entries' },
              { key: 'freshness', label: 'Freshness' },
              { key: 'source', label: 'Source' },
            ]} rows={[
              { label: 'Amazon FBA Policies', entries: '142', freshness: '1 day ago', source: 'Ingested doc' },
              { label: 'Product Categories', entries: '387', freshness: '3 days ago', source: 'AI-derived' },
              { label: 'Sourcing Patterns', entries: '219', freshness: '1 week ago', source: 'Experience log' },
              { label: 'Operator Preferences', entries: '499', freshness: 'Real-time', source: 'Interaction' },
            ]} />
          </div>
        </div>
      )}

      {view === 'entries' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Recent Entries</h3>
              <span className="pill pill-muted">Latest activity</span>
            </div>
            {[
              { entry: 'Operator prefers Set B stock levels kept below 30 units', kind: 'Preference', time: '2h ago', tone: 'pill-forest' },
              { entry: 'Listing Guardian alert pattern for B08L5VJQ7T', kind: 'Learning', time: '1d ago', tone: 'pill-ochre' },
              { entry: 'Sourcing pattern: invoice-before-verification is a risk signal', kind: 'Experience', time: '3d ago', tone: 'pill-ochre' },
              { entry: 'Q3 2026 margin observations across Set A', kind: 'Fact', time: '5d ago', tone: 'pill-muted' },
            ].map(e => (
              <div key={e.entry} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{e.entry}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{e.time}</div>
                </div>
                <span className={`pill ${e.tone}`}>{e.kind}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'unlearn' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Unlearn is reversible but reviewed">
            Revisions and unlearn requests apply to local knowledge only. Nothing is permanently destroyed without confirmation.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Revision &amp; Unlearn</h3>
            </div>
            <div className="stack" style={{ gap: 12 }}>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Topic or entry to revise</label>
                <input className="input" placeholder="e.g., Sourcing Patterns" />
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Reason</label>
                <input className="input" placeholder="What changed or why it should be unlearned" />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => toast('Revision queued for local knowledge (sample).', 'info')}>Submit Revision</button>
                <button className="btn btn-sm btn-ghost" onClick={() => toast('Unlearn requires explicit reason — surfaced for review.', 'info')}>Unlearn Entry</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}