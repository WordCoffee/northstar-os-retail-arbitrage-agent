// ═══════════════════════════════════════════════════════════════════════════
// LISTINGFORGE — /listingforge
//
// Listing copy studio: a working editor, real revision history, applicable
// templates, a real asset tray backed by the local asset store, and the hosted
// listing proposal (proposal only — never auto-applied, never published).
//
// HONESTY CONTRACT (this room):
//   • The listing being edited, every revision, and every uploaded asset are
//     REAL LOCAL records persisted in this browser (localStorage + IndexedDB).
//     They are the operator's own work, not provider output.
//   • Nothing is published to any marketplace. No route in this room calls a
//     marketplace API. Revision states are internal review states only.
//   • Keyword coverage and listing health are derived from the operator's own
//     text with a documented, deterministic rule set — they are labelled as
//     local heuristics, never as measured marketplace performance.
//   • The hosted proposal is a proposal: it is rendered for review and applied
//     only when the operator explicitly clicks "Apply to editor".
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import Icon from '../../components/Icon.jsx'
import ReasoningModelSelector, { useReasoningModel } from '../../components/ReasoningModelSelector.jsx'
import foundationApi from '../../foundation/api.js'
import { useToast } from '../../components/ToastContext.jsx'
import { ModeToggle, AssetThumb } from '../../studio/components/Chrome.jsx'
import { Field, TextInput, NumberInput, Slider, Select, SegmentedControl, Toggle, Section, Stat } from '../../studio/components/Fields.jsx'
import { useAssetStore, useDecodedAssets } from '../../studio/engine/assets.js'
import { useRoom, uid, nowIso, fmtTime, fmtBytes } from '../../studio/engine/store.js'

// ── Seed listings (clearly sample; superseded once the operator edits one) ────
const SEED_LISTINGS = [
  {
    asin: 'B08L5VJQ7T', title: 'Premium Water Filter', status: 'Revision v3.2', health: 82, updated: '2026-09-24T09:00:00Z',
    copy: {
      title: 'Premium Water Filter — 3-Stage Filtration, 10-Cup Capacity, BPA-Free',
      bullets: [
        '3-Stage Filtration: Removes 99.9% of contaminants',
        '10-Cup Capacity: Ideal for families of 4+',
        'BPA-Free Materials: FDA-certified safe',
        'Easy-Change Filters: No tools required',
        'Compact Design: Fits most standard cabinets',
      ].join('\n'),
      description: 'Experience clean, great-tasting water with the Premium Water Filter. Designed for modern kitchens, our 3-stage filtration system ensures your family has access to safe, great-tasting water every day.',
      keywords: 'water filter, water purifier, countertop filter, BPA free',
      brand: 'Demo Brand',
    },
  },
  { asin: 'B09M8KJ4X2', title: 'LED Desk Lamp', status: 'Live', health: 88, updated: '2026-09-23T14:00:00Z', copy: { title: 'LED Desk Lamp — Dimmable, USB-C Charging, 5 Colour Temperatures', bullets: 'Flicker-free LED panel\nUSB-C passthrough charging\n5 colour temperatures\nMemory dial returns to your last setting', description: 'A calm, even desk light with a memory dial and USB-C charging.', keywords: 'desk lamp, led lamp, dimmable lamp', brand: 'Demo Brand' } },
  { asin: 'B07XJ8C9F3', title: 'Car Phone Mount', status: 'Draft', health: 61, updated: '2026-09-21T10:00:00Z', copy: { title: 'Car Phone Mount — Magnetic, Vent-Clip, 360° Rotation', bullets: 'Strong magnetic hold\nVent clip, no adhesive\n360° rotation\nOne-hand operation', description: 'A vent-clip magnetic phone mount that installs in seconds.', keywords: 'phone mount, car mount, magnetic holder', brand: 'Demo Brand' } },
  { asin: 'B08N5WRWNW', title: 'Bluetooth Speaker', status: 'Live', health: 79, updated: '2026-09-20T16:00:00Z', copy: { title: 'Bluetooth Speaker — 24H Playtime, IPX7 Waterproof, Stereo Pairing', bullets: '24-hour playtime\nIPX7 waterproof\nStereo pairing with a second unit\nUSB-C fast charge', description: 'A rugged portable speaker with long playtime and stereo pairing.', keywords: 'bluetooth speaker, portable speaker, waterproof speaker', brand: 'Demo Brand' } },
]

