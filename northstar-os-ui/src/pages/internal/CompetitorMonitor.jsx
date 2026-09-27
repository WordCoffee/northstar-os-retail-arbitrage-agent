import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'landscape', label: 'Landscape', count: 8 },
  { id: 'changes', label: 'Price Changes', count: 14 },
  { id: 'watchlist', label: 'Watchlist', count: 2 },
]

export default function CompetitorMonitor() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'landscape'

  return (
    <PageLayout
      title="Competitor Monitor"
      subtitle="Competitive context — tracked brands, price and rank movement, and new entrants."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Add Competitor — track a brand or ASIN.', 'info')}>Add Competitor</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Market Report export is sample data.', 'info')}>Market Report</button>
      </>}
    >
      <DataNotice tone="sample" title="Competitive data is observed or sample">
        Brand, price, and rank records are demonstration data until provider observations are connected. Watchlist entries are indications, not verified market positions.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/competitor-monitor" />

      {view === 'landscape' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Competitive Landscape</h3>
              <span className="pill pill-forest">8 tracked</span>
            </div>
            <DataTable columns={[
              { key: 'brand', label: 'Brand' },
              { key: 'asin', label: 'ASIN' },
              { key: 'price', label: 'Price' },
              { key: 'rank', label: 'Rank' },
              { key: 'change', label: 'Rank Change' },
              { key: 'status', label: 'Status', render: (v) => <span className="pill pill-muted">{v}</span> },
            ]} rows={[
              { brand: 'PureFlow', asin: 'B08L5VJQ7T', price: '$49.99', rank: '#14,203', change: '↓ 234', status: 'Monitoring' },
              { brand: 'CleanMax', asin: 'B09ABC123', price: '$39.99', rank: '#8,450', change: '↑ 45', status: 'Competitive' },
              { brand: 'AquaPure', asin: 'B09DEF456', price: '$54.99', rank: '#12,890', change: '↓ 89', status: 'Watch' },
              { brand: 'HydroFresh', asin: 'B09GHI789', price: '$42.99', rank: '#15,300', change: '↑ 12', status: 'Watch' },
            ]} />
          </div>
        </div>
      )}

      {view === 'changes' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Recent Price &amp; Rank Movement</h3>
              <span className="pill pill-ochre">14 in 7 days</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>CleanMax reduced price by 8% — B09ABC123</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-26</div>
                </div>
                <span className="pill pill-warn">Price Alert</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>AquaPure launched 12-pack variation — B09DEF456</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-24</div>
                </div>
                <span className="pill pill-ochre">New Listing</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>PureFlow rank drop below #14,000 — B08L5VJQ7T</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-23</div>
                </div>
                <span className="pill pill-clay">Rank Drop</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'watchlist' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">New Entrants &amp; Watchlist</h3>
              <span className="pill pill-clay">2 watch</span>
            </div>
            {[
              { name: 'HydroFresh', note: 'New entrant entering category — monitor pricing strategy', state: 'Watch' },
              { name: 'AquaPure 12-pack', note: 'Variation launch — watch conversion impact', state: 'Watch' },
            ].map(c => (
              <div key={c.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{c.note}</div>
                </div>
                <span className="pill pill-ochre">{c.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  )
}