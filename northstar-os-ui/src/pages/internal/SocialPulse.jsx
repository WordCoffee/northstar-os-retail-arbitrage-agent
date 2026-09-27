import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'calendar', label: 'Calendar' },
  { id: 'queue', label: 'Queue' },
  { id: 'composer', label: 'Composer' },
  { id: 'assets', label: 'Asset Library' },
  { id: 'presets', label: 'Presets' },
  { id: 'approvals', label: 'Approvals', count: 2 },
  { id: 'analytics', label: 'Analytics' },
]

const CAMPAIGNS = [
  { id: 'set-a-launch', name: 'Set A Launch', theme: 'Product awareness', state: 'Active' },
  { id: 'q4-seasonal', name: 'Q4 Seasonal', theme: 'Seasonal promo', state: 'Planned' },
  { id: 'testimonial', name: 'Testimonial Series', theme: 'Social proof', state: 'Active' },
]

const PLATFORMS = ['TikTok', 'Instagram Reels', 'Stories', 'X Thread', 'Pinterest', 'YouTube Shorts', 'Email']

const VOICES = ['Founder voice', 'Product demo', 'Problem/solution', 'Before/after', 'Deal alert', 'UGC testimonial', 'Trend reaction', 'FAQ answer', 'Top 5 listicle', 'Seasonal promo', 'Lifestyle edit', 'Comparison/alternative']

const STAGE_PILL = { Draft: 'pill-muted', Approved: 'pill-forest', Scheduled: 'pill-ochre', Published: 'pill-muted' }

const POSTS = [
  { day: 20, platform: 'Instagram', title: 'Installation guide', stage: 'Published' },
  { day: 22, platform: 'X Thread', title: 'Behind the scenes — filtering', stage: 'Draft' },
  { day: 24, platform: 'Facebook', title: 'Customer testimonial', stage: 'Published' },
  { day: 26, platform: 'Instagram', title: 'Product highlight — Water Filter', stage: 'Published' },
  { day: 28, platform: 'Instagram Reels', title: 'Q4 promo teaser', stage: 'Scheduled' },
  { day: 30, platform: 'TikTok', title: 'Hook test — before/after', stage: 'Draft' },
]

const QUEUE = {
  Drafts: [
    { title: 'Behind the scenes — filtering', platform: 'X Thread', voice: 'Founder voice' },
    { title: 'Q4 promo teaser', platform: 'TikTok', voice: 'Seasonal promo' },
  ],
  Approved: [
    { title: 'Installation guide', platform: 'Instagram', voice: 'Product demo' },
  ],
  Scheduled: [
    { title: 'Product highlight — Water Filter', platform: 'Instagram Reels', voice: 'Lifestyle edit' },
  ],
  Published: [
    { title: 'Customer testimonial', platform: 'Facebook', voice: 'UGC testimonial' },
    { title: 'Installation guide', platform: 'Instagram', voice: 'Product demo' },
  ],
}

const ASSETS = [
  { name: 'water-filter-hero.jpg', type: 'Image', tag: 'Product', state: 'Approved' },
  { name: 'install-clip-15s.mp4', type: 'Video', tag: 'Utility', state: 'UNREVIEWED' },
  { name: 'before-after-01.jpg', type: 'Image', tag: 'Format', state: 'Approved' },
  { name: 'lifestyle-kitchen.jpg', type: 'Image', tag: 'Lifestyle', state: 'Draft' },
  { name: 'ugc-testimonial.mp4', type: 'Video', tag: 'UGC', state: 'UNREVIEWED' },
  { name: 'q4-promo-bg.jpg', type: 'Image', tag: 'Seasonal', state: 'Missing alt text' },
]

const APPROVALS = [
  { id: 'SP-014', title: 'Q4 promo teaser — TikTok', owner: 'Operator A', state: 'Awaiting Approval', tone: 'pill-ochre' },
  { id: 'SP-013', title: 'Product highlight — IG Reels', owner: 'Operator A', state: 'Approved', tone: 'pill-muted' },
  { id: 'SP-012', title: 'Testimonial series — FB', owner: 'Operator B', state: 'Changes Requested', tone: 'pill-warn' },
]