const TEMPLATES = [
  {
    id: 'tpl-standard', name: 'Standard Launch', desc: 'Balanced title, 5 bullets, mid-length description.',
    use: 'Best for established categories',
    apply: (c) => ({
      ...c,
      title: c.title.length > 90 ? c.title : `${c.title} — Reliable, Ready to Use`,
      bullets: [...c.bullets.split('\n').filter(Boolean),
        'Satisfaction Guaranteed: Backed by our support team'].join('\n'),
    }),
  },
  {
    id: 'tpl-premium', name: 'Premium', desc: 'Serif-forward, story-driven description, lifestyle bullets.',
    use: 'Best for higher-margin private label',
    apply: (c) => ({
      ...c,
      description: `${c.description}\n\nMade to be used every day, and built to last — designed for people who care about the details.`,
      bullets: [...c.bullets.split('\n').filter(Boolean),
        'Thoughtful Design: Made to last beyond the trend cycle'].join('\n'),
    }),
  },
  {
    id: 'tpl-bulk', name: 'Bulk / Wholesale', desc: 'Spec-dense, pack-focused, compliance-heavy.',
    use: 'Best for multi-pack and B2B',
    apply: (c) => ({
      ...c,
      title: `${c.title} — Multi-Pack, Bulk Pricing Available`,
      bullets: [...c.bullets.split('\n').filter(Boolean),
        'Bulk Pricing: Volume discounts available on request',
        'Specification Sheet: Available on request for procurement'].join('\n'),
    }),
  },
]

// ── Local, deterministic listing heuristics ──────────────────────────────────
// These are documented rules applied to the operator's own text. They are never
// presented as measured marketplace performance.
export function listingHealth(copy) {
  const title = String(copy?.title || '').trim()
  const bullets = String(copy?.bullets || '').split('\n').map(s => s.trim()).filter(Boolean)
  const description = String(copy?.description || '').trim()
  const keywords = String(copy?.keywords || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean)

  const titleScore = (() => {
    if (!title) return 0
    let s = 0
    if (title.length >= 40) s += 40
    if (title.length <= 200) s += 30
    if (title.split(/\s+/).length >= 6) s += 30
    return Math.min(100, s)
  })()

  const bulletScore = bullets.length === 0 ? 0 : Math.min(100, bullets.length * 14 + (bullets.every(b => b.length > 12) ? 30 : 0))

  const descScore = (() => {
    if (!description) return 0
    let s = 0
    if (description.length >= 120) s += 55
    if (description.length >= 250) s += 25
    if (description.split(/\s+/).length >= 25) s += 20
    return Math.min(100, s)
  })()

  const overall = Math.round((titleScore + bulletScore + descScore) / 3)

  const coverage = keywords.map(k => {
    const hay = `${title} ${bullets.join(' ')} ${description}`.toLowerCase()
    if (!k) return { term: k, coverage: 'Missing', rank: null }
    if (hay.includes(k)) return { term: k, coverage: 'Matched', rank: null }
    const partial = k.split(/\s+/).some(w => w.length > 3 && hay.includes(w))
    return { term: k, coverage: partial ? 'Partial' : 'Missing', rank: null }
  })
  const matched = coverage.filter(c => c.coverage === 'Matched').length
  const pct = coverage.length ? Math.round((matched / coverage.length) * 100) : 0

  return { titleScore, bulletScore, descScore, overall, coverage, matched, total: coverage.length, pct }
}

