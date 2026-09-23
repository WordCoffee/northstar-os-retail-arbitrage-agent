import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function TheWatch({ toast }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const data = await api.scanner()
        const products = (data?.data?.products || data?.products || []).slice(0, 12)
        setItems(products.map((p) => ({
          asin: p.asin,
          name: p.name,
          price: p.amazon_price || 0,
          roi: p.roi_pct || 0,
          seller: p.buy_box_seller || null,
          status: p.roi_pct >= 30 ? 'signal' : 'watch'
        })))
      } catch (e) {
        setErr(e.message)
      }
    })()
  }, [])

  return (
    <div className="page">
      <PageHead
        title="The Watch"
        sub="Monitoring Agent — live product signals from the catalog"
        badges={[{ label: 'live', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Watchlist" icon="watch">
          {err ? (
            <div className="text-coral" style={{ fontSize: 12 }}>{err}</div>
          ) : items.length === 0 ? (
            <div className="text-low" style={{ fontSize: 12 }}>Loading live signals…</div>
          ) : (
            <div className="stack">
              {items.map((w) => (
                <div key={w.asin} className="list-row">
                  <Icon name="watch" size={16} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 12.8 }}>{w.name.length > 70 ? w.name.slice(0, 70) + '…' : w.name}</div>
                    <div className="text-low mono" style={{ fontSize: 11 }}>{w.asin} · ${w.price.toFixed(2)}{w.roi ? ` · ROI ${w.roi}%` : ''}{w.seller ? ` · BB: ${w.seller}` : ''}</div>
                  </div>
                  <span className={`status-pill ${w.status === 'signal' ? 'on' : 'warn'}`}>{w.status === 'signal' ? 'signal' : 'watch'}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Snapshot" icon="gauge">
          <div className="metric">
            <Metric k="Tracked Assets" v={items.length} d="live scanner" tone="glow" />
            <Metric k="ROI ≥ 30%" v={items.filter((i) => i.roi >= 30).length} d="strong signals" tone="lime" />
            <Metric k="Avg Price" v={`$${items.length ? (items.reduce((s, i) => s + i.price, 0) / items.length).toFixed(2) : '0.00'}`} d="across watchlist" />
          </div>
        </Card>
      </div>
    </div>
  )
}