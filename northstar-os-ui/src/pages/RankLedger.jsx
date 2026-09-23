import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function RankLedger({ toast }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const data = await api.scanner()
        const products = (data?.data?.products || data?.products || [])
          .slice(0, 12)
          .map((p) => ({
            asin: p.asin,
            name: p.name,
            price: p.amazon_price || 0,
            roi: p.roi_pct || 0,
            sales: p.monthly_sales_estimate || 0,
            score: p.opportunity_score || 0
          }))
          .sort((a, b) => b.score - a.score)
        setItems(products)
      } catch (e) {
        setErr(e.message)
      }
    })()
  }, [])

  return (
    <div className="page">
      <PageHead
        title="RankLedger"
        sub="Rank Tracking Agent — live opportunity standing"
        badges={[{ label: 'live', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Product Standing" icon="rank">
          {err ? (
            <div className="text-coral" style={{ fontSize: 12 }}>{err}</div>
          ) : items.length === 0 ? (
            <div className="text-low" style={{ fontSize: 12 }}>Loading…</div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>#</th><th>Product</th><th>Price</th><th>ROI</th><th>Sales/mo</th><th>Score</th><th>Standing</th></tr>
              </thead>
              <tbody>
                {items.map((r, idx) => (
                  <tr key={r.asin}>
                    <td className="mono">#{idx + 1}</td>
                    <td>
                      <div style={{ fontWeight: 560, fontSize: 12.5 }}>{r.name.length > 60 ? r.name.slice(0, 60) + '…' : r.name}</div>
                      <div className="mono text-low" style={{ fontSize: 10.5 }}>{r.asin}</div>
                    </td>
                    <td className="mono">${r.price.toFixed(2)}</td>
                    <td className={`mono ${r.roi >= 30 ? 'text-lime' : r.roi >= 15 ? 'text-glow' : 'text-coral'}`}>{r.roi}%</td>
                    <td className="mono">{r.sales ? r.sales.toFixed(0) : '—'}</td>
                    <td className="mono">{r.score}/100</td>
                    <td>
                      <span className={`status-pill ${r.score >= 75 ? 'on' : r.score >= 50 ? 'warn' : 'off'}`}>
                        {r.score >= 75 ? 'strong' : r.score >= 50 ? 'competitive' : 'weak'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Snapshot" icon="gauge">
          <div className="metric">
            <Metric k="Tracked ASINs" v={items.length} d="live scanner" tone="glow" />
            <Metric k="Score ≥ 75" v={items.filter((i) => i.score >= 75).length} d="strong standing" tone="lime" />
            <Metric k="Avg ROI" v={items.length ? (items.reduce((s, i) => s + i.roi, 0) / items.length).toFixed(1) + '%' : '—'} d="across set" />
          </div>
        </Card>
      </div>
    </div>
  )
}