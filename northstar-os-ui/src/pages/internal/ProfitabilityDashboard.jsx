import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'set', label: 'Set Detail' },
  { id: 'scenario', label: 'Scenario Calculator' },
  { id: 'cash', label: 'Cash Cycle' },
]

export default function ProfitabilityDashboard() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'

  const exportReport = () => toast('Export prepared from observed data — review before distribution.', 'info')

  return (
    <PageLayout
      title="Profitability Dashboard"
      subtitle="Portfolio decision room — contribution, cash cycle, inventory, margin, and risk context."
      actions={<>
        <button className="btn btn-sm" onClick={exportReport}>Export Report</button>
        <button className="btn btn-sm btn-ghost">Refresh Data</button>
      </>}
    >
      <DataNotice tone="assumption" title="Margin and fee context is assumed, not verified">
        Set B margins show UNKNOWN — fee basis is assumed, not verified. Restock recommendations should account for this uncertainty. No figures imply purchase authorization.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/profitability" />

      {view === 'overview' && (
        <div className="subview">
          <MetricTiles metrics={[
            { label: 'Net Contribution', value: '$4.2K', sub: 'This month', tone: 'warn' },
            { label: 'Cash Cycle', value: '42d', sub: 'Inventory to cash' },
            { label: 'Avg Margin', value: '~18%', sub: 'Observed' },
            { label: 'Aged Stock', value: '$1.1K', sub: '90+ days', tone: 'warn' },
          ]} columns={4} />

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Portfolio Contribution</h3>
                <span className="pill pill-forest">3 sets active</span>
              </div>
              <DataTable columns={[
                { key: 'set', label: 'Set' },
                { key: 'revenue', label: 'Revenue' },
                { key: 'contribution', label: 'Contribution' },
                { key: 'margin', label: 'Margin' },
                { key: 'concentration', label: 'Concentration' },
              ]} rows={[
                { set: 'Set A', revenue: '$12.4K', contribution: '$2.8K', margin: '~22%', concentration: '45%' },
                { set: 'Set B', revenue: '$8.1K', contribution: '$1.4K', margin: 'UNKNOWN', concentration: '30%' },
                { set: 'Set C', revenue: '$5.2K', contribution: '$0.8K', margin: '~15%', concentration: '25%' },
              ]} />
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Inventory Exposure</h3>
                <span className="pill pill-warn">1.1K aged</span>
              </div>
              <Table rows={[
                { label: 'Total Inventory Value', value: '$6.8K', tone: 'normal' },
                { label: 'Aged Stock (90+ days)', value: '$1.1K', tone: 'warn' },
                { label: 'Restock Recommended', value: '$2.4K', tone: 'normal' },
                { label: 'Cash-Cycle Velocity', value: '42 days', tone: 'normal' },
                { label: 'Max Concentration Risk', value: '45% (Set A)', tone: 'warn' },
              ]} />
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Margin &amp; Fee Context</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Observed Margin</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine)' }}>~18%</div>
                <div className="text-low" style={{ fontSize: 11 }}>Historical: Q3 2026</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Fee Basis</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--ochre)' }}>ASSUMPTION</div>
                <div className="text-low" style={{ fontSize: 11 }}>Based on category average</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Risk Context</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--clay)' }}>ELEVATED</div>
                <div className="text-low" style={{ fontSize: 11 }}>Concentration in Set A</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'set' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Set B economics are incomplete">
            Margin is UNKNOWN because fee basis is assumed and cost data is missing. Sets below are sample demonstration records.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Set-Level Detail</h3>
              <span className="pill pill-muted">3 sets</span>
            </div>
            <DataTable columns={[
              { key: 'set', label: 'Set' },
              { key: 'asins', label: 'ASINs' },
              { key: 'revenue', label: 'Revenue' },
              { key: 'contribution', label: 'Contribution' },
              { key: 'margin', label: 'Margin' },
              { key: 'concentration', label: 'Concentration' },
              { key: 'feeBasis', label: 'Fee Basis' },
            ]} rows={[
              { set: 'Set A', asins: 12, revenue: '$12.4K', contribution: '$2.8K', margin: '~22%', concentration: '45%', feeBasis: 'Observed' },
              { set: 'Set B', asins: 8, revenue: '$8.1K', contribution: '$1.4K', margin: 'UNKNOWN', concentration: '30%', feeBasis: 'ASSUMPTION' },
              { set: 'Set C', asins: 15, revenue: '$5.2K', contribution: '$0.8K', margin: '~15%', concentration: '25%', feeBasis: 'Observed' },
            ]} />
          </div>
        </div>
      )}

      {view === 'scenario' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Scenario calculator requires verified inputs">
            No calculated profit authorizes a purchase. Enter verified cost/fee basis to enable a scenario. Outputs below use sample inputs.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Scenario Calculator — B08L5VJQ7T</h3>
            </div>
            <div className="grid-4" style={{ gap: 12 }}>
              {[
                { label: 'Source Cost', v: 'UNKNOWN', tone: 'var(--clay)' },
                { label: 'Fulfillment Basis', v: 'UNAVAILABLE', tone: 'var(--clay)' },
                { label: 'Fee Basis', v: 'UNAVAILABLE', tone: 'var(--clay)' },
                { label: 'Est. Profit', v: 'NOT CALCULATED', tone: 'var(--clay)' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: d.tone }}>{d.v}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16 }}>
              <button className="btn btn-sm" onClick={() => toast('Scenario blocked — verified cost basis required.', 'error')}>Calculate Scenario</button>
            </div>
          </div>
        </div>
      )}

      {view === 'cash' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Restock &amp; Aged-Stock Considerations</h3>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'stock', label: 'Units' },
              { key: 'days', label: 'Days in Stock' },
              { key: 'action', label: 'Recommended Action' },
            ]} rows={[
              { asin: 'B08L5VJQ7T', stock: 45, days: 28, action: 'Monitor' },
              { asin: 'B09M8KJ4X2', stock: 12, days: 65, action: 'Restock' },
              { asin: 'B08N5WRWNW', stock: 80, days: 110, action: 'Discount / Clear' },
              { asin: 'B07XJ8C9F3', stock: 5, days: 42, action: 'Urgent Restock' },
            ]} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Cash Cycle Snapshot</h3>
            </div>
            <DataTable columns={[
              { key: 'stage', label: 'Stage' },
              { key: 'value', label: 'Value' },
              { key: 'days', label: 'Days' },
              { key: 'state', label: 'State' },
            ]} rows={[
              { stage: 'Inventory', value: '$6.8K', days: '42 avg', state: 'In stock' },
              { stage: 'Receivables', value: '$2.1K', days: '—', state: 'Observed' },
              { stage: 'Aged Stock', value: '$1.1K', days: '90+', state: 'At risk' },
              { stage: 'Cash Reserve', value: '$4.0K', days: '—', state: 'Assumption' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}

function Table({ rows }) {
  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: i < rows.length - 1 ? '1px solid var(--divider)' : 'none' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-mid)' }}>{r.label}</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: r.tone === 'warn' ? 'var(--ochre)' : 'var(--pine-deep)' }}>{r.value}</div>
        </div>
      ))}
    </div>
  )
}