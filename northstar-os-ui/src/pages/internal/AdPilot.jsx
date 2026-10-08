import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import ReasoningModelSelector, { useReasoningModel } from '../../components/ReasoningModelSelector.jsx'
import foundationApi from '../../foundation/api.js'
import { useToast } from '../../components/ToastContext.jsx'
import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const TABS = [
  { id: 'campaigns', label: 'Campaigns', count: 8 },
  { id: 'detail', label: 'Campaign Detail' },
  { id: 'terms', label: 'Search Terms' },
  { id: 'planner', label: 'Planner' },
  { id: 'placements', label: 'Placements' },
  { id: 'rules', label: 'Rules' },
]

const CAMPAIGNS = [
  { name: 'Brand Defense', budget: '$500', spend: '$420', acos: '12.3%', placement: '#2', status: 'Healthy' },
  { name: 'Product Launch — Water Filter', budget: '$800', spend: '$760', acos: '24.1%', placement: '#5', status: 'Review' },
  { name: 'Keyword Harvest', budget: '$400', spend: '$310', acos: '16.8%', placement: '#3', status: 'Healthy' },
  { name: 'Competitor Conquest', budget: '$600', spend: '$590', acos: '31.2%', placement: '#8', status: 'Critical' },
  { name: 'Sponsored Brands', budget: '$300', spend: '$250', acos: '14.5%', placement: '#1', status: 'Healthy' },
]

const STATUS_PILL = { Healthy: 'pill-forest', Review: 'pill-warn', Critical: 'pill-ochre' }

// ═══ Hosted ad-copy proposal (OpenCode Go) — proposal only, never published ═══
function AdCopyProposalPanel() {
  const { selectedModel, catalog, persist } = useReasoningModel()
  const { toast } = useToast()
  const [form, setForm] = useState({
    product_name: 'Premium Water Filter',
    facts: '3-stage filtration; 10-cup capacity; BPA-free; easy-change filters; fits standard cabinets.',
    brand_tone: 'professional',
    format_hint: 'Amazon Sponsored Products',
  })
  const [state, setState] = useState({ phase: 'idle' })

  const submit = async () => {
    if (!(catalog && catalog.armed)) {
      toast('Hosted reasoning is not armed. Set OPENCODE_GO_ENABLED=1 and supply a key.', 'warn')
      return
    }
    setState({ phase: 'submitting' })
    try {
      const r = await foundationApi.reasoningAdCopyProposal({
        product_facts: {
          name: form.product_name,
          facts: form.facts.split('\n').map(s => s.trim()).filter(Boolean),
        },
        brand_tone: form.brand_tone,
        format_hint: form.format_hint,
        model: selectedModel?.id,
      })
      setState({ phase: 'done', value: r.proposal })
    } catch (e) {
      setState({ phase: 'error', message: e.message || 'Proposal failed.' })
    }
  }

  const prop = state.phase === 'done' ? state.value : null

  return (
    <div className="card" data-testid="ap-proposal" style={{ marginTop: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Hosted ad-copy proposal</h3>
        <span className="pill pill-ochre">proposal only · not published</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Generates proposed ad copy from supplied facts and brand tone. The output is for owner review — it is never pushed to an advertising platform.
      </p>
      <ReasoningModelSelector value={selectedModel?.id} onChange={persist} />
      <label className="stack" style={{ gap: 4, marginTop: 12 }}>
        <span className="text-low" style={{ fontSize: 11 }}>Product name</span>
        <input className="field" value={form.product_name} onChange={e => setForm(f => ({ ...f, product_name: e.target.value }))} />
      </label>
      <label className="stack" style={{ gap: 4, marginTop: 10 }}>
        <span className="text-low" style={{ fontSize: 11 }}>Approved facts (one per line)</span>
        <textarea className="field" rows={4} value={form.facts} onChange={e => setForm(f => ({ ...f, facts: e.target.value }))} />
      </label>
      <div className="grid-2" style={{ gap: 12, marginTop: 10 }}>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Brand tone</span>
          <input className="field" value={form.brand_tone} onChange={e => setForm(f => ({ ...f, brand_tone: e.target.value }))} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Format hint</span>
          <input className="field" value={form.format_hint} onChange={e => setForm(f => ({ ...f, format_hint: e.target.value }))} />
        </label>
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="btn btn-sm" onClick={submit} disabled={state.phase === 'submitting' || !(catalog && catalog.armed)}>
          {state.phase === 'submitting' ? 'Generating…' : 'Generate ad copy'}
        </button>
        {!(catalog && catalog.armed) && <span className="text-low" style={{ fontSize: 11, marginLeft: 8 }}>Hosted reasoning not armed.</span>}
      </div>
      {state.phase === 'error' && <div className="pill pill-warn" style={{ marginTop: 10 }}>{state.message}</div>}
      {prop && (
        <div style={{ marginTop: 16 }}>
          <div className="inline-flex" style={{ gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <span className={`pill ${prop.ok ? 'pill-ok' : 'pill-warn'}`}>{prop.ok ? 'proposal ok' : 'proposal failed'}</span>
            {prop.provenance && <span className="pill pill-muted">{prop.provenance.model}</span>}
          </div>
          {prop.warnings && prop.warnings.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              {prop.warnings.map((w, i) => <span key={i} className="pill pill-warn" style={{ fontSize: 10 }}>{w}</span>)}
            </div>
          )}
          {prop.unsupported_claims && prop.unsupported_claims.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Unsupported:</span>
              {prop.unsupported_claims.map((c, i) => <span key={i} className="pill pill-unknown" style={{ fontSize: 10 }}>{c}</span>)}
            </div>
          )}
          <div className="card" style={{ background: 'var(--pine-bleached)' }}>
            <div className="card-head"><h4 className="card-title" style={{ fontSize: 13 }}>Proposed copy</h4></div>
            <div style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600 }}>{(prop.headlines || []).join(' / ')}</div>
              <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{prop.body}</div>
              <div style={{ marginTop: 6, fontWeight: 600 }}>{prop.cta}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function healthRollup() {
  const c = { Healthy: 0, Review: 0, Critical: 0 }
  CAMPAIGNS.forEach(x => { c[x.status] = (c[x.status] || 0) + 1 })
  return `${c.Healthy} healthy · ${c.Review} review · ${c.Critical} critical`
}

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
                { campaign: 'Brand Defense', pace: '84% of budget', note: 'Pacing within expected range', tone: 'var(--pine)', meter: 'meter-fill-forest', w: 84 },
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
                  <span className="pill pill-forest">High Priority</span>
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

          <AdCopyProposalPanel />
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
              { key: 'suggestion', label: 'Suggestion', render: (v) => <span className={`pill ${v === 'Harvest' ? 'pill-forest' : v === 'Add Negative' ? 'pill-ochre' : 'pill-warn'}`}>{v}</span> },
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