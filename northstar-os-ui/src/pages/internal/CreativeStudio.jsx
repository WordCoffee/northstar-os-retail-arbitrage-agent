import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import MockupStudio from '../../components/MockupStudio.jsx'
import AssetRegistry from '../../components/AssetRegistry.jsx'
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
  { id: 'mockups', label: 'Exact-Text Mockups' },
  { id: 'registry', label: 'Registry & Bundles' },
  { id: 'video', label: 'Video / Shorts' },
  { id: 'queue', label: 'Production Queue' },
  { id: 'variants', label: 'Variants & History' },
  { id: 'assets', label: 'Assets' },
  { id: 'exports', label: 'Exports' },
  { id: 'library', label: 'Library' },
]

// ── Local provider posture. Verified against repo: no creative route is
//    exposed to the UI; the local engine is not connected in this build. ──
const IMAGE_PROVIDER = {
  connected: false,
  label: 'Local image engine',
  engine: 'ComfyUI',
  env: 'COMFYUI_URL',
  gate: 'MEDIA_GEN_LIVE',
  models: 'FLUX.2 klein / FLUX.1 dev (weights must be installed)',
}
const VIDEO_PROVIDER = {
  connected: false,
  label: 'Video / short-clip engine',
  engine: 'fal (Kling / Wan / Veo)',
  env: 'fal provider key',
  gate: 'MEDIA_GEN_LIVE',
  models: 'No local video pipeline exists in this build',
}

const READINESS = [
  { key: 'engine', label: 'Local image engine reachable', detail: `${IMAGE_PROVIDER.engine} at ${IMAGE_PROVIDER.env}`, ok: false },
  { key: 'models', label: 'Model weights installed', detail: IMAGE_PROVIDER.models, ok: false },
  { key: 'gate', label: 'Media live gate enabled', detail: `${IMAGE_PROVIDER.gate}=1`, ok: false },
  { key: 'gpu', label: 'GPU available for local render', detail: 'RTX 5080 16GB (per project setup notes)', ok: false },
]

const ASPECTS = ['1:1', '4:5', '9:16', '16:9', '3:2']
const SIZES = ['1024px (1MP)', '1280×720', '1536px', '2048px (4MP · 4× cost)']
const STAGES = ['Draft (iterate cheap)', 'Final (top tier)']
const FORMATS = ['Ad creative', 'Social variant', 'Listing imagery', 'A+ content', 'Email hero']
const VIDEO_PURPOSE = ['UGC / testimonial', 'Product motion', 'Ad hook', 'Storyboard / moodboard']
const VIDEO_DURATION = ['5s', '15s (Short / TikTok)', '30s']
const VIDEO_ASPECT = ['9:16 (vertical)', '1:1 (square)', '16:9 (landscape)']

const BRIEF_STATUS = { Draft: 'pill-muted', Active: 'pill-warn', 'In Review': 'pill-ochre', Archived: 'pill-muted' }
const REQUEST_STATE = {
  Draft: 'pill-muted',
  'Blocked — provider required': 'pill-unknown',
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
  return (
    <div className="alert" style={{ marginBottom: 0 }}>
      <div className="alert-title">
        <span className="pill pill-unknown">PROVIDER REQUIRED</span> {provider.label} is not connected
      </div>
      <div className="alert-text">
        Expected engine: <strong>{provider.engine}</strong> · env <span className="text-mono">{provider.env}</span> · gate <span className="text-mono">{provider.gate}</span>.
        {' '}{provider.models}. Nothing is generated until this boundary is satisfied — no placeholder image is shown in its place.
      </div>
    </div>
  )
}

