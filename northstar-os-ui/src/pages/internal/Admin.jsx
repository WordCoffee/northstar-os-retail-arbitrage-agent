import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

// ═══ Live readiness / provider presence (real reads) ═══
function AdminLiveStatus() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [status, health] = await Promise.all([
        settle(signals.systemStatus()),
        settle(signals.detailedHealth()),
      ])
      if (alive) setSt({ phase: 'loaded', status, health })
    })()
    return () => { alive = false }
  }, [])
  const env = (r) => (r && r.ok ? (r.value && r.value.data ? r.value.data : r.value) : null)
  const status = env(st.status)
  const health = env(st.health)
  const anyOk = (st.status && st.status.ok) || (st.health && st.health.ok)
  const readiness = status && status.readiness ? status.readiness : null
  const warehouse = status && status.warehouse ? status.warehouse : null
  const providers = health && health.providers ? health.providers : {}
  const configured = Object.values(providers).filter(v => v === 'configured').length
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : anyOk ? { l: 'live · backend', t: 'muted' }
      : { l: 'unavailable', t: 'unknown' }
  return (
    <div className="card" data-testid="admin-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Live readiness</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Reading backend readiness…</p>}
      {!anyOk && st.phase === 'loaded' && <p style={{ fontSize: 13 }}>Backend readiness unavailable.</p>}
      {anyOk && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            {readiness && <span className={`pill ${readiness.ready ? 'pill-ok' : 'pill-warn'}`}>overall: {readiness.ready ? 'ready' : 'not ready'}</span>}
            {warehouse && <span className="pill pill-muted">warehouse: {status.mode} · {warehouse.fresh_rows ?? '?'} fresh / {warehouse.live_rows ?? '?'} live</span>}
            <span className="pill pill-muted" title="Provider keys present (names only)">{configured} provider key{configured === 1 ? '' : 's'} configured</span>
          </div>
          {readiness && readiness.services && Object.keys(readiness.services).length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
              {Object.entries(readiness.services).map(([svc, ready]) => (
                <span key={svc} className={`pill ${ready ? 'pill-muted' : 'pill-warn'}`} title={`${svc}: ${ready ? 'ready' : 'not ready'}`}>{svc}</span>
              ))}
            </div>
          )}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Live backend reads. Provider rows are presence-only; no credential values are shown.</div>
        </>
      )}
    </div>
  )
}

const SYSTEM_STATUS = [
  { label: 'Catalog Index', status: 'Healthy', tone: 'pill-muted', basis: 'Index build (internal)' },
  { label: 'Enrichment Pipeline', status: 'Active', tone: 'pill-muted', basis: 'Worker state (internal)' },
  { label: 'Auth Service', status: 'Active', tone: 'pill-muted', basis: 'Service state (internal)' },
  { label: 'Data Warehouse', status: 'Active', tone: 'pill-muted', basis: 'Storage state (internal)' },
  { label: 'Legacy Sync', status: 'Deprecated', tone: 'pill-muted', basis: 'Retired component' },
]

const CONFIG_ROWS = [
  { setting: 'UI Mode', value: 'Full', tone: 'pill-muted' },
  { setting: 'Environment', value: 'Production', tone: 'pill-muted' },
  { setting: 'Data Provider', value: 'Local (sample)', tone: 'pill-muted' },
  { setting: 'Live Calls', value: 'Disabled', tone: 'pill-muted' },
]

const CONTROLS = [
  { name: 'Live provider calls', state: 'Disabled', note: 'Requires an explicit, named operator approval.' },
  { name: 'Automated enrichment jobs', state: 'Disabled', note: 'Runs only via an approval-gated manifest.' },
  { name: 'Autonomous publishing', state: 'Disabled', note: 'Nothing publishes or lists without operator action.' },
  { name: 'Purchase authorization', state: 'Operator-only', note: 'Never granted by a system control.' },
]

export default function InternalAdmin() {
  return (
    <PageLayout title="Internal Administration" subtitle="System configuration, controls, and internal management. Operating queues live in Beta Operations.">
      <DataNotice tone="internal" title="Administration is internal configuration">
        “Live readiness” is a real backend read. The status/configuration values below are internal/observed configuration — not source-of-truth telemetry. No control here enables live provider calls, spend, or autonomous action.
      </DataNotice>

      <AdminLiveStatus />

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">System Status</h3>
            <span className="pill pill-muted">internal · sample (see Live readiness)</span>
          </div>
          <div className="stack" style={{ gap: 8 }}>
            {SYSTEM_STATUS.map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: i < SYSTEM_STATUS.length - 1 ? '1px solid var(--divider)' : 'none' }}>
                <span style={{ flex: 1, fontSize: 13 }}>{item.label}</span>
                <span className="pill pill-muted" style={{ fontSize: 10 }} title="How this state is determined">{item.basis}</span>
                <span className={`pill ${item.tone}`} title="Internal configuration state — not live-verified">{item.status}</span>
              </div>
            ))}
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>
            Green is reserved for live probe-backed checks. Internal configuration states are muted.
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Configuration</h3>
            <span className="pill pill-muted">sample</span>
          </div>
          <DataTable columns={[
            { key: 'setting', label: 'Setting' },
            { key: 'value', label: 'Value', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
          ]} rows={CONFIG_ROWS} />
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Controls</h3>
          <span className="pill pill-clay">safety gates — all off</span>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {CONTROLS.map((c, i) => (
            <div key={c.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderBottom: i < CONTROLS.length - 1 ? '1px solid var(--divider)' : 'none' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</div>
                <div className="text-low" style={{ fontSize: 11 }}>{c.note}</div>
              </div>
              <span className={`pill ${c.state === 'Disabled' ? 'pill-muted' : 'pill-ochre'}`}>{c.state}</span>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  )
}