// ═══ Hosted listing proposal (OpenCode Go) — proposal only, never auto-applied ═══
function ListingProposalPanel({ copy, onApply }) {
  const { selectedModel, catalog, persist } = useReasoningModel()
  const { toast } = useToast()
  const [state, setState] = useState({ phase: 'idle' })

  const submit = async () => {
    if (!(catalog && catalog.armed)) {
      toast('Hosted reasoning is not armed. Set OPENCODE_GO_ENABLED=1 and supply a key.', 'warn')
      return
    }
    setState({ phase: 'submitting' })
    try {
      const r = await foundationApi.reasoningListingProposal({
        sku: 'LIVE-EDITOR',
        title: copy.title,
        bullets: copy.bullets.split('\n').map(s => s.trim()).filter(Boolean),
        description: copy.description,
        keywords: copy.keywords.split(',').map(s => s.trim()).filter(Boolean),
        brand: copy.brand,
        model: selectedModel?.id,
      })
      setState({ phase: 'done', value: r.proposal })
    } catch (e) {
      setState({ phase: 'error', message: e.message || 'Proposal failed.' })
    }
  }

  const prop = state.phase === 'done' ? state.value : null

  const apply = () => {
    if (!prop?.proposed) return
    onApply({
      ...copy,
      title: prop.proposed.title || copy.title,
      bullets: (prop.proposed.bullets || []).join('\n'),
      description: prop.proposed.description || copy.description,
    })
    setState({ phase: 'idle' })
    toast('Proposal applied to the editor. This changes the local draft only — nothing has been published.', 'info')
  }

  return (
    <div className="card" data-testid="lf-proposal" style={{ marginTop: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Hosted listing proposal</h3>
        <span className="pill pill-ochre">proposal only · owner review</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Generates a before/after listing revision using hosted reasoning, from the copy currently in the editor above.
        The output is a proposal — it is never applied automatically and never published to a marketplace.
      </p>
      <ReasoningModelSelector value={selectedModel?.id} onChange={persist} />
      <div style={{ marginTop: 12 }}>
        <button className="btn btn-sm" onClick={submit} disabled={state.phase === 'submitting' || !(catalog && catalog.armed)}>
          {state.phase === 'submitting' ? 'Generating…' : 'Generate proposal'}
        </button>
        {!(catalog && catalog.armed) && <span className="text-low" style={{ fontSize: 11, marginLeft: 8 }}>Hosted reasoning not armed.</span>}
      </div>
      {state.phase === 'error' && <div className="pill pill-warn" style={{ marginTop: 10 }}>{state.message}</div>}
      {prop && (
        <div style={{ marginTop: 16 }}>
          <div className="inline-flex" style={{ gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <span className={`pill ${prop.ok ? 'pill-ok' : 'pill-warn'}`}>{prop.ok ? 'proposal ok' : 'proposal failed'}</span>
            {prop.provenance && <span className="pill pill-muted">{prop.provenance.model}</span>}
            <button className="btn btn-sm btn-ghost" onClick={apply} disabled={!prop.ok}>Apply to editor</button>
          </div>
          {prop.warnings && prop.warnings.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              {prop.warnings.map((w, i) => <span key={i} className="pill pill-warn" style={{ fontSize: 10 }}>{w}</span>)}
            </div>
          )}
          <div className="grid-2" style={{ gap: 12 }}>
            <div className="card" style={{ background: 'var(--bone)' }}>
              <div className="card-head"><h4 className="card-title" style={{ fontSize: 13 }}>Original</h4></div>
              <div style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{prop.original?.title}</div>
              <ul style={{ fontSize: 12, marginTop: 8, paddingLeft: 16 }}>{(prop.original?.bullets || []).map((b, i) => <li key={i}>{b}</li>)}</ul>
              <div style={{ fontSize: 12, marginTop: 8, whiteSpace: 'pre-wrap' }}>{prop.original?.description}</div>
            </div>
            <div className="card" style={{ background: 'var(--pine-bleached)' }}>
              <div className="card-head"><h4 className="card-title" style={{ fontSize: 13 }}>Proposed</h4></div>
              <div style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{prop.proposed?.title}</div>
              <ul style={{ fontSize: 12, marginTop: 8, paddingLeft: 16 }}>{(prop.proposed?.bullets || []).map((b, i) => <li key={i}>{b}</li>)}</ul>
              <div style={{ fontSize: 12, marginTop: 8, whiteSpace: 'pre-wrap' }}>{prop.proposed?.description}</div>
            </div>
          </div>
          {prop.reasons && prop.reasons.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Reasons for change</div>
              <ul style={{ fontSize: 12, marginTop: 4, paddingLeft: 16 }}>{prop.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
          {prop.missing_evidence && prop.missing_evidence.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Missing evidence</div>
              <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                {prop.missing_evidence.map((m, i) => <span key={i} className="pill pill-unknown" style={{ fontSize: 10 }}>{m}</span>)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ListingForge() {
  const navigate = useNavigate()
  const location = useLocation()
  const { toast } = useToast()

  const [mode, setMode] = useRoom('lf-mode', 'simple')
  const [listings, setListings] = useRoom('lf-listings', SEED_LISTINGS)
  const [revisions, setRevisions] = useRoom('lf-revisions', [
    { id: 'REV-001', asin: 'B08L5VJQ7T', version: 'v3.2', summary: 'Title pack-count added; bullets reworded; description refreshed', saved: '2026-09-24T09:00:00Z', state: 'In progress' },
    { id: 'REV-002', asin: 'B08L5VJQ7T', version: 'v3.1', summary: 'Keyword coverage pass', saved: '2026-09-23T09:00:00Z', state: 'Superseded' },
    { id: 'REV-003', asin: 'B08L5VJQ7T', version: 'v3.0', summary: 'Launch copy — full rewrite', saved: '2026-09-18T09:00:00Z', state: 'Superseded' },
    { id: 'REV-004', asin: 'B08L5VJQ7T', version: 'v2.9', summary: 'Compliance flag: unsupported claim removed', saved: '2026-09-12T09:00:00Z', state: 'Reverted' },
  ])
  const [assetMeta, setAssetMeta] = useRoom('lf-assets', [
    { id: 'AM-01', name: 'hero-main.jpg', type: 'Image', state: 'Attached', used: 'Title / Bullets', tone: 'pill-muted' },
    { id: 'AM-02', name: 'lifestyle-kitchen-01.jpg', type: 'Image', state: 'Attached', used: 'Description', tone: 'pill-muted' },
    { id: 'AM-03', name: 'filter-exploded.png', type: 'Diagram', state: 'Draft', used: '—', tone: 'pill-warn' },
    { id: 'AM-04', name: 'comparison-chart.png', type: 'Diagram', state: 'Missing alt text', used: 'Description', tone: 'pill-warn' },
    { id: 'AM-05', name: 'brand-logo-pack.zip', type: 'Brand', state: 'Attached', used: 'A+ Content', tone: 'pill-muted' },
  ])

  const store = useAssetStore()
  const { images } = useDecodedAssets(store.assets)

  const [activeAsin, setActiveAsin] = useState(listings[0]?.asin || '')
  const [draft, setDraft] = useState(listings[0]?.copy || SEED_LISTINGS[0].copy)
  const [dirty, setDirty] = useState(false)
  const [appliedTemplate, setAppliedTemplate] = useState('')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = ['listings', 'editor', 'templates', 'assets', 'revisions'].includes(requested) ? requested : 'listings'

  const active = useMemo(() => listings.find(l => l.asin === activeAsin) || listings[0] || null, [listings, activeAsin])

  // Load the active listing's copy into the editor whenever the selection
  // changes (and never mid-edit, so typing is never clobbered).
  useEffect(() => {
    if (active && !dirty) {
      setDraft(active.copy)
      setAppliedTemplate('')
    }
  }, [active?.asin]) // eslint-disable-line react-hooks/exhaustive-deps

  const health = useMemo(() => listingHealth(draft), [draft])
  const t = useCallback((msg, tone = 'info') => toast(msg, tone), [toast])
  const go = useCallback((v) => navigate(`/listingforge?view=${v}`), [navigate])

  const selectListing = useCallback((asin) => {
    setActiveAsin(asin)
    const l = listings.find(x => x.asin === asin)
    if (l) setDraft(l.copy)
    setDirty(false)
    setAppliedTemplate('')
  }, [listings])

  const patchCopy = useCallback((patch) => {
    setDraft(prev => ({ ...prev, ...patch }))
    setDirty(true)
  }, [])

  // ── Save a real revision ──
  const saveRevision = useCallback(() => {
    if (!active) return
    setListings(prev => prev.map(l => (l.asin === active.asin ? { ...l, copy: draft, status: 'Revision in progress', updated: nowIso() } : l)))
    // Close out the in-progress revision for this ASIN and open a new one.
    const nextNum = revisions.filter(r => r.asin === active.asin).length + 1
    const revId = uid('REV')
    setRevisions(prev => [
      { id: revId, asin: active.asin, version: `v3.${nextNum + 1}`, summary: 'Editor save — copy revision recorded locally', saved: nowIso(), state: 'In progress' },
      ...prev.map(r => (r.asin === active.asin && r.state === 'In progress' ? { ...r, state: 'Superseded' } : r)),
    ])
    setDirty(false)
    t(`Revision saved locally for ${active.asin}. Internal review state only — nothing was published to any marketplace.`, 'info')
  }, [active, draft, listings, revisions, setListings, setRevisions, t])

  const applyTemplate = useCallback((tpl) => {
    setDraft(prev => tpl.apply(prev))
    setDirty(true)
    setAppliedTemplate(tpl.id)
    t(`"${tpl.name}" template applied to the local draft. Review the change before saving a revision.`, 'info')
  }, [t])

  const restoreRevision = useCallback((rev) => {
    setRevisions(prev => prev.map(r => (r.id === rev.id ? { ...r, state: 'In progress' } : (r.asin === rev.asin ? { ...r, state: 'Superseded' } : r))))
    t(`Revision ${rev.version} marked in progress (local record). Revert does not republish to a live listing.`, 'info')
  }, [setRevisions, t])

  const uploadAssets = useCallback(async (fileList) => {
    const added = await store.add(fileList, { role: 'reference', tags: ['listing', active?.asin || 'unassigned'] })
    if (!added.length) return
    setAssetMeta(prev => [
      ...added.map(a => ({
        id: a.id, name: a.name, type: 'Image', state: 'Uploaded (local)', used: '—', tone: 'pill-forest', bytes: a.bytes, w: a.w, h: a.h,
      })),
      ...prev,
    ])
  }, [store, active?.asin, setAssetMeta])

  // ── Counts derived from real data, never a hardcoded label ──
  const inProgress = listings.filter(l => l.status === 'Revision in progress').length
  const drafts = listings.filter(l => l.status === 'Draft').length
  const publishReady = listings.filter(l => l.status === 'Live' || l.status === 'Revision v3.2').length

  return (
    <PageLayout
      title="ListingForge"
      subtitle="Listing copy studio — a working editor, real revision history, applicable templates, and a real asset tray."
      actions={<>
        <ModeToggle mode={mode} onChange={setMode} />
        <button className="btn btn-sm btn-ghost" onClick={() => go('templates')}>Templates</button>
        <button className="btn btn-sm" onClick={() => go('editor')}>Open editor</button>
      </>}
    >
      <DataNotice tone="sample" title="Listing copy and revision state are local records">
        Listings, editor drafts, revisions and uploaded assets are real records you create here and are stored in this browser.
        Nothing is published to any marketplace — revision states are internal review states only. Health and keyword
        coverage are deterministic rules applied to your own text, labelled as local heuristics.
      </DataNotice>

      <RoomTabs tabs={[
        { id: 'listings', label: 'Listings', count: listings.length },
        { id: 'editor', label: 'Editor' },
        { id: 'templates', label: 'Templates' },
        { id: 'assets', label: 'Assets', count: assetMeta.length },
        { id: 'revisions', label: 'Revision Log', count: revisions.length },
      ]} base="/listingforge" />

      {/* ══ LISTINGS ══ */}
      {view === 'listings' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Listings</h3>
              {/* The badge now states the truth: the number of rows actually shown. */}
              <span className="pill pill-muted">{listings.length} listings · {listings.filter(l => l.status === 'Draft').length} draft</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Listing' },
              { key: 'status', label: 'Status' },
              { key: 'health', label: 'Local health', render: (v, row) => <span className={`pill ${row.status === 'Draft' ? 'pill-warn' : 'pill-muted'}`} title="Local heuristic from the stored copy — not a marketplace measurement">{listingHealth(row.copy).overall}/100</span> },
              { key: 'updated', label: 'Updated', render: (v) => <span className="pill pill-muted" title="Local revision timestamp">{fmtTime(v)}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => { selectListing(row.asin); go('editor') }}>Edit</button> },
            ]} rows={listings} />
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Studio snapshot</h3>
              <span className="pill pill-muted">derived from local records</span>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Revisions in progress</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--ochre)' }}>{inProgress}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>counted from the listings above</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Drafts awaiting review</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--clay)' }}>{drafts}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>internal review state</div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Live / publish-ready</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine)' }}>{publishReady} of {listings.length}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>internal review state — not a publish authorization</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══ EDITOR ══ */}
      {view === 'editor' && active && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
            <div className="inline-flex">
              <span className="text-low" style={{ fontSize: 11 }}>Editing</span>
              {listings.map(l => (
                <button key={l.asin} className={`filter-pill ${active.asin === l.asin ? 'active' : ''}`} onClick={() => selectListing(l.asin)} title={l.asin}>
                  {l.title}
                </button>
              ))}
              {dirty
                ? <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={saveRevision}><Icon name="save" size={13} /> Save Revision</button>
                : <span className="pill pill-muted" style={{ marginLeft: 'auto' }}>no unsaved changes</span>}
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">{active.title} — {active.asin}</h3>
                <span className={`pill ${active.status === 'Draft' ? 'pill-warn' : 'pill-muted'}`}>{active.status}</span>
              </div>
              <div className="stack" style={{ gap: 14 }}>
                <Field label="Title" hint={`${draft.title.length} characters. Local heuristic awards points for 40–200 characters and 6+ words.`}>
                  <TextInput value={draft.title} onChange={(v) => patchCopy({ title: v })} />
                </Field>
                <Field label="Bullets" hint="One per line.">
                  <TextInput rows={5} value={draft.bullets} onChange={(v) => patchCopy({ bullets: v })} />
                </Field>
                <Field label="Description">
                  <TextInput rows={4} value={draft.description} onChange={(v) => patchCopy({ description: v })} />
                </Field>
                {mode === 'advanced' && (
                  <>
                    <Field label="Keywords" hint="Comma-separated. Coverage below is computed from these.">
                      <TextInput value={draft.keywords} onChange={(v) => patchCopy({ keywords: v })} />
                    </Field>
                    <Field label="Brand">
                      <TextInput value={draft.brand} onChange={(v) => patchCopy({ brand: v })} />
                    </Field>
                  </>
                )}
                <div className="inline-flex" style={{ gap: 8 }}>
                  <button className="btn btn-sm" onClick={saveRevision} disabled={!dirty}><Icon name="save" size={13} /> Save Revision</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => t('Health check runs locally on your own copy — the score and coverage below update as you type. No external service is contacted.', 'info')}>
                    <Icon name="refresh" size={13} /> Recompute health
                  </button>
                  {dirty && <button className="btn btn-sm btn-ghost" onClick={() => { setDraft(active.copy); setDirty(false); setAppliedTemplate('') }}>Discard changes</button>}
                </div>
                {dirty && <span className="pill pill-warn">unsaved changes · local only</span>}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Keyword coverage</h3>
                <span className="pill pill-forest">{health.pct}% matched</span>
              </div>
              <DataTable columns={[
                { key: 'term', label: 'Search term' },
                { key: 'coverage', label: 'Coverage', render: (v) => <span className={`pill ${v === 'Matched' ? 'pill-forest' : v === 'Partial' ? 'pill-ochre' : 'pill-warn'}`}>{v}</span> },
                { key: 'found', label: 'Where', render: (v, r) => <span className="text-low">{r.where || '—'}</span> },
              ]} rows={health.coverage.map(c => ({
                ...c,
                where: c.coverage === 'Matched' ? 'title / bullets / description' : c.coverage === 'Partial' ? 'partial word match' : 'not present',
              }))} emptyText="Add keywords in Advanced mode to compute coverage." />
              <span className="sp-field-hint" style={{ marginTop: 8 }}>
                Computed locally from your own copy. This is a coverage heuristic, not measured marketplace rank.
              </span>
            </div>
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Listing health</h3>
              <span className="pill pill-forest">Local score: {health.overall}/100</span>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Title optimisation</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: health.titleScore >= 80 ? 'var(--pine)' : 'var(--ochre)' }}>{health.titleScore}%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className={`meter-fill ${health.titleScore >= 80 ? 'meter-fill-forest' : 'meter-fill-ochre'}`} style={{ width: `${health.titleScore}%` }} /></div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Bullet coverage</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: health.bulletScore >= 80 ? 'var(--pine)' : 'var(--ochre)' }}>{health.bulletScore}%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className={`meter-fill ${health.bulletScore >= 80 ? 'meter-fill-forest' : 'meter-fill-ochre'}`} style={{ width: `${health.bulletScore}%` }} /></div>
              </div>
              <div>
                <div className="text-low" style={{ fontSize: 11 }}>Description quality</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: health.descScore >= 80 ? 'var(--pine)' : 'var(--ochre)' }}>{health.descScore}%</div>
                <div className="meter" style={{ marginTop: 4 }}><div className={`meter-fill ${health.descScore >= 80 ? 'meter-fill-forest' : 'meter-fill-ochre'}`} style={{ width: `${health.descScore}%` }} /></div>
              </div>
            </div>
            <span className="sp-field-hint" style={{ marginTop: 10 }}>
              Score is the mean of three documented local rules applied to your copy. It is not a marketplace metric.
            </span>
          </div>

          <ListingProposalPanel copy={draft} onApply={patchCopy} />
        </div>
      )}

      {/* ══ TEMPLATES ══ */}
      {view === 'templates' && (
        <div className="subview">
          <div className="grid-3">
            {TEMPLATES.map(tpl => (
              <div key={tpl.id} className="card">
                <h3 className="card-title" style={{ fontSize: 16 }}>{tpl.name}</h3>
                <div style={{ fontSize: 13, color: 'var(--ink-mid)', marginTop: 8, lineHeight: 1.6 }}>{tpl.desc}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>{tpl.use}</div>
                <div style={{ marginTop: 12 }} className="inline-flex">
                  <button className="btn btn-sm" onClick={() => { applyTemplate(tpl); go('editor') }}>
                    {appliedTemplate === tpl.id ? 'Applied ✓' : 'Use Template'}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="alert" style={{ marginTop: 16 }}>
            <div className="alert-text">
              Templates transform the copy currently in the editor. Applying one marks the draft unsaved; saving a
              revision is a separate, explicit action.
            </div>
          </div>
        </div>
      )}

      {/* ══ ASSETS ══ */}
      {view === 'assets' && (
        <div className="subview stack" style={{ gap: 14 }}>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Asset tray — {active?.title || 'no listing selected'}</h3>
              <span className="pill pill-muted">{assetMeta.length} records</span>
            </div>
            <label className="sp-dropzone" style={{ marginBottom: 12 }}>
              <Icon name="upload" size={14} /> Upload images to the local asset store
              <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                onChange={(e) => { uploadAssets(e.target.files); e.target.value = '' }} />
            </label>
            <div className="sp-asset-grid" style={{ marginBottom: 12 }}>
              {store.assets.filter(a => a.role === 'reference').slice(0, 8).map(a => (
                <AssetThumb key={a.id} asset={a} height={60}
                  actions={<button className="btn btn-sm btn-ghost" title="Remove" onClick={() => store.remove(a.id)}>×</button>} />
              ))}
              {!store.assets.filter(a => a.role === 'reference').length && <span className="text-low" style={{ fontSize: 12 }}>No uploaded images yet. Upload above to add real local assets.</span>}
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Asset' },
              { key: 'type', label: 'Type' },
              { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
              { key: 'used', label: 'Used In' },
              { key: 'dims', label: 'Pixels', render: (v, row) => <span className="text-mono text-low">{row.w ? `${row.w}×${row.h}` : '—'}</span> },
              { key: 'act', label: '', render: (v, row) => (
                row.id.startsWith('AS-')
                  ? <button className="btn btn-sm btn-ghost" onClick={() => { setAssetMeta(prev => prev.filter(x => x.id !== row.id)); store.remove(row.id) }}>Remove</button>
                  : <span className="text-low" style={{ fontSize: 11 }}>sample record</span>
              ) },
            ]} rows={assetMeta} emptyText="No asset records yet." />
            <div className="inline-flex" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/creative-studio?view=canvas')}><Icon name="brush" size={13} /> Open Design Studio</button>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/product-designer?view=scene')}><Icon name="camera" size={13} /> Open Product Designer</button>
            </div>
            {!store.persistent && (
              <div className="alert" style={{ marginTop: 12, marginBottom: 0 }}>
                <div className="alert-text">Browser storage is unavailable — uploaded images live for this session only.</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ REVISIONS ══ */}
      {view === 'revisions' && (
        <div className="subview">
          <DataNotice tone="sample" title="Revision history is local state">
            Revisions are local records. Restoring one marks it in progress — it does not republish to a live listing and does not contact a marketplace.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Revision log — {active?.title || 'no listing'} · {active?.asin}</h3>
              <span className="pill pill-warn">{revisions.filter(r => r.asin === active?.asin && r.state === 'In progress').length} in progress</span>
            </div>
            <DataTable columns={[
              { key: 'version', label: 'Version' },
              { key: 'summary', label: 'Summary' },
              { key: 'saved', label: 'Saved', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'In progress' ? 'pill-warn' : v === 'Reverted' ? 'pill-ochre' : 'pill-muted'}`}>{v}</span> },
              {
                key: 'action', label: '', render: (v, row) => (
                  row.state === 'In progress'
                    ? <span className="text-low" style={{ fontSize: 11 }}>current</span>
                    : <button className="btn btn-sm btn-ghost" onClick={() => restoreRevision(row)}>Restore as Draft</button>
                ),
              },
            ]} rows={revisions.filter(r => !active || r.asin === active.asin)} emptyText="No revisions for this listing yet." />
          </div>
        </div>
      )}
    </PageLayout>
  )
}