function ReadinessChecklist() {
  const okCount = READINESS.filter(r => r.ok).length
  return (
    <div className="card">
      <div className="card-head">
        <h3 className="card-title" style={{ fontSize: 15 }}>Provider Readiness</h3>
        <span className={`pill ${okCount === READINESS.length ? 'pill-forest' : 'pill-unknown'}`}>{okCount} / {READINESS.length} ready</span>
      </div>
      <div className="stack" style={{ gap: 8 }}>
        {READINESS.map(r => (
          <div key={r.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <span className={`pill ${r.ok ? 'pill-forest' : 'pill-unknown'}`} style={{ flexShrink: 0 }}>{r.ok ? 'ready' : 'not connected'}</span>
            <div>
              <div style={{ fontSize: 12, fontWeight: 500 }}>{r.label}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{r.detail}</div>
            </div>
          </div>
        ))}
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

  const [activeBriefId, setActiveBriefId] = useState(briefs[0]?.id || '')
  const [assetFilter, setAssetFilter] = useState('All')
  const [outputs, setOutputs] = useState(['Ad creatives', 'Listing imagery'])

  // composer fields
  const [prompt, setPrompt] = useState('')
  const [brand, setBrand] = useState('Word Coffee')
  const [aspect, setAspect] = useState('1:1')
  const [size, setSize] = useState('1024px (1MP)')
  const [format, setFormat] = useState('Ad creative')
  const [stage, setStage] = useState('Draft (iterate cheap)')
  const [refIds, setRefIds] = useState([])

  // video fields
  const [vPurpose, setVPurpose] = useState('UGC / testimonial')
  const [vDuration, setVDuration] = useState('15s (Short / TikTok)')
  const [vAspect, setVAspect] = useState('9:16 (vertical)')
  const [vAssetId, setVAssetId] = useState('')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'briefs'

  const go = (t) => navigate(`/creative-studio?view=${t}`)
  const t = (msg, tone = 'info') => toast(msg, tone)

  const active = useMemo(
    () => briefs.find(b => b.id === activeBriefId) || briefs[0] || null,
    [briefs, activeBriefId],
  )

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
    t('New brief draft created — work-brief inputs are local drafts (sample). No image generates until a local provider is connected.', 'info')
    go('composer')
  }

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
      refs: kind === 'image' ? refIds : (vAssetId ? [vAssetId] : []),
      // No provider is connected: the honest terminal state is "blocked".
      state: 'Blocked — provider required',
      providerState: 'not_connected',
      note: kind === 'image' ? 'Awaiting connected local image provider.' : 'Awaiting connected video provider.',
      createdAt: nowIso(),
    }
    setRequests(prev => [rec, ...prev])
    t(`${kind === 'image' ? 'Image' : 'Video'} request queued locally — blocked until a provider is connected. Nothing was generated.`, 'info')
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

  const setVariantState = (id, state) => {
    setVariants(prev => prev.map(v => v.id === id ? { ...v, state } : v))
    t(`Variant ${id} → ${state} (internal review state — not publishing authorization).`, 'info')
  }

  const toggleOutput = (o) => setOutputs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o])

  const prepareBundle = () => {
    const id = uid('BX')
    setBundles(prev => [{
      id, briefId: active?.id || '', outputs: [...outputs], basis: 'local workspace records',
      status: 'Ready for handoff', createdAt: nowIso(),
    }, ...prev])
    t('Bundle manifest prepared locally — contains references only. Download is unavailable until an asset store is connected.', 'info')
  }

  const briefName = (id) => briefs.find(b => b.id === id)?.name || id || '—'
  const totalCollectionItems = SEED_COLLECTIONS.reduce((n, c) => n + c.count, 0)
  const blockedCount = requests.filter(r => r.state === 'Blocked — provider required').length
  const queuedCount = requests.filter(r => r.state === 'Queued').length

  return (
    <PageLayout
      title="Creative Studio"
      subtitle="Creative operations — work briefs, image and short-clip requests, reference assets, variants, and export bundles."
      actions={<>
        <button className="btn btn-sm" onClick={addBrief}>New Brief</button>
        <button className="btn btn-sm btn-ghost" onClick={() => { go('composer'); t('Image Composer opened — provider not connected, so no variants generate yet.', 'info') }}>Compose Image</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('exports')}>Export Bundle</button>
      </>}
    >
      <DataNotice tone="sample" title="This room is a local workflow workspace">
        Briefs, requests, assets, variants, and bundles are real records you create here and are stored in this browser.
        No image or video is generated or depicted — there is no wired creative provider in this build. A blocked request
        means the local engine is not connected, not that an asset failed.
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
                <span className={`pill ${BRIEF_STATUS[active.status] || 'pill-muted'}`}>{active.status}</span>
              </div>
              <div className="grid-4" style={{ gap: 16 }}>
                {[
                  { label: 'Objective', v: active.objective },
                  { label: 'Audience', v: active.audience },
                  { label: 'Brand', v: active.brand },
                  { label: 'Formats', v: active.formats.join(', ') },
                ].map(d => (
                  <div key={d.label}>
                    <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{d.v}</div>
                  </div>
                ))}
              </div>
              <div className="text-low" style={{ fontSize: 11, marginTop: 12 }}>{active.note}</div>
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
                </div>

                <div>
                  <div className="label">Reference assets (frame consistency)</div>
                  {assets.length === 0
                    ? <div className="text-low" style={{ fontSize: 12 }}>No reference assets yet — add them in the Assets tab.</div>
                    : <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {assets.map(a => (
                          <button key={a.id} className={`filter-pill ${refIds.includes(a.id) ? 'active' : ''}`} onClick={() => toggleRef(a.id)} title={`${a.collection} · ${a.state}`}>
                            {a.name}
                          </button>
                        ))}
                      </div>}
                </div>

                <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => submitRequest('image')}>Queue Image Request</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => submitRequest('image')}>Generate Variants</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { setPrompt(''); setRefIds([]); t('Composer cleared (local).', 'info') }}>Clear</button>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>
                  Queueing stores a real local request record. It cannot render until {IMAGE_PROVIDER.env} points at a running
                  {' '}{IMAGE_PROVIDER.engine} and {IMAGE_PROVIDER.gate}=1.
                </div>
              </div>
            </div>

            <div className="stack" style={{ gap: 16 }}>
              <ReadinessChecklist />
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Preview</h3>
                  <span className="pill pill-unknown" style={{ fontSize: 10 }}>provider required</span>
                </div>
                <Thumb height={150} label={`${aspect} · ${format}`} note="No generated asset — provider required" />
                <div className="text-low" style={{ fontSize: 11 }}>
                  This preview stays empty until a connected provider returns an asset. A blank frame here is the honest state, not a failed load.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'mockups' && <MockupStudio />}

      {view === 'registry' && <AssetRegistry />}

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
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Video storyboard is a local planning record only — no clip is generated.', 'info')}>Save Storyboard</button>
                </div>
                <div className="text-low" style={{ fontSize: 11 }}>
                  Video tooling is a planning shell. No local video pipeline exists in this build; a connected
                  {' '}{VIDEO_PROVIDER.engine} provider plus {VIDEO_PROVIDER.gate}=1 is required before any clip can render.
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Clip Preview</h3>
                <span className="pill pill-unknown" style={{ fontSize: 10 }}>provider required</span>
              </div>
              <Thumb height={150} label={`${vAspect} · ${vDuration}`} note="No clip — provider required" />
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
            { label: 'Blocked — provider required', value: String(blockedCount), sub: 'Honest terminal state', tone: blockedCount ? 'warn' : undefined },
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
                <div className="empty-text">Queue an image or video request from the composer to record it here. Until a provider is connected, requests stay blocked — they never fake a completion.</div>
                <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={() => go('composer')}>Open Image Composer</button>
              </div>
            ) : (
              <DataTable
                columns={[
                  { key: 'id', label: 'ID' },
                  { key: 'kind', label: 'Type', render: (v) => <span className="pill pill-muted">{v === 'video' ? 'Video' : 'Image'}</span> },
                  { key: 'prompt', label: 'Brief', render: (v) => <span style={{ fontSize: 12 }}>{v.length > 52 ? v.slice(0, 52) + '…' : v}</span> },
                  { key: 'format', label: 'Format' },
                  { key: 'state', label: 'State', render: (v) => <span className={`pill ${pillFor(v)}`} title="Local workflow state — a provider still has to render">{v}</span> },
                  { key: 'actions', label: '', render: (v, row) => (
                    <div className="inline-flex" style={{ gap: 6 }}>
                      {row.state === 'Blocked — provider required' && (
                        <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(row.id, 'Queued')} title="Queueing does not connect a provider">Queue anyway</button>
                      )}
                      {row.state === 'Queued' && (
                        <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(row.id, 'Error')} title="Simulate the worker error path (local demo)">Simulate error</button>
                      )}
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
            <span className="pill pill-muted" style={{ marginRight: 'auto' }}>{active ? active.name : 'no active brief'} · {variants.length} variants · local records</span>
            <button className="btn btn-sm" onClick={addVariant}>Add Variant</button>
          </div>
          <div className="grid-cards-3">
            {variants.map(v => (
              <div key={v.id} className="card" style={{ padding: 12 }}>
                <Thumb height={110} label={`${v.aspect} · ${v.format}`} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: 12 }}>{v.id}</strong>
                  <span className={`pill ${pillFor(v.state)}`} style={{ fontSize: 10 }} title="Internal review state — not publishing authorization">{v.state}</span>
                </div>
                <div className="text-low" style={{ fontSize: 11, marginBottom: 2 }}>{briefName(v.brief)}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginBottom: 8 }}>{v.note}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(v.id, 'Changes Requested')}>Request Changes</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(v.id, 'Approved')}>Approve</button>
                </div>
              </div>
            ))}
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title" style={{ fontSize: 15 }}>History</h3>
              <span className="pill pill-muted">local record log</span>
            </div>
            {(requests.length === 0 && variants.length === 0) ? (
              <div className="text-low" style={{ fontSize: 12 }}>No history yet.</div>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {[...requests.map(r => ({ ...r, _kind: 'request' })), ...variants.map(v => ({ ...v, _kind: 'variant' }))]
                  .sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
                  .slice(0, 12)
                  .map((h, i) => (
                    <div key={`${h._kind}-${h.id}-${i}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                      <div>
                        <span className={`pill ${pillFor(h.state)}`} style={{ marginRight: 8 }}>{h.state}</span>
                        <span style={{ fontSize: 12 }}>{h._kind === 'request' ? `${h.kind === 'video' ? 'Video' : 'Image'} request` : 'Variant'} {h.id}</span>
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
            <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={() => t('Asset upload is not connected — this room records asset metadata only. Nothing is uploaded.', 'warn')}>Upload Asset</button>
          </div>
          <div className="grid-cards-3">
            {assets.filter(a => assetFilter === 'All' || a.type === assetFilter).map(a => (
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
              </div>
            ))}
            {assets.filter(a => assetFilter === 'All' || a.type === assetFilter).length === 0 && (
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
              <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Select outputs</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                {['Ad creatives', 'Social variants', 'Listing imagery'].map(o => (
                  <button key={o} className={`filter-pill ${outputs.includes(o) ? 'active' : ''}`} onClick={() => toggleOutput(o)}>{o}</button>
                ))}
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {[
                  { item: 'Ad creatives', basis: `${variants.filter(v => v.format === 'Ad creative').length} variant refs` },
                  { item: 'Listing imagery', basis: `${variants.filter(v => v.format === 'Listing imagery').length} panel refs` },
                  { item: 'Social variants', basis: `${variants.filter(v => v.format === 'Social variant').length} refs` },
                ].map(r => (
                  <div key={r.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{r.item}</div>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{r.basis}</span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm" onClick={prepareBundle}>Prepare Export</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/socialpulse'); t('Bundle handed to SocialPulse — reference only, uncertainty preserved.', 'info') }}>Send to SocialPulse</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/listingforge'); t('Bundle handed to ListingForge — reference only, uncertainty preserved.', 'info') }}>Send to ListingForge</button>
              </div>
              {bundles.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Prepared bundles (local)</div>
                  <div className="stack" style={{ gap: 6 }}>
                    {bundles.map(b => (
                      <div key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, fontSize: 12 }}>
                        <span>{b.id} · {b.outputs.join(', ')}</span>
                        <span className="pill pill-muted" style={{ fontSize: 10 }}>{b.status}</span>
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
              <div className="inline-flex" style={{ gap: 8, marginTop: 10 }}>
                <button className="btn btn-sm" disabled title="Download requires a connected asset store; the bundle manifest is local only">Download Bundle</button>
                <span className="pill pill-unknown" style={{ fontSize: 10 }}>download unavailable — no asset store</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'library' && (
        <div className="subview">
          <MetricTiles columns={4} metrics={[
            { label: 'Collections', value: String(SEED_COLLECTIONS.length), sub: 'Brand library · sample counts' },
            { label: 'Assets in library', value: String(totalCollectionItems), sub: 'Sample inventory' },
            { label: 'Tracked in this room', value: String(assets.length), sub: 'Local asset records' },
            { label: 'Unreviewed', value: String(assets.filter(a => a.state === 'UNREVIEWED').length), sub: 'Needs review — not an authorization', tone: 'warn' },
          ]} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Creative Collections</h3>
              <span className="pill pill-muted">brand library · sample counts</span>
            </div>
            <div className="grid-cards-4">
              {SEED_COLLECTIONS.map(c => (
                <div key={c.name} className="card" style={{ padding: 14 }}>
                  <Thumb height={72} label="collection" note={`${c.count} items`} />
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{c.name}</div>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>{c.note}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{c.count} items</span>
                    <button className="btn btn-sm btn-ghost" onClick={() => t(`${c.name} collection opened (sample inventory).`, 'info')}>Open</button>
                  </div>
                </div>
              ))}
            </div>
            <div className="text-low" style={{ fontSize: 11, marginTop: 14 }} title="Library counts are sample inventory — not publishing or purchase authorization">
              Collection counts are sample inventory. Opening a collection never publishes or authorizes anything.
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
