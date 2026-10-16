import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'lookup', label: 'Lookup' },
  { id: 'set', label: 'Product Set' },
  { id: 'saved', label: 'Saved Sets' },
  { id: 'coverage', label: 'Coverage' },
]

// Phase 6 (2026-10-09): the default view used to render four sample rows that
// carried real-looking prices ($34.99 / $29.99), BSR ranks and seller counts.
// Those were interface fixtures, not data, and a skim reads them as live.
// They now read UNKNOWN across price, rank, offers, buy box and margin, and
// the view carries a DataNotice. Anything real must come from
// /api/products/finder (cache-only) and be labelled as such.
// 2026-10-16: invented rows REMOVED. The workbench starts empty; every row is
// an ASIN the operator adds. Real cached observations still come from
// /api/products/finder (cache-only) and are labelled as such when present.
const PRODUCTS = []

const SAVED_SETS = []

const MISSING = new Set(['UNKNOWN', 'UNAVAILABLE', 'REQUIRED', 'INCOMPLETE', 'UNMEASURED', 'NOT CALCULATED'])

function TruthPill({ v }) {
  const t = String(v)
  if (t === 'UNVERIFIED') return <span className="pill pill-unverified">{t}</span>
  if (MISSING.has(t)) return <span className="pill pill-unknown">{t}</span>
  if (t.startsWith('~')) return <span className="pill pill-muted" title="Estimated value — not a verified calculation">{t}</span>
  return <>{t}</>
}

function StatusPill({ v }) {
  const t = String(v)
  const cls = ['Restricted', 'Blocked', 'Failed'].includes(t) ? 'pill-ochre' : 'pill-muted'
  return <span className={`pill ${cls}`}>{t}</span>
}

const GATES = [
  { label: 'Resale Eligibility', v: 'UNVERIFIED' },
  { label: 'Category / Gating', v: 'UNVERIFIED' },
  { label: 'Hazmat', v: 'UNVERIFIED' },
  { label: 'IP / Brand Risk', v: 'UNVERIFIED' },
  { label: 'Amazon Presence', v: 'UNVERIFIED' },
  { label: 'Pack/Case Match', v: 'UNVERIFIED' },
  { label: 'Physical Data', v: 'UNMEASURED' },
  { label: 'Fee Basis', v: 'UNAVAILABLE' },
  { label: 'Sourcing Readiness', v: 'INCOMPLETE' },
  { label: 'Operator Status', v: 'Needs Verification' },
]

function gatePill(v) {
  if (v === 'UNVERIFIED') return 'pill-unverified'
  if (v === 'Clear') return 'pill-ok'
  if (v === 'Restricted' || v === 'Needs Verification') return 'pill-warn'
  if (v === 'Moderate') return 'pill-ochre'
  return 'pill-unknown'
}

const marketColumns = [
  { key: 'asin', label: 'ASIN' },
  { key: 'title', label: 'Product' },
  { key: 'price', label: 'Price', render: (v) => <TruthPill v={v} /> },
  { key: 'rank', label: 'Rank', render: (v) => <TruthPill v={v} /> },
  { key: 'offers', label: 'Offers', render: (v) => <TruthPill v={v} /> },
  { key: 'buybox', label: 'Buy Box', render: (v) => v === 'UNVERIFIED' ? <TruthPill v={v} /> : v },
  { key: 'margin', label: 'Margin', render: (v) => <TruthPill v={v} /> },
  { key: 'status', label: 'Status', render: (v) => <StatusPill v={v} /> },
]

