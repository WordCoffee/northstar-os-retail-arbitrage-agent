// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — /creative-studio
//
// One studio for every creative channel: the master canvas, paid-ad sets,
// social content sets, A+ listing modules, image generation, and short-clip
// storyboards — with a Simple / Advanced switch so a fast edit and a full
// layout job use the same room.
//
// HONESTY CONTRACT (this room):
//   • Briefs, design documents, ad sets, social sets, A+ modules, requests,
//     variants, assets and bundles are REAL LOCAL records (this browser).
//     They are the operator's own work — never provider output.
//   • The canvas renders and exports REAL PNGs from layers the operator built.
//     Multi-format rendering is real: the document geometry is normalised, so
//     one master renders correctly at every output size.
//   • NO image or video is ever generated or depicted here. Generate and Video
//     are real request recorders whose honest terminal state is
//     "Blocked — provider required".
//   • No file is transmitted between rooms. "Send to" moves a local record id
//     and navigates; it never uploads, publishes, lists, or downloads.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { DataNotice, DataTable } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import Icon from '../../components/Icon.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import Stage from '../../studio/components/Stage.jsx'
import {
  ModeToggle, ToolRail, ProviderBoundary, EngineArmed, AssetThumb, ThumbPlaceholder,
} from '../../studio/components/Chrome.jsx'
import {
  Section, Field, TextInput, NumberInput, Slider, Select, ColorInput,
  SegmentedControl, Toggle, ChipRow, Stat,
} from '../../studio/components/Fields.jsx'
import {
  KIND_LABEL, docFromTemplate, applyKit, addLayer, updateLayer, removeLayer,
  duplicateLayer, reorderLayer, rescaleDoc, docToDataUrl, downloadDataUrl, safeFileName,
} from '../../studio/engine/doc.js'
// Phase 7 item 4: the Projects canvas gains the SAME gate mechanics as the
// compositing surface - a locked reference runs the real fidelity diff and a
// human compare sign-off before any export.
import {
  renderDoc, fidelityVerdict, compareStepStatus, makeCompareSignOff,
} from '../../studio/engine/compose.js'
import {
  useAssetStore, useDecodedAssets, putAsset, newAssetId, approxBytesOfDataUrl,
} from '../../studio/engine/assets.js'
import { useRoom, uid, nowIso, fmtTime, fmtBytes, hashDoc } from '../../studio/engine/store.js'
import { checkCompliance, rulesInScope } from '../../studio/engine/compliance.js'
import {
  planToday, loopReadiness, CHANNEL_KIND, DEFAULT_BRAND_PROFILE,
} from '../../studio/engine/loop.js'
import {
  TEMPLATES, templateById, ALL_FORMATS, formatById, DEFAULT_BRAND_KITS,
  GEN_PURPOSES, GEN_TIERS,
} from '../../studio/engine/presets.js'
import { engineApi } from '../../studio/engine/engineApi.js'

// ── Tools ────────────────────────────────────────────────────────────────────
const TOOLS = [
  { id: 'canvas', label: 'Canvas', icon: 'brush', note: 'The master design editor.' },
  { id: 'ads', label: 'Ad sets', icon: 'target', note: 'Render the master into every paid placement.' },
  { id: 'social', label: 'Social', icon: 'users', note: 'Render the master into social placements.' },
  { id: 'aplus', label: 'A+ content', icon: 'list', note: 'Listing modules at Amazon sizes.' },
  { id: 'generate', label: 'Generate', icon: 'sparkle', note: 'Image requests — provider-gated.' },
  { id: 'video', label: 'Video', icon: 'film', note: 'Short-clip storyboards — provider-gated.' },
  { id: 'briefs', label: 'Briefs', icon: 'file', note: 'Work briefs that scope the studio.' },
  { id: 'brand', label: 'Brand', icon: 'target', note: 'The one brand profile every channel reads.' },
  { id: 'loop', label: 'Today', icon: 'sparkle', note: 'The proposed work for today — approve or dismiss.' },
  { id: 'queue', label: 'Queue', icon: 'clock', note: 'Every request this room has recorded.' },
  { id: 'variants', label: 'Variants', icon: 'layers', note: 'Review states for finished work.' },
  { id: 'assets', label: 'Assets', icon: 'image', note: 'Uploaded artwork and saved renders.' },
  { id: 'exports', label: 'Exports', icon: 'download', note: 'Bundle builder and export log.' },
  { id: 'library', label: 'Library', icon: 'stack', note: 'Saved documents and collections.' },
]

// Output channels the render-master feature supports.
const CHANNEL_SETS = [
  { id: 'ads', label: 'Paid ads', channel: 'Meta', note: 'Feed + story placements.' },
  { id: 'social', label: 'Social content', channel: 'Instagram', note: 'Post, carousel, portrait.' },
  { id: 'aplus', label: 'A+ content', channel: 'Amazon A+', note: 'Listing modules.' },
]

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
const pillFor = (s) => REQUEST_STATE[s] || BRIEF_STATUS[s] || 'pill-muted'

// ── Seed records removed (Phase 0). Empty states only. ───────────────────────
// The operator creates every brief, variant, asset and request. Nothing here
// is fabricated; generation is gated behind explicit Run actions.
const SEED_BRIEFS = []
const SEED_VARIANTS = []

