import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Real Brain model catalog (dual-engine; presence-only, no secrets) ═══
function BrainCatalog() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.brainModels()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value.data || r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
      : { l: 'live · brain', t: 'muted' }
  const mapRows = (m) => Object.entries(m || {}).map(([k, val]) => ({ key: k, value: val }))
  return (
    <div className="card" data-testid="mb-catalog" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Brain model catalog</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading model catalog…</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Model catalog unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {(v.providers || []).map(p => <span key={p} className="pill pill-muted">{p}</span>)}
          </div>
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
            {(v.tiers || []).map(t => <span key={t} className="pill pill-muted" title="Escalating tiers prompt once; never silent">{t}{v.tier_labels && v.tier_labels[t] ? ` · ${v.tier_labels[t]}` : ''}</span>)}
          </div>
          <div className="grid-2" style={{ gap: 16 }}>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Local defaults</div>
              <DataTable columns={[{ key: 'key', label: 'Service' }, { key: 'value', label: 'Model' }]} rows={mapRows(v.local && v.local.defaults)} emptyText="No local defaults" />
            </div>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Cloud defaults</div>
              <DataTable columns={[{ key: 'key', label: 'Service' }, { key: 'value', label: 'Model' }]} rows={mapRows(v.cloud && v.cloud.defaults)} emptyText="No cloud defaults" />
            </div>
          </div>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
            <span className={`pill ${v.cloud && v.cloud.key_present ? 'pill-ochre' : 'pill-muted'}`} title="Cloud key presence only — no value shown">cloud key: {v.cloud && v.cloud.key_present ? 'present' : 'absent'}</span>
            <span className={`pill ${v.cloud && v.cloud.live_armed ? 'pill-warn' : 'pill-muted'}`} title="Cloud live arming — owner-gated">cloud armed: {v.cloud && v.cloud.live_armed ? 'yes' : 'no'}</span>
            <span className="pill pill-muted" title="Media provider keys (presence only)">media keys: {Object.values(v.media_key_present || {}).filter(Boolean).length} present</span>
            <span className={`pill ${v.media_armed ? 'pill-warn' : 'pill-muted'}`}>media armed: {v.media_armed ? 'yes' : 'no'}</span>
          </div>
          {v.consent && <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>{v.consent}</div>}
          <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>Presence/availability only — no credential values. Arming any provider is an owner decision.</div>
        </>
      )}
    </div>
  )
}

const TABS = [
  { id: 'sessions', label: 'Sessions', count: 3 },
  { id: 'decisions', label: 'Decision Flow' },
  { id: 'reasoning', label: 'Reasoning Checkpoints' },
  { id: 'control', label: 'Control' },
]

// ═══ Real local knowledge-plane sessions (memory + audit, read-only) ═══
function RealSessions() {
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
  const s = (v && v.summary) || {}
  const audit = Array.isArray(s.audit) ? s.audit.slice(0, 5) : []
  const byType = s.by_type || {}
  return (
    <div className="card" data-testid="mb-real-sessions" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Knowledge-plane sessions</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${items.length} entries · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Session read unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        <>
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {Object.entries(byType).map(([k, n]) => <span key={k} className="pill pill-muted" style={{ fontSize: 10 }}>{k}: {n}</span>)}
            <span className="pill pill-muted" style={{ fontSize: 10 }}>audit: {s.audit_entries ?? 0}</span>
          </div>
          {items.length > 0 ? (
            <DataTable columns={[
              { key: 'entry_type', label: 'Type', render: (x) => <span className="pill pill-muted">{x || 'UNKNOWN'}</span> },
              { key: 'content', label: 'Content', render: (x) => <span title={x}>{x && x.length > 60 ? x.slice(0, 59) + '…' : x}</span> },
              { key: 'source', label: 'Source', render: (x) => x || 'UNKNOWN' },
              { key: 'confidence', label: 'Conf.', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{x}</span> },
            ]} rows={items.slice(0, 15)} />
          ) : <p className="text-low" style={{ fontSize: 13 }}>No memory entries. Honest empty state.</p>}
          {audit.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Recent audit</div>
              <div className="stack" style={{ gap: 4 }}>
                {audit.map((a, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{a.action}</span>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.entity_type || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Real local knowledge/audit records (read-only). No external call.</div>
        </>
      )}
    </div>
  )
}

export default function MasterBrain() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'sessions'

  return (
    <PageLayout
      title="Master Brain"
      subtitle="Orchestration visibility — active sessions, decision flow, reasoning checkpoints, and control surfaces."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Sessions view — active runs and their engines.', 'info')}>View Sessions</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Decision Log — full reasoning trail per decision.', 'info')}>Decision Log</button>
      </>}
    >
      <DataNotice tone="internal" title="Research assistance only">
        The “Brain model catalog” is a live read (presence-only). Master Brain does NOT authorize purchases, make pricing decisions, or contact providers without explicit operator approval. Confidence values are internal estimates, not verified fact.
      </DataNotice>

      <BrainCatalog />
      <RealSessions />

      <RoomTabs tabs={TABS} base="/master-brain" />

      {view === 'sessions' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Sessions</h3>
              <span className="pill pill-forest">3 running</span>
            </div>
            <DataTable columns={[
              { key: 'session', label: 'Session' },
              { key: 'engine', label: 'Engine' },
              { key: 'focus', label: 'Focus' },
              { key: 'started', label: 'Started' },
              { key: 'state', label: 'State' },
            ]} rows={[
              { session: 'S-001', engine: 'Ling 3.0 Flash', focus: 'Buy box risk — Set A', started: '10:04', state: 'Running' },
              { session: 'S-002', engine: 'Northstar Inline', focus: 'Margin hypothesis scan', started: '09:41', state: 'Queued' },
              { session: 'S-003', engine: 'Ling 3.0 Flash', focus: 'Listing copy quality', started: '08:12', state: 'Review' },
            ]} />
          </div>
        </div>
      )}

      {view === 'decisions' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Decision Flow — Recent</h3>
              <span className="pill pill-muted">47 today</span>
            </div>
            <DataTable columns={[
              { key: 'input', label: 'Input' },
              { key: 'decision', label: 'Decision' },
              { key: 'confidence', label: 'Confidence' },
              { key: 'model', label: 'Model' },
              { key: 'state', label: 'State' },
            ]} rows={[
              { input: 'SourceScout B08L5VJQ7T', decision: 'Researching', confidence: '42%', model: 'Internal v2', state: 'In Progress' },
              { input: 'GG-001 Opportunity', decision: 'Hold for verification', confidence: '55%', model: 'Internal v2', state: 'Waiting' },
              { input: 'Portfolio Set B analysis', decision: 'Monitor closely', confidence: '68%', model: 'Internal v2', state: 'Active' },
              { input: 'Keyword gap analysis', decision: 'Recommend listing update', confidence: '74%', model: 'Internal v2', state: 'Complete' },
            ]} />
          </div>
        </div>
      )}

      {view === 'reasoning' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Reasoning Checkpoints</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Cost basis validation — BLOCKED until invoice verified</div>
                <span className="pill pill-error">Block</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Pack identity match — AWAITING operator input</div>
                <span className="pill pill-warn">Wait</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Market trend analysis — COMPLETE</div>
                <span className="pill pill-ok">OK</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'control' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Control Surfaces</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Purchase authorization</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Pricing decisions</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Provider contact</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Research runs</div>
                <span className="pill pill-forest">Available</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}