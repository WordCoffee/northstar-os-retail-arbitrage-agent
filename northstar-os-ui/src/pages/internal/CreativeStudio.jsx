import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'briefs', label: 'Briefs', count: 3 },
  { id: 'variants', label: 'Variants' },
  { id: 'assets', label: 'Assets' },
  { id: 'exports', label: 'Exports' },
  { id: 'library', label: 'Library' },
]

const BRIEFS = [
  { id: 'BR-01', name: 'Set A Launch — Ad Creatives', objective: 'Drive awareness', audience: 'Homeowners 30–55', formats: ['Ad creative', 'Social variant', 'Listing imagery'], deliverables: 6, status: 'Active', tone: 'pill-warn' },
  { id: 'BR-02', name: 'Q4 Seasonal Bundle', objective: 'Seasonal promo', audience: 'Existing customers', formats: ['Social variant', 'Email hero'], deliverables: 4, status: 'Draft', tone: 'pill-muted' },
  { id: 'BR-03', name: 'Installation Guide Refresh', objective: 'Support conversion', audience: 'New buyers', formats: ['Listing imagery', 'A+ content'], deliverables: 3, status: 'In Review', tone: 'pill-ochre' },
]

const VARIANTS = [
  { id: 'V-101', brief: 'Set A Launch', format: 'Ad creative', aspect: '1:1', state: 'Approved', note: 'Hero + feature, matched brand kit' },
  { id: 'V-102', brief: 'Set A Launch', format: 'Ad creative', aspect: '4:5', state: 'In Review', note: 'Alt crop — awaiting brand reviewer' },
  { id: 'V-103', brief: 'Set A Launch', format: 'Social variant', aspect: '9:16', state: 'Draft', note: 'Reel hook frame, revision note: tighten headline' },
  { id: 'V-104', brief: 'Q4 Seasonal', format: 'Social variant', aspect: '1:1', state: 'Draft', note: 'Seasonal palette, no copy yet' },
  { id: 'V-105', brief: 'Installation Guide', format: 'Listing imagery', aspect: '16:9', state: 'Approved', note: 'Step-by-step panel 1 of 3' },
  { id: 'V-106', brief: 'Installation Guide', format: 'Listing imagery', aspect: '16:9', state: 'Changes Requested', note: 'Revision: swap diagram labels' },
]

const ASSETS = [
  { name: 'brand-kit-logos.svg', type: 'Brand', collection: 'Brand kit', state: 'Approved' },
  { name: 'product-photo-01.jpg', type: 'Photo', collection: 'Product photography', state: 'Approved' },
  { name: 'ad-creative-hero.jpg', type: 'Ad', collection: 'Ad creatives', state: 'In Review' },
  { name: 'variant-bg-q4.jpg', type: 'Ad', collection: 'Ad creatives', state: 'Draft' },
  { name: 'aplus-banner-01.jpg', type: 'A+', collection: 'Listing imagery', state: 'Approved' },
  { name: 'packshot-angle-02.jpg', type: 'Photo', collection: 'Product photography', state: 'UNREVIEWED' },
]

const COLLECTIONS = [
  { name: 'Brand kit', count: 24, note: 'Logos, type, colour, tone' },
  { name: 'Product photography', count: 38, note: 'Studio + lifestyle shots' },
  { name: 'Ad creatives', count: 17, note: 'Static + video ad frames' },
  { name: 'Listing imagery', count: 8, note: 'A+ content + main-image sets' },
]

const EXPORT_OUTPUTS = ['Ad creatives', 'Social variants', 'Listing imagery']

const VAR_STATE_PILL = { Approved: 'pill-muted', 'In Review': 'pill-warn', Draft: 'pill-muted', 'Changes Requested': 'pill-ochre' }

