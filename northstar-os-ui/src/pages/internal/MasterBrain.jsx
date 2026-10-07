import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
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
  const audit = Array.isArray(s.audit) ? s.audit.slice(0, 6) : []
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
          ) : <p style={{ fontSize: 13 }}>No memory entries. Honest empty state.</p>}
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
        </>
      )}
    </div>
  )
}

export default function MasterBrain() {
  return (
    <PageLayout
      title="Master Brain"
      subtitle="Orchestration visibility — model catalog and the local knowledge plane."
    >
      <DataNotice tone="internal" title="Research assistance only">
        The catalog and knowledge-plane sessions are live reads (presence-only, no secrets). Master Brain does NOT authorize purchases, make pricing decisions, or contact providers without explicit operator approval.
      </DataNotice>
      <BrainCatalog />
      <RealSessions />
    </PageLayout>
  )
}
