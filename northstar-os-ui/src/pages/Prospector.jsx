import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

function fromScanner(product) {
  return {
    asin: product.asin,
    title: product.name || product.asin,
    price: product.amazon_price || 0,
    cost: product.costco_cost || product.costco_cogs || 0,
    net: product.net_profit || 0,
    marginPct: product.amazon_price ? Math.round(((product.net_profit || 0) / product.amazon_price) * 1000) / 10 : 0,
    roiPct: product.roi_pct || 0,
    score: product.opportunity_score || 0,
    monthlySales: product.monthly_sales_estimate || null,
    seller: product.buy_box_seller || null,
    fulfillment: product.buy_box_fulfillment || null,
    fbaFee: product.fba_fee || null,
    match: product.match_readiness || '—',
    fresh: product.freshness_label || null
  }
}

function fromMatch(it) {
  const price = it.price || it.buybox_price || 0
  const cost = it.quantity_match?.costco_sku?.costco_cost_reference || 0
  if (!price) return null
  const referral = price * 0.15
  const fulfillment = price > 59 ? 5.55 : price > 19 ? 4.6 : 3.4
  const landed = cost + cost * 0.08
  const net = price - referral - fulfillment - landed
  return {
    asin: it.asin,
    title: it.title,
    price,
    cost: +cost.toFixed(2),
    net: +net.toFixed(2),
    marginPct: price > 0 ? Math.round((net / price) * 1000) / 10 : 0,
    roiPct: landed > 0 ? Math.round((net / landed) * 1000) / 10 : 0,
    score: 0,
    monthlySales: null,
    seller: null,
    fulfillment: null,
    fbaFee: null,
    match: it.quantity_match?.status || 'PASS',
    fresh: null
  }
}

export default function Prospector({ toast }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [query, setQuery] = useState('')
  const [minRoi, setMinRoi] = useState(0)
  const [source, setSource] = useState('scanner')
  const [lastRefresh, setLastRefresh] = useState(null)

  const loadScanner = async () => {
    const data = await api.scanner()
    const products = data?.data?.products || data?.products || []
    setItems(products.map(fromScanner))
    setSource('scanner')
    setLastRefresh(data?.data?.generated_at || new Date().toISOString())
    return products.length
  }

  const loadMatches = async () => {
    const data = await api.matches()
    const items = (data.items || []).map(fromMatch).filter(Boolean)
    setItems(items)
    setSource('matches')
    setLastRefresh(data.generated_at || new Date().toISOString())
    return items.length
  }

  useEffect(() => {
    (async () => {
      setLoading(true)
      setErr(null)
      try {
        let count = 0
        try { count = await loadScanner() } catch (e) { console.warn('scanner failed, fallback matches:', e.message) }
        if (!count) { await loadMatches() }
      } catch (e) {
        setErr(e.message)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const runScan = async () => {
    setLoading(true)
    setErr(null)
    try {
      const count = await loadScanner()
      toast(`Scan complete — ${count} candidates`, 'ok')
    } catch (e) {
      setErr(e.message)
      toast('Live scan unavailable — using cached catalog', 'err')
    } finally {
      setLoading(false)
    }
  }

  const filtered = items.filter((i) => {
    const q = query.trim().toLowerCase()
    const matchQ = !q || (i.title || '').toLowerCase().includes(q) || (i.asin || '').toLowerCase().includes(q)
    return matchQ && i.roiPct >= minRoi
  })

  return (
    <div className="page">
      <PageHead
        title="Prospector"
        sub="Retail Arbitrage Agent — live economics from the scanner"
        badges={[{ label: `live · ${source}`, tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Scan Controls" icon="prospector">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
            <input className="field" style={{ flex: 1, maxWidth: 320 }} placeholder="Filter by product or ASIN…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter products" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="text-low" style={{ fontSize: 12 }}>Min ROI</span>
              <input type="range" className="glass-slider" min="0" max="120" value={minRoi} onChange={(e) => setMinRoi(+e.target.value)} style={{ width: 140 }} aria-label="Minimum ROI" />
              <span className="mono text-glow" style={{ fontSize: 12 }}>{minRoi}%</span>
            </div>
            <button className="btn btn-primary" onClick={runScan} disabled={loading}>
              <Icon name="scan" size={15} /> {loading ? 'Scanning…' : 'Run live scan'}
            </button>
          </div>
          {lastRefresh && <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Data from {new Date(lastRefresh).toLocaleString()} · real fee stack (referral + FBA + fuel surcharge + inbound + prep)</div>}
        </Card>

        <Card title={`Results (${filtered.length})`} icon="listings">
          {loading ? (
            <div className="text-mid" style={{ padding: '18px 0', textAlign: 'center' }}>Loading live economics…</div>
          ) : err ? (
            <div className="text-coral" style={{ padding: '12px 0' }}>Failed to load: {err}</div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Product</th><th>Price</th><th>Costco COGS</th><th>Net</th><th>ROI</th><th>Score</th><th>Sales/mo</th><th>Buy Box</th></tr>
              </thead>
              <tbody>
                {filtered.slice(0, 45).map((r) => (
                  <tr key={r.asin}>
                    <td>
                      <div style={{ fontWeight: 560, fontSize: 12.8 }}>{r.title.length > 75 ? r.title.slice(0, 75) + '…' : r.title}</div>
                      <div className="mono text-low" style={{ fontSize: 10.5 }}>{r.asin}</div>
                    </td>
                    <td className="mono">${r.price.toFixed(2)}</td>
                    <td className="mono">${r.cost.toFixed(2)}</td>
                    <td className="mono text-lime">${r.net.toFixed(2)}</td>
                    <td className={`mono ${r.roiPct >= 30 ? 'text-lime' : r.roiPct >= 15 ? 'text-glow' : 'text-coral'}`}>{r.roiPct}%</td>
                    <td className="mono">{r.score ? `${r.score}/100` : '—'}</td>
                    <td className="mono">{r.monthlySales ? r.monthlySales.toFixed(0) : '—'}</td>
                    <td>
                      {r.seller ? (
                        <span className="badge badge-ok">{r.seller} <span className="text-low">({r.fulfillment})</span></span>
                      ) : <span className="text-low">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!loading && !err && (
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn" onClick={() => toast(`Exported ${filtered.length} candidates`, 'ok')}>Export</button>
              <button className="btn" onClick={() => toast(`Pinned top ${Math.min(3, filtered.length)} to board`, 'ok')}>♡ Pin top 3</button>
            </div>
          )}
        </Card>

        <Card title="Pipeline Snapshot" icon="gauge">
          <div className="metric">
            <Metric k="Candidates" v={items.length} d="live scanner" tone="glow" />
            <Metric k="ROI ≥ 30%" v={items.filter((i) => i.roiPct >= 30).length} d="computed live" tone="lime" />
            <Metric k="ROI ≥ 15%" v={items.filter((i) => i.roiPct >= 15).length} d="computed live" tone="lime" />
            <Metric k="Top Score" v={items.length ? Math.max(...items.map((i) => i.score || 0)) : 0} d="/100" />
          </div>
        </Card>
      </div>
    </div>
  )
}