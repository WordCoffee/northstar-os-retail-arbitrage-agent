import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'adapters', label: 'Adapters', count: 4 },
  { id: 'health', label: 'Health' },
  { id: 'config', label: 'Configuration' },
]

export default function ProviderAdapters() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'adapters'

  return (
    <PageLayout
      title="Provider Adapters"
      subtitle="Data provider status — adapter health, rate limits, freshness, and controlled provider state."
      actions={<>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Adapter Log — full call history per adapter.', 'info')}>Adapter Log</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Configuration view opened.', 'info')}>Configuration</button>
      </>}
    >
      <DataNotice tone="internal" title="Controlled provider state">
        Adapters operate under rate limits and controlled state. Live provider calls are NOT made during normal browsing. Data is cached, observed, or historical.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/provider-adapters" />

      {view === 'adapters' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Adapter Status</h3>
              <span className="pill pill-muted">4 adapters</span>
            </div>
            <DataTable columns={[
              { key: 'adapter', label: 'Adapter' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Active' ? 'pill-muted' : v === 'Rate Limited' ? 'pill-warn' : 'pill-muted'}`} title="Sample/observed adapter state — not a live probe">{v}</span> },
              { key: 'latency', label: 'Latency' },
              { key: 'data', label: 'Data State' },
              { key: 'calls', label: 'Calls (24h)' },
            ]} rows={[
              { adapter: 'Market Price Feed', status: 'Active', latency: '420ms', data: 'Cached', calls: '1,240' },
              { adapter: 'Rank Tracker', status: 'Active', latency: '180ms', data: 'Observed', calls: '890' },
              { adapter: 'Buy Box Monitor', status: 'Rate Limited', latency: '—', data: 'Stale', calls: '3,200' },
              { adapter: 'Review Aggregator', status: 'Idle', latency: '—', data: 'Unavailable', calls: '0' },
            ]} />
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Truth-state rule: green means live-verified only">
              Adapter states here are sample/observed. Green is reserved for genuinely probe-backed, live-verified outcomes; adverse states keep their distinct colour.
            </div>
          </div>
        </div>
      )}

      {view === 'health' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Health &amp; Rate Limits</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              {[
                { label: 'Rate Limit Usage', v: '72%', note: 'Of quota used', warn: true },
                { label: 'Data Freshness', v: '2h', note: 'Avg staleness' },
                { label: 'Data Quality', v: 'Good', note: 'Adapters healthy' },
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
              <h3 className="card-title">Watch Items</h3>
            </div>
            {[
              { item: 'Buy Box Monitor near quota — expect staleness', state: 'Watch', tone: 'pill-warn' },
              { item: 'Review Aggregator idle — no provider key bound', state: 'Idle', tone: 'pill-muted' },
            ].map(w => (
              <div key={w.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 13 }}>{w.item}</div>
                <span className={`pill ${w.tone}`}>{w.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'config' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Adapter Configuration</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Market Price Feed — refresh cadence 2h</div>
                <span className="pill pill-muted">Configured</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Rank Tracker — refresh cadence 1h</div>
                <span className="pill pill-muted">Configured</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Buy Box Monitor — rate limit tripped</div>
                <span className="pill pill-warn">Cooldown</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Review Aggregator — no key bound</div>
                <span className="pill pill-muted">Unbound</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}