import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

// ═══════════════════════════════════════════════════════════════════════════
// SOCIALPULSE — social-content operations workspace.
//
// HONESTY CONTRACT (this room):
//   • Campaigns, content records, assets, and approvals are REAL LOCAL records
//     persisted in this browser. State transitions (Draft → In Review →
//     Approved → Publish-ready → Scheduled) are genuine local workflow state.
//   • NOTHING PUBLISHES. There is no social OAuth, no external post, no
//     outbound communication. "Scheduled" records a manual reminder only.
//   • Performance (reach / engagement / followers) requires a connected social
//     analytics provider that does not exist in this build, so those surfaces
//     read UNKNOWN — never a fabricated number.
//   • A real local caption engine exists in-repo (Northstar_backend/
//     social_pulse.py, local Ollama + deterministic fallback), but it is NOT
//     wired to this UI. The composer states that boundary instead of
//     pretending generated copy came from it.
// ═══════════════════════════════════════════════════════════════════════════

const TABS = [
  { id: 'calendar', label: 'Calendar' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'queue', label: 'Workflow', count: 2 },
  { id: 'composer', label: 'Composer' },
  { id: 'channels', label: 'Channel Fit' },
  { id: 'assets', label: 'Asset Library' },
  { id: 'presets', label: 'Presets' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'analytics', label: 'Analytics' },
]

const STAGES = [
  { key: 'Draft', label: 'Drafts', action: { label: 'Send to Approvals', next: 'In Review', note: 'Sent to review — nothing publishes automatically.' } },
  { key: 'In Review', label: 'In Review', action: { label: 'Approve', next: 'Approved', note: 'Approved — still requires an explicit publish-ready step; nothing publishes.' } },
  { key: 'Approved', label: 'Approved', action: { label: 'Mark Publish-Ready', next: 'Publish-ready', note: 'Marked publish-ready — still requires a manual schedule slot.' } },
  { key: 'Publish-ready', label: 'Publish-Ready', action: { label: 'Schedule (manual)', next: 'Scheduled', note: 'Recorded a manual schedule reminder — no post publishes autonomously.' } },
  { key: 'Scheduled', label: 'Scheduled', action: { label: 'Unschedule', next: 'Approved', note: 'Removed the manual schedule reminder.' } },
]
const STAGE_PILL = { Draft: 'pill-muted', 'In Review': 'pill-ochre', Approved: 'pill-forest', 'Publish-ready': 'pill-forest', Scheduled: 'pill-warn' }

const PLATFORMS = ['TikTok', 'Instagram Reels', 'Stories', 'X Thread', 'Pinterest', 'YouTube Shorts', 'Email']
const VOICES = ['Founder voice', 'Product demo', 'Problem/solution', 'Before/after', 'Deal alert', 'UGC testimonial', 'Trend reaction', 'FAQ answer', 'Top 5 listicle', 'Seasonal promo', 'Lifestyle edit', 'Comparison/alternative']

// Channel-fit heuristics (editorial guidance, NOT measured performance).
const CHANNEL_FIT = [
  { platform: 'TikTok', formats: ['Reel / Short', 'UGC testimonial'], aspect: '9:16', strength: 'Discovery reach', note: 'Native vertical video; hook within the first 2s.' },
  { platform: 'Instagram Reels', formats: ['Reel', 'Product demo'], aspect: '9:16', strength: 'Reach + saves', note: 'Reward watch-through; keep captions short.' },
  { platform: 'Stories', formats: ['Image', 'Poll / question'], aspect: '9:16', strength: 'Existing audience', note: 'Ephemeral; good for warm-audience nudges.' },
  { platform: 'X Thread', formats: ['Thread', 'Text + image'], aspect: '16:9', strength: 'Founder voice', note: 'Text-first; one idea per post.' },
  { platform: 'Pinterest', formats: ['Pin', 'Idea Pin'], aspect: '2:3', strength: 'Evergreen search', note: 'Durable discovery; keyword in the pin title.' },
  { platform: 'YouTube Shorts', formats: ['Short'], aspect: '9:16', strength: 'Search + reach', note: 'Title carries the search intent.' },
  { platform: 'Email', formats: ['Review request', 'Hero'], aspect: 'n/a', strength: 'Owned list', note: 'TOS-compliant review requests only; no incentives.' },
]

