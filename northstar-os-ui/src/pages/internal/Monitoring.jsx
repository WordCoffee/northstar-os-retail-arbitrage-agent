import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

const TABS = [
  { id: 'alerts', label: 'Alerts' },
  { id: 'health', label: 'Health' },
  { id: 'sync', label: 'Sync & Staleness' },
]

const SEV_PILL = { High: 'pill-error', Medium: 'pill-warn', Low: 'pill-muted' }

const DESTINATIONS = [
  { label: 'Shared Data Layer', route: '/shared-data', context: 'sources & freshness', match: 'Shared Data Layer' },
  { label: 'Provider Adapters', route: '/provider-adapters', context: 'runs & spend', match: 'Provider Adapters' },
  { label: 'Commerce Ops', route: '/commerce-ops', context: 'inventory & approvals', match: 'Commerce Ops' },
]

const env = (r) => (r && r.ok ? (r.value && r.value.data ? r.value.data : r.value) : null)
const ts = (x) => (x ? String(x).slice(0, 19).replace('T', ' ') : '—')

// ═══ One real read set for the whole room (read-only, honest) ═══
function useMonitoring() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [mon, status, health, sources] = await Promise.all([
        settle(signals.monitoringAlerts()),
        settle(signals.systemStatus()),
        settle(signals.detailedHealth()),
        settle(signals.ncSources()),
      ])
      if (alive) setSt({ loaded: true, mon, status, health, sources })
    })()
    return () => { alive = false }
  }, [])
  const mon = env(st.mon)
  const status = env(st.status)
  const health = env(st.health)
  const src = st.sources && st.sources.ok ? st.sources.value : null

  const summary = (mon && mon.summary) || null
  const alert = (mon && mon.alert) || null
  const readiness = (status && status.readiness) || (health && health.readiness) || null
  const warehouse = (status && status.warehouse) || null
  const services = (health && health.readiness && health.readiness.services) || null
  const refresh = (src && Array.isArray(src.items)) ? src.items : []

  // Derived real alerts (no fabrication).
  const alerts = []
  if (summary && summary.breached) {
    alerts.push({ id: 'MON-ERR', type: 'System', message: (alert && alert.message) || 'API 5xx rate exceeded threshold', severity: 'High', source: 'Monitoring', time: 'now' })
  }
  refresh.forEach((r, i) => {
    const failed = Number(r.records_failed || 0)
    const bad = failed > 0 || !['ok', 'complete', 'success'].includes(String(r.status || '').toLowerCase())
    if (bad) {
      alerts.push({
        id: 'MON-REF-' + i, type: 'Data Freshness',
        message: `${r.provider || 'source'} refresh ${r.status || 'unknown'}${failed ? ` (${failed} failed)` : ''}${r.error_message ? ` — ${r.error_message}` : ''}`,
        severity: failed > 0 ? 'High' : 'Medium', source: 'Shared Data Layer', time: ts(r.started_at),
      })
    }
  })

  // Derived real service checks.
  const checks = []
  if (summary) {
    checks.push({ svc: 'API error rate', state: summary.breached ? 'Breached' : 'Within threshold', tone: summary.breached ? 'pill-warn' : 'pill-muted', basis: 'error tracker (live)', live: true })
  }
  if (services) {
    Object.entries(services).forEach(([svc, r]) => {
      checks.push({ svc, state: (r && r.ready) ? 'Ready' : 'Not ready', tone: (r && r.ready) ? 'pill-muted' : 'pill-warn', basis: (r && r.reason) || 'readiness (live)', live: true })
    })
  }
  if (warehouse) {
    checks.push({ svc: 'Warehouse', state: `${warehouse.fresh_rows ?? '?'} fresh / ${warehouse.live_rows ?? '?'} live`, tone: 'pill-muted', basis: 'catalog (live)', live: true })
  }

  // Derived real staleness rows.
  const staleness = refresh.map((r, i) => {
    const bad = !['ok', 'complete', 'success'].includes(String(r.status || '').toLowerCase())
    return { src: `${r.provider || 'source'} · ${r.refresh_type || 'refresh'}`, last: ts(r.finished_at || r.started_at), state: bad ? 'Stale' : 'Observed', tone: bad ? 'pill-ochre' : 'pill-muted', owner: 'Shared Data Layer' }
  })
  const lastSync = refresh.length ? refresh.map(r => r.finished_at || r.started_at || '').sort().slice(-1)[0] : null

  return { loaded: st.loaded, anyOk: !!(mon || status || health || src), summary, alert, readiness, warehouse, services, alerts, checks, staleness, lastSync, refresh }
}

