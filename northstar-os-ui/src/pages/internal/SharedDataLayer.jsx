import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'sources', label: 'Sources', count: 6 },
  { id: 'readiness', label: 'Readiness' },
  { id: 'provenance', label: 'Provenance' },
]

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
      <DataNotice tone="internal" title="Readiness states are explicit, not assumed">
        Every dataset carries a truth state: OBSERVED, CACHED, HISTORICAL, UNVERIFIED, or UNAVAILABLE. No dataset is treated as verified unless proven.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/shared-data" />

      {view === 'sources' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Source Readiness</h3>
              <span className="pill pill-muted">v2.1 schema</span>
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