export default function CreativeStudio() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [brief, setBrief] = useState('Set A Launch — Ad Creatives')
  const [assetFilter, setAssetFilter] = useState('All')
  const [outputs, setOutputs] = useState(['Ad creatives', 'Listing imagery'])

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'briefs'

  const go = (t) => navigate(`/creative-studio?view=${t}`)
  const t = (msg, tone = 'info') => toast(msg, tone)
  const active = BRIEFS.find(b => b.name === brief) || BRIEFS[0]
  const toggleOutput = (o) => setOutputs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o])

  return (
    <PageLayout
      title="Creative Studio"
      subtitle="Creative workshop — briefs, variant sets, asset trays, and export bundles for ads, social, and listings."
      actions={<>
        <button className="btn btn-sm" onClick={() => t('New brief opened (sample).', 'info')}>New Brief</button>
        <button className="btn btn-sm btn-ghost" onClick={() => t('Variant generation runs against the active brief (sample).', 'info')}>Generate Variants</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('exports')}>Export Bundle</button>
      </>}
    >
      <DataNotice tone="sample" title="Creative records are sample data">
        Briefs, variants, and asset counts are demonstration records until a creative backend is connected. Approval states are internal review states — not publishing or purchase authorization.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="text-low" style={{ fontSize: 11 }}>Active brief</span>
          {BRIEFS.map(b => (
            <button key={b.id} className={`filter-pill ${brief === b.name ? 'active' : ''}`} onClick={() => setBrief(b.name)} title={`${b.objective} · ${b.status}`}>{b.name}</button>
          ))}
          <span className={`pill ${active.tone}`} style={{ marginLeft: 'auto' }}>{active.status}</span>
        </div>
      </div>

      <RoomTabs tabs={TABS} base="/creative-studio" />

      {view === 'briefs' && (
        <div className="subview">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 20 }}>
            {BRIEFS.map(b => (
              <div key={b.id} className="card" style={{ padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: 13 }}>{b.name}</strong>
                  <span className={`pill ${b.tone}`}>{b.status}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--ink-mid)', marginBottom: 8 }}>{b.objective} · {b.audience}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  {b.formats.map(f => <span key={f} className="pill pill-muted" style={{ fontSize: 10 }}>{f}</span>)}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="text-low" style={{ fontSize: 11 }}>{b.deliverables} deliverables</span>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setBrief(b.name); go('variants') }}>Open</button>
                </div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Brief — {active.name}</h3>
              <span className={`pill ${active.tone}`}>{active.status}</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'Objective', v: active.objective },
                { label: 'Audience', v: active.audience },
                { label: 'Formats', v: active.formats.join(', ') },
                { label: 'Deliverables', v: `${active.deliverables} assets` },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{d.v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {view === 'variants' && (
        <div className="subview">
          <div className="room-toolbar">
            <span className="pill pill-muted" style={{ marginRight: 'auto' }}>{active.name} · {VARIANTS.length} variants · sample</span>
            <button className="btn btn-sm" onClick={() => t('Variant added to the set (sample).', 'info')}>Add Variant</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
            {VARIANTS.map(v => (
              <div key={v.id} className="card" style={{ padding: 12 }}>
                <div style={{ height: 110, borderRadius: 6, background: 'linear-gradient(135deg, rgba(196,148,26,0.10), rgba(138,138,122,0.10))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>
                  {v.aspect} · {v.format}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: 12 }}>{v.id}</strong>
                  <span className={`pill ${VAR_STATE_PILL[v.state] || 'pill-muted'}`} style={{ fontSize: 10 }} title="Internal review state">{v.state}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginBottom: 8 }}>{v.note}</div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Variant opened for revision (sample).', 'info')}>Revise</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Variant sent for approval (sample).', 'info')}>Approve</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'assets' && (
        <div className="subview">
          <div className="room-toolbar">
            {['All', 'Brand', 'Photo', 'Ad', 'A+'].map(f => (
              <button key={f} className={`filter-pill ${assetFilter === f ? 'active' : ''}`} onClick={() => setAssetFilter(f)}>{f}</button>
            ))}
            <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={() => t('Upload accepts images, video, and A+ blocks (sample).', 'info')}>Upload Asset</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
            {ASSETS.filter(a => assetFilter === 'All' || a.type === assetFilter).map(a => (
              <div key={a.name} className="card" style={{ padding: 12 }}>
                <div style={{ height: 90, borderRadius: 6, background: 'linear-gradient(135deg, rgba(138,138,122,0.10), rgba(45,106,45,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>
                  {a.type} asset
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>{a.name}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.collection}</span>
                  {a.state === 'Approved'
                    ? <span className="pill pill-muted" style={{ fontSize: 10 }} title="Internal review state — not an authorization">{a.state}</span>
                    : a.state === 'UNREVIEWED'
                      ? <span className="pill pill-unknown" style={{ fontSize: 10 }}>{a.state}</span>
                      : <span className="pill pill-warn" style={{ fontSize: 10 }}>{a.state}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'exports' && (
        <div className="subview">
          <DataNotice tone="internal" title="Export bundles are prepared, not published">
            Bundles package existing creative for handoff to SocialPulse or ListingForge. Nothing is published or listed from here.
          </DataNotice>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20, alignItems: 'start' }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Bundle Builder — {active.name}</h3>
              </div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Select outputs</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                {EXPORT_OUTPUTS.map(o => (
                  <button key={o} className={`filter-pill ${outputs.includes(o) ? 'active' : ''}`} onClick={() => toggleOutput(o)}>{o}</button>
                ))}
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {[
                  { item: 'Ad creatives (4 variants)', basis: 'approved' },
                  { item: 'Listing imagery (3 panels)', basis: 'in review' },
                  { item: 'Social variants (2)', basis: 'draft' },
                ].map(r => (
                  <div key={r.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{r.item}</div>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{r.basis}</span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm" onClick={() => t('Bundle prepared — review before handoff.', 'info')}>Prepare Export</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/socialpulse'); t('Bundle handed to SocialPulse — uncertainty preserved.', 'info') }}>Send to SocialPulse</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/listingforge'); t('Bundle handed to ListingForge — uncertainty preserved.', 'info') }}>Send to ListingForge</button>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Bundle Preview</h3>
                <span className="pill pill-muted">{outputs.length} outputs</span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {outputs.length ? outputs.map(o => <span key={o} className="pill pill-muted" style={{ fontSize: 10 }}>{o}</span>) : <span className="text-low" style={{ fontSize: 11 }}>No outputs selected</span>}
              </div>
              <div style={{ height: 120, borderRadius: 6, background: 'linear-gradient(135deg, rgba(196,148,26,0.10), rgba(45,106,45,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)' }}>
                collection preview
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'library' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Creative Collections</h3>
              <span className="pill pill-muted">brand library · sample</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
              {COLLECTIONS.map(c => (
                <div key={c.name} className="card" style={{ padding: 14 }}>
                  <div style={{ height: 72, borderRadius: 6, background: 'linear-gradient(135deg, rgba(45,106,45,0.10), rgba(196,148,26,0.10))', marginBottom: 10 }} />
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{c.name}</div>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>{c.note}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{c.count} items</span>
                    <button className="btn btn-sm btn-ghost" onClick={() => t(`${c.name} collection opened (sample).`, 'info')}>Open</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