const COPILOT_SUGGESTIONS = [
  'Repurpose: turn the installation guide into a 15s Reel hook',
  'Variant: rewrite caption in Founder voice',
  'Hook ideas: 3 openers for a before/after post',
  'FAQ answer: "is it compatible with hard water?"',
]

// ── Local room store (browser-persisted). Isolated per room; no shared shell. ──
function useLocalRoom(key, seed) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw) return JSON.parse(raw)
    } catch { /* storage unavailable */ }
    return seed
  })
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* storage unavailable */ }
  }, [key, value])
  return [value, setValue]
}

const uid = (p) => `${p}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`
const nowIso = () => new Date().toISOString()

const SEED_CAMPAIGNS = [
  { id: 'C-01', key: 'set-a-launch', name: 'Set A Launch', theme: 'Product awareness', objective: 'Introduce Set A to new audiences', audience: 'Homeowners 30–55', state: 'Active', channels: ['Instagram Reels', 'TikTok'], start: '2026-09-20' },
  { id: 'C-02', key: 'q4-seasonal', name: 'Q4 Seasonal', theme: 'Seasonal promo', objective: 'Seasonal demand capture', audience: 'Existing customers', state: 'Planned', channels: ['Stories', 'Email'], start: '2026-10-01' },
  { id: 'C-03', key: 'testimonial', name: 'Testimonial Series', theme: 'Social proof', objective: 'Social proof at scale', audience: 'Warm audience', state: 'Active', channels: ['Instagram Reels', 'Pinterest'], start: '2026-09-24' },
]
const SEED_POSTS = [
  { id: 'SP-01', campaign: 'set-a-launch', title: 'Installation guide', platform: 'Instagram Reels', format: 'Reel', voice: 'Product demo', state: 'Scheduled', when: 'Sep 28 · 08:00 (manual reminder)', note: 'Slot is a manual reminder — nothing auto-publishes.' },
  { id: 'SP-02', campaign: 'set-a-launch', title: 'Behind the scenes — filtering', platform: 'X Thread', format: 'Thread', voice: 'Founder voice', state: 'Draft', when: '', note: 'Not yet submitted for review.' },
  { id: 'SP-03', campaign: 'testimonial', title: 'Customer testimonial', platform: 'Instagram Reels', format: 'Reel', voice: 'UGC testimonial', state: 'Approved', when: '', note: 'Approved — still requires publish-ready + manual schedule.' },
  { id: 'SP-04', campaign: 'q4-seasonal', title: 'Q4 promo teaser', platform: 'TikTok', format: 'Short', voice: 'Seasonal promo', state: 'In Review', when: '', note: 'Awaiting brand review.' },
  { id: 'SP-05', campaign: 'set-a-launch', title: 'Product highlight — Water Filter', platform: 'Instagram Reels', format: 'Reel', voice: 'Lifestyle edit', state: 'Publish-ready', when: '', note: 'Ready to schedule manually.' },
  { id: 'SP-06', campaign: 'testimonial', title: 'Before/after hook test', platform: 'TikTok', format: 'Short', voice: 'Before/after', state: 'Draft', when: '', note: 'Hook options pending.' },
]
const SEED_ASSETS = [
  { id: 'SA-01', name: 'water-filter-hero.jpg', type: 'Image', tag: 'Product', state: 'Approved', attached: ['SP-01'] },
  { id: 'SA-02', name: 'install-clip-15s.mp4', type: 'Video', tag: 'Utility', state: 'UNREVIEWED', attached: [] },
  { id: 'SA-03', name: 'before-after-01.jpg', type: 'Image', tag: 'Format', state: 'Approved', attached: ['SP-06'] },
  { id: 'SA-04', name: 'lifestyle-kitchen.jpg', type: 'Image', tag: 'Lifestyle', state: 'Draft', attached: ['SP-05'] },
  { id: 'SA-05', name: 'ugc-testimonial.mp4', type: 'Video', tag: 'UGC', state: 'UNREVIEWED', attached: ['SP-03'] },
  { id: 'SA-06', name: 'q4-promo-bg.jpg', type: 'Image', tag: 'Seasonal', state: 'Missing alt text', attached: ['SP-04'] },
]

