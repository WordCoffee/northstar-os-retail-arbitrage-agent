import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

// ═══════════════════════════════════════════════════════════════════════════
// CREATIVE STUDIO — service-local creative operations workspace.
//
// HONESTY CONTRACT (this room):
//   • Briefs, compose requests, reference assets, variants, and export bundles
//     are REAL LOCAL workspace records (persisted in this browser). They are
//     the operator's own planning/record data — not provider output.
//   • NO image or video is ever generated or depicted here. There is no wired
//     image/video provider in this build. Preview surfaces show an explicit
//     "local provider required" boundary instead of a fabricated asset.
//   • A local image CLI exists in-repo (tools/generate_images.py → ComfyUI,
//     plus pollinations/cloudflare/huggingface) and model_router.resolve_vision
//     resolves local generation to `comfyui`, gated by MEDIA_GEN_LIVE. Neither
//     is exposed to this UI yet, so the room states that boundary rather than
//     pretending a pipeline exists.
//   • No video pipeline exists anywhere in the repo.
// ═══════════════════════════════════════════════════════════════════════════

const TABS = [
  { id: 'briefs', label: 'Briefs' },
  { id: 'composer', label: 'Image Composer' },
  { id: 'adcreative', label: 'Ad Creative' },
  { id: 'video', label: 'Video / Shorts' },
  { id: 'queue', label: 'Production Queue' },
  { id: 'variants', label: 'Variants & History' },
  { id: 'assets', label: 'Assets' },
  { id: 'exports', label: 'Exports' },
  { id: 'library', label: 'Library' },
]

// Ad-creative framing — placements are editorial guidance for variant planning,
// NOT live ad-platform reporting. Each yields a placement-appropriate aspect.
const AD_PLACEMENTS = [
  { key: 'top-search', label: 'Top of Search', aspect: '16:9', note: 'Highest intent — lead with the offer and a clear headline.' },
  { key: 'product-pages', label: 'Product Pages', aspect: '1:1', note: 'Comparison shoppers — show the offer, rating, and pack.' },
  { key: 'reels', label: 'Reels / Shorts', aspect: '9:16', note: 'Sound-off hook in the first two seconds.' },
  { key: 'stories', label: 'Stories', aspect: '9:16', note: 'Single benefit + one tap-through CTA.' },
  { key: 'feed', label: 'Social Feed', aspect: '4:5', note: 'Thumb-stopping visual; the caption carries the offer.' },
]
const AD_CTA = ['Shop now', 'Learn more', 'See the offer', 'Get the deal', 'Compare options']

// ── Local provider posture. Verified against the repo (2026-10-04):
//    → A local image CLI exists (tools/generate_images.py --backend local →
//      ComfyUI at COMFYUI_URL), but NO HTTP route exposes it to this app.
//    → No local engine is reachable in this build and MEDIA_GEN_LIVE is off.
//    → Image AND video generation are therefore PLANNED — NOT ARMED.
//    Generation truth categories this room must distinguish:
//      local (available) · gated (provider) · demo-only · planned/not-armed.
const GEN_STATE = {
  local: { pill: 'pill-forest', text: 'LOCAL GENERATION AVAILABLE' },
  gated: { pill: 'pill-ochre', text: 'PROVIDER-GATED' },
  demo: { pill: 'pill-muted', text: 'DEMO-ONLY' },
  planned: { pill: 'pill-unknown', text: 'PLANNED — NOT ARMED' },
}

const IMAGE_PROVIDER = {
  connected: false,
  state: 'planned',
  label: 'Local image engine',
  engine: 'ComfyUI',
  env: 'COMFYUI_URL',
  gate: 'MEDIA_GEN_LIVE',
  models: 'FLUX.2 klein / FLUX.1 dev (weights must be installed)',
}
const VIDEO_PROVIDER = {
  connected: false,
  state: 'planned',
  label: 'Video / short-clip engine',
  engine: 'fal (Kling / Wan / Veo)',
  env: 'fal provider key',
  gate: 'MEDIA_GEN_LIVE',
  models: 'No local video pipeline exists in this build',
}

// Static prerequisite checklist. The app does NOT probe the engine yet (no
// media route is wired), so each item is labelled with its honest truth state.
const READINESS = [
  { key: 'route', label: 'Generation route exposed to the app', detail: 'No media endpoint exists — planned, not wired', ok: false },
  { key: 'engine', label: 'Local engine reachable', detail: `${IMAGE_PROVIDER.engine} at ${IMAGE_PROVIDER.env} (default http://127.0.0.1:8188) — not probed`, ok: false },
  { key: 'models', label: 'Model weights installed', detail: `${IMAGE_PROVIDER.models} — operator-managed, unknown`, ok: false },
  { key: 'gate', label: 'Media live gate enabled', detail: `${IMAGE_PROVIDER.gate}=1 (off by default)`, ok: false },
  { key: 'gpu', label: 'GPU available for local render', detail: 'Operator machine only (RTX 5080 16GB per setup notes) — not probed', ok: false },
]

const ASPECTS = ['1:1', '4:5', '9:16', '16:9', '3:2']
const SIZES = ['1024px (1MP)', '1280×720', '1536px', '2048px (4MP · 4× cost)']
const STAGES = ['Draft (iterate cheap)', 'Final (top tier)']
const FORMATS = ['Ad creative', 'Social variant', 'Listing imagery', 'A+ content', 'Email hero']
const STYLE_DIRECTIONS = ['Clean studio', 'Lifestyle / in-use', 'Bold graphic', 'Editorial', 'Flat lay', 'UGC / candid']
const VIDEO_PURPOSE = ['UGC / testimonial', 'Product motion', 'Ad hook', 'Storyboard / moodboard']
const VIDEO_DURATION = ['5s', '15s (Short / TikTok)', '30s']
const VIDEO_ASPECT = ['9:16 (vertical)', '1:1 (square)', '16:9 (landscape)']

const BRIEF_STATUS = { Draft: 'pill-muted', Active: 'pill-warn', 'In Review': 'pill-ochre', Archived: 'pill-muted' }
// Terminal local state before any engine exists. Aligned with the verified
// media truth (no route wired, engine not reachable) — "planned, not armed",
// not "provider required".
const REQ_BLOCKED = 'Blocked — generation not armed'
const REQUEST_STATE = {
  Draft: 'pill-muted',
  [REQ_BLOCKED]: 'pill-unknown',
  Queued: 'pill-warn',
  'In Review': 'pill-ochre',
  Approved: 'pill-forest',
  'Changes Requested': 'pill-warn',
  Complete: 'pill-forest',
  Error: 'pill-error',
}

function pillFor(state) { return REQUEST_STATE[state] || BRIEF_STATUS[state] || 'pill-muted' }

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

