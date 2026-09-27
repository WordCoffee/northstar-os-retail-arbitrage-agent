import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'

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
        These controls configure the platform. Status values are internal/observed configuration — not a live health probe and not source-of-truth telemetry. No control here enables live provider calls, spend, or autonomous action.
      </DataNotice>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">System Status</h3>
            <span className="pill pill-muted">internal · sample</span>
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
