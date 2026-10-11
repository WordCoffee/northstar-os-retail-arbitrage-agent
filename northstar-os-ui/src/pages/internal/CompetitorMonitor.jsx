import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'
import MasterBrainPanel from '../../studio/components/MasterBrainPanel.jsx'

const short = (t, n = 58) => (t && t.length > n ? t.slice(0, n - 1) + '…' : t)

// ═══ Cached market observations (real SourceScout catalog read) ═══
function CachedMarketObservations() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.sourceScout()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error' })
    })
    return () => { alive = false }
  }, [])
  if (st.phase === 'loading') {
    return <div className="card" data-testid="cm-cached-market" style={{ marginBottom: 20 }}><p style={{ fontSize: 13 }}>Loading cached market observations…</p></div>
  }
  if (st.phase !== 'loaded') {
    return (
      <div className="card" data-testid="cm-cached-market" style={{ marginBottom: 20 }}>
        <div className="card-head"><h3 className="card-title">Cached market observations</h3><span className="pill pill-unknown">unavailable</span></div>
        <p className="text-low" style={{ fontSize: 12 }}>SourceScout cached catalog could not be read. No observations are fabricated.</p>
      </div>
    )
  }
  const items = st.items
  const rated = items.filter(i => i.rating && i.rating.value != null)
  const votesTotal = rated.reduce((s, i) => s + (i.rating.votes_count || 0), 0)
  const prices = items.map(i => i.price).filter(p => typeof p === 'number')
  const avgPrice = prices.length ? (prices.reduce((a, b) => a + b, 0) / prices.length) : null
  const top = [...rated].sort((a, b) => (b.rating.votes_count || 0) - (a.rating.votes_count || 0)).slice(0, 6)
  return (
    <div className="card" data-testid="cm-cached-market" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Cached market observations</h3>
        <span className="pill pill-muted" title="Observed SourceScout cached catalog — not live competitor tracking">cached catalog · observed</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Observed price, rating and review signals from the SourceScout cached catalog. This is cached observation data, not live competitor tracking.
      </p>
      <MetricTiles columns={4} metrics={[
        { label: 'Tracked ASINs', value: String(items.length) },
        { label: 'With rating', value: String(rated.length), sub: 'observed ratings present' },
        { label: 'Avg observed price', value: avgPrice == null ? 'UNKNOWN' : '$' + avgPrice.toFixed(2) },
        { label: 'Total review votes', value: votesTotal.toLocaleString() },
      ]} />
      <DataTable columns={[
        { key: 'title', label: 'Observation', render: (v) => <span title={v}>{short(v)}</span> },
        { key: 'price', label: 'Observed Price', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : '$' + Number(v).toFixed(2) },
        { key: 'rating', label: 'Rating', render: (v, row) => row.rating && row.rating.value != null
          ? <span className="pill pill-muted" title={`${row.rating.votes_count || 0} votes`}>{row.rating.value}</span>
          : <span className="pill pill-unknown">UNKNOWN</span> },
        { key: 'votes', label: 'Votes', render: (v, row) => row.rating && row.rating.votes_count != null ? (row.rating.votes_count).toLocaleString() : <span className="pill pill-unknown">UNKNOWN</span> },
        { key: 'quantity_match', label: 'Quantity Match', render: (v) => <span className={`pill ${v && v.status === 'PASS' ? 'pill-ok' : v && v.status === 'FAIL' ? 'pill-warn' : 'pill-ochre'}`}>{v ? v.status : 'UNKNOWN'}</span> },
      ]} rows={top} />
    </div>
  )
}

// ═══ Real local market observations (products + costco source products) ═══
function RealMarketObservations() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncCompetitorObservations()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const items = v && Array.isArray(v.items) ? v.items : []
  const s = (v && v.summary) || {}
  const src = s.source_products && Array.isArray(s.source_products) ? s.source_products.slice(0, 8) : []
  return (
    <div className="card" data-testid="cm-real-observations" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Local market observations</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${items.length} products · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Market observations unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <span className="pill pill-muted">{s.products ?? 0} products</span>
            <span className="pill pill-muted">{s.source_products?.length ?? 0} source products</span>
            <span className="pill pill-muted">{s.distinct_brands ?? 0} brands</span>
            <span className="pill pill-muted">avg source price: {s.source_avg_price == null ? 'UNKNOWN' : '$' + s.source_avg_price}</span>
          </div>
          {items.length > 0 ? (
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Product', render: (x) => <span title={x}>{x && x.length > 42 ? x.slice(0, 41) + '…' : x}</span> },
              { key: 'brand', label: 'Brand', render: (x) => x || 'UNKNOWN' },
              { key: 'amazon_price', label: 'Amazon', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : '$' + Number(x).toFixed(2) },
              { key: 'costco_cost', label: 'Costco', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : '$' + Number(x).toFixed(2) },
              { key: 'roi_pct', label: 'ROI', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{x}%</span> },
            ]} rows={items.slice(0, 25)} />
          ) : <p className="text-low" style={{ fontSize: 13 }}>No local product observations. Honest empty state.</p>}
          {src.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Recent source products (Costco)</div>
              <div className="stack" style={{ gap: 4 }}>
                {src.map((r, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }} title={r.title_normalized}>{r.costco_item_number} · {(r.brand_normalized || 'UNKNOWN')}</span>
                    <span className="pill pill-muted">{r.costco_price == null ? 'UNKNOWN' : '$' + Number(r.costco_price).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Real local catalog/market records (read-only). Not live competitor tracking.</div>
        </>
      )}
    </div>
  )
}

export default function CompetitorMonitor() {
  const { toast } = useToast()
  return (
    <PageLayout
      title="Competitor Monitor"
      subtitle="Competitive context from real local catalog and market observations — not live competitor tracking."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Tracking a live competitor requires a connected provider — gated.', 'info')}>Add Competitor</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Market Report uses local catalog data.', 'info')}>Market Report</button>
      </>}
    >
      <DataNotice tone="internal" title="Real local market observations">
        Both panels are real local reads (SourceScout cached catalog + local product/source records). This is observation data, not live competitor tracking — no fabricated brands or ranks.
      </DataNotice>
      <CachedMarketObservations />
      <RealMarketObservations />
    <MasterBrainPanel title="Studio evidence for market observations (read-only)" />
    </PageLayout>
  )
}
