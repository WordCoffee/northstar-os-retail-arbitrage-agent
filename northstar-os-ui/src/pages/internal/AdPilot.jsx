import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useNavigate, useLocation } from 'react-router-dom'

const TABS = [
  { id: 'campaigns', label: 'Campaigns', count: 8 },
  { id: 'detail', label: 'Campaign Detail' },
  { id: 'planner', label: 'Planner' },
]

const CAMPAIGNS = [
  { name: 'Brand Defense', budget: '$500', spend: '$420', acos: '12.3%', placement: '#2', status: 'Healthy' },
  { name: 'Product Launch — Water Filter', budget: '$800', spend: '$760', acos: '24.1%', placement: '#5', status: 'Review' },
  { name: 'Keyword Harvest', budget: '$400', spend: '$310', acos: '16.8%', placement: '#3', status: 'Healthy' },
  { name: 'Competitor Conquest', budget: '$600', spend: '$590', acos: '31.2%', placement: '#8', status: 'Critical' },
  { name: 'Sponsored Brands', budget: '$300', spend: '$250', acos: '14.5%', placement: '#1', status: 'Healthy' },
]

export default function AdPilot() {
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'campaigns'

  return (
    <PageLayout
      title="AdPilot"
      subtitle="Advertising operations workbench — campaign health, budget, placements, performance."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=planner')}>Create Campaign</button>
        <button className="btn btn-sm btn-ghost">Bulk Actions</button>
      </>}
    >
      <DataNotice tone="sample" title="All performance data is sample/observed data">
        Do not use for purchase authorization or budget spend decisions. Actual costs and conversions require verified tracking.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/adpilot" />

      {view === 'campaigns' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Campaign Health</h3>
              <span className="pill pill-forest">6 of 8 healthy</span>
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Campaign' },
              { key: 'budget', label: 'Budget' },
              { key: 'spend', label: 'Spend' },
              { key: 'acos', label: 'ACoS' },
              { key: 'placement', label: 'Top Placement' },
              { key: 'status', label: 'Status' },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=detail')}>Open</button> },
            ]} rows={CAMPAIGNS} />
          </div>
        </div>
      )}

      {view === 'detail' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Product Launch — Water Filter</h3>
              <span className="pill pill-warn">Review</span>
            </div>
            <div className="grid-4" style={{ gap: 12 }}>
              {[
                { label: 'Budget', v: '$800' },
                { label: 'Spend', v: '$760' },
                { label: 'ACoS', v: '24.1%' },
                { label: 'Top Placement', v: '#5' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine-deep)' }}>{d.v}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Search Term Performance</h3>
              <span className="pill pill-muted">Top 5 terms</span>
            </div>
            <DataTable columns={[
              { key: 'term', label: 'Search Term' },
              { key: 'impressions', label: 'Impressions' },
              { key: 'clicks', label: 'Clicks' },
              { key: 'ctr', label: 'CTR' },
              { key: 'acos', label: 'ACoS' },
            ]} rows={[
              { term: 'water filter', impressions: 24500, clicks: 1820, ctr: '7.4%', acos: '11.2%' },
              { term: 'water purifier', impressions: 18200, clicks: 1340, ctr: '7.4%', acos: '19.8%' },
              { term: 'countertop filter', impressions: 12100, clicks: 890, ctr: '7.4%', acos: '14.1%' },
              { term: 'BPA free filter', impressions: 9800, clicks: 720, ctr: '7.3%', acos: '22.3%' },
              { term: 'family water filter', impressions: 7600, clicks: 540, ctr: '7.1%', acos: '28.5%' },
            ]} />
          </div>
        </div>
      )}

      {view === 'planner' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Planner uses assumed conversion and cost basis">
            Bid and budget recommendations are assumptions for planning only. They do not authorize spend. Verify against connected tracking before action.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Bid Recommendations</h3>
              <span className="pill pill-ochre">2 recommendations</span>
            </div>
            <div className="stack" style={{ gap: 10 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div><div style={{ fontSize: 13, fontWeight: 500 }}>Increase bid: "water filter"</div><div className="text-low" style={{ fontSize: 11 }}>Top 3 position achievable (+$0.15)</div></div>
                <span className="pill pill-forest">High Priority</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div><div style={{ fontSize: 13, fontWeight: 500 }}>Reduce bid: "family water filter"</div><div className="text-low" style={{ fontSize: 11 }}>ACoS exceeds target by 10pp (-$0.20)</div></div>
                <span className="pill pill-warn">Medium Priority</span>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Proposed Allocation — Next Cycle</h3>
            </div>
            <DataTable columns={[
              { key: 'campaign', label: 'Campaign' },
              { key: 'current', label: 'Current Budget' },
              { key: 'proposed', label: 'Proposed' },
              { key: 'delta', label: 'Delta' },
              { key: 'basis', label: 'Basis' },
            ]} rows={[
              { campaign: 'Brand Defense', current: '$500', proposed: '$500', delta: '—', basis: 'Observed' },
              { campaign: 'Product Launch', current: '$800', proposed: '$950', delta: '+$150', basis: 'Assumption' },
              { campaign: 'Competitor Conquest', current: '$600', proposed: '$450', delta: '-$150', basis: 'Assumption' },
              { campaign: 'Sponsored Brands', current: '$300', proposed: '$300', delta: '—', basis: 'Observed' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}