import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

const TABS = [
  { id: 'runs', label: 'Runs' },
  { id: 'composer', label: 'Composer' },
  { id: 'output', label: 'Output Detail' },
]

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
            <span className={`pill ${v.cloud_available ? 'pill-ochre' : 'pill-muted'}`} title="Cloud provider key present (e.g. OpenRouter)">{v.cloud_available ? 'cloud key present' : 'no cloud key'}</span>
            <span className={`pill ${v.cloud_live_armed ? 'pill-warn' : 'pill-muted'}`} title="Cloud live arming — owner-gated">cloud armed: {v.cloud_live_armed ? 'yes' : 'no'}</span>
            <span className="pill pill-muted" title="Cloud provider">{v.cloud_provider || 'openrouter'}</span>
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

// ═══ Real composer: local Ollama or cloud (OpenRouter) — provider-gated ═══
function AutothinKComposer({ onResult }) {
  const [avail, setAvail] = useState(null)
  const [form, setForm] = useState({ query: '', provider: 'local', tier: 'T2' })
  const [state, setState] = useState({ phase: 'idle' })

  useEffect(() => {
    let alive = true
    settle(signals.autothinkModels()).then(r => { if (alive) setAvail(r.ok ? r.value : null) })
    return () => { alive = false }
  }, [])

  const localOk = !!(avail && avail.local_available)
  const cloudOk = !!(avail && avail.cloud_available)
  const providerOk = form.provider === 'local' ? localOk : cloudOk
  const canRun = providerOk && form.query.trim().length > 0 && state.phase !== 'submitting'

  const run = async () => {
    if (!canRun) return
    setState({ phase: 'submitting' })
    const r = await settle(signals.autothinkRun({ query: form.query.trim(), provider: form.provider, tier: form.tier }))
    if (r.ok) {
      setState({ phase: 'done', value: r.value })
      if (onResult) onResult(r.value)
    } else {
      setState({ phase: 'error', message: (r.error && r.error.message) || 'Run failed.' })
    }
  }

  return (
    <div className="card" data-testid="at-composer">
      <div className="card-head">
        <h3 className="card-title">Research Run Composer</h3>
        <span className={`pill ${providerOk ? 'pill-muted' : 'pill-unknown'}`}>{providerOk ? 'provider ready' : 'provider not ready'}</span>
      </div>
      <div className="stack" style={{ gap: 12 }}>
        <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Research Topic</label>
          <input className="input field" placeholder="e.g., Buy Box risk on Set A ASINs" value={form.query} onChange={e => setForm(f => ({ ...f, query: e.target.value }))} />
        </div>
        <div className="grid-2" style={{ gap: 12 }}>
          <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Provider</label>
            <select className="select field" value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}>
              <option value="local">Local (Ollama) {localOk ? '— ready' : '— not reachable'}</option>
              <option value="cloud">Cloud (OpenRouter) {cloudOk ? '— key present' : '— no key'}</option>
            </select>
          </div>
          <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Tier</label>
            <select className="select field" value={form.tier} onChange={e => setForm(f => ({ ...f, tier: e.target.value }))}>
              <option value="T1">T1</option>
              <option value="T2">T2</option>
              <option value="T3">T3</option>
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn btn-sm" onClick={run} disabled={!canRun}>{state.phase === 'submitting' ? 'Running…' : 'Run Research Task'}</button>
          {!providerOk && <span className="text-low" style={{ fontSize: 11 }}>{form.provider === 'local' ? 'Local Ollama is not reachable.' : 'No cloud key present (OpenRouter).'}</span>}
        </div>
        {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
        {state.phase === 'done' && (
          <div className="alert" style={{ marginBottom: 0 }}>
            <div className="alert-title"><span className={`pill ${state.value.ok ? 'pill-ok' : 'pill-warn'}`}>{state.value.ok ? 'ok' : 'failed'}</span> {state.value.model || 'UNKNOWN'} · {state.value.provider}</div>
            <div className="alert-text" style={{ whiteSpace: 'pre-wrap' }}>{state.value.content || state.value.reason || 'No content returned.'}</div>
          </div>
        )}
        <div className="text-low" style={{ fontSize: 11 }}>A research run never fabricates claims — every output cites its source or says UNKNOWN. Cloud (OpenRouter) calls are owner-armed and spend-gated.</div>
      </div>
    </div>
  )
}

export default function AutothinK() {
  const navigate = useNavigate()
  const location = useLocation()
  const [lastResult, setLastResult] = useState(null)
  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'runs'

  return (
    <PageLayout
      title="AutothinK"
      subtitle="Research run workspace — compose research tasks, review outputs, and track the knowledge plane."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/autothink?view=composer')}>New Research Run</button>
      </>}
    >
      <DataNotice tone="internal" title="Live engine + real runs">
        “Engine status”, “Session history”, and the composer are live reads/calls. Running a task is provider-gated (local Ollama or an armed OpenRouter cloud key). No fabricated outputs.
      </DataNotice>

      <AutothinKStatus />

      <RoomTabs tabs={TABS} base="/autothink" />

      {view === 'runs' && (
        <div className="subview">
          <AutothinKHistory />
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <AutothinKComposer onResult={setLastResult} />
        </div>
      )}

      {view === 'output' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Output Detail</h3>
              <span className="pill pill-muted">{lastResult ? (lastResult.model || 'UNKNOWN') : 'no run yet'}</span>
            </div>
            {lastResult ? (
              <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{lastResult.content || lastResult.reason || 'No content returned.'}</div>
            ) : <p style={{ fontSize: 13 }}>Run a research task in the Composer to see its output here. Honest empty state.</p>}
          </div>
        </div>
      )}
    </PageLayout>
  )
}