const COPILOT_SUGGESTIONS = [
  'Repurpose: turn the installation guide into a 15s Reel hook',
  'Variant: rewrite caption in Founder voice',
  'Hook ideas: 3 openers for a before/after post',
  'FAQ answer: “is it compatible with hard water?”',
]

const POSTS_BY_DAY = POSTS.reduce((m, p) => { (m[p.day] = m[p.day] || []).push(p); return m }, {})
const MONTH_CELLS = (() => {
  const cells = []
  for (let i = 0; i < 35; i++) {
    const day = i - 1
    cells.push(day >= 1 && day <= 30 ? day : null)
  }
  return cells
})()

export default function SocialPulse() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [campaign, setCampaign] = useState('Set A Launch')
  const [voice, setVoice] = useState('Founder voice')
  const [assetFilter, setAssetFilter] = useState('All')
  const [queueMode, setQueueMode] = useState('Board')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'calendar'

  const go = (t) => navigate(`/socialpulse?view=${t}`)
  const t = (msg, tone = 'info') => toast(msg, tone)

  return (
    <PageLayout
      title="SocialPulse"
      subtitle="Social content studio — plan on the calendar, shape drafts in the composer, approve, and schedule."
      actions={<>
        <button className="btn btn-sm" onClick={() => go('composer')}>Draft Post</button>
        <button className="btn btn-sm btn-ghost" onClick={() => t('Variants generated from the active draft (sample) — review before scheduling.', 'info')}>Generate Variants</button>
        <button className="btn btn-sm btn-ghost" onClick={() => t('Draft queued for scheduling — no post publishes without an approved slot.', 'info')}>Schedule</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('approvals')}>Send for Approval</button>
      </>}
    >
      <DataNotice tone="sample" title="Social data is sample or observed">
        Calendar, queue, and campaign records are demonstration data. Engagement rate and follower counts are NOT verified — do not use for budget or purchase decisions. Scheduling is manual; nothing publishes autonomously.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Campaign</span>
          {CAMPAIGNS.map(c => (
            <button key={c.id} className={`filter-pill ${campaign === c.name ? 'active' : ''}`} onClick={() => setCampaign(c.name)} title={`${c.theme} · ${c.state}`}>{c.name}</button>
          ))}
          <span className="pill pill-muted" style={{ marginLeft: 'auto' }} title="Brand voice / tone preset applied to generated drafts">
            Voice: {voice}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="text-low" style={{ fontSize: 11 }}>Platform presets</span>
          {PLATFORMS.map(p => (
            <span key={p} className="pill pill-muted" style={{ fontSize: 11 }} title={`Format preset for ${p}`}>{p}</span>
          ))}
        </div>
      </div>

      <RoomTabs tabs={TABS} base="/socialpulse" />

      {view === 'calendar' && (
        <div className="subview">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, alignItems: 'start' }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">September 2026 — {campaign}</h3>
                <span className="pill pill-muted">{POSTS.length} posts · sample</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, fontSize: 11 }}>
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => (
                  <div key={d} className="text-low" style={{ textAlign: 'center', paddingBottom: 4 }}>{d}</div>
                ))}
                {MONTH_CELLS.map((day, i) => (
                  <div key={i} style={{ minHeight: 74, border: '1px solid var(--divider)', borderRadius: 6, padding: 6, background: day ? 'var(--surface-2, rgba(138,138,122,0.04))' : 'transparent' }}>
                    {day && <div className="text-low" style={{ fontSize: 10, marginBottom: 4 }}>{day}</div>}
                    {day && (POSTS_BY_DAY[day] || []).map((p, j) => (
                      <div key={j} style={{ fontSize: 10, padding: '2px 5px', borderRadius: 4, marginBottom: 3, background: 'rgba(29,90,29,0.08)', color: 'var(--pine-deep)' }} title={`${p.platform} · ${p.stage}`}>
                        {p.title.length > 18 ? p.title.slice(0, 18) + '…' : p.title}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Draft Composer Preview</h3>
                  <span className="pill pill-muted">draft</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--ink-mid)', marginBottom: 8 }}>
                  Hook: “Stop buying filters that miss the sediment.”
                </div>
                <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>Instagram Reels · {voice} · {campaign}</div>
                <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => go('composer')}>Continue Editing</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Draft sent for approval (sample).', 'info')}>Send for Approval</button>
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>AI Copilot</h3>
                  <span className="pill pill-unverified" title="Suggestions only — nothing publishes or changes without operator action">suggestions</span>
                </div>
                <div className="stack" style={{ gap: 6 }}>
                  {COPILOT_SUGGESTIONS.map(s => (
                    <button key={s} className="btn btn-sm btn-ghost" style={{ textAlign: 'left', justifyContent: 'flex-start', whiteSpace: 'normal' }} onClick={() => t('Copilot suggestion staged — review before use.', 'info')}>{s}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'queue' && (
        <div className="subview">
          <div className="room-toolbar">
            <span className="text-low" style={{ fontSize: 11, marginRight: 8 }}>View</span>
            {['Board', 'List'].map(m => (
              <button key={m} className={`filter-pill ${queueMode === m ? 'active' : ''}`} onClick={() => setQueueMode(m)}>{m}</button>
            ))}
          </div>
          {queueMode === 'Board' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
              {Object.entries(QUEUE).map(([stage, cards]) => (
                <div key={stage} className="card" style={{ padding: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <strong style={{ fontSize: 13 }}>{stage}</strong>
                    <span className={`pill ${STAGE_PILL[stage]}`}>{cards.length}</span>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    {cards.map((c, i) => (
                      <div key={i} style={{ border: '1px solid var(--divider)', borderRadius: 6, padding: 10 }}>
                        <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>{c.title}</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <span className="pill pill-muted" style={{ fontSize: 10 }}>{c.platform}</span>
                          <span className="pill pill-muted" style={{ fontSize: 10 }}>{c.voice}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card">
              <DataTable columns={[
                { key: 'title', label: 'Post' },
                { key: 'platform', label: 'Platform' },
                { key: 'voice', label: 'Voice preset' },
                { key: 'stage', label: 'Stage', render: (v) => <span className={`pill ${STAGE_PILL[v] || 'pill-muted'}`}>{v}</span> },
              ]} rows={Object.entries(QUEUE).flatMap(([stage, cards]) => cards.map(c => ({ ...c, stage })))} />
            </div>
          )}
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <DataNotice tone="internal" title="Composer drafts are not published">
            Nothing here posts autonomously. Drafts move only through explicit Schedule or Send for Approval.
          </DataNotice>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20, alignItems: 'start' }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Draft Post</h3>
                <span className="pill pill-muted">{campaign} · {voice}</span>
              </div>
              <div className="stack" style={{ gap: 12 }}>
                <div className="field-group">
                  <label className="label">Hook / Title</label>
                  <input className="field" defaultValue="Stop buying filters that miss the sediment." />
                </div>
                <div className="field-group">
                  <label className="label">Caption</label>
                  <textarea className="field" rows={4} defaultValue={'Sediment, chlorine, and taste — one countertop filter handles all three.\n\nInstall in under 5 minutes. No tools.'} />
                </div>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <div className="field-group" style={{ minWidth: 180 }}>
                    <label className="label">Platform preset</label>
                    <select className="field" defaultValue="Instagram Reels">
                      {PLATFORMS.map(p => <option key={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 180 }}>
                    <label className="label">Voice preset</label>
                    <select className="field" value={voice} onChange={e => setVoice(e.target.value)}>
                      {VOICES.map(v => <option key={v}>{v}</option>)}
                    </select>
                  </div>
                </div>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => t('Draft saved (sample).', 'info')}>Save Draft</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Variants generated — review each before scheduling.', 'info')}>Generate Variants</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Queued for scheduling — requires an approved slot.', 'info')}>Schedule</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => go('approvals')}>Send for Approval</button>
                </div>
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Platform Preview</h3>
                  <span className="pill pill-muted" style={{ fontSize: 10 }}>preview</span>
                </div>
                <div style={{ border: '1px solid var(--divider)', borderRadius: 8, padding: 12 }}>
                  <div style={{ height: 120, borderRadius: 6, background: 'linear-gradient(135deg, rgba(29,90,29,0.10), rgba(196,148,26,0.12))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>
                    media placeholder
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Stop buying filters that miss the sediment.</div>
                  <div style={{ fontSize: 11, color: 'var(--ink-mid)' }}>Sediment, chlorine, and taste — one countertop filter handles all three.</div>
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>AI Copilot</h3>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Suggestions only — operator applies changes">suggestions</span>
                </div>
                <div className="field-group" style={{ marginBottom: 10 }}>
                  <label className="label">Repurpose from</label>
                  <input className="field" placeholder="Paste URL, product page, copy, or UGC note…" />
                </div>
                <div className="stack" style={{ gap: 6 }}>
                  {COPILOT_SUGGESTIONS.map(s => (
                    <button key={s} className="btn btn-sm btn-ghost" style={{ textAlign: 'left', justifyContent: 'flex-start', whiteSpace: 'normal' }} onClick={() => t('Copilot suggestion staged — review before use.', 'info')}>{s}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'assets' && (
        <div className="subview">
          <div className="room-toolbar">
            {['All', 'Image', 'Video'].map(f => (
              <button key={f} className={`filter-pill ${assetFilter === f ? 'active' : ''}`} onClick={() => setAssetFilter(f)}>{f}</button>
            ))}
            <span className="pill pill-muted" style={{ marginLeft: 'auto' }}>posting assets · sample</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
            {ASSETS.filter(a => assetFilter === 'All' || a.type === assetFilter).map(a => (
              <div key={a.name} className="card" style={{ padding: 12 }}>
                <div style={{ height: 90, borderRadius: 6, background: 'linear-gradient(135deg, rgba(138,138,122,0.10), rgba(29,90,29,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>
                  {a.type} preview
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>{a.name}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.tag}</span>
                  {a.state === 'Approved'
                    ? <span className="pill pill-muted" style={{ fontSize: 10 }} title="Internal review state — not an authorization">{a.state}</span>
                    : a.state === 'UNREVIEWED' || a.state === 'Missing alt text'
                      ? <span className="pill pill-unknown" style={{ fontSize: 10 }}>{a.state}</span>
                      : <span className="pill pill-warn" style={{ fontSize: 10 }}>{a.state}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'presets' && (
        <div className="subview">
          <div className="grid-2" style={{ gap: 20, alignItems: 'start' }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Platform Presets</h3>
                <span className="pill pill-muted">{PLATFORMS.length}</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {PLATFORMS.map(p => (
                  <div key={p} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{p}</div>
                    <button className="btn btn-sm btn-ghost" onClick={() => t(`${p} preset applied to the active draft.`, 'info')}>Use</button>
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Brand Voice &amp; Content Formats</h3>
                <span className="pill pill-muted">{VOICES.length} formats</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {VOICES.map(v => (
                  <button key={v} className={`filter-pill ${voice === v ? 'active' : ''}`} onClick={() => { setVoice(v); t(`Voice set to ${v}.`, 'info') }}>{v}</button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'approvals' && (
        <div className="subview">
          <DataNotice tone="internal" title="Approval is internal review, not autonomous publishing">
            Approving a post marks it ready to schedule. Nothing publishes automatically, and approval is never a purchase or budget authorization.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Approval Queue</h3>
              <span className="pill pill-ochre">1 awaiting</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Draft' },
              { key: 'owner', label: 'Owner' },
              { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
              { key: 'action', label: '', render: (v, row) => row.state === 'Awaiting Approval'
                ? <button className="btn btn-sm" onClick={() => t('Approved — ready to schedule. Still requires an explicit schedule action.', 'info')}>Approve</button>
                : <button className="btn btn-sm btn-ghost" onClick={() => t('Opened draft (sample).', 'info')}>Open</button> },
            ]} rows={APPROVALS} />
          </div>
        </div>
      )}

      {view === 'analytics' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Engagement metrics are not verified">
            Follower and engagement figures require a connected social analytics provider. The surface below is a placeholder rollup, not a report.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Performance Rollup</h3>
              <span className="pill pill-muted">sample / cached</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'Posts Published', v: '4', note: 'This month · sample' },
                { label: 'Reach', v: 'UNKNOWN', note: 'No provider connected' },
                { label: 'Engagement Rate', v: 'UNKNOWN', note: 'No provider connected' },
                { label: 'Top Platform', v: 'UNKNOWN', note: 'No provider connected' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: d.v === 'UNKNOWN' ? 'var(--clay)' : 'var(--pine-deep)' }}>{d.v}</div>
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
