import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'

// Read-only view of a local cross-room store (handoffs recorded by Creative
// Studio). Never writes; never implies a live/paid ad system.
function readLocal(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

const CAMPAIGNS = [
  { name: 'Brand Defense', budget: '$500', spend: '$420', acos: '12.3%', placement: '#2', status: 'Healthy' },
  { name: 'Product Launch — Water Filter', budget: '$800', spend: '$760', acos: '24.1%', placement: '#5', status: 'Review' },
  { name: 'Keyword Harvest', budget: '$400', spend: '$310', acos: '16.8%', placement: '#3', status: 'Healthy' },
  { name: 'Competitor Conquest', budget: '$600', spend: '$590', acos: '31.2%', placement: '#8', status: 'Critical' },
  { name: 'Sponsored Brands', budget: '$300', spend: '$250', acos: '14.5%', placement: '#1', status: 'Healthy' },
]

const TABS = [
  { id: 'campaigns', label: 'Campaigns', count: CAMPAIGNS.length },
  { id: 'detail', label: 'Campaign Detail' },
  { id: 'terms', label: 'Search Terms' },
  { id: 'planner', label: 'Planner' },
  { id: 'placements', label: 'Placements' },
  { id: 'rules', label: 'Rules' },
]

const STATUS_PILL = { Healthy: 'pill-muted', Review: 'pill-ochre', Critical: 'pill-clay' }

function healthRollup() {
  const c = { Healthy: 0, Review: 0, Critical: 0 }
  CAMPAIGNS.forEach(x => { c[x.status] = (c[x.status] || 0) + 1 })
  return `${c.Healthy} healthy · ${c.Review} review · ${c.Critical} critical`
}

export default function AdPilot() {
  const navigate = useNavigate()
  const location = useLocation()
  const { toast } = useToast()
  // Read-only: creative sets handed over from Creative Studio (local handoffs).
  const [receivedCreative] = useState(() => readLocal('ns-creative-handoffs', []).filter(h => h && h.target === 'AdPilot'))

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'campaigns'

  return (
    <PageLayout
      title="AdPilot"
      subtitle="Advertising operations workbench — campaign health, budget, placements, performance."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=planner')}>Open Planner</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Bulk actions require operator approval and verified tracking — not available against this sample data.', 'info')}>Bulk Actions</button>
      </>}
    >
      <DataNotice tone="sample" title="All performance data is sample/observed data">
        Do not use for purchase authorization or budget spend decisions. Actual costs and conversions require verified
        tracking. Status and suggestion colors are muted because none of this is live-verified — green is reserved for
        live-verified checks.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/adpilot" />

      {view === 'campaigns' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Campaign Health</h3>
              <span className="pill pill-muted" title="Rollup computed from the sample rows below — not live campaign data">{healthRollup()}</span>
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Campaign' },
              { key: 'budget', label: 'Budget' },
              { key: 'spend', label: 'Spend' },
              { key: 'acos', label: 'ACoS' },
              { key: 'placement', label: 'Top Placement' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${STATUS_PILL[v] || 'pill-muted'}`}>{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=detail')}>Open</button> },
            ]} rows={CAMPAIGNS} />
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Budget Watch</h3>
              <span className="pill pill-muted">Basis: sample campaign data</span>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              {[
                { campaign: 'Competitor Conquest', pace: '98% of budget', note: 'Spend pacing ahead of cycle — review before renewal', tone: 'var(--clay)', meter: 'meter-fill-ochre', w: 98 },
                { campaign: 'Product Launch — Water Filter', pace: '95% of budget', note: 'High spend with ACoS above target', tone: 'var(--ochre)', meter: 'meter-fill-ochre', w: 95 },
                { campaign: 'Brand Defense', pace: '84% of budget', note: 'Pacing within expected range', tone: 'var(--ink-mid)', meter: 'meter-fill-muted', w: 84 },
              ].map(b => (
                <div key={b.campaign}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{b.campaign}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: b.tone, marginTop: 2 }}>{b.pace}</div>
                  <div className="meter" style={{ marginTop: 4 }}><div className={`meter-fill ${b.meter}`} style={{ width: `${b.w}%` }}></div></div>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 4 }} title="Sample pacing estimate — not live spend data">{b.note}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Creative handoffs received</h3>
              <span className="pill pill-muted">local reference · read-only</span>
            </div>
            {receivedCreative.length === 0 ? (
              <div className="text-low" style={{ fontSize: 12 }}>
                No creative sets handed over yet. Sending an ad set from Creative Studio records a local reference here —
                nothing is transferred, and no ad account is connected.
              </div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {receivedCreative.map(h => (
                  <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 12 }}>{h.what}</div>
                      <div className="text-low" style={{ fontSize: 10, marginTop: 2 }}>{h.id} · {(h.refs || []).length} refs{(h.refs || []).length ? `: ${h.refs.slice(0, 6).join(', ')}${h.refs.length > 6 ? '…' : ''}` : ''}</div>
                    </div>
                    <span className="text-low" style={{ fontSize: 11, flexShrink: 0 }}>{h.at ? new Date(h.at).toLocaleString() : ''}</span>
                  </div>
                ))}
              </div>
            )}
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
                  <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Sample campaign data — not verified tracking">Basis: sample data</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Search Term Performance</h3>
              <span className="pill pill-muted" title="Sample performance window — not verified tracking">Top 5 terms · sample</span>
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
                <div className="inline-flex" style={{ gap: 6 }}>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Modeled suggestion — not verified tracking">assumption</span>
                  <span className="pill pill-muted" title="Priority is a modeled suggestion on sample data — not verified tracking">High Priority</span>
                </div>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div><div style={{ fontSize: 13, fontWeight: 500 }}>Reduce bid: "family water filter"</div><div className="text-low" style={{ fontSize: 11 }}>ACoS exceeds target by 10pp (-$0.20)</div></div>
                <div className="inline-flex" style={{ gap: 6 }}>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Modeled suggestion — not verified tracking">assumption</span>
                  <span className="pill pill-warn">Medium Priority</span>
                </div>
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
              { key: 'basis', label: 'Basis', render: (v) => v === 'Assumption'
                ? <span className="pill pill-unverified" title="Modeled value — planning only, does not authorize spend">{v}</span>
                : <span className="pill pill-muted" title="Observed in the sample window — not verified tracking">{v}</span> },
            ]} rows={[
              { campaign: 'Brand Defense', current: '$500', proposed: '$500', delta: '—', basis: 'Observed' },
              { campaign: 'Product Launch', current: '$800', proposed: '$950', delta: '+$150', basis: 'Assumption' },
              { campaign: 'Competitor Conquest', current: '$600', proposed: '$450', delta: '-$150', basis: 'Assumption' },
              { campaign: 'Sponsored Brands', current: '$300', proposed: '$300', delta: '—', basis: 'Observed' },
            ]} />
          </div>
        </div>
      )}

      {view === 'terms' && (
        <div className="subview">
          <DataNotice tone="sample" title="Search-term analytics are sample data">
            Harvest and negative suggestions are planning aids only. No campaign changes are made automatically — apply actions require operator approval.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Term Analysis — Product Launch</h3>
              <span className="pill pill-muted" title="Sample performance window — not verified tracking">Sample window</span>
            </div>
            <DataTable columns={[
              { key: 'term', label: 'Search Term' },
              { key: 'impressions', label: 'Impr.' },
              { key: 'clicks', label: 'Clicks' },
              { key: 'spend', label: 'Spend' },
              { key: 'acos', label: 'ACoS' },
              { key: 'suggestion', label: 'Suggestion', render: (v) => <span className={`pill ${v === 'Add Negative' ? 'pill-ochre' : v === 'Harvest' ? 'pill-muted' : 'pill-warn'}`} title="Planning aid on sample data — not verified tracking">{v}</span> },
            ]} rows={[
              { term: 'water filter', impressions: 24500, clicks: 1820, spend: '$54.10', acos: '11.2%', suggestion: 'Harvest' },
              { term: 'water purifier', impressions: 18200, clicks: 1340, spend: '$68.70', acos: '19.8%', suggestion: 'Monitor' },
              { term: 'countertop filter', impressions: 12100, clicks: 890, spend: '$32.40', acos: '14.1%', suggestion: 'Harvest' },
              { term: 'BPA free filter', impressions: 9800, clicks: 720, spend: '$41.80', acos: '22.3%', suggestion: 'Add Negative' },
              { term: 'family water filter', impressions: 7600, clicks: 540, spend: '$39.90', acos: '28.5%', suggestion: 'Reduce Bid' },
            ]} />
          </div>
        </div>
      )}

      {view === 'placements' && (
        <div className="subview">
          <DataNotice tone="cached" title="Placement insights are cached sample snapshots">
            Placement data reflects a stored sample window, not live ad-platform reporting.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Placement Insights — Product Launch</h3>
              <span className="pill pill-muted" title="Cached snapshot — not live data">Cached snapshot</span>
            </div>
            <DataTable columns={[
              { key: 'placement', label: 'Placement' },
              { key: 'share', label: 'Impression Share' },
              { key: 'ctr', label: 'CTR' },
              { key: 'acos', label: 'ACoS' },
              { key: 'basis', label: 'Basis', render: (v) => <span className="pill pill-muted" title="Stored sample window — not live reporting">{v}</span> },
            ]} rows={[
              { placement: 'Top of Search', share: '62%', ctr: '8.9%', acos: '18.2%', basis: 'CACHED' },
              { placement: 'Rest of Search', share: '21%', ctr: '4.1%', acos: '26.7%', basis: 'CACHED' },
              { placement: 'Product Pages', share: '17%', ctr: '3.2%', acos: '31.4%', basis: 'CACHED' },
            ]} />
          </div>
        </div>
      )}

      {view === 'rules' && (
        <div className="subview">
          <DataNotice tone="internal" title="Rules execute only after operator approval">
            Rules shown here are sample definitions. No rule fires automatically; every execution requires explicit approval.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Rule Management</h3>
              <span className="pill pill-muted">3 rules</span>
            </div>
            <DataTable columns={[
              { key: 'rule', label: 'Rule' },
              { key: 'scope', label: 'Scope' },
              { key: 'condition', label: 'Condition' },
              { key: 'evaluated', label: 'Last Evaluated' },
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'Armed' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
            ]} rows={[
              { rule: 'Pause term if ACoS > 30%', scope: 'Product Launch', condition: 'ACoS 30% over 7d', evaluated: 'sample window', state: 'Draft' },
              { rule: 'Raise budget if pacing < 80%', scope: 'All campaigns', condition: 'Pacing < 80% at day 14', evaluated: 'sample window', state: 'Draft' },
              { rule: 'Flag placement ACoS drift', scope: 'Product Launch', condition: 'ACoS delta > +8pp week/week', evaluated: 'sample window', state: 'Armed' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}