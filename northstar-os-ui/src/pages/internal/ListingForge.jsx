import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useNavigate, useLocation } from 'react-router-dom'

const TABS = [
  { id: 'listings', label: 'Listings', count: 24 },
  { id: 'editor', label: 'Editor' },
  { id: 'templates', label: 'Templates' },
  { id: 'assets', label: 'Assets' },
  { id: 'revisions', label: 'Revision Log' },
]

const LISTINGS = [
  { asin: 'B08L5VJQ7T', title: 'Premium Water Filter', status: 'Revision v3.2', health: 82, updated: '2h ago' },
  { asin: 'B09M8KJ4X2', title: 'LED Desk Lamp', status: 'Live', health: 88, updated: '1d ago' },
  { asin: 'B07XJ8C9F3', title: 'Car Phone Mount', status: 'Draft', health: 61, updated: '3d ago' },
  { asin: 'B08N5WRWNW', title: 'Bluetooth Speaker', status: 'Live', health: 79, updated: '4d ago' },
]

const TEMPLATES = [
  { name: 'Standard Launch', desc: 'Balanced title, 5 bullets, mid-length description.', use: 'Best for established categories' },
  { name: 'Premium', desc: 'Serif-forward, story-driven description, lifestyle bullets.', use: 'Best for higher-margin private label' },
  { name: 'Bulk / Wholesale', desc: 'Spec-dense, pack-focused, compliance-heavy.', use: 'Best for multi-pack and B2B' },
]