// ═══ Live checks (error rate, readiness, warehouse) ═══
function LiveObservability() {
  const m = useMonitoring()
  const rowStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: '1px solid var(--divider)' }
  return (
    <div className="card" data-testid="mon-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Live checks</h3>
        {!m.loaded ? <span className="pill pill-muted">Loading…</span>
          : m.anyOk ? <span className="pill pill-muted" title="Live read-only checks from the local backend">live read</span>
            : <span className="pill pill-unknown" title="Backend reads failed — not fabricated">unavailable</span>}
      </div>
      <div style={rowStyle}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>API error rate (5xx)</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/monitoring/error-alerts · rolling window</div>
        </div>
        {m.summary
          ? <span className="inline-flex" style={{ gap: 6 }}>
              <span className={`pill ${m.summary.breached ? 'pill-warn' : 'pill-ok'}`}>{m.summary.breached ? 'breached' : 'within threshold'}</span>
              <span className="pill pill-muted">{m.summary.five_xx_rate == null ? 'UNKNOWN' : (m.summary.five_xx_rate * 100).toFixed(1) + '%'} · {m.summary.total_requests ?? 0} req</span>
            </span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>
      <div style={rowStyle}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Foundation readiness</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/v1/status · service readiness</div>
        </div>
        {m.readiness
          ? <span className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <span className={`pill ${m.readiness.ready ? 'pill-ok' : 'pill-warn'}`}>{m.readiness.ready ? 'ready' : 'not ready'}</span>
            </span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>
      <div style={{ ...rowStyle, borderBottom: 'none' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Warehouse state</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/v1/status · live catalog</div>
        </div>
        {m.warehouse
          ? <span className="pill pill-muted">{m.warehouse.fresh_rows ?? '?'} fresh · {m.warehouse.live_rows ?? '?'} live</span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>
    </div>
  )
}

// ═══ Detailed health (files, scanner, provider presence, readiness reasons) ═══
function DetailedHealth() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.detailedHealth()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
      : { l: 'live · backend probe', t: 'muted' }
  const checks = v && v.checks ? v.checks : {}
  const providers = v && v.providers ? v.providers : {}
  const readiness = v && v.readiness && v.readiness.services ? v.readiness.services : {}
  const fileChecks = Object.entries(checks).filter(([k]) => k.startsWith('file_'))
  return (
    <div className="card" data-testid="mon-detailed-health" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Detailed health</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Running detailed health probe…</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Detailed health probe unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <span className={`pill ${v.scanner_mode === 'live_allowed' ? 'pill-warn' : 'pill-muted'}`} title="Live scanner gate — live calls are owner-gated">scanner: {v.scanner_mode || 'UNKNOWN'}</span>
            <span className="pill pill-muted">tests: {v.test_status || 'unknown'}</span>
            {v.timestamp && <span className="pill pill-muted">at {v.timestamp}</span>}
          </div>
          <div className="grid-2" style={{ gap: 16 }}>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Data file checks</div>
              <div className="stack" style={{ gap: 6 }}>
                {fileChecks.length > 0 ? fileChecks.map(([k, val]) => (
                  <div key={k} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{k.replace(/^file_/, '')}</span>
                    <span className={`pill ${val === 'ok' ? 'pill-muted' : 'pill-warn'}`}>{val}</span>
                  </div>
                )) : <span className="text-low" style={{ fontSize: 12 }}>No file checks reported.</span>}
              </div>
              <div className="text-low" style={{ fontSize: 11, margin: '12px 0 6px' }}>Provider keys (presence only)</div>
              <div className="stack" style={{ gap: 6 }}>
                {Object.keys(providers).length > 0 ? Object.entries(providers).map(([name, state]) => (
                  <div key={name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{name}</span>
                    <span className={`pill ${state === 'configured' ? 'pill-muted' : 'pill-unknown'}`} title="Key presence only — values are never read or shown">{state === 'configured' ? 'configured' : 'not configured'}</span>
                  </div>
                )) : <span className="text-low" style={{ fontSize: 12 }}>No provider keys reported.</span>}
              </div>
            </div>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Readiness services</div>
              <div className="stack" style={{ gap: 6 }}>
                {Object.keys(readiness).length > 0 ? Object.entries(readiness).map(([svc, r]) => (
                  <div key={svc} style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '4px 0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12 }}>{svc}</span>
                      <span className={`pill ${r && r.ready ? 'pill-ok' : 'pill-warn'}`}>{r && r.ready ? 'ready' : 'not ready'}</span>
                    </div>
                    {r && r.reason && <span className="text-low" style={{ fontSize: 11 }}>{r.reason}</span>}
                  </div>
                )) : <span className="text-low" style={{ fontSize: 12 }}>No readiness services reported.</span>}
              </div>
            </div>
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Provider rows show key presence only. This probe performs no live provider call.</div>
        </>
      )}
    </div>
  )
}

export default function Monitoring() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const m = useMonitoring()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'
  const staleCount = m.staleness.filter(s => s.state !== 'Observed').length

  return (
    <PageLayout
      title="Monitoring"
      subtitle="Observability watchtower — service health, alert stream, and sync/staleness summary. Source-level detail lives in Shared Data Layer and Provider Adapters."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Alert configuration: severities and channels (sample).', 'info')}>Configure Alerts</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/shared-data')}>Open Shared Data Layer</button>
      </>}
    >
      <DataNotice tone="internal" title="Observability — derived from live local reads">
        This room derives its alerts, service checks, and staleness summary from live local reads (error tracker, readiness, refresh registry). When no adverse signal exists it shows an honest empty state — nothing is fabricated.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/monitoring" />

      {view === 'alerts' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Alerts</h3>
              <span className={`pill ${m.alerts.length ? 'pill-clay' : 'pill-muted'}`}>{m.alerts.length} active · derived</span>
            </div>
            {m.alerts.length > 0 ? (
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'type', label: 'Type' },
                { key: 'message', label: 'Message' },
                { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${SEV_PILL[v] || 'pill-muted'}`}>{v}</span> },
                { key: 'source', label: 'Detail Source', render: (v) => <span className="pill pill-muted" title="Where the source-level detail lives">{v}</span> },
                { key: 'time', label: 'Time', render: (v) => <span className="pill pill-muted">{v}</span> },
              ]} rows={m.alerts} />
            ) : <p data-testid="mon-alerts-empty" style={{ fontSize: 13 }}>No adverse signals detected in the live reads. Honest empty state — no fabricated alerts.</p>}
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Where to investigate</h3>
              <span className="pill pill-muted">routes to source-of-truth</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {DESTINATIONS.map(d => {
                const count = m.alerts.filter(a => a.source === d.match).length
                return (
                  <div key={d.label} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{d.label}</div>
                      <div className="text-low" style={{ fontSize: 11 }}>{d.context}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className={`pill ${count ? 'pill-clay' : 'pill-muted'}`} title="Active alerts pointing at this room">{count} alert{count === 1 ? '' : 's'}</span>
                      <button className="btn btn-sm btn-ghost" onClick={() => navigate(d.route)}>Open</button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {view === 'health' && (
        <div className="subview">
          <LiveObservability />
          <DetailedHealth />
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">System Health</h3>
              <span className="pill pill-muted">live · derived</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'Overall readiness', v: m.readiness ? (m.readiness.ready ? 'Ready' : 'Not ready') : 'UNKNOWN', note: 'from /api/v1/status', warn: m.readiness && !m.readiness.ready },
                { label: 'Open alerts', v: String(m.alerts.length), note: 'derived from live reads', warn: m.alerts.length > 0 },
                { label: 'API error rate', v: m.summary && m.summary.five_xx_rate != null ? (m.summary.five_xx_rate * 100).toFixed(1) + '%' : 'UNKNOWN', note: 'rolling 5xx window', warn: m.summary && m.summary.breached },
                { label: 'Last refresh', v: m.lastSync ? ts(m.lastSync) : 'UNKNOWN', note: 'refresh registry' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: d.warn ? 'var(--ochre)' : 'var(--pine-deep)' }}>{d.v}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.note}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Service Checks</h3>
              <span className="pill pill-muted">live · basis per row</span>
            </div>
            {m.checks.length > 0 ? (
              <div className="stack" style={{ gap: 8 }}>
                {m.checks.map(s => (
                  <div key={s.svc} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{s.svc}</div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="pill pill-muted" style={{ fontSize: 10 }} title="How this state is determined">{s.basis}</span>
                      <span className={`pill ${s.tone}`} title="Live probe-backed check">{s.state}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : <p style={{ fontSize: 13 }}>No live service checks available right now.</p>}
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Truth-state rule: green means live-verified only">
              Green is reserved for live probe-backed checks. Adverse states keep their distinct colour.
            </div>
          </div>
        </div>
      )}

      {view === 'sync' && (
        <div className="subview">
          <div className="grid-3" style={{ gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Sources monitored</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{m.staleness.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>from refresh registry</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Needs attention</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ochre)' }}>{staleCount}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Stale or failed</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Last refresh</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--pine-deep)' }}>{m.lastSync ? ts(m.lastSync) : 'UNKNOWN'}</div>
              <div className="text-low" style={{ fontSize: 11 }}>latest registry entry</div>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Staleness Summary</h3>
              <span className="pill pill-muted" title="High-level only — full freshness matrix lives in Shared Data Layer">summary · not full matrix</span>
            </div>
            {m.staleness.length > 0 ? (
              <DataTable columns={[
                { key: 'src', label: 'Source' },
                { key: 'last', label: 'Last Update' },
                { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.tone}`} title={v === 'Stale' ? 'Exceeded freshness threshold — investigate' : 'Within window'}>{v}</span> },
                { key: 'owner', label: 'Detail Source', render: (v) => <span className="pill pill-muted">{v}</span> },
              ]} rows={m.staleness} />
            ) : <p data-testid="mon-stale-empty" style={{ fontSize: 13 }}>No refresh records yet. Honest empty state.</p>}
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Investigate in the right room</h3>
            </div>
            <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-sm" onClick={() => navigate('/shared-data')}>Shared Data Layer — freshness matrix</button>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/provider-adapters')}>Provider Adapters — runs &amp; logs</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
