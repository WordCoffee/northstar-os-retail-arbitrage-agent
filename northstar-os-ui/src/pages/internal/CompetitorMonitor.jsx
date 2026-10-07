import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'

const short = (t, n = 58) => (t && t.length > n ? t.slice(0, n - 1) + '…' : t)

// ═══ Cached market observations (real read, explicitly labelled) ═══
// Derives observed price/rating/review signals from the real SourceScout cached
// catalog. This is NOT live competitor tracking — it is a cached-catalog read,
// labelled as such. Empty/unavailable states are honest.
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
        Observed price, rating and review signals from the SourceScout cached catalog. This is cached observation data, not live competitor tracking — competitor-specific rows below remain sample.
      </p>
      <MetricTiles columns={4} metrics={[
        { label: 'Tracked ASINs', value: String(items.length) },
        { label: 'With rating', value: String(rated.length), sub: 'observed ratings present' },
        { label: 'Avg observed price', value: avgPrice == null ? 'UNKNOWN' : '$' + avgPrice.toFixed(2) },
        { label: 'Total review votes', value: votesTotal.toLocaleString() },
      ]} />
      <DataTable columns={[
        { key: 'title', label: 'Observation', render: (v, row) => <span title={v}>{short(v)}</span> },
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

const TABS = [
  { id: 'landscape', label: 'Landscape', count: 8 },
  { id: 'changes', label: 'Price Changes', count: 14 },
  { id: 'watchlist', label: 'Watchlist', count: 2 },
]

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
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'landscape'

  return (
    <PageLayout
      title="Competitor Monitor"
      subtitle="Competitive context — tracked brands, price and rank movement, and new entrants."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Add Competitor — track a brand or ASIN.', 'info')}>Add Competitor</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Market Report export is sample data.', 'info')}>Market Report</button>
      </>}
    >
      <DataNotice tone="sample" title="Competitive data is observed or sample">
        Brand, price, and rank records below are demonstration data until provider observations are connected. The “Cached market observations” card is a real SourceScout cached-catalog read, labelled as cached observation — not live competitor tracking. Watchlist entries are indications, not verified market positions.
      </DataNotice>

      <CachedMarketObservations />
      <RealMarketObservations />

      <RoomTabs tabs={TABS} base="/competitor-monitor" />

      {view === 'landscape' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Competitive Landscape</h3>
              <span className="pill pill-forest">8 tracked</span>
            </div>
            <DataTable columns={[
              { key: 'brand', label: 'Brand' },
              { key: 'asin', label: 'ASIN' },
              { key: 'price', label: 'Price' },
              { key: 'rank', label: 'Rank' },
              { key: 'change', label: 'Rank Change' },
              { key: 'status', label: 'Status', render: (v) => <span className="pill pill-muted">{v}</span> },
            ]} rows={[
              { brand: 'PureFlow', asin: 'B08L5VJQ7T', price: '$49.99', rank: '#14,203', change: '↓ 234', status: 'Monitoring' },
              { brand: 'CleanMax', asin: 'B09ABC123', price: '$39.99', rank: '#8,450', change: '↑ 45', status: 'Competitive' },
              { brand: 'AquaPure', asin: 'B09DEF456', price: '$54.99', rank: '#12,890', change: '↓ 89', status: 'Watch' },
              { brand: 'HydroFresh', asin: 'B09GHI789', price: '$42.99', rank: '#15,300', change: '↑ 12', status: 'Watch' },
            ]} />
          </div>
        </div>
      )}

      {view === 'changes' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Recent Price &amp; Rank Movement</h3>
              <span className="pill pill-ochre">14 in 7 days</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>CleanMax reduced price by 8% — B09ABC123</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-26</div>
                </div>
                <span className="pill pill-warn">Price Alert</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>AquaPure launched 12-pack variation — B09DEF456</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-24</div>
                </div>
                <span className="pill pill-ochre">New Listing</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>PureFlow rank drop below #14,000 — B08L5VJQ7T</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed 2026-09-23</div>
                </div>
                <span className="pill pill-clay">Rank Drop</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'watchlist' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">New Entrants &amp; Watchlist</h3>
              <span className="pill pill-clay">2 watch</span>
            </div>
            {[
              { name: 'HydroFresh', note: 'New entrant entering category — monitor pricing strategy', state: 'Watch' },
              { name: 'AquaPure 12-pack', note: 'Variation launch — watch conversion impact', state: 'Watch' },
            ].map(c => (
              <div key={c.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{c.note}</div>
                </div>
                <span className="pill pill-ochre">{c.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  )
}