export default function ListingForge() {
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'listings'

  return (
    <PageLayout
      title="ListingForge"
      subtitle="Listing studio — titles, bullets, descriptions, keyword coverage, media, health."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/listingforge?view=editor')}>Create Listing</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/listingforge?view=templates')}>Templates</button>
      </>}
    >
      <DataNotice tone="sample" title="Listing health and revision state is sample data">
        Counts below (24 active listings, health scores) are demonstration values. Real health scoring requires connected listing data.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/listingforge" />

      {view === 'listings' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Listings</h3>
              <span className="pill pill-forest">24 across 6 ASINs</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Listing' },
              { key: 'status', label: 'Status' },
              { key: 'health', label: 'Health', render: (v, row) => <span className={`pill ${row.status === 'Draft' ? 'pill-warn' : 'pill-muted'}`} title="Sample health score — not a verified calculation">{v}/100</span> },
              { key: 'updated', label: 'Updated', render: (v) => <span className="pill pill-muted" title="Provenance stamp — sample revision state, not live listing data">{v} · sample</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/listingforge?view=editor`)}>Edit</button> },
            ]} rows={LISTINGS} />
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Studio Snapshot</h3>
              <span className="pill pill-muted">Basis: sample data</span>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Revisions in progress</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--ochre)' }}>2</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }} title="Sample workflow state">Water Filter v3.2 · Speaker v1.4</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Drafts awaiting health check</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--clay)' }}>1</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }} title="Sample workflow state">Car Phone Mount — REQUIRED</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Publish-ready (reviewed)</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine)' }}>2 of 4</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }} title="Internal review state — not an authorization to publish">Internal review ready</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'editor' && (
        <div className="subview">
          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Current Listing — Premium Water Filter</h3>
                <span className="pill pill-warn">Revision v3.2</span>
              </div>
              <div className="stack" style={{ gap: 16 }}>
                <div>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Title</div>
                  <input className="field" style={{ width: '100%' }} defaultValue="Premium Water Filter — 3-Stage Filtration, 10-Cup Capacity, BPA-Free" />
                </div>
                <div>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Bullet Points</div>
                  <div style={{ fontSize: 13, color: 'var(--ink-mid)', lineHeight: 1.8 }}>
                    <div>1. 3-Stage Filtration: Removes 99.9% of contaminants</div>
                    <div>2. 10-Cup Capacity: Ideal for families of 4+</div>
                    <div>3. BPA-Free Materials: FDA-certified safe</div>
                    <div>4. Easy-Change Filters: No tools required</div>
                    <div>5. Compact Design: Fits most standard cabinets</div>
                  </div>
                </div>
                <div>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Description</div>
                  <textarea className="field" rows={3} style={{ width: '100%', resize: 'vertical' }} defaultValue="Experience clean, great-tasting water with the Premium Water Filter. Designed for modern kitchens, our 3-stage filtration system ensures your family has access to safe, great-tasting water every day." />
                </div>
                <div className="inline-flex" style={{ gap: 8 }}>
                  <button className="btn btn-sm">Save Revision</button>
                  <button className="btn btn-sm btn-ghost">Request Health Check</button>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Keyword Coverage</h3>
                <span className="pill pill-forest">68% matched</span>
              </div>
              <DataTable columns={[
                { key: 'term', label: 'Search Term' },
                { key: 'rank', label: 'Rank' },
                { key: 'coverage', label: 'Coverage' },
                { key: 'status', label: 'Status' },
              ]} rows={[
                { term: 'water filter', rank: 14, coverage: 'Matched', status: 'Good' },
                { term: 'water purifier', rank: 32, coverage: 'Partial', status: 'Weak' },
                { term: 'countertop filter', rank: 8, coverage: 'Matched', status: 'Good' },
                { term: 'BPA free filter', rank: 45, coverage: 'Missing', status: 'Gap' },
                { term: 'family water filter', rank: 21, coverage: 'Partial', status: 'Weak' },
              ]} />
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Listing Health</h3>
              <span className="pill pill-forest">Score: 82/100</span>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Title Optimization</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--pine)' }}>92%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className="meter-fill meter-fill-forest" style={{ width: '92%' }}></div></div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Bullet Coverage</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ochre)' }}>76%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className="meter-fill meter-fill-ochre" style={{ width: '76%' }}></div></div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Description Quality</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--pine)' }}>88%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className="meter-fill meter-fill-forest" style={{ width: '88%' }}></div></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'templates' && (
        <div className="subview">
          <div className="grid-3">
            {TEMPLATES.map(t => (
              <div key={t.name} className="card">
                <h3 className="card-title" style={{ fontSize: 16 }}>{t.name}</h3>
                <div style={{ fontSize: 13, color: 'var(--ink-mid)', marginTop: 8, lineHeight: 1.6 }}>{t.desc}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>{t.use}</div>
                <div style={{ marginTop: 12 }}>
                  <button className="btn btn-sm">Use Template</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'assets' && (
        <div className="subview">
          <DataNotice tone="sample" title="Asset library is sample content">
            Attachments become real only when connected to a live listing workspace.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Asset Tray — Premium Water Filter</h3>
              <span className="pill pill-muted">6 assets</span>
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Asset' },
              { key: 'type', label: 'Type' },
              { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
              { key: 'used', label: 'Used In' },
            ]} rows={[
              { name: 'hero-main.jpg', type: 'Image', state: 'Attached', used: 'Title / Bullets', tone: 'pill-muted' },
              { name: 'lifestyle-kitchen-01.jpg', type: 'Image', state: 'Attached', used: 'Description', tone: 'pill-muted' },
              { name: 'filter-exploded.png', type: 'Diagram', state: 'Draft', used: '—', tone: 'pill-warn' },
              { name: 'install-clip-15s.mp4', type: 'Video', state: 'UNREVIEWED', used: '—', tone: 'pill-unverified' },
              { name: 'comparison-chart.png', type: 'Diagram', state: 'Missing alt text', used: 'Description', tone: 'pill-warn' },
              { name: 'brand-logo-pack.zip', type: 'Brand', state: 'Attached', used: 'A+ Content', tone: 'pill-muted' },
            ]} />
            <div className="inline-flex" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/creative-studio')}>Open Creative Studio</button>
              <button className="btn btn-sm btn-ghost">Upload Assets</button>
            </div>
          </div>
        </div>
      )}

      {view === 'revisions' && (
        <div className="subview">
          <DataNotice tone="sample" title="Revision history is sample data">
            Version states below are demonstration workflow. Revert restores draft state only — it does not republish to a live listing.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Revision Log — Premium Water Filter</h3>
              <span className="pill pill-warn">v3.2 in progress</span>
            </div>
            <DataTable columns={[
              { key: 'version', label: 'Version' },
              { key: 'summary', label: 'Summary' },
              { key: 'saved', label: 'Saved' },
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'In progress' ? 'pill-warn' : v === 'Reverted' ? 'pill-ochre' : 'pill-muted'}`}>{v}</span> },
              { key: 'action', label: '', render: (v, row) => row.state === 'In progress' ? null : <button className="btn btn-sm btn-ghost">Restore as Draft</button> },
            ]} rows={[
              { version: 'v3.2', summary: 'Title pack-count added; bullets reworded; description refreshed', saved: '2h ago', state: 'In progress' },
              { version: 'v3.1', summary: 'Keyword coverage pass — 68% matched', saved: '1d ago', state: 'Published (sample)' },
              { version: 'v3.0', summary: 'Launch copy — full rewrite', saved: '6d ago', state: 'Published (sample)' },
              { version: 'v2.9', summary: 'Compliance flag: unsupported claim removed', saved: '12d ago', state: 'Reverted' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}