// ── Seed records (clearly sample; only used until the operator adds their own) ──
const SEED_BRIEFS = [
  { id: 'BR-01', name: 'Set A Launch — Ad Creatives', objective: 'Drive awareness', audience: 'Homeowners 30–55', brand: 'Word Coffee', formats: ['Ad creative', 'Social variant', 'Listing imagery'], deliverables: 6, status: 'Active', note: 'Hero + feature set, matched brand kit.', createdAt: '2026-09-20T00:00:00Z' },
  { id: 'BR-02', name: 'Q4 Seasonal Bundle', objective: 'Seasonal promo', audience: 'Existing customers', brand: 'Word Coffee', formats: ['Social variant', 'Email hero'], deliverables: 4, status: 'Draft', note: 'Seasonal palette, copy pending.', createdAt: '2026-09-22T00:00:00Z' },
  { id: 'BR-03', name: 'Installation Guide Refresh', objective: 'Support conversion', audience: 'New buyers', brand: 'Mogra Organics', formats: ['Listing imagery', 'A+ content'], deliverables: 3, status: 'In Review', note: 'Step-by-step panel set.', createdAt: '2026-09-24T00:00:00Z' },
]
const SEED_ASSETS = [
  { id: 'AS-01', name: 'brand-kit-logos.svg', type: 'Brand', collection: 'Brand kit', state: 'Approved', attached: ['BR-01'] },
  { id: 'AS-02', name: 'product-photo-01.jpg', type: 'Photo', collection: 'Product photography', state: 'Approved', attached: [] },
  { id: 'AS-03', name: 'ad-creative-hero.jpg', type: 'Ad', collection: 'Ad creatives', state: 'In Review', attached: ['BR-01'] },
  { id: 'AS-04', name: 'variant-bg-q4.jpg', type: 'Ad', collection: 'Ad creatives', state: 'Draft', attached: ['BR-02'] },
  { id: 'AS-05', name: 'aplus-banner-01.jpg', type: 'A+', collection: 'Listing imagery', state: 'Approved', attached: ['BR-03'] },
  { id: 'AS-06', name: 'packshot-angle-02.jpg', type: 'Photo', collection: 'Product photography', state: 'UNREVIEWED', attached: [] },
]
const SEED_VARIANTS = [
  { id: 'V-101', brief: 'BR-01', format: 'Ad creative', aspect: '1:1', state: 'Approved', note: 'Hero + feature, matched brand kit', createdAt: '2026-09-21T00:00:00Z' },
  { id: 'V-102', brief: 'BR-01', format: 'Ad creative', aspect: '4:5', state: 'In Review', note: 'Alt crop — awaiting brand reviewer', createdAt: '2026-09-21T00:00:00Z' },
  { id: 'V-103', brief: 'BR-01', format: 'Social variant', aspect: '9:16', state: 'Draft', note: 'Reel hook frame — tighten headline', createdAt: '2026-09-22T00:00:00Z' },
  { id: 'V-104', brief: 'BR-02', format: 'Social variant', aspect: '1:1', state: 'Draft', note: 'Seasonal palette, no copy yet', createdAt: '2026-09-23T00:00:00Z' },
  { id: 'V-105', brief: 'BR-03', format: 'Listing imagery', aspect: '16:9', state: 'Approved', note: 'Step-by-step panel 1 of 3', createdAt: '2026-09-24T00:00:00Z' },
]
const SEED_COLLECTIONS = [
  { name: 'Brand kit', count: 24, note: 'Logos, type, colour, tone' },
  { name: 'Product photography', count: 38, note: 'Studio + lifestyle shots' },
  { name: 'Ad creatives', count: 17, note: 'Static + video ad frames' },
  { name: 'Listing imagery', count: 8, note: 'A+ content + main-image sets' },
]

// Video storyboard beats — local planning records only (no clip is rendered).
const SEED_BEATS = [
  { id: 'SB-01', seconds: 2, text: 'Hook — product on counter, natural light' },
  { id: 'SB-02', seconds: 4, text: 'Problem — sediment visible in tap water' },
  { id: 'SB-03', seconds: 5, text: 'Demo — install in under 5 minutes, no tools' },
  { id: 'SB-04', seconds: 4, text: 'Proof — before/after taste test' },
]

function Thumb({ height = 90, label, note = 'no preview · local record' }) {
  return (
    <div style={{
      height, borderRadius: 6, marginBottom: 10,
      border: '1px dashed var(--divider-mid)',
      background: 'repeating-linear-gradient(45deg, rgba(138,138,122,0.07) 0 6px, transparent 6px 12px)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3,
      color: 'var(--ink-soft)',
    }} title="Placeholder — this room stores workflow records, not generated imagery">
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: 0.06, textTransform: 'uppercase' }}>{label}</span>
      <span style={{ fontSize: 10, textAlign: 'center', padding: '0 8px' }}>{note}</span>
    </div>
  )
}

function ProviderBoundary({ provider }) {
  const meta = GEN_STATE[provider.state] || GEN_STATE.planned
  return (
    <div className="alert" style={{ marginBottom: 0 }}>
      <div className="alert-title">
        <span className={`pill ${meta.pill}`}>{meta.text}</span> {provider.label} — no generation route is wired to this app
      </div>
      <div className="alert-text">
        This build records <strong>local planning records only</strong>. Nothing is rendered: the app exposes no media
        endpoint and no local engine is reachable here. Expected engine: <strong>{provider.engine}</strong> · env{' '}
        <span className="text-mono">{provider.env}</span> · gate <span className="text-mono">{provider.gate}</span>.{' '}
        {provider.models}. No placeholder image is shown in place of a render.
      </div>
    </div>
  )
}

// Compact legend so the four generation truth states are explicit, not implied.
function GenerationTruthLegend({ active = 'planned' }) {
  return (
    <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
      {Object.entries(GEN_STATE).map(([k, v]) => (
        <span key={k} className={`pill ${k === active ? v.pill : 'pill-muted'}`} style={{ fontSize: 10, opacity: k === active ? 1 : 0.6 }} title={k === active ? 'This room’s current media state' : 'Not the current state'}>
          {v.text}
        </span>
      ))}
    </div>
  )
}

