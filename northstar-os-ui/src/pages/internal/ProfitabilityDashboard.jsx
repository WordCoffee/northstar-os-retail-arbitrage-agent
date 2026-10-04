import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'fee', label: 'Fee Basis' },
  { id: 'inventory', label: 'Inventory Impact' },
  { id: 'export', label: 'Export' },
]

const SETS = [
  { set: 'Set A', asins: 12, revenue: '$12.4K', contribution: '$2.8K', margin: '~22%', concentration: '45%', feeBasis: 'Observed' },
  { set: 'Set B', asins: 8, revenue: '$8.1K', contribution: '$1.4K', margin: 'UNKNOWN', concentration: '30%', feeBasis: 'ASSUMPTION' },
  { set: 'Set C', asins: 15, revenue: '$5.2K', contribution: '$0.8K', margin: '~15%', concentration: '25%', feeBasis: 'Observed' },
]

const MARGIN_PILL = (v) => {
  if (v === 'UNKNOWN') return <span className="pill pill-unknown" title="Fee basis assumed and cost data missing — margin not computable">UNKNOWN</span>
  return <span className="pill pill-muted" title="Sample estimate from observed history — not a verified calculation">{v}</span>
}

const SCENARIOS = [
  { name: 'Base Case', note: 'Observed margins, current velocity', profit: 'NOT CALCULATED' },
  { name: 'Optimistic', note: 'Assumes faster sell-through', profit: 'NOT CALCULATED' },
  { name: 'Constrained', note: 'Assumes capital cap + MOQ floor', profit: 'NOT CALCULATED' },
  { name: 'Worst Case', note: 'Assumes aged-stock discounting', profit: 'NOT CALCULATED' },
]

// ═══ Authoritative economics engine (backend calculator) ═══
// The backend is the ONLY authoritative calculator. Inputs are operator-supplied;
// missing inputs stay UNKNOWN and purchase_ready stays false unless every gate is
// verified. Nothing here defines its own formula.
function EngineValue({ label, value, tone, title }) {
  const unknown = value == null
  return (
    <div title={title || ''}>
      <div className="text-low" style={{ fontSize: 11 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color: unknown ? 'var(--ink-soft)' : (tone || 'var(--pine-deep)') }}>
        {unknown ? 'UNKNOWN' : value}
      </div>
    </div>
  )
}