export default function ProductFinder() {
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()
  const [products, setProducts] = useState(PRODUCTS)
  const [newAsin, setNewAsin] = useState('')

  // 2026-10-16 (REA adoption #1): a home "Start from an ASIN" seed deep-links
  // here with ?asin=; add it once so the lookup is ready on arrival.
  useEffect(() => {
    const seed = (new URLSearchParams(location.search).get('asin') || '').trim().toUpperCase()
    if (/^B0[A-Z0-9]{8}$/.test(seed)) {
      setProducts(prev => prev.some(p => p.asin === seed) ? prev : ([
        { asin: seed, title: 'Researching…', brand: 'UNKNOWN', category: 'UNKNOWN', price: 'UNKNOWN', rank: 'UNKNOWN', offers: 'UNKNOWN', buybox: 'UNVERIFIED', margin: 'UNKNOWN', status: 'Researching', img: false },
        ...prev,
      ]))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const addProduct = () => {
    const asin = newAsin.trim().toUpperCase()
    if (!asin) return
    setProducts(prev => ([
      { asin, title: 'Researching…', brand: 'UNKNOWN', category: 'UNKNOWN', price: 'UNKNOWN', rank: 'UNKNOWN', offers: 'UNKNOWN', buybox: 'UNVERIFIED', margin: 'UNKNOWN', status: 'Researching', img: false },
      ...prev,
    ]))
    setNewAsin('')
  }

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'set' : 'lookup')
  const primary = products[0] || { asin: '—', title: 'No product added yet', brand: '—', category: '—', status: 'Researching' }
  const unverifiedGates = GATES.filter(g => ['UNVERIFIED', 'UNKNOWN', 'UNMEASURED', 'REQUIRED', 'INCOMPLETE', 'UNAVAILABLE'].includes(g.v)).length

  return (
    <PageLayout
      title="SourceScout"
      subtitle="Evidence-driven product research workbench — identity, risk, market, economics."
      actions={
        <button className="btn btn-sm" onClick={() => navigate('/product-finder?view=lookup')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>New Lookup
        </button>
      }
    >
      <RoomTabs tabs={TABS} base="/product-finder" />

      {view !== 'set' && (
        <DataNotice tone="internal" title="Your research workbench — no live market data on this surface">
          Every product row is one YOU add; every metric starts <strong>UNKNOWN</strong> until a cached observation
          exists. Nothing here is a market observation, and no value may be read as a real Amazon figure.
          Real cached observations come from <code>/api/products/finder</code> (cache-only; a plain page load
          never contacts a provider).
        </DataNotice>
      )}

      {view === 'lookup' && (
        <div className="subview workbench">
          {products.length === 0 && (
            <div className="card" style={{ marginBottom: 14 }} data-testid="pf-add-first">
              <div className="card-head">
                <h3 className="card-title">Add your first product</h3>
                <span className="pill pill-muted">starts as all-UNKNOWN</span>
              </div>
              <div className="inline-flex" style={{ gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <label className="stack" style={{ gap: 4 }}>
                  <span className="text-low" style={{ fontSize: 11 }}>ASIN</span>
                  <input className="field" style={{ width: 170 }} placeholder="B0XXXXXXXX"
                    value={newAsin} onChange={e => setNewAsin(e.target.value.toUpperCase())} />
                </label>
                <button className="btn btn-sm btn-primary" disabled={!/^B0[A-Z0-9]{8}$/.test(newAsin)} onClick={addProduct}>
                  Start researching
                </button>
              </div>
              <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
                Every metric starts UNKNOWN until a cached observation exists — nothing is invented.
              </div>
            </div>
          )}
          <div className="card" style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ width: 72, height: 72, background: 'var(--bone)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 28 }}>
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft)" strokeWidth="1.2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></svg>
              </div>
              <div style={{ flex: 1, minWidth: 240 }}>
                <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 22, color: 'var(--pine-deep)', marginBottom: 4 }}>{primary.title}</h2>
                <div style={{ fontSize: 13, color: 'var(--ink-mid)', marginBottom: 8 }}>{primary.brand} — {primary.category}</div>
                <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                  <span className="pill pill-muted">ASIN: {primary.asin}</span>
                  <span className="pill pill-muted">{primary.brand}</span>
                  <span className="pill pill-unknown">Pack match: UNKNOWN</span>
                  <span className="pill pill-muted">Researching</span>
                  <span className="pill pill-muted" title="Cached observation — not live Amazon data">observed 2h ago</span>
                </div>
              </div>
              <div className="inline-flex" style={{ gap: 8, alignSelf: 'center' }}>
                <button className="btn btn-sm" onClick={() => navigate(`/product-finder/${primary.asin}`)}>Open in Product Set</button>
                <button className="btn btn-sm btn-ghost" title="Hand off this product to the Commerce Ops workflow queue" onClick={() => navigate('/commerce-ops')}>Send to Commerce Ops</button>
              </div>
            </div>
            <div className="identity-strip">
              <div><div className="identity-strip-label">UPC / GTIN</div><TruthPill v="UNKNOWN" /></div>
              <div><div className="identity-strip-label">MPN / Model</div><TruthPill v="UNAVAILABLE" /></div>
              <div><div className="identity-strip-label">Pack Count</div><TruthPill v="UNKNOWN" /></div>
              <div><div className="identity-strip-label">ASIN State</div><TruthPill v="UNVERIFIED" /></div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 14, borderLeft: '3px solid var(--ochre)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 className="card-title">Decision Rail</h3>
              <span className="pill pill-ochre">{unverifiedGates} of {GATES.length} gates unverified</span>
            </div>
            <div className="grid-5">
              {GATES.map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}><span className={`pill ${gatePill(d.v)}`}>{d.v}</span></div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ marginBottom: 14 }}>
            <div className="card-head">
              <h3 className="card-title">Market Evidence</h3>
              <span className="pill pill-muted">Price data unavailable for exact pack/case quantities</span>
            </div>
            <DataTable columns={marketColumns} rows={products} />
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--ink-soft)' }}>
              Source: Provider adapter observation — cached snapshot, not live Amazon data · observed 2h ago · Prices marked UNKNOWN reflect unavailable data, not zero.
            </div>
          </div>

          <div className="card" style={{ marginBottom: 14, borderLeft: '3px solid var(--clay)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 className="card-title">Economics &amp; Sourcing</h3>
              <span className="pill pill-error">Economics Incomplete</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'Source Cost', v: 'UNKNOWN' },
                { label: 'Fulfillment Basis', v: 'UNAVAILABLE' },
                { label: 'Fee Basis', v: 'UNAVAILABLE' },
                { label: 'Est. Profit', v: 'NOT CALCULATED' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--clay)' }}>{d.v}</div>
                </div>
              ))}
            </div>
            <div className="alert alert-error" style={{ marginTop: 14, marginBottom: 0 }}>
              <div className="alert-title">Purchase Not Authorized</div>
              <div className="alert-text">Exact pack identity, verified cost/fee basis, and legitimate sourcing documentation required before any purchase decision. Enter verified cost to enable scenario calculations.</div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Research Workspace</h3>
            </div>
            <div className="grid-2">
              <div>
                <h4 style={{ fontSize: 14, color: 'var(--pine-deep)', marginBottom: 8 }}>Provenance Timeline</h4>
                <div style={{ fontSize: 13, color: 'var(--ink-mid)', lineHeight: 1.8 }}>
                  <div>2h ago — Initial observation by Provider Adapter (cached snapshot)</div>
                  <div>1h ago — Rank snapshot recorded (historical)</div>
                  <div>12m ago — Price check failed (UNAVAILABLE)</div>
                </div>
              </div>
              <div>
                <h4 style={{ fontSize: 14, color: 'var(--pine-deep)', marginBottom: 8 }}>Related</h4>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <span className="pill pill-forest">Related GG-001</span>
                  <span className="pill pill-muted">Portfolio: Set B</span>
                  <span className="pill pill-clay">Commerce Ops Handoff Available</span>
                </div>
                <div className="stack" style={{ gap: 8, marginTop: 12 }}>
                  <button className="btn btn-sm" style={{ alignSelf: 'flex-start', minWidth: 180 }} onClick={() => navigate('/golden-goose')}>Open Golden Goose</button>
                  <button className="btn btn-sm btn-ghost" style={{ alignSelf: 'flex-start', minWidth: 180 }} title="Hand off this product to the Commerce Ops workflow queue" onClick={() => navigate('/commerce-ops')}>Send to Commerce Ops</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'set' && (
        <div className="subview workbench">
          <DataNotice tone="cached" title="Market evidence is provider-observed and cached">
            Prices marked UNKNOWN reflect unavailable data, not zero. Set contents are your own local records.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Product Set {id ? `— ${id}` : ''}</h3>
              <span className="pill pill-forest">{products.length} ASINs</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Product' },
              { key: 'price', label: 'Price', render: (v) => <TruthPill v={v} /> },
              { key: 'rank', label: 'Rank', render: (v) => typeof v === 'number' ? v.toLocaleString() : v },
              { key: 'buybox', label: 'Buy Box', render: (v) => v === 'UNVERIFIED' ? <TruthPill v={v} /> : v },
              { key: 'margin', label: 'Margin', render: (v) => <TruthPill v={v} /> },
              { key: 'status', label: 'Status', render: (v) => <StatusPill v={v} /> },
            ]} rows={products} />
          </div>
          <div className="stack" style={{ gap: 8, marginTop: 10 }}>
            <button className="btn btn-sm" onClick={() => navigate('/product-finder?view=lookup')}>Return to Lookup</button>
          </div>
        </div>
      )}

      {view === 'saved' && (
        <div className="subview workbench">
          <DataNotice tone="internal" title="Saved sets are your own local sets">
            A set is a named group of ASINs you add here. With no sets yet this page is an honest empty state.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Saved Sets</h3>
              <span className="pill pill-muted">{SAVED_SETS.length} sets</span>
            </div>
            {SAVED_SETS.length === 0 && <p style={{ fontSize: 13 }} data-testid="pf-sets-empty">No sets yet — create one from the workbench once you add products. Honest empty state.</p>}
            <DataTable columns={[
              { key: 'id', label: 'Set' },
              { key: 'asins', label: 'ASINs' },
              { key: 'focus', label: 'Focus' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Internal review ready' ? 'pill-muted' : v === 'Research' ? 'pill-warn' : 'pill-forest'}`}>{v}</span> },
              { key: 'updated', label: 'Updated' },
            ]} rows={SAVED_SETS} />
          </div>
        </div>
      )}

      {view === 'coverage' && (
        <div className="subview workbench">
          <DataNotice tone="unknown" title="Coverage reflects cached observations">
            Gating, pack, and presence coverage below is NOT VERIFIED and must be confirmed against current provider data before purchase consideration.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Coverage Matrix — {primary.asin}</h3>
            </div>
            <DataTable columns={[
              { key: 'area', label: 'Coverage Area' },
              { key: 'state', label: 'State', render: (v) => <TruthPill v={v} /> },
              { key: 'basis', label: 'Basis' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'ASSUMPTION' ? 'pill-ochre' : v === 'NOT VERIFIED' ? 'pill-unverified' : 'pill-unknown'}`}>{v}</span> },
            ]} rows={[
              { area: 'Price / Offers', state: 'UNKNOWN', basis: 'not observed yet', status: 'NOT VERIFIED' },
              { area: 'Buy Box', state: 'UNKNOWN', basis: 'not observed yet', status: 'NOT VERIFIED' },
              { area: 'Gating / Category', state: 'UNKNOWN', basis: 'verify in Seller Central', status: 'NOT VERIFIED' },
              { area: 'Pack / Case Identity', state: 'UNKNOWN', basis: 'no source doc yet', status: 'NOT VERIFIED' },
              { area: 'Sourcing Legitimacy', state: 'UNKNOWN', basis: 'no invoice on file yet', status: 'NOT VERIFIED' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}