const MONTH_START_OFFSET = 1
const MONTH_CELLS = (() => {
  const cells = []
  for (let i = 0; i < MONTH_START_OFFSET; i++) cells.push({ out: true, label: 31 - i })
  for (let d = 1; d <= 30; d++) cells.push({ out: false, day: d })
  let n = 1
  while (cells.length < 35) cells.push({ out: true, label: n++ })
  return cells
})()

function assetStatePill(state) {
  if (state === 'Approved') return 'pill-muted'
  if (state === 'UNREVIEWED' || state === 'Missing alt text') return 'pill-unknown'
  return 'pill-warn'
}

export default function SocialPulse() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [campaigns] = useLocalRoom('ns-social-campaigns', SEED_CAMPAIGNS)
  const [posts, setPosts] = useLocalRoom('ns-social-posts', SEED_POSTS)
  const [assets, setAssets] = useLocalRoom('ns-social-assets', SEED_ASSETS)

  const [campaign, setCampaign] = useState('Set A Launch')
  const [voice, setVoice] = useState('Founder voice')
  const [assetFilter, setAssetFilter] = useState('All')
  const [queueMode, setQueueMode] = useState('Board')

  // composer fields
  const [hook, setHook] = useState('Stop buying filters that miss the sediment.')
  const [caption, setCaption] = useState('Sediment, chlorine, and taste — one countertop filter handles all three.\n\nInstall in under 5 minutes. No tools.')
  const [platform, setPlatform] = useState('Instagram Reels')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'calendar'

  const go = (t) => navigate(`/socialpulse?view=${t}`)
  const t = (msg, tone = 'info') => toast(msg, tone)

  const activeCampaign = useMemo(
    () => campaigns.find(c => c.name === campaign) || campaigns[0] || null,
    [campaigns, campaign],
  )

  const postsInCampaign = useMemo(
    () => posts.filter(p => !activeCampaign || p.campaign === activeCampaign.key),
    [posts, activeCampaign],
  )
  const postsByStage = useMemo(() => {
    const m = {}
    for (const s of STAGES) m[s.key] = []
    for (const p of postsInCampaign) (m[p.state] = m[p.state] || []).push(p)
    return m
  }, [postsInCampaign])

  const campaignName = (key) => campaigns.find(c => c.key === key)?.name || key
  const inReview = posts.filter(p => p.state === 'In Review')
  const reviewCount = inReview.length

  const advance = (id, next, note) => {
    setPosts(prev => prev.map(p => p.id === id ? { ...p, state: next } : p))
    t(`${id} → ${next}. ${note}`, 'info')
  }

  const addDraft = () => {
    const id = uid('SP')
    setPosts(prev => [{
      id, campaign: activeCampaign?.key || campaigns[0]?.key || '', title: hook.slice(0, 40) || 'Untitled draft',
      platform, format: 'Reel', voice, state: 'Draft', when: '', note: 'Created locally from the composer.',
    }, ...prev])
    t(`${id} saved as a local draft — nothing publishes.`, 'info')
  }

  return (
    <PageLayout
      title="SocialPulse"
      subtitle="Social content operations — plan campaigns, draft, review, approve, and mark publish-ready. Nothing publishes from here."
      actions={<>
        <button className="btn btn-sm" onClick={() => go('composer')}>Draft Post</button>
        <button className="btn btn-sm btn-ghost" onClick={() => t('Variant suggestions are a local planning aid (sample) — nothing publishes.', 'info')}>Generate Variants</button>
        <button className="btn btn-sm btn-ghost" onClick={() => t('Schedule records a manual reminder only — no post publishes autonomously, and no social account is connected.', 'info')}>Schedule</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('approvals')}>Send for Approval</button>
      </>}
    >
      <DataNotice tone="sample" title="Local content operations — not a publisher">
        Campaigns, posts, and approvals are real records stored in this browser. There is no social OAuth and no outbound
        posting. Performance figures require a connected analytics provider and read UNKNOWN until one exists — never a
        fabricated number.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Campaign</span>
          {campaigns.map(c => (
            <button key={c.id} className={`filter-pill ${campaign === c.name ? 'active' : ''}`} onClick={() => setCampaign(c.name)} title={`${c.theme} · ${c.state}`}>{c.name}</button>
          ))}
          <span className="pill pill-muted" style={{ marginLeft: 'auto' }} title="Brand voice / tone preset applied to drafts">
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
          <div className="split-aside-r">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">September 2026 — {campaign}</h3>
                <span className="pill pill-muted">{postsInCampaign.length} planned · local records</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6, fontSize: 11 }}>
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => (
                  <div key={d} className="text-low" style={{ textAlign: 'center', paddingBottom: 4 }}>{d}</div>
                ))}
                {MONTH_CELLS.map((cell, i) => {
                  const dayPosts = cell.out ? [] : postsInCampaign.filter(p => p.when && p.when.includes(`Sep ${cell.day}`))
                  return (
                    <div key={i} style={{
                      minHeight: 74,
                      border: `1px ${cell.out ? 'dashed' : 'solid'} var(--divider)`,
                      borderRadius: 6, padding: 6,
                      background: cell.out
                        ? 'repeating-linear-gradient(45deg, rgba(138,138,122,0.06) 0 6px, transparent 6px 12px)'
                        : 'var(--surface-2, rgba(138,138,122,0.04))',
                    }} title={cell.out ? 'Outside September 2026 — not interactive' : undefined}>
                      {cell.out
                        ? <div className="text-low" style={{ fontSize: 10, opacity: 0.55 }}>{cell.label}</div>
                        : <>
                            <div className="text-low" style={{ fontSize: 10, marginBottom: 4 }}>{cell.day}</div>
                            {dayPosts.map((p, j) => (
                              <div key={j} style={{ fontSize: 10, padding: '2px 5px', borderRadius: 4, marginBottom: 3, background: 'rgba(29,90,29,0.08)', color: 'var(--pine-deep)' }} title={`${p.platform} · ${p.state}`}>
                                {p.title.length > 18 ? p.title.slice(0, 18) + '…' : p.title}
                              </div>
                            ))}
                          </>}
                    </div>
                  )
                })}
              </div>
              <div className="text-low" style={{ fontSize: 11, marginTop: 12 }}>
                Only posts with a manual schedule reminder appear on the grid. The calendar is a planning surface — it never triggers a post.
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Campaign Snapshot</h3>
                  <span className="pill pill-muted">{activeCampaign?.state || '—'}</span>
                </div>
                {activeCampaign ? (
                  <div className="stack" style={{ gap: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--ink-mid)' }}>{activeCampaign.objective}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>Audience: {activeCampaign.audience}</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {activeCampaign.channels.map(c => <span key={c} className="pill pill-muted" style={{ fontSize: 10 }}>{c}</span>)}
                    </div>
                    <div className="text-low" style={{ fontSize: 11 }}>{postsInCampaign.length} planned posts · {postsInCampaign.filter(p => p.state === 'In Review').length} in review</div>
                  </div>
                ) : <div className="text-low" style={{ fontSize: 12 }}>No campaign selected.</div>}
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>AI Copilot</h3>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Suggestions only — nothing publishes or changes without operator action">suggestions</span>
                </div>
                <div className="stack" style={{ gap: 6 }}>
                  {COPILOT_SUGGESTIONS.map(s => (
                    <button key={s} className="btn btn-sm btn-ghost" style={{ textAlign: 'left', justifyContent: 'flex-start', whiteSpace: 'normal' }} onClick={() => t('Copilot suggestion staged locally — review before use; nothing publishes.', 'info')}>{s}</button>
                  ))}
                </div>
                <div className="text-low" style={{ fontSize: 10, marginTop: 8 }}>
                  Assisted generation runs through the local SocialPulse engine when its endpoint is connected — not connected in this build.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'campaigns' && (
        <div className="subview">
          <div className="room-toolbar">
            <span className="pill pill-muted" style={{ marginRight: 'auto' }}>{campaigns.length} campaigns · local records</span>
            <button className="btn btn-sm" onClick={() => t('New campaign is a local planning record (sample) — no channel is connected.', 'info')}>New Campaign</button>
          </div>
          <div className="grid-cards-3">
            {campaigns.map(c => {
              const campPosts = postsInCampaignFor(c.key, posts)
              return (
                <div key={c.id} className="card" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <strong style={{ fontSize: 13 }}>{c.name}</strong>
                    <span className={`pill ${c.state === 'Active' ? 'pill-forest' : c.state === 'Planned' ? 'pill-muted' : 'pill-warn'}`}>{c.state}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-mid)', marginBottom: 6 }}>{c.theme} · {c.audience}</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                    {c.channels.map(ch => <span key={ch} className="pill pill-muted" style={{ fontSize: 10 }}>{ch}</span>)}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="text-low" style={{ fontSize: 11 }}>{campPosts.length} posts · {campPosts.filter(p => p.state === 'Draft').length} draft</span>
                    <button className="btn btn-sm btn-ghost" onClick={() => { setCampaign(c.name); go('queue') }}>Open Workflow</button>
                  </div>
                </div>
              )
            })}
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
            <span className="pill pill-unknown" style={{ marginLeft: 'auto' }}>state changes are local · nothing publishes</span>
          </div>
          {queueMode === 'Board' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(170px, 1fr))', gap: 14, overflowX: 'auto', paddingBottom: 4 }}>
              {STAGES.map(stage => (
                <div key={stage.key} className="card" style={{ padding: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <strong style={{ fontSize: 13 }}>{stage.label}</strong>
                    <span className={`pill ${STAGE_PILL[stage.key] || 'pill-muted'}`}>{(postsByStage[stage.key] || []).length}</span>
                  </div>
                  <div className="stack" style={{ gap: 8 }}>
                    {(postsByStage[stage.key] || []).length === 0 && (
                      <div className="text-low" style={{ fontSize: 11 }}>No posts in this state.</div>
                    )}
                    {(postsByStage[stage.key] || []).map(p => (
                      <div key={p.id} style={{ border: '1px solid var(--divider)', borderRadius: 6, padding: 10 }}>
                        <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>{p.title}</div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                          <span className="pill pill-muted" style={{ fontSize: 10 }}>{p.platform}</span>
                          <span className="pill pill-muted" style={{ fontSize: 10 }}>{p.voice}</span>
                        </div>
                        <div className="text-low" style={{ fontSize: 10, marginBottom: 8 }}>{p.note}</div>
                        <button className="btn btn-sm" onClick={() => advance(p.id, stage.action.next, stage.action.note)}>{stage.action.label}</button>
                      </div>
                    ))}
                  </div>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--divider)' }}>
                    {(postsByStage[stage.key] || []).length} {(postsByStage[stage.key] || []).length === 1 ? 'post' : 'posts'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card">
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'title', label: 'Post' },
                { key: 'platform', label: 'Platform' },
                { key: 'voice', label: 'Voice preset' },
                { key: 'state', label: 'State', render: (v) => <span className={`pill ${STAGE_PILL[v] || 'pill-muted'}`} title="Local workflow state — not a publishing authorization">{v}</span> },
                { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => t(`${row.id} opened in the local workflow — nothing publishes.`, 'info')}>Open</button> },
              ]} rows={postsInCampaign} />
            </div>
          )}
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <DataNotice tone="internal" title="Composer drafts are not published">
            Nothing here posts autonomously. Drafts move only through explicit review → approve → publish-ready → manual schedule.
            Assisted caption generation requires the local SocialPulse engine, which is not connected in this build.
          </DataNotice>
          <div className="split-aside-r">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Draft Post</h3>
                <span className="pill pill-muted">{campaign} · {voice}</span>
              </div>
              <div className="stack" style={{ gap: 12 }}>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="sp-hook">Hook / Title</label>
                  <input id="sp-hook" className="field" value={hook} onChange={e => setHook(e.target.value)} />
                </div>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="sp-caption">Caption</label>
                  <textarea id="sp-caption" className="field" rows={4} value={caption} onChange={e => setCaption(e.target.value)} />
                </div>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="sp-platform">Platform preset</label>
                    <select id="sp-platform" className="field" value={platform} onChange={e => setPlatform(e.target.value)}>
                      {PLATFORMS.map(p => <option key={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="sp-voice">Voice preset</label>
                    <select id="sp-voice" className="field" value={voice} onChange={e => setVoice(e.target.value)}>
                      {VOICES.map(v => <option key={v}>{v}</option>)}
                    </select>
                  </div>
                </div>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={addDraft}>Save Draft</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Variant suggestions are a local planning aid — review each before scheduling; nothing publishes.', 'info')}>Generate Variants</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Schedule records a manual reminder only — no account is connected.', 'info')}>Schedule</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { addDraft(); go('approvals') }}>Send for Approval</button>
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
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>{hook || 'Hook / title'}</div>
                  <div style={{ fontSize: 11, color: 'var(--ink-mid)', whiteSpace: 'pre-wrap' }}>{caption || 'Caption preview'}</div>
                </div>
                <div className="text-low" style={{ fontSize: 10, marginTop: 8 }}>{platform} · {voice}</div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>AI Copilot</h3>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Suggestions only — operator applies changes">suggestions</span>
                </div>
                <div className="field-group" style={{ marginBottom: 10 }}>
                  <label className="label" htmlFor="sp-repurpose">Repurpose from</label>
                  <input id="sp-repurpose" className="field" placeholder="Paste URL, product page, copy, or UGC note…" />
                </div>
                <div className="stack" style={{ gap: 6 }}>
                  {COPILOT_SUGGESTIONS.map(s => (
                    <button key={s} className="btn btn-sm btn-ghost" style={{ textAlign: 'left', justifyContent: 'flex-start', whiteSpace: 'normal' }} onClick={() => t('Copilot suggestion staged locally — review before use.', 'info')}>{s}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'channels' && (
        <div className="subview">
          <DataNotice tone="concept" title="Channel fit is editorial guidance, not measured performance">
            Fit notes describe how each channel typically rewards a format. They are heuristics, not analytics results, and are
            not derived from any connected account.
          </DataNotice>
          <div className="grid-cards-3">
            {CHANNEL_FIT.map(ch => {
              const count = posts.filter(p => p.platform === ch.platform).length
              return (
                <div key={ch.platform} className="card" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <strong style={{ fontSize: 13 }}>{ch.platform}</strong>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{ch.aspect}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                    {ch.formats.map(f => <span key={f} className="pill pill-muted" style={{ fontSize: 10 }}>{f}</span>)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-mid)', marginBottom: 8 }}><strong>{ch.strength}.</strong> {ch.note}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{count} planned {count === 1 ? 'post' : 'posts'} on this channel</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {view === 'assets' && (
        <div className="subview">
          <div className="room-toolbar">
            {['All', 'Image', 'Video'].map(f => (
              <button key={f} className={`filter-pill ${assetFilter === f ? 'active' : ''}`} onClick={() => setAssetFilter(f)}>{f}</button>
            ))}
            <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={() => t('Asset upload is not connected — this room records asset metadata and attachment state only.', 'warn')}>Upload Asset</button>
          </div>
          <div className="grid-cards-3">
            {assets.filter(a => assetFilter === 'All' || a.type === assetFilter).map(a => (
              <div key={a.id} className="card" style={{ padding: 12 }}>
                <div style={{ height: 90, borderRadius: 6, background: 'linear-gradient(135deg, rgba(138,138,122,0.10), rgba(29,90,29,0.08))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 10 }}>
                  {a.type} preview
                </div>
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>{a.name}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.tag}</span>
                  <span className={`pill ${assetStatePill(a.state)}`} style={{ fontSize: 10 }} title="Internal asset state — not an authorization">{a.state}</span>
                </div>
                <div className="text-low" style={{ fontSize: 10, marginTop: 6 }}>
                  {a.attached.length ? `Attached to ${a.attached.join(', ')}` : 'Not attached to a post'}
                </div>
              </div>
            ))}
            {assets.filter(a => assetFilter === 'All' || a.type === assetFilter).length === 0 && (
              <div className="text-low" style={{ fontSize: 12 }}>No assets match this filter.</div>
            )}
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
                    <button className="btn btn-sm btn-ghost" onClick={() => { setPlatform(p); t(`${p} preset applied to the active draft.`, 'info') }}>Use</button>
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
            Approving a post moves it toward publish-readiness. Nothing publishes automatically, and approval is never a purchase
            or budget authorization.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Approval Queue</h3>
              <span className={`pill ${reviewCount ? 'pill-ochre' : 'pill-muted'}`}>{reviewCount} awaiting</span>
            </div>
            {inReview.length === 0 ? (
              <div className="empty">
                <div className="empty-title">Nothing awaiting review</div>
                <div className="empty-text">Send a draft from the Workflow board to see it here. Approval only marks readiness — nothing publishes.</div>
                <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={() => go('queue')}>Open Workflow</button>
              </div>
            ) : (
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'title', label: 'Draft' },
                { key: 'campaign', label: 'Campaign', render: (v) => campaignName(v) },
                { key: 'state', label: 'State', render: (v) => <span className={`pill ${STAGE_PILL[v] || 'pill-muted'}`}>{v}</span> },
                { key: 'actions', label: '', render: (v, row) => (
                  <div className="inline-flex" style={{ gap: 6 }}>
                    <button className="btn btn-sm" onClick={() => advance(row.id, 'Approved', 'Approved — still requires publish-ready + a manual schedule; nothing publishes.')}>Approve</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => advance(row.id, 'Draft', 'Returned to draft with requested changes.')}>Request Changes</button>
                  </div>
                ) },
              ]} rows={inReview} />
            )}
          </div>
        </div>
      )}

      {view === 'analytics' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Engagement metrics are not verified">
            Reach, engagement rate, and follower figures require a connected social analytics provider. No provider is connected
            in this build, so those read UNKNOWN. Counts below are the local workflow record only.
          </DataNotice>
          <MetricTiles columns={4} metrics={[
            { label: 'Drafts', value: String(posts.filter(p => p.state === 'Draft').length), sub: 'Local records' },
            { label: 'In Review', value: String(reviewCount), sub: 'Local records' },
            { label: 'Publish-Ready', value: String(posts.filter(p => p.state === 'Publish-ready').length), sub: 'Ready for manual schedule' },
            { label: 'Scheduled (manual)', value: String(posts.filter(p => p.state === 'Scheduled').length), sub: 'Reminders only — nothing posts' },
          ]} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Performance Rollup</h3>
              <span className="pill pill-muted">provider not connected</span>
            </div>
            <div className="grid-4" style={{ gap: 16 }}>
              {[
                { label: 'Posts published', note: 'No publishing pipeline exists' },
                { label: 'Reach', note: 'No analytics provider connected' },
                { label: 'Engagement rate', note: 'No analytics provider connected' },
                { label: 'Top platform', note: 'No analytics provider connected' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--clay)' }}>UNKNOWN</div>
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

// Count posts for a campaign key without re-running the full memo (used on the
// Campaigns grid where each card needs its own campaign's posts).
function postsInCampaignFor(key, all) {
  return all.filter(p => p.campaign === key)
}