function EconomicsEngine() {
  const [contract, setContract] = useState(null)
  const [form, setForm] = useState({ selling_price: '', acquisition_cost: '', referral_fee_rate: '', fba_fulfillment_fee: '', advertising_cost: '', quantity: '1' })
  const [result, setResult] = useState({ state: 'idle' })

  useEffect(() => {
    let alive = true
    settle(foundationApi.economicsContract()).then(r => { if (alive) setContract(r) })
    return () => { alive = false }
  }, [])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const compute = async () => {
    setResult({ state: 'loading' })
    const num = (v) => (v === '' || v == null ? undefined : Number(v))
    const input = { marketplace: 'amazon.com', currency: 'USD' }
    const sp = num(form.selling_price), ac = num(form.acquisition_cost)
    const rr = num(form.referral_fee_rate), fba = num(form.fba_fulfillment_fee), q = num(form.quantity), ads = num(form.advertising_cost)
    if (sp !== undefined) input.selling_price = sp
    if (ac !== undefined) input.acquisition_cost = ac
    if (rr !== undefined) input.referral_fee_rate = rr / 100
    if (fba !== undefined) input.fba_fulfillment_fee = fba
    if (ads !== undefined) input.advertising_cost = ads
    if (q !== undefined) input.quantity = q
    const r = await settle(foundationApi.economicsCompute(input))
    if (r.ok) setResult({ state: 'done', value: r.value })
    else setResult({ state: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
  }

  const cState = !contract ? 'loading' : contract.ok ? 'ok' : (contract.error && contract.error.status === 401 ? 'auth' : 'error')
  const cMeta = contract && contract.ok ? contract.value : null
  const out = result.state === 'done' ? result.value : null

  return (
    <div className="card" data-testid="pd-economics-engine" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Economics engine</h3>
        {cState === 'loading' && <span className="pill pill-muted">Loading contract…</span>}
        {cState === 'ok' && <span className="pill pill-muted" title="Canonical formula version (backend-authoritative)">formula {cMeta.formula_version}</span>}
        {cState === 'auth' && <span className="pill pill-unknown">sign-in required</span>}
        {cState === 'error' && <span className="pill pill-unknown">unavailable</span>}
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Authoritative, backend-computed unit economics. Inputs are operator-supplied; missing inputs stay UNKNOWN and no result authorizes a purchase. Values below are computed by the backend — the UI defines no formula of its own.
      </p>

      <div className="grid-4" style={{ gap: 12, marginBottom: 12 }}>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Selling price (USD)</span>
          <input type="number" min="0" step="0.01" value={form.selling_price} onChange={set('selling_price')} placeholder="—" style={{ padding: '6px 8px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Acquisition cost (USD)</span>
          <input type="number" min="0" step="0.01" value={form.acquisition_cost} onChange={set('acquisition_cost')} placeholder="—" style={{ padding: '6px 8px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Referral fee (%)</span>
          <input type="number" min="0" step="0.1" value={form.referral_fee_rate} onChange={set('referral_fee_rate')} placeholder="e.g. 15" style={{ padding: '6px 8px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>FBA fulfillment fee (USD)</span>
          <input type="number" min="0" step="0.01" value={form.fba_fulfillment_fee} onChange={set('fba_fulfillment_fee')} placeholder="—" style={{ padding: '6px 8px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Advertising cost (USD)</span>
          <input type="number" min="0" step="0.01" value={form.advertising_cost} onChange={set('advertising_cost')} placeholder="0 if none" style={{ padding: '6px 8px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
      </div>

      <div className="inline-flex" style={{ gap: 8, alignItems: 'center', marginBottom: 14 }}>
        <button className="btn btn-sm" onClick={compute} disabled={result.state === 'loading'}>
          {result.state === 'loading' ? 'Calculating…' : 'Calculate with backend engine'}
        </button>
        <label className="inline-flex" style={{ gap: 6, alignItems: 'center' }}>
          <span className="text-low" style={{ fontSize: 11 }}>Quantity</span>
          <input type="number" min="1" step="1" value={form.quantity} onChange={set('quantity')} style={{ width: 64, padding: '4px 6px', border: '1px solid var(--divider-mid)', borderRadius: 6, fontFamily: 'var(--font-ui)' }} />
        </label>
      </div>

      {result.state === 'idle' && (
        <p className="text-low" style={{ fontSize: 12 }}>Enter verified inputs, then calculate. Empty or partial inputs return an honest not-calculable result — never a fabricated number.</p>
      )}
      {result.state === 'auth' && (
        <p className="text-low" style={{ fontSize: 12 }}>Sign in and select an organization to use the economics engine.</p>
      )}
      {result.state === 'error' && (
        <p className="text-low" style={{ fontSize: 12 }}>Economics engine unavailable{result.error && result.error.code ? ` (${result.error.code})` : ''}.</p>
      )}
      {out && (
        <div data-testid="pd-engine-result">
          <div className="inline-flex" style={{ gap: 8, marginBottom: 12 }}>
            <span className={`pill ${out.readiness === 'PURCHASE_READY' ? 'pill-ok' : 'pill-unknown'}`} title="Readiness is gate-driven; a score alone never yields PURCHASE_READY">{out.readiness}</span>
            <span className={`pill ${out.purchase_ready ? 'pill-ok' : 'pill-muted'}`} title="Purchase authorization is never granted by the calculator">{out.purchase_ready ? 'purchase-ready (gates passed)' : 'purchase NOT authorized'}</span>
          </div>
          <div className="grid-4" style={{ gap: 16, marginBottom: 12 }}>
            <EngineValue label="Contribution profit (after ads)" value={out.contribution_profit_after_ads} title="Backend-computed contribution after advertising" />
            <EngineValue label="Pre-ad contribution" value={out.pre_ad_contribution} />
            <EngineValue label="Margin on revenue" value={out.margin_on_revenue} />
            <EngineValue label="ROI on invested cost" value={out.roi_on_invested_cost} title={`ROI denominator: ${out.roi_denominator_label}`} />
            <EngineValue label="Gross revenue" value={out.gross_revenue} />
            <EngineValue label="Marketplace fees" value={out.marketplace_fees} />
            <EngineValue label="Payout before ads" value={out.marketplace_payout_before_ads} />
            <EngineValue label="Landed inventory cost" value={out.landed_inventory_cost} />
          </div>
          {out.missing_inputs && out.missing_inputs.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Missing inputs — stays UNKNOWN until supplied</div>
              <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                {out.missing_inputs.map(m => <span key={m} className="pill pill-unknown" style={{ fontSize: 10 }}>{m}</span>)}
              </div>
            </div>
          )}
          {out.explanation && out.explanation.length > 0 && (
            <details>
              <summary className="text-low" style={{ fontSize: 11, cursor: 'pointer' }}>Calculation steps ({out.explanation.length})</summary>
              <ul className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
                {out.explanation.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProfitabilityDashboard() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [scope, setScope] = useState('Portfolio')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'

  const rows = scope === 'Portfolio' ? SETS : SETS.filter(s => s.set === scope)
  const exportReport = () => toast('Export prepared from observed data — review before distribution.', 'info')
  const createScenario = () => {
    navigate('/profitability?view=scenarios')
    toast('Scenario requires verified cost/fee basis — current inputs are assumptions.', 'info')
  }
  const sendToCommerceOps = () => {
    navigate('/commerce-ops')
    toast('Handed to Commerce Ops — operator decision required there.', 'info')
  }

  return (
    <PageLayout
      title="Profitability Dashboard"
      subtitle="Portfolio decision room — scenarios, fee basis, inventory impact, and explicit assumptions. Not a KPI wall."
      actions={<>
        <button className="btn btn-sm" onClick={createScenario}>Create Scenario</button>
        <button className="btn btn-sm" onClick={exportReport}>Export Report</button>
        <button className="btn btn-sm btn-ghost" onClick={sendToCommerceOps}>Send to Commerce Ops</button>
        <button className="btn btn-sm btn-ghost">Refresh Data</button>
      </>}
    >
      <DataNotice tone="assumption" title="Live economics engine + assumed portfolio context">
        The “Economics engine” card computes real, backend-authoritative unit economics from the inputs you supply. The portfolio sets below remain sample/assumed context — Set B margin is UNKNOWN because fee basis is assumed. No figure implies purchase authorization.
      </DataNotice>

      <EconomicsEngine />

      <RoomTabs tabs={TABS} base="/profitability" />

      {view === 'overview' && (
        <div className="subview">
          <div className="room-toolbar">
            {['Portfolio', 'Set A', 'Set B', 'Set C'].map(s => (
              <button key={s} className={`filter-pill ${scope === s ? 'active' : ''}`} onClick={() => setScope(s)}>{s}</button>
            ))}
            <span className="pill pill-muted" style={{ marginLeft: 'auto' }} title="Sample scope switch — demonstration data">Sample selector</span>
          </div>

          <MetricTiles metrics={[
            { label: 'Net Contribution', value: '$4.2K', sub: 'This month · sample', tone: 'warn' },
            { label: 'Cash Cycle', value: '42d', sub: 'Inventory to cash' },
            { label: 'Avg Margin', value: '~18%', sub: 'Observed · sample estimate' },
            { label: 'Aged Stock', value: '$1.1K', sub: '90+ days', tone: 'warn' },
          ]} columns={4} />

          <ScenarioCards />

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Portfolio Contribution</h3>
                <span className="pill pill-muted">{rows.length} of 3 sets · sample</span>
              </div>
              <DataTable columns={[
                { key: 'set', label: 'Set' },
                { key: 'revenue', label: 'Revenue' },
                { key: 'contribution', label: 'Contribution' },
                { key: 'margin', label: 'Margin', render: (v) => MARGIN_PILL(v) },
                { key: 'concentration', label: 'Concentration' },
              ]} rows={rows} />
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
              <h3 className="card-title">Unit Economics Basis</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Observed Margin</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine)' }}>~18%</span>
                  <span className="pill pill-muted" title="Sample estimate from observed history — not a verified calculation">sample</span>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>Historical: Q3 2026</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Fee Basis</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--ochre)' }}>ASSUMPTION</span>
                  <span className="pill pill-unverified" title="Modeled from category average — not verified">assumption</span>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>Based on category average</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Risk Context</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--clay)' }}>ELEVATED</span>
                  <span className="pill pill-warn" title="Concentration signal — not a purchase or avoidance recommendation">concentration</span>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>Concentration in Set A</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'scenarios' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Scenario calculator requires verified inputs">
            No calculated profit authorizes a purchase. Enter verified cost/fee basis to enable a scenario. Outputs below use sample inputs.
          </DataNotice>

          <ScenarioCards />

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Scenario Calculator — B08L5VJQ7T</h3>
              <span className="pill pill-unverified" title="Inputs are assumptions — scenario blocked until verified">inputs assumed</span>
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

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Assumption Panel</h3>
                <span className="pill pill-unverified">3 assumptions</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {[
                  { label: 'Fee basis = category average', note: 'Not verified against live FBA fee schedule' },
                  { label: 'Shipping & prep = flat per-unit estimate', note: 'Carrier quotes not yet captured' },
                  { label: 'Return rate = 3% modeled', note: 'No observed return data for these ASINs' },
                ].map(a => (
                  <div key={a.label} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{a.label}</div>
                      <div className="text-low" style={{ fontSize: 11 }}>{a.note}</div>
                    </div>
                    <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Modeled value — planning only, does not authorize spend">assumption</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Warning Stack</h3>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div style={{ fontSize: 13 }}>Set B margin UNKNOWN — fee basis assumed, cost data missing</div>
                  <span className="pill pill-unknown" title="Cannot compute margin without verified basis">UNKNOWN</span>
                </div>
                <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div style={{ fontSize: 13 }}>Scenario outputs blocked — verified inputs required</div>
                  <span className="pill pill-ochre" title="Gate, not a failure — supply verified basis to proceed">REQUIRED</span>
                </div>
                <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div style={{ fontSize: 13 }}>No scenario result implies purchase authorization</div>
                  <span className="pill pill-muted" title="Restraint note — always in effect">standing</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'fee' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Set B economics are incomplete">
            Margin is UNKNOWN because fee basis is assumed and cost data is missing. Sets below are sample demonstration records.
          </DataNotice>
          <div className="room-toolbar">
            {['Portfolio', 'Set A', 'Set B', 'Set C'].map(s => (
              <button key={s} className={`filter-pill ${scope === s ? 'active' : ''}`} onClick={() => setScope(s)}>{s}</button>
            ))}
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Set-Level Fee Basis</h3>
              <span className="pill pill-muted">{rows.length} of 3 sets · sample</span>
            </div>
            <DataTable columns={[
              { key: 'set', label: 'Set' },
              { key: 'asins', label: 'ASINs' },
              { key: 'revenue', label: 'Revenue' },
              { key: 'contribution', label: 'Contribution' },
              { key: 'margin', label: 'Margin', render: (v) => MARGIN_PILL(v) },
              { key: 'concentration', label: 'Concentration' },
              { key: 'feeBasis', label: 'Fee Basis', render: (v) => v === 'ASSUMPTION'
                ? <span className="pill pill-unverified" title="Modeled from category average — not verified">ASSUMPTION</span>
                : <span className="pill pill-muted" title="Observed in sample window — not a verified calculation">{v}</span> },
            ]} rows={rows} />
          </div>
        </div>
      )}

      {view === 'inventory' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Restock &amp; Aged-Stock Considerations</h3>
              <span className="pill pill-muted" title="Recommendations weigh UNKNOWN margins — review before acting">sample recommendations</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'stock', label: 'Units' },
              { key: 'days', label: 'Days in Stock' },
              { key: 'action', label: 'Recommended Action', render: (v) => <span className={`pill ${v === 'Urgent Restock' ? 'pill-error' : v === 'Discount / Clear' ? 'pill-ochre' : v === 'Restock' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
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
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'Assumption' ? 'pill-unverified' : v === 'At risk' ? 'pill-warn' : 'pill-muted'}`} title={v === 'Assumption' ? 'Modeled value — not observed' : v === 'Observed' ? 'Sample window — not a verified calculation' : 'Working-capital state (sample)'}>{v}</span> },
            ]} rows={[
              { stage: 'Inventory', value: '$6.8K', days: '42 avg', state: 'In stock' },
              { stage: 'Receivables', value: '$2.1K', days: '—', state: 'Observed' },
              { stage: 'Aged Stock', value: '$1.1K', days: '90+', state: 'At risk' },
              { stage: 'Cash Reserve', value: '$4.0K', days: '—', state: 'Assumption' },
            ]} />
          </div>
        </div>
      )}

      {view === 'export' && (
        <div className="subview">
          <DataNotice tone="internal" title="Exports carry basis labels — review before distribution">
            Every exported figure keeps its basis (observed / assumed / unknown). No exported model implies purchase authorization.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Export Contents</h3>
              <span className="pill pill-muted">sample model</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {[
                { item: 'Scenario matrix (base / optimistic / constrained / worst case)', basis: 'NOT CALCULATED' },
                { item: 'Unit economics breakdown by set', basis: '~observed' },
                { item: 'Assumption register (fee basis, shipping, returns)', basis: 'ASSUMPTION' },
                { item: 'Inventory impact & cash-cycle snapshot', basis: 'observed' },
              ].map(r => (
                <div key={r.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div style={{ fontSize: 13 }}>{r.item}</div>
                  {r.basis === 'ASSUMPTION'
                    ? <span className="pill pill-unverified" title="Modeled value — planning only">ASSUMPTION</span>
                    : r.basis === 'NOT CALCULATED'
                      ? <span className="pill pill-unknown" title="Blocked until verified inputs supplied">NOT CALCULATED</span>
                      : <span className="pill pill-muted" title="Sample basis — review before distribution">{r.basis}</span>}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              <button className="btn btn-sm" onClick={exportReport}>Prepare Export</button>
              <button className="btn btn-sm btn-ghost" onClick={sendToCommerceOps}>Send to Commerce Ops</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}

function ScenarioCards() {
  return (
    <div className="grid-4" style={{ gap: 14, marginBottom: 20 }}>
      {SCENARIOS.map(s => (
        <div key={s.name} className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{s.name}</div>
            <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Modeled frame — planning only, does not authorize spend">assumption</span>
          </div>
          <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--clay)' }}>{s.profit}</div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>{s.note}</div>
        </div>
      ))}
    </div>
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
