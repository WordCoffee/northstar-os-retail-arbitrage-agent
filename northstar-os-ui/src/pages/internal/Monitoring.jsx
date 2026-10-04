import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Live observability (real reads) ═══
// Real, read-only checks from the running backend: API error-rate tracker,
// foundation readiness services, and warehouse counts. Unavailable reads are
// labelled honestly — never substituted with sample values.
function LiveObservability() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [mon, status] = await Promise.all([
        settle(signals.monitoringAlerts()),
        settle(signals.systemStatus()),
      ])
      if (alive) setSt({ loaded: true, mon, status })
    })()
    return () => { alive = false }
  }, [])

  const env = (r) => (r && r.ok ? (r.value && r.value.data ? r.value.data : r.value) : null)
  const mon = env(st.mon)
  const status = env(st.status)
  const summary = mon && mon.summary ? mon.summary : null
  const readiness = status && status.readiness ? status.readiness : null
  const warehouse = status && status.warehouse ? status.warehouse : null
  const anyOk = (st.mon && st.mon.ok) || (st.status && st.status.ok)

  const rowStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: '1px solid var(--divider)' }

  return (
    <div className="card" data-testid="mon-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Live checks</h3>
        {!st.loaded
          ? <span className="pill pill-muted">Loading…</span>
          : anyOk
            ? <span className="pill pill-muted" title="Live read-only checks from the local backend">live read</span>
            : <span className="pill pill-unknown" title="Backend reads failed — not fabricated">unavailable</span>}
      </div>

      <div style={rowStyle}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>API error rate (5xx)</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/monitoring/error-alerts · rolling window</div>
        </div>
        {summary
          ? <span className="inline-flex" style={{ gap: 6 }}>
              <span className={`pill ${summary.breached ? 'pill-warn' : 'pill-ok'}`}>{summary.breached ? 'breached' : 'within threshold'}</span>
              <span className="pill pill-muted">{summary.five_xx_rate == null ? 'UNKNOWN' : (summary.five_xx_rate * 100).toFixed(1) + '%'} · {summary.total_requests ?? 0} req</span>
            </span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>

      <div style={rowStyle}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Foundation readiness</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/v1/status · service readiness</div>
        </div>
        {readiness
          ? <span className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
              <span className={`pill ${readiness.ready ? 'pill-ok' : 'pill-warn'}`} title="Overall readiness across checks">{readiness.ready ? 'ready' : 'not ready'}</span>
              {Object.entries(readiness.services || {}).map(([k, v]) => (
                <span key={k} className={`pill ${v ? 'pill-muted' : 'pill-warn'}`} title={`${k}: ${v ? 'ready' : 'not ready'}`}>{k}</span>
              ))}
            </span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>

      <div style={{ ...rowStyle, borderBottom: 'none' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Warehouse state</div>
          <div className="text-low" style={{ fontSize: 11 }}>GET /api/v1/status · live catalog</div>
        </div>
        {warehouse
          ? <span className="inline-flex" style={{ gap: 6 }}>
              <span className={`pill ${status && status.mode === 'live' ? 'pill-ok' : 'pill-muted'}`}>{status ? status.mode : 'UNKNOWN'}</span>
              <span className="pill pill-muted" title="Fresh live rows / total live rows / pulls">{warehouse.fresh_rows ?? 'UNKNOWN'} fresh · {warehouse.live_rows ?? 'UNKNOWN'} live · {warehouse.pulls ?? 0} pulls</span>
            </span>
          : <span className="pill pill-unknown">unavailable</span>}
      </div>

      <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Provenance rule">
        These are live backend reads. Sample-derived checks below are muted and labelled; adverse states keep their distinct colour.
      </div>
    </div>
  )
}

const TABS = [
  { id: 'alerts', label: 'Alerts', count: 3 },
  { id: 'health', label: 'Health' },
  { id: 'sync', label: 'Sync & Staleness' },
]

const SEV_PILL = { High: 'pill-error', Medium: 'pill-warn', Low: 'pill-muted' }

const ALERTS = [
  { id: 'MON-001', type: 'Data Freshness', message: 'Price data staleness exceeded threshold for 3 ASINs', severity: 'High', time: '2h ago', source: 'Shared Data Layer' },
  { id: 'MON-002', type: 'System', message: 'Provider Adapter 3 response time elevated', severity: 'Medium', time: '4h ago', source: 'Provider Adapters' },
  { id: 'MON-003', type: 'Business', message: 'Inventory for B08N5WRWNW below reorder point', severity: 'Medium', time: '1d ago', source: 'Commerce Ops' },
]

const SERVICES = [
  { svc: 'FastAPI backend', state: 'Unreachable', tone: 'pill-error', basis: 'Health probe (sample)', live: false },
  { svc: 'Provider Adapters', state: 'Rate limited', tone: 'pill-warn', basis: 'Adapter state (sample)', live: false },
  { svc: 'UI build', state: 'Healthy', tone: 'pill-muted', basis: 'Build check (sample)', live: false },
  { svc: 'Screenshot pipeline', state: 'Healthy', tone: 'pill-muted', basis: 'Pipeline check (sample)', live: false },
]

const DESTINATIONS = [
  { label: 'Shared Data Layer', route: '/shared-data', context: 'sources & freshness', match: 'Shared Data Layer' },
  { label: 'Provider Adapters', route: '/provider-adapters', context: 'runs & spend', match: 'Provider Adapters' },
  { label: 'Commerce Ops', route: '/commerce-ops', context: 'inventory & approvals', match: 'Commerce Ops' },
]

const STALENESS = [
  { src: 'Market Price Feed', last: '2h ago', state: 'Stale', tone: 'pill-ochre', owner: 'Shared Data Layer' },
  { src: 'Rank Tracker', last: '1h ago', state: 'Observed', tone: 'pill-muted', owner: 'Shared Data Layer' },
  { src: 'Buy Box Monitor', last: '6h ago', state: 'Stale', tone: 'pill-ochre', owner: 'Shared Data Layer' },
  { src: 'Review Aggregator', last: 'N/A', state: 'Unavailable', tone: 'pill-error', owner: 'Provider Adapters' },
]

export default function Monitoring() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'

  const staleCount = STALENESS.filter(s => s.state !== 'Observed').length

  return (
    <PageLayout
      title="Monitoring"
      subtitle="Observability watchtower — service health, alert stream, and sync/staleness summary. Source-level detail lives in Shared Data Layer and Provider Adapters."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Alert configuration: severities and channels (sample).', 'info')}>Configure Alerts</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/shared-data')}>Open Shared Data Layer</button>
      </>}
    >
      <DataNotice tone="internal" title="Observability summary — not source-of-truth">
        This room summarizes system and business monitoring. Source freshness detail lives in Shared Data Layer; adapter runs and spend live in Provider Adapters. Figures are sample until a monitoring backend is connected.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/monitoring" />

      {view === 'alerts' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Alerts</h3>
              <span className="pill pill-clay">{ALERTS.length} active · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'type', label: 'Type' },
              { key: 'message', label: 'Message' },
              { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${SEV_PILL[v]}`}>{v}</span> },
              { key: 'source', label: 'Detail Source', render: (v) => <span className="pill pill-muted" title="Where the source-level detail lives">{v}</span> },
              { key: 'time', label: 'Time', render: (v) => <span className="pill pill-muted" title="Relative time (sample)">{v}</span> },
            ]} rows={ALERTS} />
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Where to investigate</h3>
              <span className="pill pill-muted">routes to source-of-truth</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {DESTINATIONS.map(d => {
                const count = ALERTS.filter(a => a.source === d.match).length
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
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">System Health</h3>
              <span className="pill pill-muted">sample</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'System Health', v: '99.8%', note: 'Last 30 days · sample' },
                { label: 'Open Alerts', v: String(ALERTS.length), note: 'From alert stream', warn: true },
                { label: 'Data Staleness', v: '2h', note: 'Avg · from Shared Data Layer' },
                { label: 'Last Sync', v: '12m ago', note: 'Successful (sample)' },
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
              <span className="pill pill-muted">basis per row</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {SERVICES.map(s => (
                <div key={s.svc} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div style={{ fontSize: 13 }}>{s.svc}</div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="pill pill-muted" style={{ fontSize: 10 }} title="How this state is determined">{s.basis}</span>
                    <span className={`pill ${s.tone}`} title={s.live ? 'Live probe-backed check' : 'Sample-derived — not live-verified'}>{s.state}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Truth-state rule: green means live-verified only">
              Green is reserved for live probe-backed checks. Sample-derived checks are muted; adverse states keep their distinct colour.
            </div>
          </div>
        </div>
      )}

      {view === 'sync' && (
        <div className="subview">
          <div className="grid-3" style={{ gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Sources monitored</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{STALENESS.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Summary only</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Needs attention</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ochre)' }}>{staleCount}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Stale or unavailable</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Last Sync</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>12m</div>
              <div className="text-low" style={{ fontSize: 11 }}>Successful (sample)</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Staleness Summary</h3>
              <span className="pill pill-muted" title="High-level only — full freshness matrix lives in Shared Data Layer">summary · not full matrix</span>
            </div>
            <DataTable columns={[
              { key: 'src', label: 'Source' },
              { key: 'last', label: 'Last Update' },
              { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.tone}`} title={v === 'Stale' ? 'Exceeded freshness threshold — investigate' : v === 'Unavailable' ? 'No data — provider or source issue' : 'Within window (sample)'}>{v}</span> },
              { key: 'owner', label: 'Detail Source', render: (v) => <span className="pill pill-muted">{v}</span> },
            ]} rows={STALENESS} />
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
