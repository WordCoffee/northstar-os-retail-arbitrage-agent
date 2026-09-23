import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function RivalBoard({ toast }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const data = await api.scanner()
        const pool = (data?.data?.products || data?.products || []).slice(0, 12)
        setItems(pool.map((p) => ({
          asin: p.asin,
          name: p.name,
          price: p.amazon_price || 0,
          roi: p.roi_pct || 0,
          seller: p.buy_box_seller || null,
          risk: p.roi_pct < 15 ? 'price-saturated' : p.roi_pct >= 30 ? 'high-margin' : 'benign'
        })))
      } catch (e) {
        setErr(e.message)
      }
    })()
  }, [])

  const riskPill = (r) => (r === 'price-saturated' ? 'off' : r === 'high-margin' ? 'on' : 'warn')

  return (
    <div className="page">
      <PageHead
        title="The Rival Board"
        sub="Competitor Analysis — live margin/ROI landscape"
        badges={[{ label: 'live', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Competitive Landscape" icon="rival">
          {err ? (
            <div className="text-coral" style={{ fontSize: 12 }}>{err}</div>
          ) : items.length === 0 ? (
            <div className="text-low" style={{ fontSize: 12 }}>Loading…</div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Product</th><th>Price</th><th>ROI</th><th>Buy Box</th><th>Posture</th></tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.asin}>
                    <td>
                      <div style={{ fontWeight: 560, fontSize: 12.5 }}>{r.name.length > 55 ? r.name.slice(0, 55) + '…' : r.name}</div>
                      <div className="mono text-low" style={{ fontSize: 10.5 }}>{r.asin}</div>
                    </td>
                    <td className="mono">${r.price.toFixed(2)}</td>
                    <td className={`mono ${r.roi >= 30 ? 'text-lime' : r.roi >= 15 ? 'text-glow' : 'text-coral'}`}>{r.roi}%</td>
                    <td>{r.seller ? <span className="badge badge-ok">{r.seller}</span> : <span className="text-low">—</span>}</td>
                    <td>
                      <span className={`status-pill ${riskPill(r.risk)}`}>{r.risk}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Snapshot" icon="gauge">
          <div className="metric">
            <Metric k="Assessed ASINs" v={items.length} d="live scanner" tone="glow" />
            <Metric k="High-Margin" v={items.filter((i) => i.risk === 'high-margin').length} d="ROI ≥ 30%" tone="lime" />
            <Metric k="Price-Saturated" v={items.filter((i) => i.risk === 'price-saturated').length} d="ROI < 15%" tone="coral" />
          </div>
        </Card>
      </div>
    </div>
  )
}