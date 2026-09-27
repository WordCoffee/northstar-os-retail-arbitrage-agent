import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'calendar', label: 'Content Calendar', count: 6 },
  { id: 'campaigns', label: 'Campaigns', count: 4 },
  { id: 'performance', label: 'Performance' },
]

export default function SocialPulse() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'calendar'

  return (
    <PageLayout
      title="SocialPulse"
      subtitle="Social presence — scheduled content, campaign publishing, and audience context."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Create Post — compose and schedule a new social post.', 'info')}>Create Post</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Analytics requires a connected social analytics provider.', 'info')}>Analytics</button>
      </>}
    >
      <DataNotice tone="sample" title="Social data is sample or observed">
        Calendar, campaign, and engagement records are demonstration data. Engagement rate and follower counts are NOT verified — do not use for budget or purchase decisions.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/socialpulse" />

      {view === 'calendar' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Content Calendar</h3>
              <span className="pill pill-forest">6 posts this month</span>
            </div>
            <DataTable columns={[
              { key: 'date', label: 'Date' },
              { key: 'platform', label: 'Platform' },
              { key: 'content', label: 'Content' },
              { key: 'status', label: 'Status' },
            ]} rows={[
              { date: '2026-09-26', platform: 'Instagram', content: 'Product highlight — Water Filter', status: 'Published' },
              { date: '2026-09-24', platform: 'Facebook', content: 'Customer testimonial', status: 'Published' },
              { date: '2026-09-22', platform: 'Twitter', content: 'Behind the scenes — filtering process', status: 'Draft' },
              { date: '2026-09-20', platform: 'Instagram', content: 'Installation guide', status: 'Published' },
            ]} />
          </div>
        </div>
      )}

      {view === 'campaigns' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Social Campaigns</h3>
              <span className="pill pill-muted">4 active</span>
            </div>
            {[
              { name: 'Launch awareness — Set A', platform: 'Instagram + Facebook', spend: '$0 (organic)', state: 'Active', tone: 'pill-forest' },
              { name: 'Installation guide push', platform: 'Instagram', spend: 'UNKNOWN', state: 'Draft', tone: 'pill-muted' },
              { name: 'Testimonial series', platform: 'Facebook', spend: '$0 (organic)', state: 'Scheduled', tone: 'pill-ochre' },
              { name: 'Seasonal promo', platform: 'All', spend: 'NOT APPROVED', state: 'Awaiting Approval', tone: 'pill-clay' },
            ].map(c => (
              <div key={c.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{c.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{c.platform} · {c.spend}</div>
                </div>
                <span className={`pill ${c.tone}`}>{c.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'performance' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Engagement metrics are not verified">
            Follower and engagement figures would require a connected social analytics provider. The surface below is a placeholder, not a report.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Audience Context</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              {[
                { label: 'Followers', v: 'UNKNOWN', note: 'Across platforms' },
                { label: 'Engagement Rate', v: 'UNKNOWN', note: 'No provider connected' },
                { label: 'Top Platform', v: 'UNKNOWN', note: 'No provider connected' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--clay)' }}>{d.v}</div>
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