import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'alerts', label: 'Alerts', count: 3 },
  { id: 'health', label: 'Health' },
  { id: 'sync', label: 'Sync' },
]

export default function Monitoring() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'

  return (
    <PageLayout
      title="Monitoring"
      subtitle="System and business monitoring — alerts, health, data freshness, and sync state."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Configure Alerts — choose severities and channels.', 'info')}>Configure Alerts</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('History — past alerts and resolutions.', 'info')}>History</button>
      </>}
    >
      <DataNotice tone="sample" title="Monitoring records are sample data">
        Alert counts, health figures, and sync times are demonstration records until a monitoring backend is connected.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/monitoring" />

      {view === 'alerts' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Alerts</h3>
              <span className="pill pill-clay">3 active</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'type', label: 'Type' },
              { key: 'message', label: 'Message' },
              { key: 'severity', label: 'Severity' },
              { key: 'time', label: 'Time' },
            ]} rows={[
              { id: 'MON-001', type: 'Data Freshness', message: 'Price data staleness exceeded threshold for 3 ASINs', severity: 'High', time: '2h ago' },
              { id: 'MON-002', type: 'System', message: 'Provider Adapter 3 response time elevated', severity: 'Medium', time: '4h ago' },
              { id: 'MON-003', type: 'Business', message: 'Inventory for B08N5WRWNW below reorder point', severity: 'Medium', time: '1d ago' },
            ]} />
          </div>
        </div>
      )}

      {view === 'health' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">System Health</h3>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'System Health', v: '99.8%', note: 'Last 30 days' },
                { label: 'Open Alerts', v: '3', note: '2 high priority', warn: true },
                { label: 'Data Staleness', v: '2h', note: 'Avg' },
                { label: 'Last Sync', v: '12m ago', note: 'Successful' },
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
            </div>
            {[
              { svc: 'FastAPI backend', state: 'Unreachable', tone: 'pill-error' },
              { svc: 'Provider Adapters', state: 'Rate limited', tone: 'pill-warn' },
              { svc: 'UI build', state: 'Healthy', tone: 'pill-forest' },
              { svc: 'Screenshot pipeline', state: 'Healthy', tone: 'pill-forest' },
            ].map(s => (
              <div key={s.svc} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 13 }}>{s.svc}</div>
                <span className={`pill ${s.tone}`}>{s.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'sync' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Data Freshness by Source</h3>
            </div>
            {[
              { src: 'Market Price Feed', last: '2h ago', state: 'Cached', tone: 'pill-forest' },
              { src: 'Rank Tracker', last: '1h ago', state: 'Observed', tone: 'pill-forest' },
              { src: 'Buy Box Monitor', last: '6h ago', state: 'Stale', tone: 'pill-warn' },
              { src: 'Review Aggregator', last: 'N/A', state: 'Unavailable', tone: 'pill-error' },
            ].map(d => (
              <div key={d.src} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{d.src}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.last}</div>
                </div>
                <span className={`pill ${d.tone}`}>{d.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  )
}