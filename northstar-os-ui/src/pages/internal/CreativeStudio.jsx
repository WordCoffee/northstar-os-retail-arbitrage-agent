import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'library', label: 'Library', count: 87 },
  { id: 'templates', label: 'Templates', count: 6 },
  { id: 'health', label: 'Asset Health' },
]

export default function CreativeStudio() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'library'

  return (
    <PageLayout
      title="Creative Studio"
      subtitle="Creative workspace — images, videos, A+ content, templates, and asset health."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Upload Asset — library accepts images, video, and A+ blocks.', 'info')}>Upload Asset</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Templates view opened.', 'info')}>Templates</button>
      </>}
    >
      <DataNotice tone="sample" title="Asset records are sample data">
        Library counts, file sizes, and approval states are demonstration records until an asset backend is connected.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/creative-studio" />

      {view === 'library' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Recent Assets</h3>
              <span className="pill pill-muted">Last 10</span>
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Asset' },
              { key: 'type', label: 'Type' },
              { key: 'size', label: 'Size' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Approved' ? 'pill-forest' : v === 'In Review' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
            ]} rows={[
              { name: 'water-filter-hero.jpg', type: 'Image', size: '2.4 MB', status: 'Approved' },
              { name: 'installation-video.mp4', type: 'Video', size: '18.2 MB', status: 'In Review' },
              { name: 'aplus-banner-01.jpg', type: 'Image', size: '1.1 MB', status: 'Approved' },
              { name: 'feature-infographic.jpg', type: 'Image', size: '890 KB', status: 'Draft' },
              { name: 'lifestyle-shot-03.jpg', type: 'Image', size: '3.2 MB', status: 'Approved' },
            ]} />
          </div>
        </div>
      )}

      {view === 'templates' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Template Gallery</h3>
              <span className="pill pill-muted">6 templates</span>
            </div>
            {[
              { name: 'Hero + feature banner', kind: 'A+ Content', use: 'Set A listings' },
              { name: 'Installation guide block', kind: 'A+ Content', use: 'Utility products' },
              { name: 'Lifestyle scene', kind: 'Image layout', use: 'Brand building' },
              { name: 'Comparison matrix', kind: 'A+ Content', use: 'Category sets' },
            ].map(t => (
              <div key={t.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{t.kind} · {t.use}</div>
                </div>
                <button className="btn btn-sm btn-ghost" onClick={() => toast('Template applied to composer (sample).', 'info')}>Use</button>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'health' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Asset Health</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              {[
                { label: 'Approved Assets', v: '62', note: 'In use' },
                { label: 'In Review', v: '5', note: 'Pending approval', warn: true },
                { label: 'Resolution Issues', v: '2', note: 'Needs attention', warn: true },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: d.warn ? 'var(--ochre)' : 'var(--pine-deep)' }}>{d.v}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.note}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}