function ReadinessChecklist() {
  const okCount = READINESS.filter(r => r.ok).length
  return (
    <div className="card">
      <div className="card-head">
        <h3 className="card-title" style={{ fontSize: 15 }}>Provider Readiness</h3>
        <span className="pill pill-unknown" title="Static checklist — the app does not probe the engine yet">static · not live-probed</span>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        {READINESS.map(r => (
          <div key={r.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <span className={`pill ${r.ok ? 'pill-forest' : 'pill-unknown'}`} style={{ flexShrink: 0 }}>{r.ok ? 'ready' : 'not satisfied'}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500 }}>{r.label}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{r.detail}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="text-low" style={{ fontSize: 11, marginTop: 12 }}>
        {okCount} of {READINESS.length} prerequisites satisfied. This checklist is <strong>static</strong> — the app does not
        probe the local engine, so nothing here is a live check. Arming generation requires a media route plus an
        operator-side ComfyUI install, model weights, and <span className="text-mono">{IMAGE_PROVIDER.gate}=1</span>.
      </div>
      <div style={{ marginTop: 10 }}>
        <GenerationTruthLegend active={IMAGE_PROVIDER.state} />
      </div>
    </div>
  )
}

export default function CreativeStudio() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [briefs, setBriefs] = useLocalRoom('ns-creative-briefs', SEED_BRIEFS)
  const [requests, setRequests] = useLocalRoom('ns-creative-requests', [])
  const [assets, setAssets] = useLocalRoom('ns-creative-assets', SEED_ASSETS)
  const [variants, setVariants] = useLocalRoom('ns-creative-variants', SEED_VARIANTS)
  const [bundles, setBundles] = useLocalRoom('ns-creative-bundles', [])
  const [handoffs, setHandoffs] = useLocalRoom('ns-creative-handoffs', [])
  const [beats, setBeats] = useLocalRoom('ns-creative-video-beats', SEED_BEATS)
  const [adVars, setAdVars] = useLocalRoom('ns-creative-ad-variants', [])

  const [activeBriefId, setActiveBriefId] = useState(briefs[0]?.id || '')
  const [assetFilter, setAssetFilter] = useState('All')
  const [assetQuery, setAssetQuery] = useState('')
  // Variants & History filters (lineage views)
  const [variantScope, setVariantScope] = useState('active')
  const [variantStateFilter, setVariantStateFilter] = useState('All')
  const [historyFilter, setHistoryFilter] = useState('All')
  const [outputs, setOutputs] = useState(['Ad creatives', 'Listing imagery'])

  // composer fields
  const [prompt, setPrompt] = useState('')
  const [brand, setBrand] = useState('Word Coffee')
  const [aspect, setAspect] = useState('1:1')
  const [size, setSize] = useState('1024px (1MP)')
  const [format, setFormat] = useState('Ad creative')
  const [stage, setStage] = useState('Draft (iterate cheap)')
  const [styleDir, setStyleDir] = useState('Clean studio')
  const [refIds, setRefIds] = useState([])

  // video fields
  const [vPurpose, setVPurpose] = useState('UGC / testimonial')
  const [vDuration, setVDuration] = useState('15s (Short / TikTok)')
  const [vAspect, setVAspect] = useState('9:16 (vertical)')
  const [vAssetId, setVAssetId] = useState('')

  // brief editing
  const [editBrief, setEditBrief] = useState(false)
  const [briefDraft, setBriefDraft] = useState(null)

  // ad creative fields
  const [adHook, setAdHook] = useState('Stop buying filters that miss the sediment.')
  const [adOffer, setAdOffer] = useState('Save 20% on the countertop filter set')
  const [adCta, setAdCta] = useState('Shop now')
  const [adAudience, setAdAudience] = useState('Homeowners 30–55')
  const [adPlacements, setAdPlacements] = useState(['top-search', 'feed'])
  const [adPlacementFilter, setAdPlacementFilter] = useState('All')
  const [adStateFilter, setAdStateFilter] = useState('All')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'briefs'

  const go = (t) => navigate(`/creative-studio?view=${t}`)
  const t = (msg, tone = 'info') => toast(msg, tone)

  const active = useMemo(
    () => briefs.find(b => b.id === activeBriefId) || briefs[0] || null,
    [briefs, activeBriefId],
  )

  // Variants recorded against the active brief — the lineage basis for the
  // bundle builder (not a global variant count).
  const briefVariants = useMemo(
    () => variants.filter(v => v.brief === (active?.id || '')),
    [variants, active],
  )
  const briefAssets = useMemo(
    () => assets.filter(a => (a.attached || []).includes(active?.id || '')),
    [assets, active],
  )

  const filteredVariants = useMemo(() => variants.filter(v =>
    (variantScope === 'all' || v.brief === (active?.id || '')) &&
    (variantStateFilter === 'All' || v.state === variantStateFilter),
  ), [variants, variantScope, variantStateFilter, active])

  const filteredAdVars = useMemo(() => adVars.filter(v =>
    (adPlacementFilter === 'All' || v.placementKey === adPlacementFilter) &&
    (adStateFilter === 'All' || v.state === adStateFilter),
  ), [adVars, adPlacementFilter, adStateFilter])
  const adDecisions = useMemo(() => adVars
    .flatMap(v => (v.history || []).map(h => ({ ...h, id: v.id, placement: v.placement })))
    .sort((a, b) => (b.at || '').localeCompare(a.at || ''))
    .slice(0, 6), [adVars])

  const filteredAssets = useMemo(() => {
    const q = assetQuery.trim().toLowerCase()
    return assets.filter(a =>
      (assetFilter === 'All' || a.type === assetFilter) &&
      (!q || a.name.toLowerCase().includes(q) || (a.collection || '').toLowerCase().includes(q)),
    )
  }, [assets, assetFilter, assetQuery])

  // Keep the active brief valid after the store changes.
  useEffect(() => {
    if (briefs.length && !briefs.some(b => b.id === activeBriefId)) setActiveBriefId(briefs[0].id)
  }, [briefs, activeBriefId])

  const addBrief = () => {
    const id = uid('BR')
    const nid = briefs.length + 1
    setBriefs(prev => [{
      id, name: `New Brief ${nid}`, objective: 'Untitled objective', audience: 'Unspecified',
      brand, formats: [format], deliverables: 1, status: 'Draft',
      note: 'Local draft — complete the work brief.', createdAt: nowIso(),
    }, ...prev])
    setActiveBriefId(id)
    t('New brief draft created — work-brief inputs are local drafts (sample). No image generates until local generation is armed.', 'info')
    go('composer')
  }

  // Inline brief editing — a brief is a real local object, so its objective,
  // audience, brand, and deliverable count are editable after creation.
  const startEditBrief = () => {
    if (!active) return
    setBriefDraft({
      name: active.name, objective: active.objective, audience: active.audience,
      brand: active.brand, deliverables: active.deliverables,
    })
    setEditBrief(true)
  }
  const saveBrief = () => {
    if (!active || !briefDraft) return
    const n = Number(briefDraft.deliverables)
    setBriefs(prev => prev.map(b => b.id === active.id ? {
      ...b, ...briefDraft,
      name: (briefDraft.name || '').trim() || b.name,
      deliverables: Number.isFinite(n) && n > 0 ? n : b.deliverables,
    } : b))
    setEditBrief(false)
    t(`Brief ${active.id} updated (local record).`, 'info')
  }
  const setBriefField = (k, v) => setBriefDraft(prev => ({ ...prev, [k]: v }))

  const toggleRef = (id) => setRefIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  const submitRequest = (kind) => {
    if (kind === 'image' && !prompt.trim()) {
      t('Add a work brief / prompt before queuing a request.', 'warn')
      return
    }
    const id = uid('RQ')
    const rec = {
      id, kind, briefId: active?.id || '',
      prompt: kind === 'image' ? prompt.trim() : `${vPurpose} · ${vDuration} · ${vAspect}`,
      brand, aspect: kind === 'image' ? aspect : vAspect,
      size: kind === 'image' ? size : vDuration,
      format: kind === 'image' ? format : 'Short clip',
      stage: kind === 'image' ? stage : 'Draft (iterate cheap)',
      style: kind === 'image' ? styleDir : '',
      refs: kind === 'image' ? refIds : (vAssetId ? [vAssetId] : []),
      // No engine exists yet: the honest terminal state is "generation not armed".
      state: REQ_BLOCKED,
      providerState: 'not_armed',
      note: kind === 'image' ? 'Awaiting armed local image generation (planned, not armed).' : 'Awaiting armed video generation (planned, not armed).',
      createdAt: nowIso(),
    }
    setRequests(prev => [rec, ...prev])
    t(`${kind === 'image' ? 'Image' : 'Video'} request queued locally — blocked because generation is planned, not armed. Nothing was generated.`, 'info')
  }

  const advanceRequest = (id, nextState) => {
    setRequests(prev => prev.map(r => r.id === id ? { ...r, state: nextState } : r))
    t(`Request ${id} → ${nextState} (local record only).`, 'info')
  }

  const removeRequest = (id) => {
    setRequests(prev => prev.filter(r => r.id !== id))
    t(`Request ${id} removed from the local queue.`, 'info')
  }

  const addVariant = () => {
    const id = uid('V')
    setVariants(prev => [{
      id, brief: active?.id || '', format, aspect, state: 'Draft',
      note: 'Added locally — not a generated asset.', createdAt: nowIso(),
    }, ...prev])
    t('Variant record added locally (sample workflow). Not a generated asset.', 'info')
  }

  // Distinct from "Queue Image Request": this records a small set of aspect
  // variant RECORDS for the active brief. It generates no media — that still
  // requires a connected provider. (Previously it duplicated queueing.)
  const generateVariants = () => {
    if (!active) { t('Select an active brief before adding variants.', 'warn'); return }
    const aspectSet = ['1:1', '4:5', '9:16']
    const created = aspectSet.map(a => ({
      id: uid('V'), brief: active.id, format, aspect: a, state: 'Draft',
      note: `Draft variant record (${a}) — local workflow record, not generated media.`,
      createdAt: nowIso(),
    }))
    setVariants(prev => [...created, ...prev])
    t(`Added ${created.length} draft variant records (${aspectSet.join(', ')}) to ${active.name} — workflow records only; no image was generated.`, 'info')
  }

  const setVariantState = (id, state) => {
    setVariants(prev => prev.map(v => v.id === id ? { ...v, state } : v))
    t(`Variant ${id} → ${state} (internal review state — not publishing authorization).`, 'info')
  }

  // Lineage: record a variant row from a queued request (no media is produced).
  const addVariantFromRequest = (req) => {
    const id = uid('V')
    setVariants(prev => [{
      id, brief: req.briefId || active?.id || '', format: req.format || format,
      aspect: req.aspect || aspect, state: 'Draft', fromRequest: req.id,
      note: `Created from request ${req.id} — local record, not generated media.`, createdAt: nowIso(),
    }, ...prev])
    t(`Variant ${id} added from request ${req.id} (local lineage record).`, 'info')
  }

  // Storyboard beats — local planning records for the short-clip shell.
  const addBeat = () => {
    setBeats(prev => [...prev, { id: uid('SB'), seconds: 3, text: '' }])
    t('Storyboard beat added (local planning record — no clip is generated).', 'info')
  }
  const updateBeat = (id, patch) => setBeats(prev => prev.map(b => b.id === id ? { ...b, ...patch } : b))
  const removeBeat = (id) => setBeats(prev => prev.filter(b => b.id !== id))
  const totalSeconds = beats.reduce((n, b) => n + (Number(b.seconds) || 0), 0)

  // Ad-creative variant set — one local record per selected placement, framed
  // by hook/offer/CTA. No ad is generated or published.
  const togglePlacement = (k) => setAdPlacements(prev => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k])
  const buildAdSet = () => {
    if (!adPlacements.length) { t('Select at least one placement before building an ad set.', 'warn'); return }
    const at = nowIso()
    const created = adPlacements.map(k => {
      const pl = AD_PLACEMENTS.find(p => p.key === k)
      return {
        id: uid('AV'), briefId: active?.id || '', placementKey: k, placement: pl.label,
        aspect: pl.aspect, hook: adHook.trim() || '(no hook)', offer: adOffer.trim() || '(no offer)',
        cta: adCta, audience: adAudience, state: 'Draft', note: pl.note, createdAt: at,
        history: [{ at, from: null, to: 'Draft' }],
      }
    })
    setAdVars(prev => [...created, ...prev])
    t(`Built ${created.length} ad-creative variant records across ${adPlacements.length} placement(s) — local planning records; no ad is generated or published.`, 'info')
  }
  const setAdVariantState = (id, state) => {
    const at = nowIso()
    setAdVars(prev => prev.map(v => v.id === id ? { ...v, state, history: [...(v.history || []), { at, from: v.state, to: state }] } : v))
    t(`Ad variant ${id} → ${state} (local review state — not a publishing or spend authorization).`, 'info')
  }
  const removeAdVariant = (id) => setAdVars(prev => prev.filter(v => v.id !== id))

  const toggleOutput = (o) => setOutputs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o])

  const prepareBundle = () => {
    const id = uid('BX')
    const briefId = active?.id || ''
    const variantRefs = briefVariants.map(v => v.id)
    const assetRefs = briefAssets.map(a => a.id)
    setBundles(prev => [{
      id, briefId, briefName: active?.name || 'No active brief',
      outputs: [...outputs], variantRefs, assetRefs, basis: 'local workspace records',
      status: 'Ready for handoff', createdAt: nowIso(),
    }, ...prev])
    t(`Bundle ${id} prepared locally — ${variantRefs.length} variant refs · ${assetRefs.length} asset refs. References only; download needs an asset store.`, 'info')
  }

  // Local handoff log — records what was handed to an adjacent room (references
  // only; nothing is transferred, published, or uploaded). Persisted
  // synchronously so the entry survives the immediate room navigation.
  const recordHandoff = (target, what, refs) => {
    setHandoffs(prev => {
      const next = [{ id: uid('HX'), target, what, refs: refs || [], at: nowIso() }, ...prev].slice(0, 20)
      try { localStorage.setItem('ns-creative-handoffs', JSON.stringify(next)) } catch { /* storage unavailable */ }
      return next
    })
  }

  const briefName = (id) => briefs.find(b => b.id === id)?.name || id || '—'
  const totalCollectionItems = SEED_COLLECTIONS.reduce((n, c) => n + c.count, 0)
  const blockedCount = requests.filter(r => r.state === REQ_BLOCKED).length
  const queuedCount = requests.filter(r => r.state === 'Queued').length

  return (
    <PageLayout
      title="Creative Studio"
      subtitle="Creative operations — work briefs, image and short-clip requests, reference assets, variants, and export bundles."
      actions={<>
        <button className="btn btn-sm" onClick={addBrief}>New Brief</button>
        <button className="btn btn-sm btn-ghost" onClick={() => { go('composer'); t('Image Composer opened — generation is planned, not armed; only local records are created.', 'info') }}>Compose Image</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('exports')}>Export Bundle</button>
      </>}
    >
      <div className="room-bottom-safe">
      <DataNotice tone="sample" title="This room is a local workflow workspace">
        Briefs, requests, assets, variants, and bundles are real records you create here and are stored in this browser.
        No image or video is generated or depicted — there is no wired creative provider in this build. A blocked request
        means generation is <strong>planned, not armed</strong>, not that an asset failed.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="text-low" style={{ fontSize: 11 }}>Active brief</span>
          {briefs.map(b => (
            <button key={b.id} className={`filter-pill ${active?.id === b.id ? 'active' : ''}`} onClick={() => setActiveBriefId(b.id)} title={`${b.objective} · ${b.status}`}>{b.name}</button>
          ))}
          {active && <span className={`pill ${BRIEF_STATUS[active.status] || 'pill-muted'}`} style={{ marginLeft: 'auto' }}>{active.status}</span>}
        </div>
      </div>

      <RoomTabs tabs={TABS} base="/creative-studio" />

      {view === 'briefs' && (
        <div className="subview">
          <div className="grid-cards-3" style={{ marginBottom: 20 }}>
            {briefs.map(b => (
              <div key={b.id} className="card" style={{ padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: 13 }}>{b.name}</strong>
                  <span className={`pill ${BRIEF_STATUS[b.status] || 'pill-muted'}`}>{b.status}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--ink-mid)', marginBottom: 6 }}>{b.objective} · {b.audience}</div>
                <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>{b.brand}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                  {b.formats.map(f => <span key={f} className="pill pill-muted" style={{ fontSize: 10 }}>{f}</span>)}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="text-low" style={{ fontSize: 11 }}>{b.deliverables} deliverables</span>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setActiveBriefId(b.id); go('composer') }}>Open</button>
                </div>
              </div>
            ))}
          </div>

          {active && (
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Active Brief — {active.name}</h3>
                <div className="inline-flex" style={{ gap: 8 }}>
                  <span className={`pill ${BRIEF_STATUS[active.status] || 'pill-muted'}`}>{active.status}</span>
                  {!editBrief && <button className="btn btn-sm btn-ghost" onClick={startEditBrief}>Edit Brief</button>}
                </div>
              </div>
              {editBrief && briefDraft ? (
                <div className="stack" style={{ gap: 12 }}>
                  <div className="field-group" style={{ marginBottom: 0 }}>
                    <label className="label" htmlFor="br-name">Brief name</label>
                    <input id="br-name" className="field" value={briefDraft.name} onChange={e => setBriefField('name', e.target.value)} />
                  </div>
                  <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                    <div className="field-group" style={{ minWidth: 200, marginBottom: 0 }}>
                      <label className="label" htmlFor="br-objective">Objective</label>
                      <input id="br-objective" className="field" value={briefDraft.objective} onChange={e => setBriefField('objective', e.target.value)} />
                    </div>
                    <div className="field-group" style={{ minWidth: 200, marginBottom: 0 }}>
                      <label className="label" htmlFor="br-audience">Audience</label>
                      <input id="br-audience" className="field" value={briefDraft.audience} onChange={e => setBriefField('audience', e.target.value)} />
                    </div>
                  </div>
                  <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                    <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                      <label className="label" htmlFor="br-brand">Brand / context</label>
                      <select id="br-brand" className="field" value={briefDraft.brand} onChange={e => setBriefField('brand', e.target.value)}>
                        {['Word Coffee', 'Mogra Organics', 'Neck Nirvana', 'Northstar OS'].map(b => <option key={b}>{b}</option>)}
                      </select>
                    </div>
                    <div className="field-group" style={{ minWidth: 140, marginBottom: 0 }}>
                      <label className="label" htmlFor="br-deliverables">Deliverables</label>
                      <input id="br-deliverables" className="field" type="number" min="1" value={briefDraft.deliverables} onChange={e => setBriefField('deliverables', e.target.value)} />
                    </div>
                  </div>
                  <div className="inline-flex" style={{ gap: 8 }}>
                    <button className="btn btn-sm" onClick={saveBrief}>Save Brief</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => setEditBrief(false)}>Cancel</button>
                  </div>
                  <div className="text-low" style={{ fontSize: 11 }}>Brief fields are local workspace records — not provider output.</div>
                </div>
              ) : (
                <>
                  <div className="grid-4" style={{ gap: 16 }}>
                    {[
                      { label: 'Objective', v: active.objective },
                      { label: 'Audience', v: active.audience },
                      { label: 'Brand', v: active.brand },
                      { label: 'Deliverables', v: `${active.deliverables} · ${active.formats.join(', ')}` },
                    ].map(d => (
                      <div key={d.label}>
                        <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{d.v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 12 }}>{active.note}</div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <ProviderBoundary provider={IMAGE_PROVIDER} />
          <div className="split-aside" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Work Brief — Image Request</h3>
                <span className="pill pill-muted">{active ? active.name : 'no active brief'}</span>
              </div>
              <div className="stack" style={{ gap: 12 }}>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="cs-prompt">Prompt / work brief</label>
                  <textarea
                    id="cs-prompt" className="field" rows={4} value={prompt}
                    onChange={e => setPrompt(e.target.value)}
                    placeholder="Describe the intended image: subject, mood, composition, copy to render, and where it will be used…"
                  />
                </div>
                <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-brand">Brand / context</label>
                    <select id="cs-brand" className="field" value={brand} onChange={e => setBrand(e.target.value)}>
                      {['Word Coffee', 'Mogra Organics', 'Neck Nirvana', 'Northstar OS'].map(b => <option key={b}>{b}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 150, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-format">Output format</label>
                    <select id="cs-format" className="field" value={format} onChange={e => setFormat(e.target.value)}>
                      {FORMATS.map(f => <option key={f}>{f}</option>)}
                    </select>
                  </div>
                </div>
                <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                  <div className="field-group" style={{ minWidth: 120, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-aspect">Aspect</label>
                    <select id="cs-aspect" className="field" value={aspect} onChange={e => setAspect(e.target.value)}>
                      {ASPECTS.map(a => <option key={a}>{a}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 190, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-size">Resolution</label>
                    <select id="cs-size" className="field" value={size} onChange={e => setSize(e.target.value)}>
                      {SIZES.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 200, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-stage">Staging tier</label>
                    <select id="cs-stage" className="field" value={stage} onChange={e => setStage(e.target.value)}>
                      {STAGES.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="cs-style">Style direction</label>
                    <select id="cs-style" className="field" value={styleDir} onChange={e => setStyleDir(e.target.value)}>
                      {STYLE_DIRECTIONS.map(s => <option key={s}>{s}</option>)}
                    </select>
                  </div>
                </div>

                <div>
                  <div className="label">Reference assets (frame consistency)</div>
                  {assets.length === 0
                    ? <div className="text-low" style={{ fontSize: 12 }}>No reference assets yet — add them in the Assets tab.</div>
                    : <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {assets.map(a => (
                          <button
                            key={a.id}
                            type="button"
                            aria-pressed={refIds.includes(a.id)}
                            className={`ref-chip ${refIds.includes(a.id) ? 'selected' : ''}`}
                            onClick={() => toggleRef(a.id)}
                            title={`${a.collection} · ${a.state}`}
                          >
                            {a.name}
                          </button>
                        ))}
                      </div>}
                </div>

                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => submitRequest('image')}>Queue Image Request</button>
                  <button className="btn btn-sm btn-ghost" onClick={generateVariants} title="Records draft variant rows for the active brief — generates no image">Generate Variants</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setPrompt(''); setRefIds([]); t('Composer cleared (local).', 'info') }}>Clear</button>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>
                  Queue Image Request stores a real local request record. Generate Variants records draft variant rows for the
                  active brief. Neither renders an image: the app has no media route, so generation is{' '}
                  <strong>planned, not armed</strong>. Arming needs {IMAGE_PROVIDER.env} pointing at a running{' '}
                  {IMAGE_PROVIDER.engine}, model weights installed, and {IMAGE_PROVIDER.gate}=1.
                </div>
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <ReadinessChecklist />
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Preview</h3>
                  <span className="pill pill-unknown" style={{ fontSize: 10 }}>planned · not armed</span>
                </div>
                <Thumb height={150} label={`${aspect} · ${format}`} note="No generated asset — planned, not armed" />
                <div className="text-low" style={{ fontSize: 11 }}>
                  This preview stays empty until a connected provider returns an asset. A blank frame here is the honest state, not a failed load.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'adcreative' && (
        <div className="subview">
          <DataNotice tone="internal" title="Ad-creative variants are local planning records">
            Hook, offer, and CTA framing plus placement targeting are recorded locally. No ad is generated, no ad account is
            connected, and placement guidance is editorial — not live ad-platform reporting. Nothing here authorizes spend.
          </DataNotice>

          <div className="split-aside" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Ad Creative Brief</h3>
                <span className="pill pill-muted">{active ? active.name : 'no active brief'}</span>
              </div>
              <div className="stack" style={{ gap: 12 }}>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="ad-hook">Hook / headline</label>
                  <input id="ad-hook" className="field" value={adHook} onChange={e => setAdHook(e.target.value)} />
                </div>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="ad-offer">Offer</label>
                  <input id="ad-offer" className="field" value={adOffer} onChange={e => setAdOffer(e.target.value)} />
                </div>
                <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="ad-cta">Call to action</label>
                    <select id="ad-cta" className="field" value={adCta} onChange={e => setAdCta(e.target.value)}>
                      {AD_CTA.map(c => <option key={c}>{c}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 200, marginBottom: 0 }}>
                    <label className="label" htmlFor="ad-audience">Audience</label>
                    <input id="ad-audience" className="field" value={adAudience} onChange={e => setAdAudience(e.target.value)} />
                  </div>
                </div>

                <div>
                  <div className="label">Placements (targeting)</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {AD_PLACEMENTS.map(pl => (
                      <button
                        key={pl.key}
                        type="button"
                        aria-pressed={adPlacements.includes(pl.key)}
                        className={`filter-pill ${adPlacements.includes(pl.key) ? 'active' : ''}`}
                        onClick={() => togglePlacement(pl.key)}
                        title={pl.note}
                      >
                        {pl.label} · {pl.aspect}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={buildAdSet}>Build Ad Set</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setAdHook(''); setAdOffer(''); t('Ad brief cleared (local).', 'info') }}>Clear</button>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>
                  Building records one variant per selected placement with a placement-appropriate aspect. No image is
                  generated — a connected provider is still required to render any creative.
                </div>
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Placement Fit</h3>
                  <span className="pill pill-unverified" style={{ fontSize: 10 }} title="Editorial guidance — not measured performance">guidance</span>
                </div>
                <div className="stack" style={{ gap: 8 }}>
                  {AD_PLACEMENTS.map(pl => (
                    <div key={pl.key}>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{pl.label} <span className="text-low">· {pl.aspect}</span></div>
                      <div className="text-low" style={{ fontSize: 11 }}>{pl.note}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Ad Variant Set</h3>
              <span className="pill pill-muted">{filteredAdVars.length} of {adVars.length} · local records</span>
            </div>
            {adVars.length > 0 && (
              <div className="room-toolbar">
                <span className="text-low" style={{ fontSize: 11, marginRight: 4 }}>Placement</span>
                <button className={`filter-pill ${adPlacementFilter === 'All' ? 'active' : ''}`} onClick={() => setAdPlacementFilter('All')}>All</button>
                {AD_PLACEMENTS.map(pl => (
                  <button key={pl.key} className={`filter-pill ${adPlacementFilter === pl.key ? 'active' : ''}`} onClick={() => setAdPlacementFilter(pl.key)}>{pl.label}</button>
                ))}
                <span className="text-low" style={{ fontSize: 11, marginLeft: 8, marginRight: 4 }}>State</span>
                {['All', 'Draft', 'Changes Requested', 'Approved'].map(s => (
                  <button key={s} className={`filter-pill ${adStateFilter === s ? 'active' : ''}`} onClick={() => setAdStateFilter(s)}>{s}</button>
                ))}
              </div>
            )}
            {adVars.length === 0 ? (
              <div className="empty">
                <div className="empty-title">No ad variants yet</div>
                <div className="empty-text">Pick placements and build an ad set to record placement-aware variants here. Nothing is generated or published.</div>
              </div>
            ) : (
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'briefId', label: 'Brief', render: (v) => <span className="text-low" style={{ fontSize: 11 }}>{briefName(v)}</span> },
                { key: 'placement', label: 'Placement' },
                { key: 'aspect', label: 'Aspect', render: (v) => <span className="pill pill-muted">{v}</span> },
                { key: 'hook', label: 'Hook', render: (v) => <span style={{ fontSize: 12 }}>{v.length > 30 ? v.slice(0, 30) + '…' : v}</span> },
                { key: 'cta', label: 'CTA' },
                { key: 'state', label: 'State', render: (v) => <span className={`pill ${pillFor(v)}`} title="Local review state — not a publishing or spend authorization">{v}</span> },
                { key: 'actions', label: '', render: (v, row) => (
                  <div className="inline-flex" style={{ gap: 6 }}>
                    {row.state === 'Approved'
                      ? <span className="text-low" style={{ fontSize: 10 }}>Approved</span>
                      : <>
                          <button className="btn btn-sm btn-ghost" onClick={() => setAdVariantState(row.id, 'Changes Requested')}>Request Changes</button>
                          <button className="btn btn-sm btn-ghost" onClick={() => setAdVariantState(row.id, 'Approved')}>Approve</button>
                        </>}
                    <button className="btn btn-sm btn-ghost" onClick={() => removeAdVariant(row.id)}>Remove</button>
                  </div>
                ) },
              ]} rows={filteredAdVars} />
            )}
            {filteredAdVars.length === 0 && adVars.length > 0 && (
              <div className="text-low" style={{ fontSize: 12 }}>No ad variants match this placement/state filter.</div>
            )}
            {adDecisions.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Recent ad-set decisions · local review trail</div>
                <div className="stack" style={{ gap: 6 }}>
                  {adDecisions.map((d, i) => (
                    <div key={`${d.id}-${i}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, fontSize: 11 }}>
                      <span className="text-low">{d.from ? `${d.from} → ${d.to}` : `created → ${d.to}`} · {d.id} · {d.placement}</span>
                      <span className="text-low">{d.at ? new Date(d.at).toLocaleString() : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {adVars.length > 0 && (
              <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm btn-ghost" onClick={() => { recordHandoff('AdPilot', `Ad set (${adVars.length} variants)`, adVars.map(v => v.id)); navigate('/adpilot'); t('Ad set handed to AdPilot — planning references only; nothing was published or spent.', 'info') }}>Send to AdPilot</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { recordHandoff('SocialPulse', `Ad set (${adVars.length} variants)`, adVars.map(v => v.id)); navigate('/socialpulse'); t('Ad set handed to SocialPulse — references only; uncertainty preserved.', 'info') }}>Send to SocialPulse</button>
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'video' && (
        <div className="subview">
          <ProviderBoundary provider={VIDEO_PROVIDER} />
          <div className="split-aside" style={{ marginTop: 16 }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Short-Clip Workflow Shell</h3>
                <span className="pill pill-muted">{active ? active.name : 'no active brief'}</span>
              </div>
              <div className="stack" style={{ gap: 12 }}>
                <div className="inline-flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                  <div className="field-group" style={{ minWidth: 190, marginBottom: 0 }}>
                    <label className="label" htmlFor="v-purpose">Purpose</label>
                    <select id="v-purpose" className="field" value={vPurpose} onChange={e => setVPurpose(e.target.value)}>
                      {VIDEO_PURPOSE.map(p => <option key={p}>{p}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 200, marginBottom: 0 }}>
                    <label className="label" htmlFor="v-duration">Duration</label>
                    <select id="v-duration" className="field" value={vDuration} onChange={e => setVDuration(e.target.value)}>
                      {VIDEO_DURATION.map(d => <option key={d}>{d}</option>)}
                    </select>
                  </div>
                  <div className="field-group" style={{ minWidth: 180, marginBottom: 0 }}>
                    <label className="label" htmlFor="v-aspect">Aspect</label>
                    <select id="v-aspect" className="field" value={vAspect} onChange={e => setVAspect(e.target.value)}>
                      {VIDEO_ASPECT.map(a => <option key={a}>{a}</option>)}
                    </select>
                  </div>
                </div>
                <div className="field-group" style={{ marginBottom: 0 }}>
                  <label className="label" htmlFor="v-asset">Seed / source asset</label>
                  <select id="v-asset" className="field" value={vAssetId} onChange={e => setVAssetId(e.target.value)}>
                    <option value="">None (text-to-video)</option>
                    {assets.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => submitRequest('video')}>Queue Clip Request</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t(`Storyboard saved locally (${beats.length} beats, ~${totalSeconds}s) — no clip is generated.`, 'info')}>Save Storyboard</button>
                </div>

                <div style={{ borderTop: '1px solid var(--divider)', paddingTop: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span className="label" style={{ marginBottom: 0 }}>Storyboard beats</span>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{beats.length} beats · ~{totalSeconds}s</span>
                  </div>
                  <div className="stack" style={{ gap: 6 }}>
                    {beats.map((b, i) => (
                      <div key={b.id} className="inline-flex" style={{ gap: 6, flexWrap: 'nowrap', alignItems: 'center' }}>
                        <span className="text-low" style={{ fontSize: 10, width: 16, flexShrink: 0 }}>{i + 1}</span>
                        <input className="field" style={{ flex: 1, minWidth: 0, padding: '5px 8px', fontSize: 12 }} value={b.text} placeholder="Beat description…" onChange={e => updateBeat(b.id, { text: e.target.value })} />
                        <input className="field" type="number" min="1" style={{ width: 60, flexShrink: 0, padding: '5px 8px', fontSize: 12 }} value={b.seconds} onChange={e => updateBeat(b.id, { seconds: e.target.value })} />
                        <button className="btn btn-sm btn-ghost" style={{ flexShrink: 0 }} onClick={() => removeBeat(b.id)} title="Remove beat">✕</button>
                      </div>
                    ))}
                    {beats.length === 0 && <div className="text-low" style={{ fontSize: 12 }}>No beats yet — add one to sketch the clip.</div>}
                  </div>
                  <button className="btn btn-sm btn-ghost" style={{ marginTop: 8 }} onClick={addBeat}>Add Beat</button>
                  <div className="text-low" style={{ fontSize: 10, marginTop: 6 }}>Beats are local planning records — no clip is generated from them.</div>
                </div>

                <div className="text-low" style={{ fontSize: 11 }}>
                  Video tooling is a planning shell — <strong>planned, not armed</strong>. No local video pipeline exists in
                  this build and no media route is wired; a connected {VIDEO_PROVIDER.engine} provider plus{' '}
                  {VIDEO_PROVIDER.gate}=1 is required before any clip can render.
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Clip Preview</h3>
                <span className="pill pill-unknown" style={{ fontSize: 10 }}>planned · not armed</span>
              </div>
              <Thumb height={150} label={`${vAspect} · ${vDuration}`} note="No clip — planned, not armed" />
              <div className="stack" style={{ gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span className="text-low">Purpose</span><span>{vPurpose}</span></div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span className="text-low">Source asset</span><span>{vAssetId ? (assets.find(a => a.id === vAssetId)?.name || vAssetId) : 'text-to-video'}</span></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'queue' && (
        <div className="subview">
          <MetricTiles columns={3} metrics={[
            { label: 'Requests', value: String(requests.length), sub: 'Local records' },
            { label: 'Blocked — generation not armed', value: String(blockedCount), sub: 'Honest terminal state', tone: blockedCount ? 'warn' : undefined },
            { label: 'Queued', value: String(queuedCount), sub: 'Awaiting a worker' },
          ]} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Production Queue</h3>
              <span className="pill pill-muted">local records · no worker connected</span>
            </div>
            {requests.length === 0 ? (
              <div className="empty">
                <div className="empty-title">No requests yet</div>
                <div className="empty-text">Queue an image or video request from the composer to record it here. Until local generation is armed, requests stay blocked — they never fake a completion.</div>
                <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={() => go('composer')}>Open Image Composer</button>
              </div>
            ) : (
              <DataTable
                columns={[
                  { key: 'id', label: 'ID' },
                  { key: 'kind', label: 'Type', render: (v) => <span className="pill pill-muted">{v === 'video' ? 'Video' : 'Image'}</span> },
                  { key: 'briefId', label: 'Brief', render: (v) => <span className="text-low" style={{ fontSize: 11 }}>{briefName(v)}</span> },
                  { key: 'prompt', label: 'Prompt', render: (v) => <span style={{ fontSize: 12 }}>{v.length > 40 ? v.slice(0, 40) + '…' : v}</span> },
                  { key: 'format', label: 'Format' },
                  { key: 'state', label: 'State', render: (v) => <span className={`pill ${pillFor(v)}`} title="Local workflow state — a provider still has to render">{v}</span> },
                  { key: 'actions', label: '', render: (v, row) => (
                    <div className="inline-flex" style={{ gap: 6 }}>
                      {row.state === REQ_BLOCKED && (
                        <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(row.id, 'Queued')} title="Queueing does not connect a provider">Queue anyway</button>
                      )}
                      {row.state === 'Queued' && (
                        <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(row.id, 'Error')} title="Simulate the worker error path (local demo)">Simulate error</button>
                      )}
                      <button className="btn btn-sm btn-ghost" onClick={() => addVariantFromRequest(row)} title="Record a variant row from this request (no media produced)">Add variant</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => removeRequest(row.id)}>Remove</button>
                    </div>
                  ) },
                ]}
                rows={requests}
              />
            )}
          </div>
        </div>
      )}

      {view === 'variants' && (
        <div className="subview">
          <div className="room-toolbar">
            <span className="text-low" style={{ fontSize: 11, marginRight: 4 }}>Scope</span>
            {[['active', 'Active brief'], ['all', 'All briefs']].map(([k, lbl]) => (
              <button key={k} className={`filter-pill ${variantScope === k ? 'active' : ''}`} onClick={() => setVariantScope(k)}>{lbl}</button>
            ))}
            <span className="text-low" style={{ fontSize: 11, marginLeft: 8, marginRight: 4 }}>State</span>
            {['All', 'Draft', 'In Review', 'Approved', 'Changes Requested'].map(s => (
              <button key={s} className={`filter-pill ${variantStateFilter === s ? 'active' : ''}`} onClick={() => setVariantStateFilter(s)}>{s}</button>
            ))}
            <span className="pill pill-muted" style={{ marginLeft: 'auto' }}>{filteredVariants.length} of {variants.length} · local records</span>
            <button className="btn btn-sm" onClick={addVariant}>Add Variant</button>
          </div>
          <div className="grid-cards-3">
            {filteredVariants.map(v => (
              <div key={v.id} className="card" style={{ padding: 12 }}>
                <Thumb height={110} label={`${v.aspect} · ${v.format}`} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: 12 }}>{v.id}</strong>
                  <span className={`pill ${pillFor(v.state)}`} style={{ fontSize: 10 }} title="Internal review state — not publishing authorization">{v.state}</span>
                </div>
                <div className="text-low" style={{ fontSize: 11, marginBottom: 2 }}>{briefName(v.brief)}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginBottom: 8 }}>{v.note}</div>
                {v.fromRequest && (
                  <div className="text-low" style={{ fontSize: 10, marginBottom: 8 }} title="Lineage: the queued request this variant was recorded from">From request: {v.fromRequest}</div>
                )}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {v.state === 'Approved' ? (
                    <span className="pill pill-forest" style={{ fontSize: 10 }} title="Approved — final internal review state; not a publishing authorization">Approved — no action needed</span>
                  ) : (
                    <>
                      {v.state !== 'Changes Requested' && (
                        <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(v.id, 'Changes Requested')}>Request Changes</button>
                      )}
                      <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(v.id, 'Approved')}>Approve</button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {filteredVariants.length === 0 && (
              <div className="text-low" style={{ fontSize: 12 }}>No variants match this scope/state filter.</div>
            )}
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title" style={{ fontSize: 15 }}>History</h3>
              <div className="inline-flex" style={{ gap: 6 }}>
                {['All', 'Requests', 'Variants'].map(f => (
                  <button key={f} className={`filter-pill ${historyFilter === f ? 'active' : ''}`} onClick={() => setHistoryFilter(f)}>{f}</button>
                ))}
                <span className="pill pill-muted">local record log</span>
              </div>
            </div>
            {(requests.length === 0 && variants.length === 0) ? (
              <div className="text-low" style={{ fontSize: 12 }}>No history yet.</div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {[...requests.map(r => ({ ...r, _kind: 'request' })), ...variants.map(v => ({ ...v, _kind: 'variant' }))]
                  .filter(h => historyFilter === 'All' || (historyFilter === 'Requests' ? h._kind === 'request' : h._kind === 'variant'))
                  .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
                  .slice(0, 12)
                  .map((h, i) => (
                    <div key={`${h._kind}-${h.id}-${i}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                      <div>
                        <span className={`pill ${pillFor(h.state)}`} style={{ marginRight: 8 }}>{h.state}</span>
                        <span style={{ fontSize: 12 }}>{h._kind === 'request' ? `${h.kind === 'video' ? 'Video' : 'Image'} request` : 'Variant'} {h.id}</span>
                        <span className="text-low" style={{ fontSize: 11, marginLeft: 8 }}>{briefName(h._kind === 'request' ? h.briefId : h.brief)}</span>
                        {h._kind === 'variant' && h.fromRequest && <span className="text-low" style={{ fontSize: 10, marginLeft: 8 }}>← {h.fromRequest}</span>}
                      </div>
                      <span className="text-low" style={{ fontSize: 11 }}>{h.createdAt ? new Date(h.createdAt).toLocaleString() : '—'}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'assets' && (
        <div className="subview">
          <div className="room-toolbar">
            <span className="text-low" style={{ fontSize: 11, marginRight: 4 }}>Filter</span>
            {['All', 'Brand', 'Photo', 'Ad', 'A+'].map(f => (
              <button key={f} className={`filter-pill ${assetFilter === f ? 'active' : ''}`} onClick={() => setAssetFilter(f)}>{f}</button>
            ))}
            <input
              className="field"
              style={{ width: 200, padding: '5px 10px', fontSize: 12 }}
              placeholder="Search assets or collections…"
              value={assetQuery}
              onChange={e => setAssetQuery(e.target.value)}
              aria-label="Search assets"
            />
            <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={() => t('Asset upload is not connected — this room records asset metadata only. Nothing is uploaded.', 'warn')}>Upload Asset</button>
          </div>
          <div className="grid-cards-3">
            {filteredAssets.map(a => (
              <div key={a.id} className="card" style={{ padding: 12 }}>
                <Thumb label={a.type} note="reference asset · metadata only" />
                <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>{a.name}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.collection}</span>
                  {a.state === 'Approved'
                    ? <span className="pill pill-muted" style={{ fontSize: 10 }} title="Internal review state — not an authorization">{a.state}</span>
                    : a.state === 'UNREVIEWED'
                      ? <span className="pill pill-unknown" style={{ fontSize: 10 }}>{a.state}</span>
                      : <span className="pill pill-warn" style={{ fontSize: 10 }}>{a.state}</span>}
                </div>
                <div className="text-low" style={{ fontSize: 10, marginTop: 6 }}>
                  {a.attached.length ? `Attached to ${a.attached.map(briefName).join(', ')}` : 'Not attached'}
                </div>
                <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Variants recorded against the attached brief(s) — local linkage, not a rendered asset">
                  Linked variants: {variants.filter(v => a.attached.includes(v.brief)).length}
                </div>
                <div className="inline-flex" style={{ gap: 6, marginTop: 8 }}>
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => { setRefIds([a.id]); setAssetFilter('All'); go('composer'); t(`${a.name} set as the composer reference asset (frame consistency) — local only.`, 'info') }}
                  >
                    Use as reference
                  </button>
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => { recordHandoff('SocialPulse', `Asset ${a.name}`, [a.id]); navigate('/socialpulse'); t(`${a.name} handed to SocialPulse as a reference — metadata only; no upload or publish.`, 'info') }}
                  >
                    Send to SocialPulse
                  </button>
                </div>
              </div>
            ))}
            {filteredAssets.length === 0 && (
              <div className="text-low" style={{ fontSize: 12 }}>No assets match this filter.</div>
            )}
          </div>
        </div>
      )}

      {view === 'exports' && (
        <div className="subview">
          <DataNotice tone="internal" title="Export bundles package references, not media">
            A bundle lists existing creative references for handoff to SocialPulse or ListingForge. Download is unavailable
            until an asset store is connected — nothing is published, listed, or transferred from here.
          </DataNotice>
          <div className="split-aside">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Bundle Builder — {active ? active.name : 'no active brief'}</h3>
              </div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Select outputs · basis is the active brief’s lineage</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                {['Ad creatives', 'Social variants', 'Listing imagery'].map(o => (
                  <button key={o} className={`filter-pill ${outputs.includes(o) ? 'active' : ''}`} onClick={() => toggleOutput(o)}>{o}</button>
                ))}
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {[
                  { item: 'Ad creatives', basis: `${briefVariants.filter(v => v.format === 'Ad creative').length} variant refs` },
                  { item: 'Listing imagery', basis: `${briefVariants.filter(v => v.format === 'Listing imagery').length} panel refs` },
                  { item: 'Social variants', basis: `${briefVariants.filter(v => v.format === 'Social variant').length} refs` },
                ].map(r => (
                  <div key={r.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{r.item}</div>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{r.basis}</span>
                  </div>
                ))}
              </div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 8 }}>
                Lineage for {active ? active.name : 'no active brief'}: {briefVariants.length} variants · {briefAssets.length} attached assets.
              </div>
              <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm" onClick={prepareBundle}>Prepare Export</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { recordHandoff('SocialPulse', `Bundle outputs: ${outputs.join(', ') || 'none selected'}`, [...briefVariants.map(v => v.id), ...briefAssets.map(a => a.id)]); navigate('/socialpulse'); t('Bundle handed to SocialPulse — reference only, uncertainty preserved.', 'info') }}>Send to SocialPulse</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { recordHandoff('ListingForge', `Bundle outputs: ${outputs.join(', ') || 'none selected'}`, [...briefVariants.map(v => v.id), ...briefAssets.map(a => a.id)]); navigate('/listingforge'); t('Bundle handed to ListingForge — reference only, uncertainty preserved.', 'info') }}>Send to ListingForge</button>
              </div>
              {bundles.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Prepared bundles (local)</div>
                  <div className="stack" style={{ gap: 0 }}>
                    {bundles.map(b => (
                      <div key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: 500 }}>{b.id} · {b.briefName || briefName(b.briefId)}</div>
                          <div className="text-low" style={{ fontSize: 10 }}>{b.outputs.join(', ')} · {(b.variantRefs || []).length} variant refs · {(b.assetRefs || []).length} asset refs</div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <span className="pill pill-muted" style={{ fontSize: 10 }}>{b.status}</span>
                          <div className="text-low" style={{ fontSize: 10, marginTop: 2 }}>{b.createdAt ? new Date(b.createdAt).toLocaleString() : ''}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Bundle Preview</h3>
                <span className="pill pill-muted">{outputs.length} outputs</span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
                {outputs.length ? outputs.map(o => <span key={o} className="pill pill-muted" style={{ fontSize: 10 }}>{o}</span>) : <span className="text-low" style={{ fontSize: 11 }}>No outputs selected</span>}
              </div>
              <Thumb height={120} label="bundle manifest" note="references only — no media packaged" />
              <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Manifest contents (references)</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                {briefVariants.length === 0 && briefAssets.length === 0 && <span className="text-low" style={{ fontSize: 11 }}>No lineage yet — record variants or attach assets for this brief.</span>}
                {briefVariants.map(v => <span key={v.id} className="pill pill-muted" style={{ fontSize: 10 }} title={`${v.format} · ${v.aspect} · ${v.state}`}>{v.id}</span>)}
                {briefAssets.map(a => <span key={a.id} className="pill pill-muted" style={{ fontSize: 10 }} title={a.collection}>{a.id}</span>)}
              </div>
              <div className="inline-flex" style={{ gap: 8, marginTop: 10 }}>
                <button className="btn btn-sm" disabled title="Download requires a connected asset store; the bundle manifest is local only">Download Bundle</button>
                <span className="pill pill-unknown" style={{ fontSize: 10 }}>download unavailable — no asset store</span>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title" style={{ fontSize: 15 }}>Handoff log</h3>
              <span className="pill pill-muted">local record · references only</span>
            </div>
            {handoffs.length === 0 ? (
              <div className="text-low" style={{ fontSize: 12 }}>No handoffs recorded yet. Sending a bundle or ad set to an adjacent room records a local reference entry here — nothing is transferred.</div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {handoffs.map(h => (
                  <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ minWidth: 0 }}>
                      <span className="pill pill-muted" style={{ fontSize: 10, marginRight: 8 }}>{h.target}</span>
                      <span style={{ fontSize: 12 }}>{h.what}</span>
                      <div className="text-low" style={{ fontSize: 10, marginTop: 2 }}>{h.id} · {(h.refs || []).length} refs{(h.refs || []).length ? `: ${h.refs.slice(0, 6).join(', ')}${h.refs.length > 6 ? '…' : ''}` : ''}</div>
                    </div>
                    <span className="text-low" style={{ fontSize: 11, flexShrink: 0 }}>{h.at ? new Date(h.at).toLocaleString() : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'library' && (
        <div className="subview">
          <MetricTiles columns={4} metrics={[
            { label: 'Collections', value: String(SEED_COLLECTIONS.length), sub: 'Brand library structure (sample)' },
            { label: 'Sample inventory', value: String(totalCollectionItems), sub: 'Sample counts — not a real index' },
            { label: 'Tracked in this room', value: String(assets.length), sub: 'Real local asset records' },
            { label: 'Unreviewed', value: String(assets.filter(a => a.state === 'UNREVIEWED').length), sub: 'Needs review — not an authorization', tone: 'warn' },
          ]} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Creative Collections</h3>
              <span className="pill pill-muted">sample inventory + tracked-local</span>
            </div>
            <div className="grid-cards-4">
              {SEED_COLLECTIONS.map(c => {
                const tracked = assets.filter(a => a.collection === c.name).length
                return (
                  <div key={c.name} className="card" style={{ padding: 14 }}>
                    <Thumb height={72} label="collection" note={`${c.count} sample items`} />
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{c.name}</div>
                    <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>{c.note}</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                      <span className="pill pill-muted" style={{ fontSize: 10 }} title="Static sample inventory count">sample: {c.count}</span>
                      <span className="pill pill-forest" style={{ fontSize: 10 }} title="Real asset records in this room for this collection">tracked: {tracked}</span>
                    </div>
                    <button className="btn btn-sm btn-ghost" onClick={() => { setAssetQuery(c.name); go('assets'); t(`${c.name} — showing tracked assets in this room. Sample inventory counts are illustrative only.`, 'info') }}>Open tracked assets</button>
                  </div>
                )
              })}
            </div>
            <div className="text-low" style={{ fontSize: 11, marginTop: 14 }} title="Library counts are sample inventory — not publishing or purchase authorization">
              “sample” counts are static illustrative inventory; “tracked” counts are real asset records stored in this room.
              Opening a collection never publishes or authorizes anything.
            </div>
          </div>
        </div>
      )}
      </div>
    </PageLayout>
  )
}
