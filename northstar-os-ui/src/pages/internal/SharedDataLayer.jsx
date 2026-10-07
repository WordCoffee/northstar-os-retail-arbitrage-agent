import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Live data readiness (warehouse + data-file checks + catalog coverage) ═══
function SharedDataLive() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [status, health, catalog] = await Promise.all([
        settle(signals.systemStatus()),
        settle(signals.detailedHealth()),
        settle(signals.sourceScoutSummary()),
      ])
      if (alive) setSt({ phase: 'loaded', status, health, catalog })
    })()
    return () => { alive = false }
  }, [])
  const env = (r) => (r && r.ok ? (r.value && r.value.data ? r.value.data : r.value) : null)
  const status = env(st.status)
  const health = env(st.health)
  const catalog = st.catalog && st.catalog.ok ? st.catalog.value : null
  const anyOk = (st.status && st.status.ok) || (st.health && st.health.ok) || (st.catalog && st.catalog.ok)
  const warehouse = status && status.warehouse ? status.warehouse : null
  const checks = health && health.checks ? health.checks : {}
  const fileChecks = Object.entries(checks).filter(([k]) => k.startsWith('file_'))
  const readiness = status && status.readiness ? status.readiness : null
  return (
    <div className="card" data-testid="sdl-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Live data readiness</h3>
        <span className={`pill pill-${anyOk ? 'muted' : 'unknown'}`}>{st.phase === 'loading' ? 'Loading…' : anyOk ? 'live · backend' : 'unavailable'}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Reading data readiness…</p>}
      {st.phase === 'loaded' && !anyOk && <p style={{ fontSize: 13 }}>Data readiness unavailable.</p>}
      {st.phase === 'loaded' && anyOk && (
        <div className="grid-2" style={{ gap: 16 }}>
          <div>
            <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Warehouse</div>
            {warehouse ? (
              <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                <span className={`pill ${status.mode === 'live' ? 'pill-ok' : 'pill-muted'}`}>{status.mode}</span>
                <span className="pill pill-muted">{warehouse.fresh_rows ?? 'UNKNOWN'} fresh</span>
                <span className="pill pill-muted">{warehouse.live_rows ?? 'UNKNOWN'} live</span>
                <span className="pill pill-muted">{warehouse.pulls ?? 0} pulls</span>
              </div>
            ) : <span className="pill pill-unknown">unavailable</span>}
            <div className="text-low" style={{ fontSize: 11, margin: '12px 0 6px' }}>Data file checks</div>
            <div className="stack" style={{ gap: 4 }}>
              {fileChecks.length > 0 ? fileChecks.map(([k, v]) => (
                <div key={k} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{k.replace(/^file_/, '')}</span>
                  <span className={`pill ${v === 'ok' ? 'pill-muted' : 'pill-warn'}`}>{v}</span>
                </div>
              )) : <span className="text-low" style={{ fontSize: 12 }}>No file checks reported.</span>}
            </div>
          </div>
          <div>
            <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Catalog coverage (SourceScout)</div>
            {catalog ? (
              <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                <span className="pill pill-muted">{catalog.total ?? 'UNKNOWN'} items</span>
                <span className="pill pill-ok">{catalog.pass ?? 0} pass</span>
                <span className="pill pill-warn">{catalog.fail ?? 0} fail</span>
                <span className="pill pill-ochre">{catalog.review ?? 0} review</span>
              </div>
            ) : <span className="pill pill-unknown">unavailable</span>}
            <div className="text-low" style={{ fontSize: 11, margin: '12px 0 6px' }}>Readiness services</div>
            <div className="stack" style={{ gap: 4 }}>
              {readiness && readiness.services && Object.keys(readiness.services).length > 0
                ? Object.entries(readiness.services).map(([svc, ready]) => (
                  <div key={svc} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                    <span style={{ fontSize: 12 }}>{svc}</span>
                    <span className={`pill ${ready ? 'pill-muted' : 'pill-warn'}`}>{ready ? 'ready' : 'not ready'}</span>
                  </div>
                ))
                : <span className="text-low" style={{ fontSize: 12 }}>No readiness services reported.</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ═══ Real local source/refresh registry (read-only) ═══
function RealSourceRegistry() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncSources()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const refresh = v && Array.isArray(v.items) ? v.items : []
  const s = (v && v.summary) || {}
  const pulls = Array.isArray(s.live_pulls) ? s.live_pulls.slice(0, 8) : []
  return (
    <div className="card" data-testid="sdl-source-registry" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Source refresh registry</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${refresh.length} refreshes · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Source registry unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        <>
          {refresh.length > 0 ? (
            <DataTable columns={[
              { key: 'provider', label: 'Provider' },
              { key: 'refresh_type', label: 'Type', render: (x) => <span className="pill pill-muted">{x || '—'}</span> },
              { key: 'status', label: 'Status', render: (x) => <span className={`pill ${x === 'partial' ? 'pill-warn' : 'pill-muted'}`}>{x || 'UNKNOWN'}</span> },
              { key: 'records_imported', label: 'Imported', render: (x) => x ?? 0 },
              { key: 'records_failed', label: 'Failed', render: (x) => <span className={`pill ${x ? 'pill-warn' : 'pill-muted'}`}>{x ?? 0}</span> },
              { key: 'started_at', label: 'Started', render: (x) => x ? String(x).slice(0, 19).replace('T', ' ') : '—' },
            ]} rows={refresh} />
          ) : <p style={{ fontSize: 13 }}>No refresh records. Honest empty state.</p>}
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
            <span className="pill pill-muted">{s.live_pulls ?? 0} live pulls</span>
            <span className="pill pill-muted">{s.pipeline_runs ?? 0} pipeline runs</span>
          </div>
          {pulls.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Recent live pulls</div>
              <div className="stack" style={{ gap: 4 }}>
                {pulls.map((p, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{p.query} · {p.provider_id}</span>
                    <span className={`pill ${p.ok ? 'pill-muted' : 'pill-warn'}`} style={{ fontSize: 10 }}>{p.rows_returned ?? 0} rows</span>
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

export default function SharedDataLayer() {
  return (
    <PageLayout
      title="Shared Data Layer"
      subtitle="Centralized data readiness — warehouse, file checks, catalog coverage, and the source refresh registry."
    >
      <DataNotice tone="internal" title="Live data readiness — no fabricated sources">
        Every panel here is a live local read (warehouse, file checks, catalog coverage, refresh registry). Empty/unknown is shown honestly; no dataset is treated as verified unless proven.
      </DataNotice>
      <SharedDataLive />
      <RealSourceRegistry />
    </PageLayout>
  )
}
