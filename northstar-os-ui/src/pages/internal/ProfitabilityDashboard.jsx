import { PageLayout, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'
import MasterBrainPanel from '../../studio/components/MasterBrainPanel.jsx'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'fee', label: 'Fee Basis' },
  { id: 'inventory', label: 'Inventory Impact' },
  { id: 'export', label: 'Export' },
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
      {result.state === 'idle' && <p className="text-low" style={{ fontSize: 12 }}>Enter verified inputs, then calculate. Empty or partial inputs return an honest not-calculable result — never a fabricated number.</p>}
      {result.state === 'auth' && <p className="text-low" style={{ fontSize: 12 }}>Sign in and select an organization to use the economics engine.</p>}
      {result.state === 'error' && <p className="text-low" style={{ fontSize: 12 }}>Economics engine unavailable{result.error && result.error.code ? ` (${result.error.code})` : ''}.</p>}
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

function NotConnected({ title, children }) {
  return (
    <div className="card">
      <div className="card-head">
        <h3 className="card-title">{title}</h3>
        <span className="pill pill-muted">not connected</span>
      </div>
      <p style={{ fontSize: 13 }}>{children}</p>
    </div>
  )
}

export default function ProfitabilityDashboard() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'
  const exportReport = () => toast('Export prepared from observed data — review before distribution.', 'info')
  const createScenario = () => {
    navigate('/profitability?view=scenarios')
    toast('Enter verified cost/fee basis in the economics engine to compute a scenario.', 'info')
  }

  return (
    <PageLayout
      title="Profitability Dashboard"
      subtitle="Unit economics and decision support — the backend economics engine is the authoritative calculator."
      actions={<>
        <button className="btn btn-sm" onClick={createScenario}>Create Scenario</button>
        <button className="btn btn-sm" onClick={exportReport}>Export Report</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/commerce-ops')}>Send to Commerce Ops</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Refresh requires a live provider — the engine computes from your inputs.', 'info')}>Refresh Data</button>
      </>}
    >
      <DataNotice tone="assumption" title="Live economics engine — no fabricated portfolio">
        The “Economics engine” computes real, backend-authoritative unit economics from the inputs you supply. No portfolio/fee/inventory backend is connected, so those views show honest empty states — no fabricated figures. No result implies purchase authorization.
      </DataNotice>

      <EconomicsEngine />

      <RoomTabs tabs={TABS} base="/profitability" />

      {view === 'overview' && (
        <div className="subview">
          <NotConnected title="Portfolio contribution">
            No portfolio backend is connected. Use the economics engine above for authoritative per-unit economics; portfolio-level aggregation is not wired yet.
          </NotConnected>
        </div>
      )}

      {view === 'scenarios' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Scenario calculator = the economics engine">
            Scenarios are computed by the authoritative backend engine from the inputs you supply. No scenario result authorizes a purchase.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Scenario Calculator</h3>
              <span className="pill pill-muted">use the engine above</span>
            </div>
            <p style={{ fontSize: 13 }}>Enter selling price, acquisition cost, referral %, FBA fee, and advertising cost in the “Economics engine” card above, then calculate. Empty/partial inputs return an honest not-calculable result.</p>
          </div>
        </div>
      )}

      {view === 'fee' && (
        <div className="subview">
          <DataNotice tone="unknown" title="No fee-basis backend connected">
            Fee basis is supplied directly to the economics engine as an input. No portfolio fee-basis table is wired, so nothing is shown here — no fabricated sets.
          </DataNotice>
          <NotConnected title="Set-Level Fee Basis">
            No set/portfolio fee-basis backend is connected. Provide fee inputs per unit in the economics engine.
          </NotConnected>
        </div>
      )}

      {view === 'inventory' && (
        <div className="subview">
          <NotConnected title="Restock &amp; Aged-Stock Considerations">
            No inventory backend is connected. Inventory impact cannot be computed without local inventory data — shown honestly as empty.
          </NotConnected>
        </div>
      )}

      {view === 'export' && (
        <div className="subview">
          <DataNotice tone="internal" title="Exports carry basis labels — review before distribution">
            Any exported figure keeps its basis (observed / assumed / unknown). No exported model implies purchase authorization. Export wiring is not connected; the button produces a review note only.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Export Contents</h3>
              <span className="pill pill-muted">not connected</span>
            </div>
            <p style={{ fontSize: 13 }}>No export backend is connected. Nothing is fabricated.</p>
            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              <button className="btn btn-sm" onClick={exportReport}>Prepare Export</button>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/commerce-ops')}>Send to Commerce Ops</button>
            </div>
          </div>
        </div>
      )}
    <MasterBrainPanel title="Studio evidence for margin work (read-only)" />
    </PageLayout>
  )
}
