import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'

// Real Amazon ad economics — break-even ACoS from fee structure
export default function Auctioneer({ toast }) {
  const [price, setPrice] = useState(24.99)
  const [cogs, setCogs] = useState(12.5)
  const [ctr, setCtr] = useState(0.6)
  const [conv, setConv] = useState(9)

  const referral = price * 0.15
  const fulfillment = price > 59 ? 5.55 : price > 19 ? 4.6 : 3.4
  const gross = price - referral - fulfillment - cogs
  const breakEvenAcos = price > 0 ? Math.max(0, (gross / price) * 100) : 0
  const targetAcos = breakEvenAcos * 0.7 // 70% of break-even for profit
  const cpc = ctr > 0 ? (price * conv / 100 * (targetAcos / 100)) / (ctr / 100) : 0
  const estSales = 10000 * (ctr / 100) * (conv / 100) // 10k impressions
  const estSpend = estSales * (targetAcos / 100)
  const estProfit = estSales * (gross / price) - estSpend

  return (
    <div className="page">
      <PageHead
        title="The Auctioneer"
        sub="Amazon Ads Agent — live campaign economics calculator"
        badges={[{ label: 'live · computed', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Campaign Economics" icon="auctioneer">
          <div className="grid-2">
            <div className="stack" style={{ gap: 10 }}>
              {[
                ['Selling price ($)', price, setPrice, 1],
                ['Landed COGS ($)', cogs, setCogs, 0.5],
                ['CTR (%)', ctr, setCtr, 0.1],
                ['Conversion (%)', conv, setConv, 0.5]
              ].map(([label, val, setter, step]) => (
                <label key={label} className="stack" style={{ gap: 4 }}>
                  <span className="text-low" style={{ fontSize: 11.5 }}>{label}</span>
                  <input type="number" className="field" value={val} step={step} onChange={(e) => setter(+e.target.value)} />
                </label>
              ))}
            </div>
            <div className="stack">
              <div className="metric" style={{ gridTemplateColumns: '1fr' }}>
                <Metric k="Gross Margin / Unit" v={`$${gross.toFixed(2)}`} d={`after ${referral.toFixed(2)} referral + ${fulfillment.toFixed(2)} fulfillment`} tone="glow" />
                <Metric k="Break-Even ACoS" v={`${breakEvenAcos.toFixed(1)}%`} d="max ad spend % at zero profit" tone="lime" />
                <Metric k="Target ACoS" v={`${targetAcos.toFixed(1)}%`} d="70% of break-even (profit)" tone="lime" />
                <Metric k="Est. CPC" v={`$${cpc.toFixed(2)}`} d="implied from CTR + conv" />
              </div>
            </div>
          </div>
        </Card>

        <Card title="Projection (10,000 impressions)" icon="gauge">
          <div className="metric">
            <Metric k="Est. Sales" v={estSales.toFixed(0)} d="units" />
            <Metric k="Est. Ad Spend" v={`$${estSpend.toFixed(2)}`} d="at target ACoS" />
            <Metric k="Est. Profit" v={`$${estProfit.toFixed(2)}`} d={estProfit >= 0 ? 'net of ads' : 'negative — lower target ACoS'} tone={estProfit >= 0 ? 'lime' : 'coral'} />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-primary" onClick={() => toast('Campaign plan built — publishing is gated', 'ok')}>Build campaign plan</button>
            <button className="btn" onClick={() => toast('Saving to ad plan workspace', 'ok')}>Save</button>
          </div>
        </Card>
      </div>
    </div>
  )
}