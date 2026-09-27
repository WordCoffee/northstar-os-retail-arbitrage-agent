import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'

const TABS = [
  { id: 'alerts', label: 'Alerts', count: 5 },
  { id: 'tracked', label: 'Tracked Entities', count: 24 },
  { id: 'rules', label: 'Guardian Rules' },
]

const ALERTS = [
  { id: 'AL-001', asin: 'B08L5VJQ7T', type: 'Content Change', severity: 'High', date: '2026-09-26', status: 'Review', tone: 'pill-clay' },
  { id: 'AL-002', asin: 'B09M8KJ4X2', type: 'Rank Drop', severity: 'Medium', date: '2026-09-25', status: 'Monitoring', tone: 'pill-ochre' },
  { id: 'AL-003', asin: 'B08N5WRWNW', type: 'Price Change', severity: 'Low', date: '2026-09-24', status: 'Resolved', tone: 'pill-forest' },
  { id: 'AL-004', asin: 'B07XJ8C9F3', type: 'New Competitor', severity: 'High', date: '2026-09-23', status: 'Review', tone: 'pill-clay' },
  { id: 'AL-005', asin: 'B08L5VJQ7T', type: 'Listing Health', severity: 'Medium', date: '2026-09-22', status: 'Monitoring', tone: 'pill-ochre' },
]

const TRACKED = [
  { asin: 'B08L5VJQ7T', title: 'Premium Water Filter', rank: '#14,203', change: '↓ 234', status: 'Monitoring', tone: 'pill-ochre' },
  { asin: 'B09M8KJ4X2', title: 'LED Desk Lamp', rank: '#8,721', change: '↑ 12', status: 'Healthy', tone: 'pill-forest' },
  { asin: 'B07XJ8C9F3', title: 'Car Phone Mount', rank: '#23,450', change: '↓ 890', status: 'At Risk', tone: 'pill-clay' },
  { asin: 'B08N5WRWNW', title: 'Bluetooth Speaker', rank: '#5,632', change: '↑ 45', status: 'Healthy', tone: 'pill-forest' },
]

export default function ListingGuardian() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'

  return (
    <PageLayout
      title="Listing Guardian"
      subtitle="Alert and monitoring surface — content changes, rank drops, price shifts, and the rules that watch them."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/listings?view=rules')}>New Rule</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('History view is sample data — full log pending backend.', 'info')}>History</button>
      </>}
    >
      <DataNotice tone="sample" title="Guardian records are sample data">
        Alerts, ranks, and tracked entities are demonstration records until a connected Listing Guardian backend exists. Rank movement should be treated as an indication, not verified fact.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/listings" />

      {view === 'alerts' && (
        <div className="subview">
          <MetricTiles metrics={[
            { label: 'Open Alerts', value: '5', sub: '2 high priority', tone: 'warn' },
            { label: 'Content Violations', value: '1', sub: 'Under review' },
            { label: 'Rank Drops', value: '2', sub: 'Last 7 days' },
          ]} columns={3} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Alert Feed</h3>
              <span className="pill pill-clay">5 active</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'asin', label: 'ASIN' },
              { key: 'type', label: 'Alert Type' },
              { key: 'severity', label: 'Severity' },
              { key: 'date', label: 'Date' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
            ]} rows={ALERTS} />
          </div>
        </div>
      )}

      {view === 'tracked' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Tracked Entities</h3>
              <span className="pill pill-forest">24 monitored</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Product' },
              { key: 'rank', label: 'Current Rank' },
              { key: 'change', label: 'Rank Change' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
            ]} rows={TRACKED} />
          </div>
        </div>
      )}

      {view === 'rules' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Rules are not yet enforced">
            No Guardian rule can take automated action on a listing. Rules below are proposed guardrails awaiting operator confirmation.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Guardian Rules</h3>
              <span className="pill pill-muted">Proposed</span>
            </div>
            {[
              { rule: 'Alert on rank drop below #20,000', trigger: 'Observed rank shift', state: 'Proposed' },
              { rule: 'Flag content change with no history entry', trigger: 'Content diff', state: 'Proposed' },
              { rule: 'Monitor price change over 10% in 24h', trigger: 'Price observation', state: 'Proposed' },
              { rule: 'Escalate listing health below threshold', trigger: 'Health score', state: 'Proposed' },
            ].map(r => (
              <div key={r.rule} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{r.rule}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{r.trigger}</div>
                </div>
                <span className="pill pill-muted">{r.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  )
}