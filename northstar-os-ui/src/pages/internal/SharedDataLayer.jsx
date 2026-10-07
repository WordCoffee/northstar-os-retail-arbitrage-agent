import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'
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
      <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Live local reads. Presence/availability only; no credential values or external calls.</div>
    </div>
  )
}

const TABS = [
  { id: 'sources', label: 'Sources', count: 6 },
  { id: 'readiness', label: 'Readiness' },
  { id: 'provenance', label: 'Provenance' },
]

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
  const pulls = Array.isArray(s.live_pulls) ? s.live_pulls.slice(0, 6) : []
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
          ) : <p className="text-low" style={{ fontSize: 13 }}>No refresh records. Honest empty state.</p>}
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
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Real local refresh/live-pull metadata (read-only). No provider call is made by this view.</div>
        </>
      )}
    </div>
  )
}

export default function SharedDataLayer() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'sources'

  return (
    <PageLayout
      title="Shared Data Layer"
      subtitle="Centralized data readiness — schemas, readiness states, freshness, and provenance of every dataset."
      actions={<>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Schema View — inspect the canonical schema.', 'info')}>Schema View</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Provenance Log — full source chain per field.', 'info')}>Provenance Log</button>
      </>}
    >
      <DataNotice tone="internal" title="Live data readiness + sample source table">
        “Live data readiness” is a real backend read (warehouse, file checks, catalog coverage, service readiness). The source/provenance tables below are sample data. Every dataset carries a truth state: OBSERVED, CACHED, HISTORICAL, UNVERIFIED, or UNAVAILABLE.
      </DataNotice>

      <SharedDataLive />
      <RealSourceRegistry />

      <RoomTabs tabs={TABS} base="/shared-data" />

      {view === 'sources' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Source Readiness</h3>
              <span className="pill pill-muted">sample · v2.1 schema</span>
            </div>
            <DataTable columns={[
              { key: 'source', label: 'Source' },
              { key: 'status', label: 'Readiness', render: (v) => <span className="pill pill-muted">{v}</span> },
              { key: 'lastSync', label: 'Last Sync' },
              { key: 'records', label: 'Records' },
            ]} rows={[
              { source: 'Provider Adapter 1', status: 'CACHED', lastSync: '2h ago', records: '4,200' },
              { source: 'Provider Adapter 2', status: 'OBSERVED', lastSync: '1h ago', records: '2,800' },
              { source: 'Market Benchmark', status: 'HISTORICAL', lastSync: '7 days ago', records: '12,400' },
              { source: 'Sourcing Registry', status: 'UNVERIFIED', lastSync: 'N/A', records: '890' },
              { source: 'Provider Adapter 3', status: 'UNAVAILABLE', lastSync: 'N/A', records: '0' },
            ]} />
          </div>
        </div>
      )}

      {view === 'readiness' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Readiness Matrix</h3>
            </div>
            {[
              { dataset: 'Price data', state: 'OBSERVED (cached)', note: 'Fresh 2h · safe for research' },
              { dataset: 'Rank data', state: 'OBSERVED', note: 'Fresh 1h · safe for research' },
              { dataset: 'Market benchmarks', state: 'HISTORICAL', note: '7d old · context only' },
              { dataset: 'Sourcing registry', state: 'UNVERIFIED', note: 'Needs verification before use' },
              { dataset: 'Invoice records', state: 'UNAVAILABLE', note: 'No backend connected' },
            ].map(d => (
              <div key={d.dataset} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{d.dataset}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.note}</div>
                </div>
                <span className="pill pill-muted">{d.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'provenance' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Provenance Log</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Price data — Provider observation (cached)</div>
                <span className="pill pill-forest">CACHED</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Rank data — Provider observation (observed)</div>
                <span className="pill pill-sage">OBSERVED</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Market benchmarks — Historical dataset</div>
                <span className="pill pill-unknown">HISTORICAL</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Sourcing registry — Imported, unverified</div>
                <span className="pill pill-clay">UNVERIFIED</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}