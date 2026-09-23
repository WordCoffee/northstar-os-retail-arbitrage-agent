import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

function scoreDeals(items) {
  return items
    .map((it) => {
      // Scanner product (has real economics) OR match record
      const price = it.amazon_price || it.price || 0
      const cost = it.costco_cost || it.quantity_match?.costco_sku?.costco_cost_reference || 0
      const net = it.net_profit ?? (price ? price - price * 0.15 - (price > 59 ? 5.55 : price > 19 ? 4.6 : 3.4) - (cost + cost * 0.08) : 0)
      const roi = it.roi_pct ?? (cost + cost * 0.08 > 0 ? (net / (cost + cost * 0.08)) * 100 : 0)
      const score = it.opportunity_score ?? Math.round(clamp(net * 3, 0, 60) + clamp(roi, 0, 80) * 0.35 + 10)
      return {
        asin: it.asin,
        title: it.name || it.title,
        net: +net.toFixed(2),
        marginPct: price ? +(net / price * 100).toFixed(1) : 0,
        roiPct: +roi.toFixed(1),
        rating: it.rating?.value || null,
        score,
        monthlySales: it.monthly_sales_estimate || null
      }
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)
    .slice(0, 50)
}

const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n))

export default function GoldenGoose({ toast }) {
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [minScore, setMinScore] = useState(50)
  const [pinned, setPinned] = useState(new Set())

  useEffect(() => {
    (async () => {
      try {
        const data = await api.scanner()
        const products = data?.data?.products || data?.products || []
        setDeals(scoreDeals(products))
      } catch (e) {
        // fallback to matches scoring
        try {
          const m = await api.matches()
          const scoreFallback = scoreDeals((m.items || []).map((it) => ({
            name: it.title,
            asin: it.asin,
            amazon_price: it.price || 0,
            costco_cost: it.quantity_match?.costco_sku?.costco_cost_reference || 0,
            net_profit: it.price ? it.price - it.price * 0.15 - 4.6 : 0,
            roi_pct: 0
          })))
          setDeals(scoreFallback)
        } catch (e2) {
          setErr(e2.message)
        }
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const filtered = deals.filter((d) => d.score >= minScore)

  return (
    <div className="page">
      <PageHead
        title="Golden Goose"
        sub="Deal Finder Agent — live ranking by margin, ROI, and rating signal"
        badges={[{ label: 'live · ranked', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Filters" icon="prospector">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
            <span className="text-low" style={{ fontSize: 12 }}>Min deal score</span>
            <input type="range" className="glass-slider" min="0" max="100" value={minScore} onChange={(e) => setMinScore(+e.target.value)} style={{ width: 180 }} aria-label="Minimum deal score" />
            <span className="mono text-glow" style={{ fontSize: 12 }}>{minScore}/100</span>
            <span className="badge badge-live">{filtered.length} qualified</span>
          </div>
        </Card>

        <Card title="Qualified Deals" icon="goose">
          {loading ? (
            <div className="text-mid" style={{ padding: '18px 0', textAlign: 'center' }}>Ranking deals…</div>
          ) : err ? (
            <div className="text-coral" style={{ padding: '12px 0' }}>Failed: {err}</div>
          ) : (
            <div className="stack">
              {filtered.slice(0, 30).map((d, idx) => (
                <div key={d.asin} className="list-row">
                  <span className="mono text-glow" style={{ width: 28 }}>#{idx + 1}</span>
                  <Icon name="star" size={16} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{d.title.length > 70 ? d.title.slice(0, 70) + '…' : d.title}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>
                      <span className="mono">{d.asin}</span> · est. net <span className="text-lime mono">${d.net.toFixed(2)}</span> · ROI <span className="text-lime mono">{d.roiPct}%</span>{d.rating ? ` · ★ ${d.rating}` : ''}
                    </div>
                  </div>
                  <span className="badge badge-live">{d.marginPct}%</span>
                  <span className={`status-pill ${d.score >= 70 ? 'on' : d.score >= 50 ? 'warn' : 'off'}`}>{d.score}/100</span>
                  <button
                    className="btn btn-ghost"
                    style={{ padding: '4px 10px' }}
                    onClick={() => {
                      setPinned((prev) => { const n = new Set(prev); n.has(d.asin) ? n.delete(d.asin) : n.add(d.asin); return n })
                      toast(pinned.has(d.asin) ? `Unpinned ${d.asin}` : `Pinned ${d.asin}`, 'ok')
                    }}
                    aria-label="Pin deal"
                  >
                    {pinned.has(d.asin) ? '★' : '♡'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Snapshot" icon="gauge">
          <div className="metric">
            <Metric k="Deals Scored" v={deals.length} d="live catalog" tone="glow" />
            <Metric k="Score ≥ 70" v={deals.filter((d) => d.score >= 70).length} d="top-tier" tone="lime" />
            <Metric k="Qualified" v={filtered.length} d={`at ≥ ${minScore}`} tone="lime" />
          </div>
        </Card>
      </div>
    </div>
  )
}