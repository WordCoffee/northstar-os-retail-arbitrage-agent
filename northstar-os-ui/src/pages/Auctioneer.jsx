import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import foundationApi from '../foundation/api.js'

// NOTE (1C-03R): this page performs NO authoritative business math.
// All economics come from the canonical backend engine via /economics/compute.
const FIELDS = [
  ['selling_price', 'Selling price ($)'],
  ['acquisition_cost', 'Landed cost ($)'],
  ['referral_fee_amount', 'Referral fee ($)'],
  ['fba_fulfillment_fee', 'FBA fulfillment fee ($)'],
  ['advertising_cost', 'Advertising cost ($)'],
  ['impressions', 'Impressions'],
  ['clicks', 'Clicks'],
  ['orders', 'Orders'],
]

export default function Auctioneer({ toast }) {
  const [form, setForm] = useState({
    selling_price: '24.99', acquisition_cost: '12.50',
    referral_fee_amount: '3.75', fba_fulfillment_fee: '4.60',
    advertising_cost: '0', impressions: '10000', clicks: '60', orders: '5',
  })
  const [out, setOut] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const compute = async () => {
    setLoading(true); setErr(null)
    try {
      const input = {}
      for (const [k] of FIELDS) {
        const v = form[k]
        if (v === '' || v === undefined) continue
        input[k] = ['impressions', 'clicks', 'orders'].includes(k) ? parseInt(v, 10) : v
      }
      input.currency = 'USD'
      input.marketplace = 'amazon.com'
      input.provenance = 'user_supplied'
      input.total_revenue = form.selling_price // demo scope; labelled below
      const res = await foundationApi.economicsCompute(input)
      setOut(res)
      toast(`Canonical economics computed (${res.formula_version})`, 'ok')
    } catch (e) {
      setErr(e.message)
      toast('Backend required for economics', 'err')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <PageHead
        title="The Auctioneer"
        sub="Amazon Ads Agent — canonical economics (backend-authoritative)"
        badges={[{ label: out ? 'live · canonical' : 'canonical engine', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Campaign Economics" icon="auctioneer">
          <div className="grid-2">
            <div className="stack" style={{ gap: 10 }}>
              {FIELDS.map(([k, label]) => (
                <label key={k} className="stack" style={{ gap: 4 }}>
                  <span className="text-low" style={{ fontSize: 11.5 }}>{label}</span>
                  <input className="field" value={form[k]} onChange={(e) => set(k, e.target.value)} />
                </label>
              ))}
              <button className="btn btn-primary" onClick={compute} disabled={loading}>
                <Icon name="gauge" size={15} /> {loading ? 'Computing…' : 'Compute (canonical)'}
              </button>
              {err && <div className="text-coral" style={{ fontSize: 12 }}>{err}</div>}
            </div>
            <div className="stack">
              {out ? (
                <div className="metric" style={{ gridTemplateColumns: '1fr' }}>
                  <Metric k="Contribution profit / unit" v={`$${out.contribution_profit_after_ads ?? '—'}`} d={`readiness: ${out.readiness}`} tone="glow" />
                  <Metric k="Break-even ACoS" v={out.break_even_acos ?? '—'} d="pre-ad contribution / ad revenue" tone="lime" />
                  <Metric k="Target ACoS" v={out.target_acos ?? '—'} d="policy (not hardcoded)" tone="lime" />
                  <Metric k="Max CPC" v={out.maximum_cpc != null ? `$${out.maximum_cpc}` : '—'} d="derived from economics + CVR" />
                  <Metric k="ROI (denominator: landed)" v={out.roi_on_invested_cost ?? '—'} d={out.roi_denominator_label} />
                  <Metric k="Formula version" v={out.formula_version} d="canonical engine" />
                </div>
              ) : (
                <div className="text-low" style={{ fontSize: 12 }}>
                  Enter inputs and compute. Values are produced by the canonical backend engine —
                  this page holds no formulas. Unknown inputs stay unknown (never zero).
                </div>
              )}
              {out && out.missing_inputs?.length > 0 && (
                <div className="text-low" style={{ fontSize: 11 }}>
                  Missing inputs: {out.missing_inputs.join(', ')}
                </div>
              )}
            </div>
          </div>
        </Card>

        <Card title="Notes" icon="alert">
          <div className="text-low" style={{ fontSize: 12 }}>
            Backend-authoritative (1C-03). This UI formats decimal strings returned by the
            engine; it does not define referral/FBA/margin/ACoS formulas. Demo scope only —
            no live ad data is used.
          </div>
        </Card>
      </div>
    </div>
  )
}