export default function CreativeStudio() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [mode, setMode] = useRoom('ds-mode', 'simple')
  const [briefs, setBriefs] = useRoom('ns-creative-briefs', SEED_BRIEFS)
  const [requests, setRequests] = useRoom('ns-creative-requests', [])
  const [variants, setVariants] = useRoom('ns-creative-variants', SEED_VARIANTS)
  const [bundles, setBundles] = useRoom('ns-creative-bundles', [])
  const [docs, setDocs] = useRoom('ds-docs', [])
  const [exportLog, setExportLog] = useRoom('ds-export-log', [])
  const [kits, setKits] = useRoom('ds-kits', DEFAULT_BRAND_KITS)
  const [activeKitId, setActiveKitId] = useRoom('ds-active-kit', 'kit-pine')
  const [profile, setProfile] = useRoom('ds-brand-profile', { ...DEFAULT_BRAND_PROFILE, createdAt: nowIso() })
  const [loopLog, setLoopLog] = useRoom('ds-loop-log', [])
  const [outputs, setOutputs] = useRoom('ds-bundle-outputs', ['Ad creatives', 'Listing imagery'])

  const store = useAssetStore()
  const { images, ready } = useDecodedAssets(store.assets)
  const kit = kits.find(k => k.id === activeKitId) || kits[0] || DEFAULT_BRAND_KITS[0]

  const requested = new URLSearchParams(location.search).get('view') || ''
  const tool = TOOLS.some(x => x.id === requested) ? requested : 'canvas'

  const [activeBriefId, setActiveBriefId] = useState(briefs[0]?.id || '')
  const [zoom, setZoom] = useState(1)
  const [activeDocId, setActiveDocId] = useState('')
  const [selectedLayerId, setSelectedLayerId] = useState('')
  const [templateId, setTemplateId] = useState('tpl-hero-paper')
  const [formatId, setFormatId] = useState('meta-feed')
  // The channel-set tabs are 1:1 with a channel set, so derive it from the tab
  // instead of holding separate state that can disagree with the URL.
  const renderChannel = tool === 'social' ? 'social' : tool === 'aplus' ? 'aplus' : 'ads'
  const [showGrid, setShowGrid] = useState(false)
  const [assetFilter, setAssetFilter] = useState('All')
  const [genPurpose, setGenPurpose] = useState('product-scene')
  const [genTier, setGenTier] = useState('draft')
  const [genPrompt, setGenPrompt] = useState('')
  const [textSafe, setTextSafe] = useState(true) // blueprint #5: never let the model draw letters
  const [vPurpose, setVPurpose] = useState('UGC / testimonial')
  const [vDuration, setVDuration] = useState('15s (Short / TikTok)')
  const [vAspect, setVAspect] = useState('9:16 (vertical)')
  const [engine, setEngine] = useState(null)          // local ComfyUI engine state
  const [genBusy, setGenBusy] = useState(false)
  const [videoBusy, setVideoBusy] = useState(false)
  const [lastRender, setLastRender] = useState(null)  // latest generated image asset
  const [lastClip, setLastClip] = useState(null)      // latest generated video asset

  const t = useCallback((msg, tone = 'info') => toast(msg, tone), [toast])
  const go = useCallback((id) => navigate(`/creative-studio?view=${id}`), [navigate])
  const fmt = formatById(formatId) || ALL_FORMATS[0]

  const active = useMemo(() => briefs.find(b => b.id === activeBriefId) || briefs[0] || null, [briefs, activeBriefId])

  useEffect(() => {
    if (briefs.length && !briefs.some(b => b.id === activeBriefId)) setActiveBriefId(briefs[0].id)
  }, [briefs, activeBriefId])

  // ── The working document ──
  // A document is created from a template at a format size; the working copy
  // lives in state and is persisted to the docs room store on demand.
  const [doc, setDoc] = useState(() => docFromTemplate(TEMPLATES[0], { w: 1080, h: 1080, kit: DEFAULT_BRAND_KITS[0] }))
  const [docName, setDocName] = useState(TEMPLATES[0].name)
  const [savedHash, setSavedHash] = useState('')
  const dirty = useMemo(() => hashDoc(doc) !== savedHash, [doc, savedHash])

  // ── Undo / redo (Phase 7 item 4) ─────────────────────────────────────────
  // The document is the only undoable thing on this canvas; the stack watches
  // `doc` and records the previous value on every change, bounded to 50 steps.
  // Undo/redo applications are flagged so they do not record themselves.
  const historyRef = useRef({ past: [], future: [] })
  const applyingHistoryRef = useRef(false)
  const lastDocRef = useRef(null)
  const [historyTick, setHistoryTick] = useState(0)

  useEffect(() => {
    if (lastDocRef.current === null) { lastDocRef.current = doc; return }
    if (applyingHistoryRef.current) { applyingHistoryRef.current = false; lastDocRef.current = doc; return }
    if (doc === lastDocRef.current) return
    const h = historyRef.current
    h.past = [...h.past.slice(-49), lastDocRef.current]
    h.future = []
    lastDocRef.current = doc
    setHistoryTick(v => v + 1)
  }, [doc])

  const undoDoc = useCallback(() => {
    const h = historyRef.current
    if (!h.past.length) return
    const prev = h.past[h.past.length - 1]
    h.past = h.past.slice(0, -1)
    h.future = [doc, ...h.future].slice(0, 50)
    applyingHistoryRef.current = true
    lastDocRef.current = prev
    setDoc(prev)
    setHistoryTick(v => v + 1)
  }, [doc])

  const redoDoc = useCallback(() => {
    const h = historyRef.current
    if (!h.future.length) return
    const next = h.future[0]
    h.future = h.future.slice(1)
    h.past = [...h.past, doc].slice(-50)
    applyingHistoryRef.current = true
    lastDocRef.current = next
    setDoc(next)
    setHistoryTick(v => v + 1)
  }, [doc])

  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const tag = (e.target && e.target.tagName) || ''
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return
      const k = String(e.key || '').toLowerCase()
      if (k === 'z') { e.preventDefault(); if (e.shiftKey) redoDoc(); else undoDoc() }
      else if (k === 'y') { e.preventDefault(); redoDoc() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undoDoc, redoDoc])

  const canUndo = historyRef.current.past.length > 0
  const canRedo = historyRef.current.future.length > 0
  void historyTick // re-render trigger for the button states

  // Every EDIT goes through commitDoc, which stamps meta.lastEditAt — the value
  // the compare sign-off is bound to (assetVersion). Any edit therefore
  // invalidates a previous sign-off. Non-content writes (save/open from the
  // library, undo/redo application, meta-only lock/sign actions) use raw setDoc.
  const commitDoc = useCallback((updater) => {
    setDoc(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      if (!next || next === prev) return prev
      return { ...next, meta: { ...next.meta, lastEditAt: nowIso() } }
    })
  }, [])

  // ── Reference lock + compare sign-off (Phase 7 item 4) ───────────────────
  // Locking a reference turns on the REAL fidelity diff (the rendered canvas
  // against the locked file, in the product region) and requires a human
  // compare sign-off before export - the same mechanics the compositing
  // surface uses, via the same engine functions.
  const resolveAssetDataUrl = useCallback(
    (id) => ((store.assets || []).find(a => a.id === id) || {}).dataUrl,
    [store.assets],
  )
  const lockedReference = doc.meta?.fidelityMode === 'locked'
  const compareStatus = useMemo(() => compareStepStatus(doc), [doc])

  const lockReference = useCallback(() => {
    const layer = (doc.layers || []).find(l =>
      l.visible !== false && (l.kind === 'image' || l.kind === 'product') && l.assetId && resolveAssetDataUrl(l.assetId))
    if (!layer) {
      t('Add an image or product layer first — the locked reference is that layer\'s own file.', 'warn')
      return
    }
    const dataUrl = resolveAssetDataUrl(layer.assetId)
    setDoc(prev => ({
      ...prev,
      meta: { ...prev.meta, fidelityMode: 'locked', referenceAssetId: layer.assetId, referenceDataUrl: dataUrl },
    }))
    t('Reference locked to the product layer. Export now runs the fidelity diff and requires a human compare sign-off.', 'info')
  }, [doc.layers, resolveAssetDataUrl, t])

  const unlockReference = useCallback(() => {
    setDoc(prev => {
      const meta = { ...prev.meta }
      delete meta.fidelityMode
      delete meta.referenceAssetId
      delete meta.referenceDataUrl
      delete meta.compareConfirmed
      return { ...prev, meta }
    })
    t('Reference lock removed. Export falls back to the compliance pre-flight only.', 'info')
  }, [t])

  const signCompare = useCallback(() => {
    setDoc(prev => ({ ...prev, meta: { ...prev.meta, compareConfirmed: makeCompareSignOff(prev, { user: 'operator' }) } }))
    t('Comparison signed off — a self-declaration: it records who and when, not proof of review.', 'info')
  }, [t])

  // The shared export gate: when a reference is locked, a HUMAN compare
  // sign-off (version-bound) is required before export. The objective pixel
  // diff is available on demand (runFidelityDiff below) - a general canvas
  // legitimately differs from the raw photograph, so the diff is a readout,
  // not an automatic gate, and it never silently passes a step.
  const lockedGate = useCallback(async (candidate) => {
    if (candidate.meta?.fidelityMode !== 'locked') return { ok: true }
    const cmp = compareStepStatus(candidate)
    if (!cmp.satisfied) return { ok: false, detail: cmp.detail }
    return { ok: true }
  }, [])

  // On-demand fidelity readout: the real diff of the rendered product region
  // against the locked reference, with its own stated limits.
  const [diffResult, setDiffResult] = useState(null)
  const runFidelityDiff = useCallback(async () => {
    try {
      const canvas = await renderDoc(doc, resolveAssetDataUrl)
      const fid = await fidelityVerdict(doc, canvas, resolveAssetDataUrl)
      setDiffResult(fid)
      t(fid.ok
        ? `Fidelity diff: the product region matches the reference (${fid.diff ? (fid.diff.mean * 100).toFixed(2) + '% mean' : fid.detail}).`
        : `Fidelity diff: ${fid.detail}`, fid.ok ? 'info' : 'warn')
    } catch (e) {
      setDiffResult({ status: 'not-run', ok: false, detail: `The diff could not run: ${String(e && e.message || e)}` })
      t(`Fidelity diff could not run: ${String(e && e.message || e)}`, 'warn')
    }
  }, [doc, resolveAssetDataUrl, t])


  const openTemplate = useCallback((id, fmtId) => {
    const tpl = templateById(id) || TEMPLATES[0]
    const f = formatById(fmtId || formatId) || ALL_FORMATS[0]
    const next = applyKit(docFromTemplate(tpl, { w: f.w, h: f.h, kit }), kit)
    setDoc(next)
    setDocName(`${tpl.name} — ${f.label}`)
    setTemplateId(tpl.id)
    setFormatId(f.id)
    setSelectedLayerId('')
    setSavedHash(hashDoc(next))
    t(`Opened the "${tpl.name}" template at ${f.w}×${f.h}. Layer geometry is normalised, so it stays correct at every other size.`, 'info')
  }, [formatId, kit, t])

  const changeFormat = useCallback((f) => {
    setFormatId(f.id)
    commitDoc(prev => rescaleDoc(prev, f.w, f.h))
    setDocName(`${templateById(prev.templateId)?.name || prev.name} — ${f.label}`)
    t(`Rendered at ${f.w}×${f.h}. Normalised geometry means nothing stretches.`, 'info')
  }, [t])

  const patchLayer = useCallback((id, patch) => commitDoc(prev => updateLayer(prev, id, patch)), [])

  // ── Layer add / edit ──
  const addText = useCallback(() => {
    commitDoc(prev => addLayer(prev, {
      kind: 'text', name: 'Text', role: 'headline',
      x: 0.1, y: 0.42, w: 0.8, h: 0.16, text: 'Your headline', size: 0.06,
      weight: 700, color: kit.ink, align: 'center',
    }))
    t('Text layer added. Edit it in the inspector.', 'info')
  }, [kit.ink, t])

  const addShape = useCallback((shape) => {
    commitDoc(prev => addLayer(prev, {
      kind: 'shape', name: shape === 'ellipse' ? 'Ellipse' : shape === 'triangle' ? 'Triangle' : 'Rectangle',
      shape, x: 0.34, y: 0.34, w: 0.32, h: 0.32, fill: kit.accent, radius: shape === 'rect' ? 0.02 : 0,
    }))
    t('Shape layer added.', 'info')
  }, [kit.accent, t])

  const addProduct = useCallback((assetId) => {
    commitDoc(prev => addLayer(prev, {
      kind: 'product', name: 'Product', assetId, fit: 'contain',
      x: 0.3, y: 0.2, w: 0.4, h: 0.5, contactShadow: true,
    }))
    t('Product layer added from your uploaded artwork.', 'info')
  }, [t])

  const addBadge = useCallback(() => {
    commitDoc(prev => addLayer(prev, {
      kind: 'badge', name: 'Badge', x: 0.38, y: 0.82, w: 0.24, h: 0.08,
      text: 'Learn more', fill: kit.accent, color: '#f5f0e8', size: 0.026,
    }))
    t('Badge layer added.', 'info')
  }, [kit.accent, t])

  // ── Render the master into other placements (real multi-format render) ──
  // ── Compliance pre-flight ──
  // A hard gate, not a document. Blocked prints refuse to export until the
  // operator fixes the asset or explicitly overrides — and an override is
  // recorded on the document, never silent.
  const [overridden, setOverridden] = useState(false)
  const preflight = useMemo(() => checkCompliance(doc, {
    kit,
    prohibited: profile.prohibited,
    competitors: profile.competitors || '',
    listingCopy: profile.listingCopy || '',
  }), [doc, kit, profile.prohibited, profile.competitors, profile.listingCopy])
  useEffect(() => { setOverridden(false) }, [doc.id, doc.updatedAt])
  const gate = preflight.verdict === 'block' && !overridden ? 'blocked' : 'open'

  const renderChannelFormats = useCallback(() => {
    const channel = CHANNEL_SETS.find(c => c.id === renderChannel)?.channel || 'Meta'
    return ALL_FORMATS.filter(f => f.channel === channel)
  }, [renderChannel])

  const exportChannelSet = useCallback(async () => {
    const list = renderChannelFormats()
    if (!list.length) { t('That channel has no known placements in this build.', 'warn'); return }
    // Gate the whole set: any blocked placement refuses the set.
    const bad = list.filter(f => {
      const sub = checkCompliance(rescaleDoc(doc, f.w, f.h), { kit, prohibited: profile.prohibited, competitors: profile.competitors })
      return sub.verdict === 'block'
    })
    if (bad.length && !overridden) {
      t(`Export refused: ${bad.length} placement${bad.length > 1 ? 's' : ''} break a blocking Amazon rule (${bad.map(b => b.label).slice(0, 2).join(', ')}${bad.length > 2 ? '…' : ''}). Fix them or record an override on the canvas.`, 'warn')
      return
    }
    // Phase 7 item 4: the locked-reference gate runs once for the set (same
    // document content, different raster sizes).
    const locked = await lockedGate(doc)
    if (!locked.ok) {
      t(`Export refused — ${locked.detail}`, 'warn')
      return
    }
    let ok = 0
    for (const f of list) {
      try {
        const dataUrl = docToDataUrl(rescaleDoc(doc, f.w, f.h), { assets: images, scale: 1 })
        downloadDataUrl(dataUrl, `${safeFileName(docName)}-${f.w}x${f.h}.png`)
        ok += 1
        setExportLog(prev => [{ id: uid('EX'), name: `${docName} · ${f.w}×${f.h}`, kind: 'png', note: `${renderChannel} set${overridden ? ' (override recorded)' : ''}`, at: nowIso() }, ...prev].slice(0, 80))
      } catch (e) {
        t(`${f.label} failed: ${String(e && e.message || e)}`, 'warn')
      }
    }
    t(`${ok} placement${ok === 1 ? '' : 's'} exported from the master. Each is a real local render at the placement's own pixel size.`, 'info')
  }, [renderChannelFormats, doc, docName, images, renderChannel, kit, profile.prohibited, profile.competitors, overridden, setExportLog, t, lockedGate])

  const saveDoc = useCallback(() => {
    const next = { ...doc, name: docName, kitId: kit.id, savedAt: nowIso() }
    setDocs(prev => {
      const rest = prev.filter(d => d.id !== next.id)
      return [next, ...rest].slice(0, 40)
    })
    setSavedHash(hashDoc(next))
    setDoc(next)
    t('Document saved to the local library.', 'info')
  }, [doc, docName, kit.id, setDocs, t])

  const openDoc = useCallback((d) => {
    setDoc(d)
    setDocName(d.name)
    setFormatId(d.formatId)
    setTemplateId(d.templateId || '')
    setSavedHash(hashDoc(d))
    setSelectedLayerId('')
    go('canvas')
    t(`Opened "${d.name}" from the library.`, 'info')
  }, [go, t])

  const saveRenderToAssets = useCallback(async () => {
    try {
      const dataUrl = docToDataUrl(doc, { assets: images, scale: 0.5 })
      const rec = {
        id: newAssetId(), name: `${safeFileName(docName)}.png`, mime: 'image/png', dataUrl,
        w: doc.w, h: doc.h, bytes: approxBytesOfDataUrl(dataUrl), role: 'render',
        tags: ['studio-doc'], createdAt: nowIso(),
      }
      await putAsset(rec)
      await store.refresh()
      setExportLog(prev => [{ id: uid('EX'), name: rec.name, kind: 'png', note: 'Saved to assets', at: nowIso() }, ...prev].slice(0, 80))
      t('Render saved to the asset store (persisted locally in this browser).', 'info')
    } catch (e) {
      t(`Save failed: ${String(e && e.message || e)}`, 'warn')
    }
  }, [doc, docName, images, store, setExportLog, t])

  // ── Local engine status (ComfyUI) ──
  // Honest state: armed only when the backend gate is on AND ComfyUI answers.
  useEffect(() => {
    let alive = true
    const tick = () => {
      engineApi.status()
        .then(s => { if (alive) setEngine(s) })
        .catch(() => { if (alive) setEngine(prev => prev || { armed: false, reachable: false, note: 'Engine status unavailable.' }) })
    }
    tick()
    const timer = setInterval(tick, 60000)
    return () => { alive = false; clearInterval(timer) }
  }, [])

  // ── Requests ──
  const submitImageRequest = useCallback(async () => {
    if (!genPrompt.trim()) { t('Write a request brief before rendering.', 'warn'); return }
    const rec = {
      id: uid('RQ'), kind: 'image', purpose: genPurpose, prompt: genPrompt.trim(),
      tier: genTier, formatId, format: fmt.label, refs: [], createdAt: nowIso(),
    }
    if (engine && engine.armed) {
      setRequests(prev => [{ ...rec, state: 'Rendering… (local ComfyUI)', providerState: 'connected' }, ...prev])
      setGenBusy(true)
      try {
        const { job } = await engineApi.generateAsync({
          kind: 'image', purpose: genPurpose, brief: genPrompt.trim(), tier: genTier,
          width: fmt.w, height: fmt.h, text_safe: textSafe,
        })
        let j = job
        let tries = 0
        while (j && (j.status === 'queued' || j.status === 'running') && tries < 140) {
          await new Promise(res => setTimeout(res, 3000))
          const st = await engineApi.job(j.id)
          j = st.job
          tries += 1
        }
        if (!j || j.status !== 'done') throw new Error((j && j.logs) || `render ${j ? j.status : 'status unknown'}`)
        const firstId = (j.result_ids && j.result_ids[0]) || ''
        const asset = await engineApi.asset(firstId)
        let md = asset ? asset.metadata : null
        if (typeof md === 'string') { try { md = JSON.parse(md) } catch { md = {} } }
        const out = {
          asset: { ...asset, file_url: (asset && asset.file_url) || (firstId ? `/api/design-studio/assets/${firstId}/file` : '') },
          text_fidelity: (md && md.text_fidelity) || null,
        }
        const tf = out.text_fidelity
        const tfSuffix = tf && tf.check && tf.check.status === 'ok'
          ? (tf.check.contains_text ? ' · ⚠ text seen' : ` · text-free ✓${tf.retried ? ' (auto-rerun)' : ''}`)
          : ''
        setRequests(prev => prev.map(r => r.id === rec.id
          ? { ...r, state: `Done — ${(out.asset.metadata && out.asset.metadata.generation && out.asset.metadata.generation.model) || 'local model'}${tfSuffix}`, fileUrl: out.asset.file_url, assetId: out.asset.id }
          : r))
        setLastRender(out.asset)
        t('Rendered locally on this machine (ComfyUI). Nothing left the box.', 'info')
        if (tf && tf.check && tf.check.status === 'ok') {
          if (tf.verdict === 'text_free') t(`Text check passed: OCR found no lettering${tf.retried ? ' (auto-rerun used the hardened prompt)' : ''}.`, 'info')
          else if (tf.verdict === 'text_cleared' || tf.verdict === 'text_reduced') t(`Detected glyph zones cleared for the vector text layer (${(tf.text_cleanup && tf.text_cleanup.cleared) || 0} zone(s)) — clean plate ready.`, 'info')
          else t(`Text check: lettering detected${tf.check.words && tf.check.words.length ? ` ("${String(tf.check.words[0]).slice(0, 24)}…")` : ''} — use the vector text layer for this copy.`, 'warn')
        }
      } catch (e) {
        const msg = String((e && e.message) || e)
        setRequests(prev => prev.map(r => r.id === rec.id ? { ...r, state: `Failed — ${msg}` } : r))
        t(`Render failed: ${msg}`, 'warn')
      } finally { setGenBusy(false) }
      return
    }
    setRequests(prev => [{
      ...rec, state: 'Blocked — provider required', providerState: 'not_connected',
      note: 'Awaiting a connected local image engine.',
    }, ...prev])
    t('Image request recorded locally — blocked until the engine is armed. Nothing was generated.', 'info')
  }, [engine, genPrompt, genPurpose, genTier, formatId, fmt.label, fmt.w, fmt.h, setRequests, t])

  const submitVideoRequest = useCallback(async () => {
    const dims = vAspect.startsWith('9:16') ? { width: 512, height: 736 }
      : vAspect.startsWith('1:1') ? { width: 640, height: 640 }
      : { width: 832, height: 480 }
    const brief = `Short product clip - ${vPurpose}. Aspect ${vAspect}, intended length ${vDuration}. Product hero shot with a slow camera move.`
    const rec = {
      id: uid('RQ'), kind: 'video', purpose: 'ugc-clip', prompt: brief, tier: 'draft',
      formatId: 'reel-frame', format: String(vAspect), refs: [], createdAt: nowIso(),
    }
    if (engine && engine.armed) {
      setRequests(prev => [{ ...rec, state: 'Rendering clip… (local Wan 2.2)', providerState: 'connected' }, ...prev])
      setVideoBusy(true)
      try {
        const out = await engineApi.generate({
          kind: 'video', purpose: 'ugc-clip', brief, tier: 'draft',
          width: dims.width, height: dims.height,
        })
        setRequests(prev => prev.map(r => r.id === rec.id
          ? { ...r, state: `Done — ${(out.asset.metadata && out.asset.metadata.generation && out.asset.metadata.generation.model) || 'local model'}`, fileUrl: out.asset.file_url, assetId: out.asset.id }
          : r))
        setLastClip(out.asset)
        t('Clip rendered locally on this machine (Wan 2.2). Nothing left the box.', 'info')
      } catch (e) {
        const msg = String((e && e.message) || e)
        setRequests(prev => prev.map(r => r.id === rec.id ? { ...r, state: `Failed — ${msg}` } : r))
        t(`Clip render failed: ${msg}`, 'warn')
      } finally { setVideoBusy(false) }
      return
    }
    setRequests(prev => [{
      ...rec, state: 'Blocked — provider required', providerState: 'not_connected',
      note: 'Awaiting a connected local video engine.',
    }, ...prev])
    t('Clip request recorded locally — blocked until the engine is armed. Nothing was generated.', 'info')
  }, [engine, vPurpose, vDuration, vAspect, setRequests, t])

  const advanceRequest = useCallback((id, nextState) => {
    setRequests(prev => prev.map(r => r.id === id ? { ...r, state: nextState } : r))
    t(`Request ${id} → ${nextState} (local record only).`, 'info')
  }, [setRequests, t])

  const removeRequest = useCallback((id) => {
    setRequests(prev => prev.filter(r => r.id !== id))
    t(`Request ${id} removed from the local queue.`, 'info')
  }, [setRequests, t])

  // ── Variants ──
  const addVariant = useCallback(() => {
    const id = uid('V')
    setVariants(prev => [{
      id, brief: active?.id || '', format: fmt.label, aspect: `${fmt.w}:${fmt.h}`,
      state: 'Draft', note: 'Added locally — not a generated asset.', createdAt: nowIso(),
    }, ...prev])
    t('Variant record added locally (sample workflow). Not a generated asset.', 'info')
  }, [active?.id, fmt, setVariants, t])

  const setVariantState = useCallback((id, state) => {
    setVariants(prev => prev.map(v => v.id === id ? { ...v, state } : v))
    t(`Variant ${id} → ${state} (internal review state — not publishing authorization).`, 'info')
  }, [setVariants, t])

  // ── Briefs ──
  const addBrief = useCallback(() => {
    const id = uid('BR')
    setBriefs(prev => [{
      id, name: `New Brief ${prev.length + 1}`, objective: 'Untitled objective',
      audience: 'Unspecified', brand: kit.name, formats: [fmt.label], deliverables: 1,
      status: 'Draft', note: 'Local draft — complete the work brief.', createdAt: nowIso(),
    }, ...prev])
    setActiveBriefId(id)
    t('New brief draft created — local draft only. No image generates until a local provider is connected and you click Run.', 'info')
    go('canvas')
  }, [kit.name, fmt.label, setBriefs, go, t])

  // ── Bundles ──
  const toggleOutput = useCallback((o) => setOutputs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o]), [setOutputs])

  const prepareBundle = useCallback(() => {
    const id = uid('BX')
    setBundles(prev => [{
      id, briefId: active?.id || '', outputs: [...outputs], basis: 'local workspace records',
      status: 'Ready for handoff', createdAt: nowIso(),
    }, ...prev])
    t('Bundle manifest prepared locally — contains references only. Download is unavailable until an asset store is connected.', 'info')
  }, [active?.id, outputs, setBundles, t])

  // ── The approve-only loop ──
  // Approving a proposal opens a REAL editable document from its template at
  // its placement size, with the proposed headline already in the headline
  // layer. Dismissing records why. Neither publishes or generates anything.
  const today = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const plan = useMemo(() => planToday({ profile, today, docs }), [profile, today, docs])
  const loopStatus = useMemo(() => loopReadiness(profile, docs), [profile, docs])

  const decided = useCallback((id) => loopLog.find(l => l.id === id), [loopLog])

  const approveProposal = useCallback((p) => {
    const tpl = templateById(p.templateId) || TEMPLATES[0]
    const next = applyKit(docFromTemplate(tpl, { w: p.w, h: p.h, kit }), kit)
    // Put the proposed headline into the headline layer, if the template has one.
    next.layers = next.layers.map(l => (
      l.role === 'headline' ? { ...l, text: p.headline } : l
    ))
    next.name = `${p.channelLabel} — ${p.formatLabel}`
    next.loopId = p.id
    next.briefId = active?.id || ''
    commitDoc(next)
    setDocName(next.name)
    setFormatId(p.formatId)
    setTemplateId(tpl.id)
    setSavedHash(hashDoc(next))
    setSelectedLayerId('')
    setDocs(prev => [next, ...prev].slice(0, 40))
    setLoopLog(prev => [{ id: p.id, decision: 'approved', at: nowIso(), channel: p.channelLabel, format: p.formatLabel }, ...prev].slice(0, 200))
    t(`Approved: "${p.channelLabel} — ${p.formatLabel}" opened as an editable document. Approving creates local work only — nothing publishes and nothing generates.`, 'info')
    go('canvas')
  }, [kit, active?.id, setDocs, setLoopLog, t, go])

  const dismissProposal = useCallback((p) => {
    setLoopLog(prev => [{ id: p.id, decision: 'dismissed', at: nowIso(), channel: p.channelLabel, format: p.formatLabel }, ...prev].slice(0, 200))
    t(`Dismissed "${p.channelLabel} — ${p.formatLabel}". Dismissing is final for today; the plan is rebuilt tomorrow.`, 'info')
  }, [setLoopLog, t])


  const blockedCount = requests.filter(r => r.state === 'Blocked — provider required').length
  const selectedLayer = doc.layers.find(l => l.id === selectedLayerId) || null
  const artAssets = useMemo(() => store.assets.filter(a => a.role !== 'render'), [store.assets])
  const renderAssets = useMemo(() => store.assets.filter(a => a.role === 'render'), [store.assets])
  const collectionItems = useMemo(() => {
    const counts = {}
    store.assets.forEach(a => { const k = a.role || 'reference'; counts[k] = (counts[k] || 0) + 1 })
    return counts
  }, [store.assets])

  // ── Shared artwork picker ──
  const ArtworkPicker = ({ onPick, label = 'Artwork' }) => (
    <Section title={label} right={<span className="pill pill-muted">{artAssets.length}</span>}>
      <div className="sp-asset-grid">
        {artAssets.slice(0, 9).map(a => (
          <AssetThumb key={a.id} asset={a} height={52}
            onClick={() => onPick(a.id)}
            actions={<button className="btn btn-sm btn-ghost" title="Remove"
              onClick={(e) => { e.stopPropagation(); store.remove(a.id) }}>×</button>} />
        ))}
        {!artAssets.length && <ThumbPlaceholder height={52} label="no artwork uploaded yet" />}
      </div>
      <label className="sp-dropzone">
        <Icon name="upload" size={14} /> Upload images
        <input type="file" accept="image/*" multiple style={{ display: 'none' }}
          onChange={async (e) => {
            const added = await store.add(e.target.files, { role: 'reference', tags: ['studio'] })
            if (added.length) t(`${added.length} image${added.length > 1 ? 's' : ''} added to the local asset store.`, 'info')
            e.target.value = ''
          }} />
      </label>
      {!store.persistent && (
        <div className="alert" style={{ margin: 0 }}>
          <div className="alert-text">Browser storage is unavailable — uploaded images live for this session only.</div>
        </div>
      )}
    </Section>
  )

  return (
    <>
      <div className="studio-toolbar card">
        <ModeToggle mode={mode} onChange={setMode} />
        <span className="studio-toolbar-meta">Master renders to every placement · layers stay normalised</span>
        <span className="studio-toolbar-spacer" />
        <button className="btn btn-sm btn-ghost" onClick={() => go('canvas')}>Master canvas</button>
        <button className="btn btn-sm btn-ghost" onClick={() => go('exports')}>Export Bundle</button>
        <button className="btn btn-sm" onClick={addBrief}>New Brief</button>
      </div>
      <DataNotice tone="info" compact title="Workspace boundaries">
        Briefs, documents, ad sets, social sets, A+ modules, requests, variants, assets and bundles are real records you create here. The
        canvas renders and exports REAL PNGs from your own layers, and the master renders correctly at every placement size because layer
        geometry is normalised. When the local engine is armed (green banner on the Generate tab), image and video requests render on this
        machine&rsquo;s GPU through the operator&rsquo;s own ComfyUI &mdash; nothing is sent to any provider.
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

      <div className="sp-room wide-inspector">
        <ToolRail tools={TOOLS} active={tool} onSelect={go} />

        <div className="stack" style={{ gap: 14 }}>
          <RoomTabs tabs={TOOLS.map(x => ({ id: x.id, label: x.label }))} base="/creative-studio" />

          {/* ══ PRE-FLIGHT — the always-visible gate ══ */}
          <div className={`alert ${preflight.verdict === 'block' ? 'alert-error' : preflight.verdict === 'flag' ? 'alert-warn' : ''}`} data-testid="preflight">
            <div className="alert-title">
              <span className={`pill ${preflight.verdict === 'block' ? 'pill-error' : preflight.verdict === 'flag' ? 'pill-warn' : 'pill-ok'}`}>
                {preflight.verdict === 'block' ? 'BLOCKED' : preflight.verdict === 'flag' ? 'FLAGGED' : 'PRE-FLIGHT PASS'}
              </span>
              {preflight.total - preflight.blocked.length - preflight.flagged.length} of {preflight.total} checks pass
              {overridden && <span className="pill pill-ochre" style={{ marginLeft: 8 }}>override recorded</span>}
            </div>
            <div className="alert-text">
              {preflight.blocked.length === 0 && preflight.flagged.length === 0 && (
                <>No Amazon rule in scope for this document is broken. Rules are sourced and dated; Amazon changes them.</>
              )}
              {preflight.blocked.length > 0 && (
                <>
                  <strong>{preflight.blocked.length} blocking rule{preflight.blocked.length > 1 ? 's' : ''}</strong>
                  {overridden ? ' — overridden, so export proceeds with the override recorded.' : ' — export is refused until these are fixed or explicitly overridden.'}
                </>
              )}
              {preflight.flagged.length > 0 && (
                <> {preflight.flagged.length} item{preflight.flagged.length > 1 ? 's' : ''} need a human decision and never auto-block.</>
              )}
            </div>
          </div>

          {/* ══ CANVAS ══ */}
          {tool === 'canvas' && (
            <div className="subview">
              <Stage
                doc={doc}
                assets={images}
                zoom={zoom}
                onZoomChange={setZoom}
                selectedId={selectedLayerId}
                onSelectLayer={setSelectedLayerId}
                onChangeLayer={patchLayer}
                advanced={mode === 'advanced'}
                grid={showGrid && mode === 'advanced' ? { cols: 3, safe: 0.06 } : null}
                badge={<>
                  <span className="pill pill-muted">{fmt.label}</span>
                  {dirty && <span className="pill pill-warn">unsaved</span>}
                </>}
                footer={<>
                  <span>{docName}</span>
                  <span>·</span>
                  <span>{doc.layers.length} layers</span>
                  <span>·</span>
                  <span>{kit.name}</span>
                  {mode === 'advanced' && <><span>·</span><span>drag on the canvas to move a layer</span></>}
                </>}
                minHeight={300} maxHeight={560}
              />
              <div className="inline-flex" style={{ marginTop: 12, flexWrap: 'wrap' }}>
                <button className="btn btn-sm btn-primary" onClick={() => { saveDoc(); t('Saved.', 'info') }} disabled={!dirty}>
                  <Icon name="save" size={13} /> Save document
                </button>
                <button className="btn btn-sm btn-ghost" data-testid="proj-undo" disabled={!canUndo} title="Undo (Ctrl+Z)" onClick={undoDoc}>
                  <Icon name="chevronRight" size={13} /> Undo
                </button>
                <button className="btn btn-sm btn-ghost" data-testid="proj-redo" disabled={!canRedo} title="Redo (Ctrl+Shift+Z)" onClick={redoDoc}>
                  <Icon name="chevronRight" size={13} /> Redo
                </button>
                {!lockedReference ? (
                  <button className="btn btn-sm btn-ghost" data-testid="proj-lock-reference" onClick={lockReference}>
                    <Icon name="target" size={13} /> Lock reference
                  </button>
                ) : (
                  <>
                    <button className="btn btn-sm btn-ghost" data-testid="proj-unlock-reference" onClick={unlockReference}>
                      <Icon name="target" size={13} /> Unlock reference
                    </button>
                    <button className="btn btn-sm btn-ghost" data-testid="proj-sign-compare" onClick={signCompare}>
                      <Icon name="list" size={13} /> Compare &amp; sign off
                    </button>
                    <button className="btn btn-sm btn-ghost" data-testid="proj-run-diff" onClick={runFidelityDiff}>
                      <Icon name="target" size={13} /> Run fidelity diff
                    </button>
                  </>
                )}
                <button className="btn btn-sm btn-ghost" onClick={async () => {
                  if (gate === 'blocked') { t('Export refused by the compliance pre-flight. Fix the blocking rules below or record an override.', 'warn'); return }
                  const locked = await lockedGate(doc)
                  if (!locked.ok) { t(`Export refused — ${locked.detail}`, 'warn'); return }
                  downloadDataUrl(docToDataUrl(doc, { assets: images }), `${safeFileName(docName)}-${doc.w}x${doc.h}.png`)
                  setExportLog(prev => [{ id: uid('EX'), name: `${docName} · ${doc.w}×${doc.h}`, kind: 'png', note: overridden ? 'Canvas export (override recorded)' : 'Canvas export', at: nowIso() }, ...prev].slice(0, 80))
                  t(overridden ? 'Exported with a recorded compliance override.' : 'Exported the local render. No provider was contacted.', 'info')
                }} data-testid="proj-export">
                  <Icon name="download" size={13} /> Export PNG
                </button>
                <button className="btn btn-sm btn-ghost" onClick={saveRenderToAssets}><Icon name="image" size={13} /> Save to assets</button>
                {mode === 'advanced' && (
                  <button className="btn btn-sm btn-ghost" onClick={() => setShowGrid(g => !g)}>
                    <Icon name="grid" size={13} /> {showGrid ? 'Hide' : 'Show'} guides
                  </button>
                )}
              </div>
              <div className="text-low" style={{ fontSize: 11, marginTop: 8 }} data-testid="proj-gate-status">
                {lockedReference ? (
                  <>
                    <span className="pill pill-warn" data-testid="proj-reference-pill">reference locked</span>{' '}
                    {compareStatus.satisfied
                      ? `comparison signed off — ${compareStatus.detail}`
                      : `compare required before export — ${compareStatus.detail}`}
                    {diffResult && (
                      <div style={{ marginTop: 4 }} data-testid="proj-diff-result">
                        fidelity diff (on demand): <strong>{diffResult.status}</strong> — {diffResult.detail}
                        <span> The diff compares the rendered product region against the locked file; a composed canvas may legitimately differ, which is why the human sign-off is the export gate.</span>
                      </div>
                    )}
                  </>
                ) : (
                  'No reference lock: export runs the compliance pre-flight only. Lock a reference to turn on the compare sign-off (and the on-demand fidelity diff).'
                )}
              </div>
            </div>
          )}

          {/* ══ CHANNEL SETS ══ */}
          {(tool === 'ads' || tool === 'social' || tool === 'aplus') && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>
                    {tool === 'ads' ? 'Paid ad set' : tool === 'social' ? 'Social content set' : 'A+ content modules'}
                  </h3>
                  <span className="pill pill-muted">rendered from the master</span>
                </div>                <div className="alert-text" style={{ marginBottom: 12 }}>
                  Each tile below is the SAME document rendered at that placement&rsquo;s own pixel size. Because the layer geometry is
                  normalised (0–1 of the canvas), nothing stretches or clips — only the raster resolution changes.
                </div>
                <div className="sp-format-list">
                  {renderChannelFormats().map(f => (
                    <button key={f.id} className={`sp-format ${formatId === f.id ? 'active' : ''}`}
                      onClick={() => { setFormatId(f.id); commitDoc(prev => rescaleDoc(prev, f.w, f.h)); go('canvas') }}
                      title={`Set the master to ${f.w}×${f.h}`}>
                      <span className="sp-format-box ar-wide" style={{ aspectRatio: `${f.w} / ${f.h}` }} />
                      <span className="sp-format-label">{f.label}</span>
                      <span className="text-mono sp-format-dims">{f.w}×{f.h}</span>
                    </button>
                  ))}
                </div>
                <div className="inline-flex" style={{ marginTop: 14 }}>
                  <button className="btn btn-sm btn-primary" onClick={exportChannelSet}>
                    <Icon name="download" size={13} /> Export this set ({renderChannelFormats().length} placements)
                  </button>
                  <span className="pill pill-muted">real local renders · no provider contacted</span>
                </div>
              </div>
            </div>
          )}

          {/* ══ GENERATE ══ */}
          {tool === 'generate' && (
            <div className="subview stack" style={{ gap: 14 }}>
              {engine && engine.armed ? <EngineArmed engine={engine} kind="image" /> : <ProviderBoundary kind="image" />}
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Image request</h3></div>
                <div className="field-group">
                  <span className="label">Purpose</span>
                  <SegmentedControl value={genPurpose} onChange={setGenPurpose}
                    options={GEN_PURPOSES.filter(p => p.family === 'Image').map(p => ({ value: p.id, label: p.label, note: p.note }))} />
                </div>
                <div className="field-group">
                  <span className="label">Request brief</span>
                  <TextInput rows={4} value={genPrompt} onChange={setGenPrompt}
                    placeholder="Describe the product, the scene, the lighting, the mood, and what must be legible." />
                </div>
                <div className="field-group">
                  <label className="inline-flex" style={{ gap: 8, alignItems: 'flex-start', cursor: 'pointer' }}>
                    <input type="checkbox" checked={textSafe} onChange={(e) => setTextSafe(e.target.checked)} style={{ marginTop: 2 }} />
                    <span className="text-low" style={{ fontSize: 12 }}>
                      <strong>Text-safe render:</strong> typographic demands are stripped from the brief and the model is asked for
                      materials + illustration only — the render is then OCR-checked for stray lettering. Real letters belong on the
                      vector text layer (never the model).
                    </span>
                  </label>
                </div>
                <div className="grid-2">
                  <div className="field-group">
                    <span className="label">Tier</span>
                    <Select value={genTier} onChange={setGenTier}
                      options={GEN_TIERS.map(x => ({ value: x.id, label: `${x.label} — ${x.note}` }))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Target placement</span>
                    <Select value={formatId} onChange={(v) => setFormatId(v)}
                      options={ALL_FORMATS.map(f => ({ value: f.id, label: `${f.label} (${f.w}×${f.h})` }))} />
                  </div>
                </div>
                <div className="inline-flex">
                  <button className="btn btn-sm btn-primary" onClick={submitImageRequest} disabled={genBusy}>
                    <Icon name={engine && engine.armed ? 'sparkle' : 'plus'} size={13} />
                    {genBusy ? 'Rendering on this GPU…' : (engine && engine.armed ? 'Generate image (local)' : 'Record request')}
                  </button>
                  {engine && engine.armed
                    ? <span className="pill pill-forest">renders locally on this machine (ComfyUI) · nothing leaves the box</span>
                    : <span className="pill pill-warn">records a local request · renders nothing until the engine is armed</span>}
                </div>
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Request queue</h3></div>
                <DataTable columns={[
                  { key: 'id', label: 'Request' },
                  { key: 'purpose', label: 'Purpose' },
                  { key: 'brief', label: 'Brief', render: (v, r) => <span title={r.prompt}>{r.prompt.length > 46 ? `${r.prompt.slice(0, 46)}…` : r.prompt}</span> },
                  { key: 'format', label: 'Placement' },
                  { key: 'state', label: 'State', render: (v, r) => (<span className="pill pill-unknown">{v}{r.fileUrl ? <>{' · '}<a href={r.fileUrl} target="_blank" rel="noreferrer">open</a></> : null}</span>) },
                  { key: 'act', label: '', render: (v, r) => <button className="btn btn-sm btn-ghost" onClick={() => removeRequest(r.id)}>Remove</button> },
                ]} rows={requests.filter(r => r.kind !== 'video')} emptyText="No requests recorded yet." />
              </div>
              {lastRender && (
                <div className="card" data-testid="latest-render">
                  <div className="card-head">
                    <h3 className="card-title" style={{ fontSize: 15 }}>Latest render</h3>
                    <span className="pill pill-forest">local · {(lastRender.metadata && lastRender.metadata.generation && lastRender.metadata.generation.model) || 'comfyui'}</span>
                  </div>
                  <img src={lastRender.file_url} alt={lastRender.name} style={{ maxWidth: '100%', borderRadius: 10, border: '1px solid var(--border)' }} />
                  <div className="inline-flex" style={{ marginTop: 10, alignItems: 'center' }}>
                    <a className="btn btn-sm" href={lastRender.file_url} target="_blank" rel="noreferrer"><Icon name="download" size={13} /> Open full size</a>
                    <span className="text-low" style={{ fontSize: 11 }}>{lastRender.name} · {lastRender.width}×{lastRender.height} · {fmtBytes(lastRender.size_bytes || 0)}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ VIDEO ══ */}
          {tool === 'video' && (
            <div className="subview stack" style={{ gap: 14 }}>
              {engine && engine.armed ? <EngineArmed engine={engine} kind="video" /> : <ProviderBoundary kind="video" />}
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Short-clip storyboard</h3>
                  {engine && engine.armed
                    ? <span className="pill pill-forest">storyboard composer · local clip renders armed</span>
                    : <span className="pill pill-muted">storyboard composer · no render</span>}
                </div>
                <div className="field-group">
                  <span className="label">Purpose</span>
                  <Select value={vPurpose} onChange={setVPurpose}
                    options={['UGC / testimonial', 'Product motion', 'Ad hook', 'Storyboard / moodboard']} />
                </div>
                <div className="grid-2">
                  <div className="field-group">
                    <span className="label">Duration</span>
                    <Select value={vDuration} onChange={setVDuration} options={['5s', '15s (Short / TikTok)', '30s']} />
                  </div>
                  <div className="field-group">
                    <span className="label">Aspect</span>
                    <Select value={vAspect} onChange={setVAspect} options={['9:16 (vertical)', '1:1 (square)', '16:9 (landscape)']} />
                  </div>
                </div>
                <div className="inline-flex">
                  <button className="btn btn-sm btn-primary" onClick={submitVideoRequest} disabled={videoBusy}>
                    <Icon name={engine && engine.armed ? 'film' : 'plus'} size={13} />
                    {videoBusy ? 'Rendering clip on this GPU… (a few minutes)' : (engine && engine.armed ? 'Render clip (local Wan 2.2)' : 'Record clip request')}
                  </button>
                  {engine && engine.armed
                    ? <span className="pill pill-forest">renders locally · Wan 2.2 TI2V-5B · nothing leaves the box</span>
                    : <span className="pill pill-warn">no video render until the engine is armed</span>}
                </div>
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Beats</h3></div>
                <DataTable columns={[
                  { key: 'id', label: 'Beat' },
                  { key: 'purpose', label: 'Role' },
                  { key: 'brief', label: 'Brief', render: (v, r) => <span title={r.prompt}>{r.prompt}</span> },
                  { key: 'state', label: 'State', render: (v, r) => (<span className="pill pill-unknown">{v}{r.fileUrl ? <>{' · '}<a href={r.fileUrl} target="_blank" rel="noreferrer">open</a></> : null}</span>) },
                ]} rows={requests.filter(r => r.kind === 'video')} emptyText="No clip requests recorded yet." />
              </div>
              {lastClip && (
                <div className="card" data-testid="latest-clip">
                  <div className="card-head">
                    <h3 className="card-title" style={{ fontSize: 15 }}>Latest clip</h3>
                    <span className="pill pill-forest">local · {(lastClip.metadata && lastClip.metadata.generation && lastClip.metadata.generation.model) || 'wan2.2'}</span>
                  </div>
                  <video controls src={lastClip.file_url} style={{ maxWidth: '100%', borderRadius: 10, border: '1px solid var(--border)' }} />
                  <div className="inline-flex" style={{ marginTop: 10, alignItems: 'center' }}>
                    <a className="btn btn-sm" href={lastClip.file_url} target="_blank" rel="noreferrer"><Icon name="download" size={13} /> Open file</a>
                    <span className="text-low" style={{ fontSize: 11 }}>{lastClip.name} · {lastClip.width}×{lastClip.height} · {lastClip.duration_seconds || '?'}s · {fmtBytes(lastClip.size_bytes || 0)}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ BRAND PROFILE ══ */}
          {tool === 'brand' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Brand profile</h3>
                  <span className="pill pill-muted">{profile.origin === 'from-url' ? 'described from URL' : 'described manually'}</span>
                </div>
                <div className="alert-text" style={{ marginBottom: 14 }}>
                  One profile, read by every creative room. This is the &ldquo;describe your brand once&rdquo; step: nothing here
                  generates, and every field below is yours.
                </div>
                <div className="grid-2">
                  <Field label="Brand name">
                    <TextInput value={profile.name} onChange={(v) => setProfile(p => ({ ...p, name: v, updatedAt: nowIso() }))} placeholder="e.g. Word Coffee" />
                  </Field>
                  <Field label="Brand kit" hint="Palette, type and voice the renders use.">
                    <Select value={profile.kitId} onChange={(v) => { setProfile(p => ({ ...p, kitId: v, updatedAt: nowIso() })); setActiveKitId(v) }}
                      options={kits.map(k => ({ value: k.id, label: k.name }))} />
                  </Field>
                  <Field label="Audience" hint="Who this is for. Feeds the social and deck copy.">
                    <TextInput value={profile.audience} onChange={(v) => setProfile(p => ({ ...p, audience: v, updatedAt: nowIso() }))} placeholder="e.g. Homeowners 30–55" />
                  </Field>
                  <Field label="One-line promise" hint="The single claim creative may make. Never invented by the loop.">
                    <TextInput value={profile.promise} onChange={(v) => setProfile(p => ({ ...p, promise: v, updatedAt: nowIso() }))} placeholder="e.g. Water that tastes like it should" />
                  </Field>
                </div>
                <div className="field-group" style={{ marginTop: 12 }}>
                  <span className="label">Voice</span>
                  <TextInput value={profile.voice} onChange={(v) => setProfile(p => ({ ...p, voice: v, updatedAt: nowIso() }))} />
                </div>
                <div className="field-group">
                  <span className="label">Prohibited claims</span>
                  <TextInput rows={2} value={profile.prohibited} onChange={(v) => setProfile(p => ({ ...p, prohibited: v, updatedAt: nowIso() }))}
                    placeholder="Claims the brand must not make. The loop shows these beside every proposal it drafts." />
                </div>
                <div className="field-group">
                  <span className="label">Competitors never to name</span>
                  <TextInput value={profile.competitors || ''} onChange={(v) => setProfile(p => ({ ...p, competitors: v, updatedAt: nowIso() }))}
                    placeholder="Comma-separated. Amazon rejects ads that call out a competitor by name." />
                </div>
                <div className="field-group">
                  <span className="label">Detail-page copy for parity checks</span>
                  <TextInput rows={3} value={profile.listingCopy || ''} onChange={(v) => setProfile(p => ({ ...p, listingCopy: v, updatedAt: nowIso() }))}
                    placeholder="Paste the listing title and bullets. Amazon requires ad claims to be the same as on the detail page, so the pre-flight flags creative claims it cannot find there." />
                  <span className="sp-field-hint">Local only — nothing is fetched from a marketplace.</span>
                </div>
                <div className="field-group">
                  <span className="label">Active channels</span>
                  <ChipRow options={CHANNEL_KIND.map(c => ({ value: c.id, label: c.label, note: c.note }))}
                    value={profile.channels} onToggle={(v) => setProfile(p => ({
                      ...p,
                      channels: p.channels.includes(v) ? p.channels.filter(x => x !== v) : [...p.channels, v],
                      updatedAt: nowIso(),
                    }))} />
                  <span className="sp-field-hint">The daily plan makes one proposal per active channel — a three-channel brand gets three, not thirty.</span>
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Loop readiness</h3>
                  <span className={`pill ${loopStatus.ready === loopStatus.total ? 'pill-forest' : 'pill-warn'}`}>
                    {loopStatus.ready} / {loopStatus.total}
                  </span>
                </div>
                <div className="stack" style={{ gap: 10 }}>
                  {loopStatus.checks.map(c => (
                    <div key={c.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <span className={`pill ${c.ok ? 'pill-forest' : 'pill-unknown'}`} style={{ flexShrink: 0 }}>{c.ok ? 'ready' : 'missing'}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 500 }}>{c.label}</div>
                        <div className="text-low" style={{ fontSize: 11 }}>{c.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ══ TODAY'S PLAN — approve or dismiss ══ */}
          {tool === 'loop' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <DataNotice tone="internal" title="Approve-only — nothing runs without your tap">
                Each row is a proposal: copy, a template and a placement. Approving opens a real editable document in the canvas.
                Dismissing records the decision. Nothing is generated, published, or transmitted — the plan is rebuilt
                deterministically each day so you can always reason about what you approved and why.
              </DataNotice>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Today — {today}</h3>
                  <span className="pill pill-muted">{plan.proposals.length} proposals · {profile.name}</span>
                </div>
                <DataTable columns={[
                  { key: 'channelLabel', label: 'Channel' },
                  { key: 'formatLabel', label: 'Placement', render: (v, r) => <span className="text-mono">{v}<br /><span className="text-low" style={{ fontSize: 10 }}>{r.w}×{r.h}</span></span> },
                  { key: 'headline', label: 'Proposed headline', render: (v, r) => <span title={r.reason}>{v}</span> },
                  { key: 'reason', label: 'Why this', render: (v) => <span className="text-low" style={{ fontSize: 11 }}>{v}</span> },
                  {
                    key: 'state', label: 'Decision', render: (v, r) => {
                      const d = decided(r.id)
                      return d
                        ? <span className={`pill ${d.decision === 'approved' ? 'pill-forest' : 'pill-muted'}`}>{d.decision}</span>
                        : <span className="pill pill-warn">awaiting</span>
                    },
                  },
                  {
                    key: 'act', label: '', render: (v, r) => {
                      const d = decided(r.id)
                      if (d) return <span className="text-low" style={{ fontSize: 11 }}>{fmtTime(d.at)}</span>
                      return (
                        <div className="inline-flex">
                          <button className="btn btn-sm btn-primary" onClick={() => approveProposal(r)}>Approve</button>
                          <button className="btn btn-sm btn-ghost" onClick={() => dismissProposal(r)}>Dismiss</button>
                        </div>
                      )
                    },
                  },
                ]} rows={plan.proposals} emptyText="No active channels — select at least one in the Brand profile." />
                <div className="inline-flex" style={{ gap: 8, marginTop: 12 }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => go('canvas')}>Open the canvas</button>
                  <span className="pill pill-muted">templates · {TEMPLATES.length}</span>
                </div>
              </div>

              {profile.prohibited.trim() && (
                <div className="alert alert-warn">
                  <div className="alert-title"><span className="pill pill-ochre">CLAIMS GUARDRAIL</span> Prohibited claims for {profile.name}</div>
                  <div className="alert-text">{profile.prohibited}</div>
                </div>
              )}

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Decision log</h3>
                  <span className="pill pill-muted">{loopLog.length} local records</span>
                </div>
                <DataTable columns={[
                  { key: 'id', label: 'Proposal' },
                  { key: 'channel', label: 'Channel' },
                  { key: 'format', label: 'Placement' },
                  { key: 'decision', label: 'Decision', render: (v) => <span className={`pill ${v === 'approved' ? 'pill-forest' : 'pill-muted'}`}>{v}</span> },
                  { key: 'at', label: 'When', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                ]} rows={loopLog} emptyText="No decisions recorded yet." />
              </div>
            </div>
          )}

          {/* ══ BRIEFS ══ */}
          {tool === 'briefs' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Work briefs</h3>
                  <button className="btn btn-sm" onClick={addBrief}>New Brief</button>
                </div>
                <DataTable columns={[
                  { key: 'name', label: 'Brief' },
                  { key: 'objective', label: 'Objective' },
                  { key: 'audience', label: 'Audience' },
                  { key: 'deliverables', label: 'Deliverables' },
                  { key: 'status', label: 'State', render: (v) => <span className={`pill ${BRIEF_STATUS[v] || 'pill-muted'}`}>{v}</span> },
                  { key: 'note', label: 'Note' },
                  { key: 'at', label: 'Created', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                ]} rows={briefs.map(b => ({ ...b, at: b.createdAt }))} emptyText="No briefs yet." />
              </div>
              {active && (
                <div className="card">
                  <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Active — {active.name}</h3></div>
                  <div className="grid-2">
                    <div className="field-group">
                      <span className="label">Objective</span>
                      <TextInput value={active.objective} onChange={(v) => setBriefs(prev => prev.map(b => b.id === active.id ? { ...b, objective: v } : b))} />
                    </div>
                    <div className="field-group">
                      <span className="label">Audience</span>
                      <TextInput value={active.audience} onChange={(v) => setBriefs(prev => prev.map(b => b.id === active.id ? { ...b, audience: v } : b))} />
                    </div>
                    <div className="field-group">
                      <span className="label">State</span>
                      <Select value={active.status} onChange={(v) => setBriefs(prev => prev.map(b => b.id === active.id ? { ...b, status: v } : b))}
                        options={['Draft', 'Active', 'In Review', 'Archived']} />
                    </div>
                    <div className="field-group">
                      <span className="label">Deliverables</span>
                      <NumberInput value={active.deliverables} min={0} max={99}
                        onChange={(v) => setBriefs(prev => prev.map(b => b.id === active.id ? { ...b, deliverables: v } : b))} />
                    </div>
                  </div>
                  <div className="field-group" style={{ marginTop: 10 }}>
                    <span className="label">Note</span>
                    <TextInput rows={2} value={active.note} onChange={(v) => setBriefs(prev => prev.map(b => b.id === active.id ? { ...b, note: v } : b))} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ QUEUE ══ */}
          {tool === 'queue' && (
            <div className="subview">
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Production queue</h3>
                  <span className="pill pill-muted">{blockedCount} blocked · {requests.length} total</span>
                </div>
                <DataTable columns={[
                  { key: 'id', label: 'Request' },
                  { key: 'kind', label: 'Kind' },
                  { key: 'purpose', label: 'Purpose' },
                  { key: 'brief', label: 'Brief', render: (v, r) => <span title={r.prompt}>{r.prompt.length > 42 ? `${r.prompt.slice(0, 42)}…` : r.prompt}</span> },
                  { key: 'tier', label: 'Tier' },
                  { key: 'state', label: 'State', render: (v) => <span className={`pill ${pillFor(v)}`}>{v}</span> },
                  { key: 'at', label: 'Recorded', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                  {
                    key: 'act', label: 'Actions', render: (v, r) => (
                      <div className="inline-flex">
                        {r.state === 'Blocked — provider required' && (
                          <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(r.id, 'Queued')}>Queue</button>
                        )}
                        {r.state === 'Queued' && (
                          <button className="btn btn-sm btn-ghost" onClick={() => advanceRequest(r.id, 'In Review')}>Review</button>
                        )}
                        <button className="btn btn-sm btn-ghost" onClick={() => removeRequest(r.id)}>Remove</button>
                      </div>
                    ),
                  },
                ]} rows={requests.map(r => ({ ...r, at: r.createdAt, purpose: GEN_PURPOSES.find(p => p.id === r.purpose)?.label || r.purpose, tier: GEN_TIERS.find(x => x.id === r.tier)?.label || r.tier }))}
                  emptyText="No requests recorded yet. A blocked request means the engine is not connected — not that an asset failed." />
              </div>
            </div>
          )}

          {/* ══ VARIANTS ══ */}
          {tool === 'variants' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Variants &amp; history</h3>
                  <button className="btn btn-sm" onClick={addVariant}>Add Variant</button>
                </div>
                <DataTable columns={[
                  { key: 'id', label: 'Variant' },
                  { key: 'brief', label: 'Brief' },
                  { key: 'format', label: 'Format' },
                  { key: 'aspect', label: 'Aspect' },
                  {
                    key: 'state', label: 'State', render: (v) => <span className={`pill ${pillFor(v)}`}>{v}</span>,
                  },
                  { key: 'note', label: 'Note' },
                  {
                    key: 'act', label: 'Actions', render: (v, r) => (
                      <div className="inline-flex">
                        {r.state !== 'Approved' && <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(r.id, 'Approved')}>Approve</button>}
                        {r.state !== 'Changes Requested' && <button className="btn btn-sm btn-ghost" onClick={() => setVariantState(r.id, 'Changes Requested')}>Changes</button>}
                      </div>
                    ),
                  },
                ]} rows={variants} emptyText="No variants yet." />
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>History</h3></div>
                <DataTable columns={[
                  { key: 'id', label: 'Record' },
                  { key: 'source', label: 'Source' },
                  { key: 'detail', label: 'Detail' },
                  { key: 'at', label: 'When', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                ]} rows={[
                  ...requests.map(r => ({ id: r.id, source: `Request (${r.kind})`, detail: r.prompt, at: r.createdAt })),
                  ...variants.map(v => ({ id: v.id, source: 'Variant', detail: `${v.format} · ${v.state}`, at: v.createdAt })),
                ].sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 40)}
                  emptyText="Nothing recorded yet." />
              </div>
            </div>
          )}

          {/* ══ ASSETS ══ */}
          {tool === 'assets' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Reference artwork</h3>
                  <span className="pill pill-muted">{fmtBytes(store.totalBytes)}</span>
                </div>
                <label className="sp-dropzone" style={{ marginBottom: 12 }}>
                  <Icon name="upload" size={14} /> Upload images to the local store
                  <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                    onChange={async (e) => { await store.add(e.target.files, { role: 'reference', tags: ['studio'] }); e.target.value = '' }} />
                </label>
                <div className="sp-asset-grid">
                  {artAssets.map(a => (
                    <AssetThumb key={a.id} asset={a} height={64}
                      actions={<button className="btn btn-sm btn-ghost" title="Remove" onClick={() => store.remove(a.id)}>×</button>} />
                  ))}
                  {!artAssets.length && <ThumbPlaceholder height={64} label="no artwork uploaded yet" />}
                </div>
                {!store.persistent && (
                  <div className="alert" style={{ marginTop: 12, marginBottom: 0 }}>
                    <div className="alert-text">Browser storage is unavailable — uploaded images live for this session only.</div>
                  </div>
                )}
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Saved renders</h3></div>
                <div className="sp-asset-grid">
                  {renderAssets.map(a => (
                    <AssetThumb key={a.id} asset={a} height={64}
                      actions={<button className="btn btn-sm btn-ghost" title="Remove" onClick={() => store.remove(a.id)}>×</button>} />
                  ))}
                  {!renderAssets.length && <ThumbPlaceholder height={64} label="no renders saved yet" />}
                </div>
              </div>
            </div>
          )}

          {/* ══ EXPORTS ══ */}
          {tool === 'exports' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Bundle Builder — {active ? active.name : 'no active brief'}</h3>
                </div>
                <div className="field-group">
                  <span className="label">Outputs to include</span>
                  <ChipRow value={outputs} onToggle={toggleOutput}
                    options={['Ad creatives', 'Social variants', 'Listing imagery', 'A+ content', 'Email heroes']} />
                </div>
                <div className="inline-flex">
                  <button className="btn btn-sm btn-primary" onClick={prepareBundle}><Icon name="package" size={13} /> Prepare bundle</button>
                  <span className="pill pill-muted">references only · download needs an asset store</span>
                </div>
              </div>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Export log</h3>
                  <span className="pill pill-muted">{exportLog.length} entries</span>
                </div>
                <DataTable columns={[
                  { key: 'name', label: 'Export' },
                  { key: 'kind', label: 'Type' },
                  { key: 'note', label: 'Source' },
                  { key: 'at', label: 'When', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                ]} rows={exportLog} emptyText="Nothing exported from this browser yet." />
              </div>
              {bundles.length > 0 && (
                <div className="card">
                  <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Prepared bundles</h3></div>
                  <DataTable columns={[
                    { key: 'id', label: 'Bundle' },
                    { key: 'briefId', label: 'Brief' },
                    { key: 'outputs', label: 'Outputs' },
                    { key: 'status', label: 'State', render: (v) => <span className="pill pill-forest">{v}</span> },
                    { key: 'at', label: 'Prepared', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                  ]} rows={bundles.map(b => ({ ...b, at: b.createdAt }))} emptyText="No bundles yet." />
                </div>
              )}
            </div>
          )}

          {/* ══ LIBRARY ══ */}
          {tool === 'library' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Saved documents</h3>
                  <span className="pill pill-muted">{docs.length} in this browser</span>
                </div>
                <div className="sp-tpl-grid">
                  {docs.map(d => (
                    <button key={d.id} className="sp-tpl" onClick={() => openDoc(d)}>
                      <div className="sp-scene-swatch" style={{ height: 52, background: 'var(--bone)' }} />
                      <div className="sp-tpl-body">
                        <div className="sp-tpl-name">{d.name}</div>
                        <div className="sp-tpl-note">{d.w}×{d.h} · {d.layers.length} layers · {fmtTime(d.savedAt)}</div>
                      </div>
                    </button>
                  ))}
                  {!docs.length && <ThumbPlaceholder height={72} label="no documents saved yet" />}
                </div>
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Collections</h3></div>
                <DataTable columns={[
                  { key: 'name', label: 'Collection' },
                  { key: 'count', label: 'Items' },
                  { key: 'note', label: 'Note' },
                ]} rows={[
                  { name: 'Brand kit', count: collectionItems.brand || 0, note: 'Logos, type, colour, tone' },
                  { name: 'Product photography', count: collectionItems.reference || 0, note: 'Studio + lifestyle shots' },
                  { name: 'Ad creatives', count: collectionItems.render || 0, note: 'Static + video ad frames' },
                  { name: 'Listing imagery', count: collectionItems['listing'] || 0, note: 'A+ content + main-image sets' },
                ]} emptyText="Nothing in the library yet." />
              </div>
            </div>
          )}
        </div>

        {/* ══ INSPECTOR ══ */}
        <div className="sp-inspector">
          <div className="sp-inspector-head">
            <span className="sp-inspector-title">{TOOLS.find(x => x.id === tool)?.label}</span>
            <span className="pill pill-muted">{mode === 'simple' ? 'Simple' : 'Advanced'}</span>
          </div>
          <div className="sp-inspector-body">

            {tool === 'canvas' && (<>
              <Section title="Document">
                <Field label="Name">
                  <TextInput value={docName} onChange={setDocName} />
                </Field>
                <Field label="Placement" hint="Geometry is normalised — resize freely.">
                  <Select value={formatId} onChange={(v) => { const f = formatById(v); if (f) changeFormat(f) }}
                    options={ALL_FORMATS.map(f => ({ value: f.id, label: `${f.label} (${f.w}×${f.h})` }))} />
                </Field>
              </Section>

              <Section title="Templates" right={<span className="pill pill-muted">{TEMPLATES.length}</span>}>
                <div className="sp-tpl-grid">
                  {TEMPLATES.map(tpl => (
                    <button key={tpl.id} className={`sp-tpl ${templateId === tpl.id ? 'active' : ''}`}
                      onClick={() => openTemplate(tpl.id)} title={tpl.note}>
                      <div className="sp-scene-swatch" style={{ height: 46, background: tpl.layers[0].fill || 'var(--bone)' }} />
                      <div className="sp-tpl-body">
                        <div className="sp-tpl-name">{tpl.name}</div>
                        <div className="sp-tpl-note">{tpl.family}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Add">
                <div className="inline-flex">
                  <button className="btn btn-sm btn-ghost" onClick={addText}><Icon name="type" size={13} /> Text</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => addShape('rect')}><Icon name="shapes" size={13} /> Rect</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => addShape('ellipse')}>Ellipse</button>
                  <button className="btn btn-sm btn-ghost" onClick={addBadge}><Icon name="target" size={13} /> Badge</button>
                </div>
                <Field label="Product layer" hint="From your uploaded artwork.">
                  <div className="sp-asset-grid">
                    {artAssets.slice(0, 6).map(a => (
                      <AssetThumb key={a.id} asset={a} height={40} onClick={() => addProduct(a.id)} />
                    ))}
                  </div>
                  {!artAssets.length && <ThumbPlaceholder height={40} label="upload artwork first" />}
                </Field>
              </Section>

              <Section title="Brand kit" hint="Applied to text and badge layers.">
                <div className="inline-flex">
                  {kits.map(k => (
                    <button key={k.id} className={`filter-pill ${activeKitId === k.id ? 'active' : ''}`} onClick={() => setActiveKitId(k.id)}>{k.name}</button>
                  ))}
                </div>
                <div className="inline-flex" style={{ marginTop: 8 }}>
                  {kit.palette.slice(0, 6).map((c, i) => (
                    <span key={i} title={c} style={{ width: 20, height: 20, borderRadius: 5, background: c, border: '1px solid var(--divider-mid)' }} />
                  ))}
                </div>
                <button className="btn btn-sm btn-ghost" onClick={() => { commitDoc(prev => applyKit(prev, kit)); t('Kit applied to the open document.', 'info') }}>
                  <Icon name="palette" size={13} /> Apply kit to this document
                </button>
              </Section>

              {mode === 'advanced' && (
                <Section title={`Layers (${doc.layers.length})`}>
                  <div className="sp-layers">
                    {[...doc.layers].reverse().map(l => (
                      <div key={l.id} className={`sp-layer ${selectedLayerId === l.id ? 'active' : ''}`} onClick={() => setSelectedLayerId(l.id)}>
                        <Icon name="layers" size={12} />
                        <span className="sp-layer-name">{l.name || l.role || l.kind}</span>
                        <span className="sp-layer-kind">{KIND_LABEL[l.kind]}</span>
                        <span className="sp-layer-btn" title="Move up" onClick={(e) => { e.stopPropagation(); commitDoc(d => reorderLayer(d, l.id, 1)) }}><Icon name="chevronDown" size={12} /></span>
                        <span className="sp-layer-btn" title="Move down" onClick={(e) => { e.stopPropagation(); commitDoc(d => reorderLayer(d, l.id, -1)) }}><Icon name="chevronRight" size={12} /></span>
                        <span className="sp-layer-btn" title="Duplicate" onClick={(e) => { e.stopPropagation(); commitDoc(d => duplicateLayer(d, l.id)) }}><Icon name="copy" size={12} /></span>
                        <span className="sp-layer-btn" title="Delete" onClick={(e) => { e.stopPropagation(); commitDoc(d => removeLayer(d, l.id)) }}><Icon name="trash" size={12} /></span>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {selectedLayer && (
                <Section title={`Edit — ${selectedLayer.name || selectedLayer.role || selectedLayer.kind}`}>
                  {selectedLayer.kind === 'text' && (
                    <>
                      <Field label="Text">
                        <TextInput rows={2} value={selectedLayer.text || ''} onChange={(v) => patchLayer(selectedLayer.id, { text: v })} />
                      </Field>
                      <Field label="Size">
                        <Slider value={selectedLayer.size ?? 0.05} min={0.015} max={0.16} step={0.002} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { size: v })} />
                      </Field>
                      <Field label="Colour">
                        <ColorInput value={selectedLayer.color || '#1a1a1a'} onChange={(v) => patchLayer(selectedLayer.id, { color: v })} />
                      </Field>
                      <Field label="Alignment">
                        <SegmentedControl value={selectedLayer.align || 'left'} onChange={(v) => patchLayer(selectedLayer.id, { align: v })}
                          options={[{ value: 'left', label: 'L' }, { value: 'center', label: 'C' }, { value: 'right', label: 'R' }]} />
                      </Field>
                      <Field label="Weight">
                        <SegmentedControl value={String(selectedLayer.weight ?? 400)} onChange={(v) => patchLayer(selectedLayer.id, { weight: Number(v) })}
                          options={[{ value: '400', label: 'Regular' }, { value: '600', label: 'Semibold' }, { value: '700', label: 'Bold' }]} />
                      </Field>
                      <Toggle checked={!!selectedLayer.uppercase} onChange={(v) => patchLayer(selectedLayer.id, { uppercase: v })} label="Uppercase" />
                      <Toggle checked={!!selectedLayer.shadow} onChange={(v) => patchLayer(selectedLayer.id, { shadow: v })} label="Drop shadow" />
                    </>
                  )}
                  {selectedLayer.kind === 'shape' && (
                    <>
                      <Field label="Fill">
                        <ColorInput value={selectedLayer.fill || '#000000'} onChange={(v) => patchLayer(selectedLayer.id, { fill: v })} />
                      </Field>
                      {selectedLayer.shape === 'rect' && (
                        <Field label="Corner radius">
                          <Slider value={selectedLayer.radius ?? 0} min={0} max={0.2} step={0.005} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { radius: v })} />
                        </Field>
                      )}
                      <Field label="Opacity">
                        <Slider value={selectedLayer.opacity ?? 1} min={0} max={1} onChange={(v) => patchLayer(selectedLayer.id, { opacity: v })} />
                      </Field>
                    </>
                  )}
                  {selectedLayer.kind === 'badge' && (
                    <>
                      <Field label="Label">
                        <TextInput value={selectedLayer.text || ''} onChange={(v) => patchLayer(selectedLayer.id, { text: v })} />
                      </Field>
                      <Field label="Fill">
                        <ColorInput value={selectedLayer.fill || '#1d4a1d'} onChange={(v) => patchLayer(selectedLayer.id, { fill: v })} />
                      </Field>
                      <Field label="Text colour">
                        <ColorInput value={selectedLayer.color || '#f5f0e8'} onChange={(v) => patchLayer(selectedLayer.id, { color: v })} />
                      </Field>
                    </>
                  )}
                  {(selectedLayer.kind === 'image' || selectedLayer.kind === 'product') && (
                    <>
                      <Field label="Artwork" hint="Replace the image on this layer.">
                        <div className="sp-asset-grid">
                          {artAssets.slice(0, 6).map(a => (
                            <AssetThumb key={a.id} asset={a} height={40} selected={selectedLayer.assetId === a.id}
                              onClick={() => patchLayer(selectedLayer.id, { assetId: a.id })} />
                          ))}
                        </div>
                      </Field>
                      <Toggle checked={selectedLayer.contactShadow !== false} onChange={(v) => patchLayer(selectedLayer.id, { contactShadow: v })} label="Contact shadow" />
                    </>
                  )}
                  {mode === 'advanced' && (
                    <>
                      <Field label="X">
                        <Slider value={selectedLayer.x ?? 0} min={-0.2} max={1} step={0.005} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { x: v })} />
                      </Field>
                      <Field label="Y">
                        <Slider value={selectedLayer.y ?? 0} min={-0.2} max={1} step={0.005} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { y: v })} />
                      </Field>
                      <Field label="Width">
                        <Slider value={selectedLayer.w ?? 0.2} min={0.02} max={1.2} step={0.005} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { w: v })} />
                      </Field>
                      <Field label="Height">
                        <Slider value={selectedLayer.h ?? 0.2} min={0.02} max={1.2} step={0.005} suffix="%" onChange={(v) => patchLayer(selectedLayer.id, { h: v })} />
                      </Field>
                      <Field label="Rotation">
                        <Slider value={selectedLayer.rot ?? 0} min={-180} max={180} step={1} suffix="°" onChange={(v) => patchLayer(selectedLayer.id, { rot: v })} />
                      </Field>
                      <Field label="Opacity">
                        <Slider value={selectedLayer.opacity ?? 1} min={0} max={1} onChange={(v) => patchLayer(selectedLayer.id, { opacity: v })} />
                      </Field>
                    </>
                  )}
                </Section>
              )}

              <Section title="Amazon pre-flight" right={<span className={`pill ${preflight.verdict === 'block' ? 'pill-error' : preflight.verdict === 'flag' ? 'pill-warn' : 'pill-ok'}`}>{preflight.verdict}</span>}>
                <div className="stack" style={{ gap: 8 }}>
                  {preflight.blocked.map(r => (
                    <div key={r.id} className="alert alert-error" style={{ margin: 0, padding: '9px 11px' }}>
                      <div style={{ fontSize: 11.5, fontWeight: 600 }}>{r.label}</div>
                      <div className="text-low" style={{ fontSize: 10.5, marginTop: 2, lineHeight: 1.4 }}>{r.detail}</div>
                      <div className="text-mono" style={{ fontSize: 9, marginTop: 3, color: 'var(--ink-faint)' }}>{r.source} · accessed {r.accessed}{r.dateSensitive ? ' · date-sensitive' : ''}</div>
                    </div>
                  ))}
                  {preflight.flagged.map(r => (
                    <div key={r.id} className="alert" style={{ margin: 0, padding: '9px 11px' }}>
                      <div style={{ fontSize: 11.5, fontWeight: 600 }}>{r.label}</div>
                      <div className="text-low" style={{ fontSize: 10.5, marginTop: 2, lineHeight: 1.4 }}>{r.detail}</div>
                      <div className="text-mono" style={{ fontSize: 9, marginTop: 3, color: 'var(--ink-faint)' }}>{r.source} · accessed {r.accessed}{r.dateSensitive ? ' · date-sensitive' : ''}</div>
                    </div>
                  ))}
                  {!preflight.blocked.length && !preflight.flagged.length && (
                    <span className="text-low" style={{ fontSize: 11.5 }}>All {preflight.total} scoped rules pass. {rulesInScope(doc).length} rules are in scope for this format.</span>
                  )}
                </div>
                {preflight.blocked.length > 0 && (
                  <div className="inline-flex" style={{ marginTop: 8 }}>
                    {overridden
                      ? <span className="pill pill-ochre">override recorded on this document</span>
                      : <button className="btn btn-sm btn-ghost" onClick={() => {
                        setOverridden(true)
                        t('Override recorded. The document now carries a compliance override — export it knowingly, not silently.', 'warn')
                      }}>Override and export</button>}
                  </div>
                )}
              </Section>

              {(tool === 'ads' || tool === 'social' || tool === 'aplus') && (
                <Section title="Pre-flight for this set">
                  {renderChannelFormats().map(f => {
                    const sub = checkCompliance(rescaleDoc(doc, f.w, f.h), { kit, prohibited: profile.prohibited, competitors: profile.competitors })
                    return (
                      <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, padding: '3px 0' }}>
                        <span className={`pill ${sub.verdict === 'block' ? 'pill-error' : sub.verdict === 'flag' ? 'pill-warn' : 'pill-ok'}`}>{sub.verdict}</span>
                        <span className="text-mid">{f.label}</span>
                      </div>
                    )
                  })}
                  <span className="sp-field-hint">Each placement is checked at its own pixel size before the set is exported.</span>
                </Section>
              )}

              <Section title="Handoff" hint="Moves a local record id — never a file.">                <div className="sp-handoff">
                  <button className="btn btn-sm btn-ghost" onClick={() => { t('Sent to AdPilot — the campaign planner opens with the local brief id. No file is transmitted.', 'info'); navigate('/adpilot?view=planner') }}>
                    <Icon name="target" size={13} /> AdPilot
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { t('Sent to SocialPulse — the composer opens with the local brief id. No file is transmitted.', 'info'); navigate('/socialpulse?view=composer') }}>
                    <Icon name="users" size={13} /> SocialPulse
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { t('Sent to the Product Designer — the scene designer opens with the local art id.', 'info'); navigate('/product-designer?view=scene') }}>
                    <Icon name="camera" size={13} /> Product Designer
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => { t('Sent to ListingForge — the listing editor opens with the local imagery set id.', 'info'); navigate('/listingforge?view=editor') }}>
                    <Icon name="list" size={13} /> ListingForge
                  </button>
                </div>
              </Section>
            </>)}

            {(tool === 'ads' || tool === 'social' || tool === 'aplus') && (
              <Section title="Placement">
                <Field label="Set the master to">
                  <Select value={formatId} onChange={(v) => { const f = formatById(v); if (f) changeFormat(f); go('canvas') }}
                    options={renderChannelFormats().map(f => ({ value: f.id, label: `${f.label} (${f.w}×${f.h})` }))} />
                </Field>
                <button className="btn btn-sm btn-primary" onClick={exportChannelSet}>
                  <Icon name="download" size={13} /> Export {renderChannelFormats().length} placements
                </button>
                <span className="sp-field-hint">Each placement is a real local render at its own pixel size.</span>
              </Section>
            )}

            {tool === 'generate' && (
              <Section title="Tier" hint="A local cost model, not a price quote.">
                <div className="stack" style={{ gap: 8 }}>
                  {GEN_TIERS.map(x => (
                    <div key={x.id} className="sp-stat">
                      <div className="sp-stat-label">{x.label}</div>
                      <div className="sp-stat-value">{x.cost}×</div>
                      <div className="sp-stat-sub">{x.note}</div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {tool === 'video' && (
              <Section title="Provider">
                {engine && engine.armed ? <EngineArmed engine={engine} kind="video" /> : <ProviderBoundary kind="video" />}
              </Section>
            )}

            {tool === 'assets' && (
              <Section title="Store health">
                <div className="sp-stats">
                  <Stat label="Assets" value={store.assets.length} />
                  <Stat label="Size" value={fmtBytes(store.totalBytes)} />
                  <Stat label="Persistence" value={store.persistent ? 'Local' : 'Session'} tone={store.persistent ? 'forest' : 'ochre'} />
                </div>
              </Section>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

