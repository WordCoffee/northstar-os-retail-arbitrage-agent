import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Real engine status (presence-only; no credential values) ═══
function AutothinKStatus() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.autothinkModels()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
      : (v && v.local_available) ? { l: 'local available', t: 'ok' }
        : (v && v.cloud_available) ? { l: 'cloud only', t: 'ochre' }
          : { l: 'provider-gated', t: 'unavailable' }
  const models = v && Array.isArray(v.models) ? v.models : []
  return (
    <div className="card" data-testid="at-status" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Engine status</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Probing engine availability…</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Engine status unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <span className={`pill ${v.local_available ? 'pill-ok' : 'pill-warn'}`} title="Local Ollama reachable">{v.local_available ? 'local ready' : 'local not reachable'}</span>
            <span className={`pill ${v.cloud_available ? 'pill-ochre' : 'pill-muted'}`} title="Cloud provider key present">{v.cloud_available ? 'cloud key present' : 'no cloud key'}</span>
            <span className={`pill ${v.cloud_live_armed ? 'pill-warn' : 'pill-muted'}`} title="Cloud live arming — owner-gated">cloud armed: {v.cloud_live_armed ? 'yes' : 'no'}</span>
            <span className="pill pill-muted" title="Default local model">local: {v.default_local_model || 'UNKNOWN'}</span>
            <span className="pill pill-muted" title="Default cloud model">cloud: {v.default_cloud_model || 'UNKNOWN'}</span>
          </div>
          {models.length > 0 ? (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }} title="Installed local models (names only)">
              {models.map(m => <span key={m} className="pill pill-muted" style={{ fontSize: 10 }}>{m}</span>)}
            </div>
          ) : <span className="text-low" style={{ fontSize: 12 }}>{v.error ? `No local models reported (${v.error}).` : 'No local models installed.'}</span>}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Presence/availability only — no credential values are read or shown. Running a research task is provider-gated.</div>
        </>
      )}
    </div>
  )
}

// ═══ Real session history (local store) ═══
function AutothinKHistory() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.autothinkHistory(20)).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const entries = v && Array.isArray(v.entries) ? v.entries : []
  return (
    <div className="card" data-testid="at-history">
      <div className="card-head">
        <h3 className="card-title">Session history</h3>
        <span className="pill pill-muted">{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${v && v.total != null ? v.total : entries.length} entries · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>No live session history (engine server not reachable).</p>}
      {st.phase === 'loaded' && (entries.length > 0 ? (
        <DataTable columns={[
          { key: 'query', label: 'Query' },
          { key: 'provider', label: 'Provider', render: (x) => <span className="pill pill-muted">{x || 'UNKNOWN'}</span> },
          { key: 'tier', label: 'Tier', render: (x) => <span className="pill pill-muted">{x || 'UNKNOWN'}</span> },
          { key: 'model', label: 'Model', render: (x) => x || 'UNKNOWN' },
          { key: 'ok', label: 'Result', render: (x) => <span className={`pill ${x ? 'pill-ok' : 'pill-warn'}`}>{x ? 'ok' : 'failed'}</span> },
          { key: 'reason', label: 'Reason', render: (x) => x || '—' },
        ]} rows={entries} />
      ) : (
        <p data-testid="at-history-empty" style={{ fontSize: 13 }}>No research runs recorded yet. Honest empty state — nothing is fabricated.</p>
      ))}
    </div>
  )
}

const TABS = [
  { id: 'runs', label: 'Runs', count: 4 },
  { id: 'composer', label: 'Composer' },
  { id: 'output', label: 'Output Detail' },
]

const RUNS = [
  { id: 'R-01', topic: 'Competitor Pricing Shift', engine: 'Ling 3.0 Flash', status: 'Complete', started: '2026-09-22', output: '3 insights', tone: 'pill-forest' },
  { id: 'R-02', topic: 'Buy Box Risk Assessment', engine: 'Ling 3.0 Flash', status: 'Running', started: '2026-09-25', output: '—', tone: 'pill-ochre' },
  { id: 'R-03', topic: 'Margin Hypothesis Scan', engine: 'Northstar Inline', status: 'Queued', started: '—', output: '—', tone: 'pill-muted' },
  { id: 'R-04', topic: 'Listing Copy Quality', engine: 'Ling 3.0 Flash', status: 'Complete', started: '2026-09-20', output: '2 insights', tone: 'pill-forest' },
]

export default function AutothinK() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'runs'

  const newRun = () => navigate('/autothink?view=composer')

  return (
    <PageLayout
      title="AutothinK"
      subtitle="Research run workspace — compose research tasks, review outputs, and track the knowledge plane in action."
      actions={<>
        <button className="btn btn-sm" onClick={newRun}>New Research Run</button>
      </>}
    >
      <DataNotice tone="sample" title="Live engine status + sample runs">
        “Engine status” and “Session history” are live local reads. The research runs, composer, and output below are sample data. A research run never fabricates claims — every output cites its data source or says UNKNOWN. Running a task is provider-gated (local Ollama or an armed cloud provider).
      </DataNotice>

      <AutothinKStatus />

      <RoomTabs tabs={TABS} base="/autothink" />

      {view === 'runs' && (
        <div className="subview">
          <AutothinKHistory />

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Sample runs (preview)</h3>
              <span className="pill pill-muted">4 runs · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'topic', label: 'Topic' },
              { key: 'engine', label: 'Engine' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
              { key: 'started', label: 'Started' },
              { key: 'output', label: 'Output' },
            ]} rows={RUNS} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">How Outputs Are Grounded</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Every insight cites its data source or states UNKNOWN</div>
                <span className="pill pill-forest">Enforced</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Engine choice is explicit per run — no silent delegation</div>
                <span className="pill pill-muted">Explicit</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Outputs feed Memory Bank and shared data layer only after review</div>
                <span className="pill pill-ochre">Review Gate</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Research Run Composer</h3>
            </div>
            <div className="stack" style={{ gap: 12 }}>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Research Topic</label>
                <input className="input" placeholder="e.g., Buy Box risk on Set A ASINs" defaultValue="Competitor Pricing Shift" />
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Engine</label>
                <select className="select">
                  <option>Ling 3.0 Flash</option>
                  <option>Northstar Inline</option>
                </select>
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Data Sources Allowed</label>
                <input className="input" placeholder="e.g., Listing Guardian, Keyword Tracker, Monitoring" />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => toast('Run queued (sample) — engine will cite sources in every output.', 'info')}>Queue Research Run</button>
                <button className="btn btn-sm btn-ghost" onClick={() => toast('Draft saving is not connected — composer runs are sample.', 'info')}>Save Draft</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'output' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">R-02 — Buy Box Risk Assessment</h3>
              <span className="pill pill-ochre">Running</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>Buy box position may shift on Set A — engine gathering seller-side data</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Sources: Monitoring · Status: IN PROGRESS</div>
                </div>
                <span className="pill pill-muted">Streaming</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>Seller count on B08L5VJQ7T</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Status: UNKNOWN — provider data not connected</div>
                </div>
                <span className="pill pill-unknown">UNKNOWN</span>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => toast('Saved to Memory Bank (sample).', 'info')}>Send to Memory Bank</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}