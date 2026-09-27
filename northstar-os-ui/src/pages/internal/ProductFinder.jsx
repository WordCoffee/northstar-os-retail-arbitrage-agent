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

const PRODUCTS = [
  { asin: 'B08L5VJQ7T', title: 'Premium Water Filter', brand: 'PureFlow', category: 'Home & Kitchen', price: 'UNKNOWN', rank: 14203, offers: 3, buybox: 'UNVERIFIED', margin: 'UNKNOWN', status: 'Researching', img: true },
  { asin: 'B09M8KJ4X2', title: 'LED Desk Lamp', brand: 'BrightLife', category: 'Office Products', price: '$34.99', rank: 8721, offers: 7, buybox: 'No', margin: '~18%', status: 'Watch', img: true },
  { asin: 'B07XJ8C9F3', title: 'Car Phone Mount', brand: 'TechGear', category: 'Automotive', price: 'UNKNOWN', rank: 23450, offers: 2, buybox: 'UNVERIFIED', margin: 'UNKNOWN', status: 'Researching', img: true },
  { asin: 'B08N5WRWNW', title: 'Bluetooth Speaker', brand: 'SoundMax', category: 'Electronics', price: '$29.99', rank: 5632, offers: 5, buybox: 'Yes', margin: '~12%', status: 'Internal review ready', img: true },
]

const SAVED_SETS = [
  { id: 'Set A', asins: 12, focus: 'Home & Kitchen', status: 'Active', updated: '2h ago' },
  { id: 'Set B', asins: 8, focus: 'Mixed research', status: 'Research', updated: '5h ago' },
  { id: 'Set C', asins: 15, focus: 'Internal review ready', status: 'Internal review ready', updated: '1d ago' },
]

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
  { label: 'Category / Gating', v: 'Restricted' },
  { label: 'Hazmat', v: 'Clear' },
  { label: 'IP / Brand Risk', v: 'Moderate' },
  { label: 'Amazon Presence', v: 'UNVERIFIED' },
  { label: 'Pack/Case Match', v: 'REQUIRED' },
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
  { key: 'price', label: 'Price', render: (v) => <TruthPill v={v === 'UNKNOWN' ? 'UNKNOWN' : v} /> },
  { key: 'rank', label: 'Rank', render: (v) => typeof v === 'number' ? v.toLocaleString() : v },
  { key: 'offers', label: 'Offers' },
  { key: 'buybox', label: 'Buy Box', render: (v) => v === 'UNVERIFIED' ? <TruthPill v={v} /> : v },
  { key: 'margin', label: 'Margin', render: (v) => <TruthPill v={v} /> },
  { key: 'status', label: 'Status', render: (v) => <StatusPill v={v} /> },
]

export default function ProductFinder() {
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()
  const [products] = useState(PRODUCTS)

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'set' : 'lookup')
  const primary = products[0]
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

      {view === 'lookup' && (
        <div className="subview workbench">
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
          <DataNotice tone="sample" title="Market evidence is provider-observed and cached">
            Prices marked UNKNOWN reflect unavailable data, not zero. Set contents below are sample records for interface demonstration.
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
          <DataNotice tone="sample" title="Saved sets are sample workspace state">
            Set membership and statuses are demonstration data. Verified membership requires a connected portfolio.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Saved Sets</h3>
              <span className="pill pill-forest">3 sets</span>
            </div>
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
              { area: 'Price / Offers', state: 'UNKNOWN', basis: 'Provider cache 2h ago', status: 'NOT VERIFIED' },
              { area: 'Buy Box', state: 'UNVERIFIED', basis: 'No live observation', status: 'NOT VERIFIED' },
              { area: 'Gating / Category', state: 'Restricted', basis: 'Category rules (sample)', status: 'ASSUMPTION' },
              { area: 'Pack / Case Identity', state: 'REQUIRED', basis: 'No source doc', status: 'UNKNOWN' },
              { area: 'Sourcing Legitimacy', state: 'INCOMPLETE', basis: 'No invoice on file', status: 'UNVERIFIED' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}