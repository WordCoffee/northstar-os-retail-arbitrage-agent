// ═══════════════════════════════════════════════════════════════════════════
// PRODUCT DESIGNER — /product-designer
//
// Operator-owned product creative desk: scene composites, a real 3D packaging
// view, mockup placement, and a provider-gated generation queue. Every pixel is
// produced locally from the operator's own artwork and scene recipes.
//
// HONESTY CONTRACT (this room):
//   • The operator's uploaded artwork, brand kit, scene recipes, mockups,
//     exports, and queue records are REAL local records (IndexedDB + this
//     browser). They are never presented as provider output.
//   • Nothing here calls an image or video model. The Generate tab is a real
//     request recorder that lands in the honest terminal state
//     "Blocked — provider required" until a local engine is armed.
//   • The 3D view is real geometry (rotated box mesh, three-point lighting,
//     affine texture mapping) rendered on Canvas 2D. It is not a photoreal
//     render and is never labelled as one.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PageLayout, DataNotice, DataTable, MetricTiles } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import Icon from '../../components/Icon.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import Stage from '../../studio/components/Stage.jsx'
import {
  ModeToggle, ToolRail, ProviderBoundary, AssetThumb, ThumbPlaceholder, FormatGrid,
} from '../../studio/components/Chrome.jsx'
import {
  Section, Field, TextInput, NumberInput, Slider, Select, ColorInput,
  SegmentedControl, Toggle, ChipRow, Stat,
} from '../../studio/components/Fields.jsx'
import {
  KIND_LABEL, createDoc, updateLayer, removeLayer, reorderLayer, docToDataUrl, downloadDataUrl, safeFileName,
} from '../../studio/engine/doc.js'
import { buildSceneDoc } from '../../studio/engine/sceneDoc.js'
import { renderMockup, mockupToDataUrl } from '../../studio/engine/mockups.js'
import { renderBox, cameraToRadians, describeAngle, FACE_KEYS } from '../../studio/engine/three.js'
import {
  useAssetStore, useDecodedAssets, putAsset, newAssetId, loadImage, approxBytesOfDataUrl,
} from '../../studio/engine/assets.js'
import { useRoom, uid, nowIso, fmtTime, fmtBytes, hashDoc } from '../../studio/engine/store.js'
// Phase 7 item 4: the 3D render export gate (actual-photo BLOCK, pre-flight,
// disclosure, fidelity, product-accuracy sign-off).
import { gateRender3d, RENDER_PURPOSES, makeRenderDoc } from '../../studio/engine/render3d.js'
import { makeCompareSignOff, compareStepStatus } from '../../studio/engine/compose.js'
import {
  FORMAT_GROUPS, ALL_FORMATS, formatById, SCENES, sceneById, LIGHTING, lightingById,
  BOX_PRESETS, boxPresetById, MOCKUP_SURFACES, CAMERA_PRESETS,
  DEFAULT_BRAND_KITS, COPY_ROLES, GEN_PURPOSES, GEN_TIERS,
} from '../../studio/engine/presets.js'

// ── Local rooms ──────────────────────────────────────────────────────────────
const TOOLS = [
  { id: 'scene', label: 'Product scene', icon: 'camera', note: 'Composite the product onto a scene recipe and export.' },
  { id: 'pack', label: '3D pack view', icon: 'cube', note: 'Real 3D box with the pack art mapped onto each face.' },
  { id: 'mock', label: 'Mockups', icon: 'package', note: 'Place artwork on physical mockup surfaces.' },
  { id: 'gen', label: 'Generate', icon: 'sparkle', note: 'Image / clip requests — provider-gated.' },
  { id: 'brand', label: 'Backdrops & brand', icon: 'palette', note: 'Scene recipes and the active brand kit.' },
  { id: 'lib', label: 'Library', icon: 'stack', note: 'Saved renders, exports and queue history.' },
]

const FACE_LABEL = {
  front: 'Front', back: 'Back', left: 'Left', right: 'Right', top: 'Top', bottom: 'Bottom',
}

export default function ProductDesigner() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [mode, setMode] = useRoom('pd-mode', 'simple')
  const [kits, setKits] = useRoom('pd-kits', DEFAULT_BRAND_KITS)
  const [activeKitId, setActiveKitId] = useRoom('pd-active-kit', 'kit-pine')
  const [requests, setRequests] = useRoom('pd-requests', [])
  const [exports, setExports] = useRoom('pd-exports', [])
  const [savedRenders, setSavedRenders] = useRoom('pd-renders', [])

  const store = useAssetStore()
  const { images, ready } = useDecodedAssets(store.assets)
  const kit = kits.find(k => k.id === activeKitId) || kits[0] || DEFAULT_BRAND_KITS[0]

  const requested = new URLSearchParams(location.search).get('view') || ''
  const tool = TOOLS.some(t => t.id === requested) ? requested : 'scene'

  const t = useCallback((msg, tone = 'info') => toast(msg, tone), [toast])
  const go = useCallback((id) => navigate(`/product-designer?view=${id}`), [navigate])

  // ── Product scene state ──
  const [sceneId, setSceneId] = useState('scene-studio-paper')
  const [sceneFormatId, setSceneFormatId] = useState('amz-main')
  const [artId, setArtId] = useState('')
  const [sceneCopy, setSceneCopy] = useState({ headline: '', subhead: '' })
  const [cam, setCam] = useState({ yaw: 0, pitch: 6 })
  const [placement, setPlacement] = useState({ x: 0.24, y: 0.14, w: 0.52, h: 0.7 })
  const [sceneExtra, setSceneExtra] = useState({ cta: '', legal: '' })
  const [sceneDoc, setSceneDoc] = useState(() => createDoc({ w: 1600, h: 1600, name: 'Untitled scene' }))
  const [selectedLayerId, setSelectedLayerId] = useState('')

  // ── Render export gate state (Phase 7 item 4) ──
  // One sign-off covers every view of the same scene state: the gate adapter is
  // kind-agnostic and bound to the scene's canonical dims + a scene hash.
  const [renderMeta, setRenderMeta] = useState({
    purpose: 'internal',
    peopleClass: '',            // '' = unanswered -> the gate blocks
    syntheticPerformerTag: false,
    fidelityMode: '',           // '' | 'locked'
    referenceDataUrl: '',
    compareConfirmed: null,
  })
  const [gateResult, setGateResult] = useState(null)
  const sceneStamp = useMemo(() => hashDoc(sceneDoc), [sceneDoc])
  const gateMeta = useMemo(() => ({
    peopleClass: renderMeta.peopleClass || undefined,
    syntheticPerformerTag: renderMeta.syntheticPerformerTag,
    fidelityMode: renderMeta.fidelityMode || 'placed',
    referenceDataUrl: renderMeta.referenceDataUrl || undefined,
    compareConfirmed: renderMeta.compareConfirmed || undefined,
    lastEditAt: sceneStamp,
    purpose: renderMeta.purpose,
  }), [renderMeta, sceneStamp])

  const sceneFormat = formatById(sceneFormatId) || ALL_FORMATS[0]
  const scene = sceneById(sceneId)

  const builtSceneDoc = useMemo(() => buildSceneDoc({
    sceneId, format: sceneFormat, artId, copy: sceneCopy, camera: cam, placement, kit,
  }), [sceneId, sceneFormatId, artId, sceneCopy.headline, sceneCopy.subhead, cam.yaw, cam.pitch, placement.x, placement.y, placement.w, placement.h, kit.id])

  // Keep the working doc in sync with the recipe until the operator hand-edits it.
  const recipeKey = useMemo(() => JSON.stringify({
    s: sceneId, f: sceneFormatId, a: artId, c: sceneCopy, m: cam, p: placement, k: kit.id,
  }), [sceneId, sceneFormatId, artId, sceneCopy, cam, placement, kit.id])

  useEffect(() => { setSceneDoc(builtSceneDoc); setSelectedLayerId('') }, [recipeKey])

  const patchSceneLayer = useCallback((id, patch) => {
    setSceneDoc(prev => updateLayer(prev, id, patch))
  }, [])

  // ── Undo / redo for the scene document (Phase 8 item 6) ──────────────────
  const sceneHistoryRef = useRef({ past: [], future: [] })
  const sceneApplyingRef = useRef(false)
  const sceneLastRef = useRef(null)
  const [sceneHistoryTick, setSceneHistoryTick] = useState(0)
  useEffect(() => {
    if (sceneLastRef.current === null) { sceneLastRef.current = sceneDoc; return }
    if (sceneApplyingRef.current) { sceneApplyingRef.current = false; sceneLastRef.current = sceneDoc; return }
    if (sceneDoc === sceneLastRef.current) return
    const h = sceneHistoryRef.current
    h.past = [...h.past.slice(-49), sceneLastRef.current]
    h.future = []
    sceneLastRef.current = sceneDoc
    setSceneHistoryTick(v => v + 1)
  }, [sceneDoc])
  const undoScene = useCallback(() => {
    const h = sceneHistoryRef.current
    if (!h.past.length) return
    const prev = h.past[h.past.length - 1]
    h.past = h.past.slice(0, -1)
    h.future = [sceneDoc, ...h.future].slice(0, 50)
    sceneApplyingRef.current = true
    sceneLastRef.current = prev
    setSceneDoc(prev)
    setSceneHistoryTick(v => v + 1)
  }, [sceneDoc])
  const redoScene = useCallback(() => {
    const h = sceneHistoryRef.current
    if (!h.future.length) return
    const next = h.future[0]
    h.future = h.future.slice(1)
    h.past = [...h.past, sceneDoc].slice(-50)
    sceneApplyingRef.current = true
    sceneLastRef.current = next
    setSceneDoc(next)
    setSceneHistoryTick(v => v + 1)
  }, [sceneDoc])
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const tag = (e.target && e.target.tagName) || ''
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return
      const k = String(e.key || '').toLowerCase()
      if (k === 'z') { e.preventDefault(); if (e.shiftKey) redoScene(); else undoScene() }
      else if (k === 'y') { e.preventDefault(); redoScene() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undoScene, redoScene])
  const canUndoScene = sceneHistoryRef.current.past.length > 0
  const canRedoScene = sceneHistoryRef.current.future.length > 0
  void sceneHistoryTick

  // ── 3D pack state ──
  const [packPresetId, setPackPresetId] = useState('carton')
  const [packFormatId, setPackFormatId] = useState('amz-main')
  const [faces, setFaces] = useState(() => FACE_KEYS.reduce((m, k) => ({ ...m, [k]: { fill: '#e8e2d8', assetId: '' } }), {}))
  const [lightingId, setLightingId] = useState('three-point')
  const [camPresetId, setCamPresetId] = useState('hero')
  const [freeCam, setFreeCam] = useState({ yaw: -28, pitch: 12, roll: 0 })
  const [spin, setSpin] = useState(false)
  const [spinSpeed, setSpinSpeed] = useState(18)
  const [showFloor, setShowFloor] = useState(true)
  const [showGuide, setShowGuide] = useState(false)
  const [activeFace, setActiveFace] = useState('front')
  const [bgId, setBgId] = useState('scene-deep-pine')
  const packCanvasRef = useRef(null)
  const packWrapRef = useRef(null)
  const [packSize, setPackSize] = useState({ w: 640, h: 640 })
  const spinRef = useRef(false)
  spinRef.current = spin

  const packPreset = boxPresetById(packPresetId)
  const packFormat = formatById(packFormatId) || ALL_FORMATS[0]
  const lighting = lightingById(lightingId)
  const bgScene = sceneById(bgId)

  useEffect(() => {
    const el = packWrapRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(entries => {
      const rect = entries[0]?.contentRect
      if (rect) setPackSize({ w: Math.max(260, Math.round(rect.width)), h: Math.max(260, Math.round(rect.height)) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [tool])

  const camRad = cameraToRadians(CAMERA_PRESETS.find(c => c.id === camPresetId) || CAMERA_PRESETS[0], freeCam)

  const paintPack = useCallback(() => {
    const canvas = packCanvasRef.current
    if (!canvas) return
    const W = packSize.w; const H = packSize.h
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H }
    const ctx = canvas.getContext('2d')
    renderBox(ctx, {
      W, H, size: packPreset.size, faces, camera: camRad, lighting,
      floor: showFloor, edges: true, assets: images, bg: bgScene.bg, spinGuide: showGuide,
    })
  }, [packSize.w, packSize.h, packPreset.size, faces, camRad.yaw, camRad.pitch, camRad.roll, lighting, showFloor, showGuide, images, ready, bgScene.id])

  useEffect(() => { paintPack() }, [paintPack])

  // Turntable.
  useEffect(() => {
    if (tool !== 'pack' || !spin) return undefined
    let raf = 0
    let last = performance.now()
    const loop = (now) => {
      const dt = (now - last) / 1000
      last = now
      setFreeCam(prev => ({ ...prev, yaw: (prev.yaw + spinSpeed * dt) % 360 }))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [tool, spin, spinSpeed])

  // ── Mockup state ──
  const [mockSurfaceId, setMockSurfaceId] = useState('tee')
  const [mockArtId, setMockArtId] = useState('')
  const [mockBlend, setMockBlend] = useState('multiply')
  const mockCanvasRef = useRef(null)
  const mockSurface = MOCKUP_SURFACES.find(s => s.id === mockSurfaceId) || MOCKUP_SURFACES[0]

  useEffect(() => {
    if (tool !== 'mock') return undefined
    let alive = true
    const paint = () => {
      const canvas = mockCanvasRef.current
      if (!canvas || !alive) return
      const size = 560
      if (canvas.width !== size) { canvas.width = size; canvas.height = size }
      const art = mockArtId ? images.get(mockArtId) : null
      renderMockup(canvas.getContext('2d'), mockSurfaceId, art || null, { W: size, H: size, blend: mockBlend })
    }
    if (mockArtId) {
      loadImage((store.assets.find(a => a.id === mockArtId) || {}).dataUrl).then(paint).catch(paint)
    } else paint()
    return () => { alive = false }
  }, [tool, mockSurfaceId, mockArtId, mockBlend, images, ready, store.assets])

  // ── Generate state ──
  const [genPurpose, setGenPurpose] = useState('product-scene')
  const [genTier, setGenTier] = useState('draft')
  const [genPrompt, setGenPrompt] = useState('')
  const [genFormatId, setGenFormatId] = useState('meta-feed')
  const [genCount, setGenCount] = useState(2)
  const [genRefIds, setGenRefIds] = useState([])
  const [engineStatus, setEngineStatus] = useState(null)
  const [engineChecking, setEngineChecking] = useState(false)

  const genPurposeObj = GEN_PURPOSES.find(p => p.id === genPurpose) || GEN_PURPOSES[0]
  const genTierObj = GEN_TIERS.find(x => x.id === genTier) || GEN_TIERS[0]
  const genFormat = formatById(genFormatId) || ALL_FORMATS[0]

  const checkEngine = useCallback(async () => {
    setEngineChecking(true)
    try {
      const ac = new AbortController()
      const timer = setTimeout(() => ac.abort(), 2500)
      const res = await fetch('/api/v1/foundation/creative/readiness', { signal: ac.signal })
      clearTimeout(timer)
      if (!res.ok) { setEngineStatus({ ok: false, reason: `route returned ${res.status}` }); return }
      const body = await res.json()
      setEngineStatus({ ok: !!body.armed, body })
    } catch (e) {
      setEngineStatus({ ok: false, reason: String(e && e.message || e) })
    } finally {
      setEngineChecking(false)
    }
  }, [])

  const submitGen = useCallback(() => {
    if (!genPrompt.trim()) { t('Write a request brief before queueing.', 'warn'); return }
    const n = Math.max(1, Math.min(8, Number(genCount) || 1))
    const created = []
    for (let i = 0; i < n; i += 1) {
      created.push({
        id: uid('RQ'), kind: genPurposeObj.family.toLowerCase(), purpose: genPurpose,
        prompt: genPrompt.trim(), tier: genTier, formatId: genFormatId, format: genFormat.label,
        refs: [...genRefIds], state: 'Blocked — provider required', providerState: 'not_connected',
        note: genPurposeObj.family === 'Video'
          ? 'No local video pipeline exists in this build.'
          : 'Awaiting a connected local image engine.',
        createdAt: nowIso(),
      })
    }
    setRequests(prev => [...created, ...prev])
    t(`${created.length} request${created.length > 1 ? 's' : ''} recorded locally — blocked until a local engine is connected. Nothing was generated.`, 'info')
  }, [genPrompt, genCount, genPurpose, genTier, genFormatId, genRefIds, genPurposeObj.family, genFormat.label, setRequests, t])

  const dropRequest = useCallback((id) => {
    setRequests(prev => prev.filter(r => r.id !== id))
    t(`Request ${id} removed from the local queue.`, 'info')
  }, [setRequests, t])

  // ── Save / export ──
  const recordExport = useCallback((kind, name, note) => {
    setExports(prev => [{
      id: uid('EX'), kind, name, note, at: nowIso(),
    }, ...prev].slice(0, 80))
  }, [setExports])

  // ── Render gate helpers (Phase 7 item 4) ──
  const runRenderGate = useCallback(async (renderKind, actualW, actualH, dataUrl) => {
    const res = await gateRender3d({
      purpose: renderMeta.purpose,
      renderKind,
      w: sceneFormat.w, h: sceneFormat.h,   // canonical dims: the version binding
      dataUrl,
      meta: { ...gateMeta, renderW: actualW, renderH: actualH },
    })
    setGateResult(res)
    return res
  }, [renderMeta.purpose, sceneFormat, gateMeta])

  const lockRenderReference = useCallback(() => {
    const dataUrl = artId ? (store.assets.find(a => a.id === artId) || {}).dataUrl : null
    if (!dataUrl) { t('Attach the product photograph to the scene first — that file becomes the locked reference.', 'warn'); return }
    setRenderMeta(m => ({ ...m, fidelityMode: 'locked', referenceDataUrl: dataUrl }))
    t('Reference locked. Exports now run the fidelity diff against this photograph and require a compare sign-off.', 'info')
  }, [artId, store.assets, t])

  const unlockRenderReference = useCallback(() => {
    setRenderMeta(m => ({ ...m, fidelityMode: '', referenceDataUrl: '', compareConfirmed: null }))
    t('Reference lock removed. The fidelity diff and the sign-off requirement are off for internal exports.', 'info')
  }, [t])

  const signRenderCompare = useCallback(() => {
    const adapter = makeRenderDoc({ w: sceneFormat.w, h: sceneFormat.h, dataUrl: 'about:blank', meta: { ...gateMeta } })
    setRenderMeta(m => ({ ...m, compareConfirmed: makeCompareSignOff(adapter, { user: 'operator' }) }))
    t('Comparison signed off — a self-declaration bound to the current scene state.', 'info')
  }, [sceneFormat, gateMeta, t])

  const compareState = useMemo(() => {
    const adapter = makeRenderDoc({ w: sceneFormat.w, h: sceneFormat.h, dataUrl: 'about:blank', meta: { ...gateMeta } })
    return compareStepStatus(adapter)
  }, [sceneFormat, gateMeta])

  const exportScene = useCallback(async () => {
    if (!artId) { t('Attach a product image to the scene before exporting.', 'warn'); return }
    try {
      const dataUrl = docToDataUrl(sceneDoc, { assets: images, scale: 1 })
      const gate = await runRenderGate('scene', sceneFormat.w, sceneFormat.h, dataUrl)
      if (!gate.ok) { t(`Export refused — ${gate.blocked.join('; ')}. See the render gate panel.`, 'warn'); return }
      downloadDataUrl(dataUrl, `${safeFileName(sceneDoc.name)}-${sceneFormat.w}x${sceneFormat.h}.png`)
      recordExport('png', `${sceneDoc.name} · ${sceneFormat.w}×${sceneFormat.h}`, 'Scene composite')
      t('Scene exported as PNG from the local render. No provider was contacted.', 'info')
    } catch (e) {
      t(`Export failed: ${String(e && e.message || e)}`, 'warn')
    }
  }, [artId, sceneDoc, images, sceneFormat, recordExport, t, runRenderGate])

  const saveSceneToLibrary = useCallback(async () => {
    if (!artId) { t('Attach a product image before saving to the library.', 'warn'); return }
    try {
      const dataUrl = docToDataUrl(sceneDoc, { assets: images, scale: 0.5 })
      const id = newAssetId()
      const rec = {
        id, name: `${sceneDoc.name}.png`, mime: 'image/png', dataUrl,
        w: sceneFormat.w, h: sceneFormat.h, bytes: approxBytesOfDataUrl(dataUrl),
        role: 'render', tags: ['scene', sceneId], createdAt: nowIso(),
      }
      const res = await putAsset(rec)
      await store.refresh()
      setSavedRenders(prev => [{ id, name: rec.name, at: nowIso(), source: 'Product scene' }, ...prev].slice(0, 60))
      t(res.ok
        ? 'Render saved to the library (persisted locally in this browser).'
        : 'Render saved for this session only — browser storage was unavailable.', res.ok ? 'info' : 'warn')
    } catch (e) {
      t(`Save failed: ${String(e && e.message || e)}`, 'warn')
    }
  }, [artId, sceneDoc, images, sceneFormat, sceneId, store, setSavedRenders, t])

  const exportPackFrame = useCallback(async () => {
    const canvas = packCanvasRef.current
    if (!canvas) return
    try {
      const dataUrl = canvas.toDataURL('image/png')
      const gate = await runRenderGate('pack', canvas.width, canvas.height, dataUrl)
      if (!gate.ok) { t(`Export refused — ${gate.blocked.join('; ')}. See the render gate panel.`, 'warn'); return }
      downloadDataUrl(dataUrl, `${safeFileName(packPreset.name)}-pack-${Math.round(freeCam.yaw)}deg.png`)
      recordExport('png', `${packPreset.name} pack · yaw ${Math.round(freeCam.yaw)}°`, '3D pack view')
      t('3D pack frame exported from the local canvas. It is a rendered 3D view, not a photograph.', 'info')
    } catch (e) {
      t(`Export failed: ${String(e && e.message || e)}`, 'warn')
    }
  }, [packPreset.name, freeCam.yaw, recordExport, t, runRenderGate])

  const exportMockup = useCallback(async (surfaceId) => {
    const art = mockArtId ? images.get(mockArtId) : null
    if (!art) { t('Attach artwork to the mockup before exporting.', 'warn'); return }
    try {
      const dataUrl = mockupToDataUrl(surfaceId, art, 1024, mockBlend)
      const gate = await runRenderGate('mockup', 1024, 1024, dataUrl)
      if (!gate.ok) { t(`Export refused — ${gate.blocked.join('; ')}. See the render gate panel.`, 'warn'); return }
      const s = MOCKUP_SURFACES.find(x => x.id === surfaceId)
      downloadDataUrl(dataUrl, `${safeFileName(s?.name || surfaceId)}-mockup.png`)
      recordExport('png', `${s?.name || surfaceId} mockup · 1024²`, 'Mockup placement')
      t('Mockup exported as a PNG from the local vector render.', 'info')
    } catch (e) {
      t(`Export failed: ${String(e && e.message || e)}`, 'warn')
    }
  }, [mockArtId, images, mockBlend, recordExport, t, runRenderGate])

  // ── Derived ──
  const blockedCount = requests.filter(r => r.state === 'Blocked — provider required').length
  const selectedLayer = sceneDoc.layers.find(l => l.id === selectedLayerId) || null
  const sceneReady = !!artId
  const artAssets = useMemo(() => store.assets.filter(a => a.role !== 'render'), [store.assets])
  const renderAssets = useMemo(() => store.assets.filter(a => a.role === 'render'), [store.assets])

  // ── Artwork picker (shared by scene / 3D / mockup) ──
  const ArtworkPicker = ({ value, onChange, label = 'Product artwork' }) => (
    <Section title={label} hint="Your own images only. Nothing is fetched." right={<span className="pill pill-muted">{artAssets.length}</span>}>
      <div className="sp-asset-grid">
        {artAssets.slice(0, 12).map(a => (
          <AssetThumb key={a.id} asset={a} height={54} selected={value === a.id}
            onClick={() => onChange(value === a.id ? '' : a.id)}
            actions={<button className="btn btn-sm btn-ghost" title="Remove from store"
              onClick={(e) => { e.stopPropagation(); store.remove(a.id) }}>×</button>} />
        ))}
        {!artAssets.length && <ThumbPlaceholder height={54} label="no artwork uploaded yet" />}
      </div>
      <label className="sp-dropzone">
        <Icon name="upload" size={14} /> Upload product images
        <input type="file" accept="image/*" multiple style={{ display: 'none' }}
          onChange={async (e) => {
            const added = await store.add(e.target.files, { role: 'reference', tags: ['product'] })
            if (added.length) { onChange(added[0].id); t(`${added.length} image${added.length > 1 ? 's' : ''} added to the local asset store.`, 'info') }
            e.target.value = ''
          }} />
      </label>
      {store.error && <div className="alert alert-warn" style={{ margin: 0 }}><div className="alert-text">{store.error}</div></div>}
      {!store.persistent && (
        <div className="alert" style={{ margin: 0 }}>
          <div className="alert-text">Browser storage is unavailable — uploaded images live for this session only and will not survive a reload.</div>
        </div>
      )}
    </Section>
  )

  return (
    <PageLayout
      title="Product Designer"
      subtitle="Product scenes, a real 3D packaging view, mockups, and a provider-gated generation queue — all rendered locally from your own artwork."
      actions={<>
        <ModeToggle mode={mode} onChange={setMode} />
        <button className="btn btn-sm btn-ghost" onClick={() => go('brand')}>Brand kit</button>
        <button className="btn btn-sm btn-primary" onClick={() => (tool === 'scene' ? exportScene() : tool === 'pack' ? exportPackFrame() : go('gen'))}>
          <Icon name="download" size={13} /> Export
        </button>
      </>}
    >
      <DataNotice tone="info" title="Local rendering, honest boundaries">
        Scenes, pack views and mockups are real renders produced in this browser from your uploaded artwork and the built-in
        scene recipes. Nothing here contacts an image or video model — the Generate tab records requests and lands them in
        &ldquo;Blocked — provider required&rdquo; until a local engine is armed. The 3D view is real geometry, not a photograph.
      </DataNotice>

      {/* ── Render export gate (Phase 7 item 4) ─────────────────────────── */}
      <div className="card" style={{ padding: 14 }} data-testid="render3d-gate">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 13 }}>Render export gate</strong>
          <span className="pill pill-muted">a render is not a photograph</span>
          <div className="field-group" style={{ minWidth: 230 }}>
            <label className="label">Export purpose</label>
            <select className="field" value={renderMeta.purpose} data-testid="render-purpose"
              onChange={e => setRenderMeta(m => ({ ...m, purpose: e.target.value }))}>
              {RENDER_PURPOSES.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <div className="field-group" style={{ minWidth: 230 }}>
            <label className="label">People in this render</label>
            <select className="field" value={renderMeta.peopleClass} data-testid="render-people-class"
              onChange={e => setRenderMeta(m => ({ ...m, peopleClass: e.target.value }))}>
              <option value="">Unanswered (export is refused)</option>
              <option value="no-people">No people</option>
              <option value="ai-photoreal">Photorealistic AI-generated person</option>
              <option value="ai-nonphotoreal">Non-photorealistic AI person</option>
              <option value="real-people">Real people</option>
            </select>
          </div>
          {renderMeta.peopleClass === 'ai-photoreal' && (
            <label className="inline-flex" style={{ gap: 6, fontSize: 12, alignItems: 'center' }}>
              <input type="checkbox" checked={renderMeta.syntheticPerformerTag} data-testid="render-marker"
                onChange={e => setRenderMeta(m => ({ ...m, syntheticPerformerTag: e.target.checked }))} />
              Disclosure marker applied (contains-synthetic-performer)
            </label>
          )}
          {renderMeta.fidelityMode !== 'locked' ? (
            <button className="btn btn-sm btn-ghost" data-testid="render-lock-reference" onClick={lockRenderReference}>
              <Icon name="target" size={13} /> Lock reference photo
            </button>
          ) : (
            <>
              <button className="btn btn-sm btn-ghost" data-testid="render-unlock-reference" onClick={unlockRenderReference}>Unlock reference</button>
              <button className="btn btn-sm btn-ghost" data-testid="render-sign-compare" onClick={signRenderCompare}>Compare &amp; sign off</button>
            </>
          )}
        </div>
        <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
          {(RENDER_PURPOSES.find(p => p.id === renderMeta.purpose) || {}).note}
          {renderMeta.fidelityMode === 'locked' && (
            <span> · Reference locked: exports diff the render against the photograph{compareState.satisfied ? ' and the comparison is signed off.' : ' and require a compare sign-off.'}</span>
          )}
        </div>
        {gateResult && (
          <div style={{ marginTop: 8, fontSize: 12 }} data-testid="render-gate-result">
            <span className={`pill ${gateResult.ok ? 'pill-ok' : 'pill-error'}`}>{gateResult.ok ? 'GATE OPEN' : 'GATE BLOCKED'}</span>
            <span className="text-low" style={{ marginLeft: 8 }}>{gateResult.summary}</span>
            {!gateResult.ok && (
              <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>Blocked by: {gateResult.blocked.join('; ')}.</div>
            )}
          </div>
        )}
      </div>

      <MetricTiles columns={4} metrics={[
        { label: 'Artwork in store', value: artAssets.length, sub: `${fmtBytes(store.totalBytes)} local` },
        { label: 'Saved renders', value: renderAssets.length, sub: 'persisted in this browser' },
        { label: 'Scene ready', value: sceneReady ? 'Yes' : 'No', tone: sceneReady ? 'ok' : 'warn', sub: sceneReady ? 'artwork attached' : 'attach artwork' },
        { label: 'Blocked requests', value: blockedCount, sub: requests.length ? 'no engine connected' : 'queue empty' },
      ]} />

      <div className="sp-room wide-inspector">
        <ToolRail tools={TOOLS} active={tool} onSelect={go} />

        <div className="stack" style={{ gap: 14 }}>
          <RoomTabs tabs={TOOLS.map(x => ({ id: x.id, label: x.label }))} base="/product-designer" />

          {tool === 'scene' && (
            <div className="subview">
              <div className="inline-flex" style={{ marginBottom: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm btn-ghost" data-testid="pd-undo" disabled={!canUndoScene} title="Undo (Ctrl+Z)" onClick={undoScene}>
                  <Icon name="chevronRight" size={13} /> Undo
                </button>
                <button className="btn btn-sm btn-ghost" data-testid="pd-redo" disabled={!canRedoScene} title="Redo (Ctrl+Shift+Z)" onClick={redoScene}>
                  <Icon name="chevronRight" size={13} /> Redo
                </button>
                <span className="text-low" style={{ fontSize: 11, alignSelf: 'center' }}>
                  Scene edits are undoable; reordering happens in the Layers list.
                </span>
              </div>
              <Stage
                doc={sceneDoc}
                assets={images}
                zoom={1}
                selectedId={selectedLayerId}
                onSelectLayer={setSelectedLayerId}
                onChangeLayer={patchSceneLayer}
                advanced={mode === 'advanced'}
                grid={mode === 'advanced' ? { cols: 3, safe: 0.06 } : null}
                badge={<span className="pill pill-muted">{scene.name}</span>}
                footer={<>
                  <span>{sceneFormat.label} · {sceneFormat.w}×{sceneFormat.h}px</span>
                  <span>·</span>
                  <span>yaw {Math.round(cam.yaw)}° pitch {Math.round(cam.pitch)}°</span>
                  <span>·</span>
                  <span>Drag the product on the canvas to reposition it</span>
                </>}
                emptyHint="No scene document open."
                minHeight={280} maxHeight={520}
              />
              {!sceneReady && (
                <div className="alert alert-warn" style={{ marginTop: 12 }}>
                  <div className="alert-title">No product artwork attached</div>
                  <div className="alert-text">Upload a product image in the inspector. Until then the scene renders an honest
                    placeholder frame — it never substitutes stock imagery.</div>
                </div>
              )}
            </div>
          )}

          {tool === 'pack' && (
            <div className="subview">
              <div ref={packWrapRef} className="sp3d-pane" style={{ minHeight: 460 }}>
                <canvas ref={packCanvasRef} className="sp3d-canvas" data-testid="pack-canvas"
                  style={{ width: packSize.w, height: packSize.h }} />
                <div className="sp3d-hud">
                  <span className="pill pill-muted">{describeAngle(freeCam.yaw, freeCam.pitch)}</span>
                  <span className="pill pill-muted">{lighting.name}</span>
                  <span className="pill pill-muted">{packPreset.name}</span>
                </div>
              </div>
              <div className="sp3d-facebar">
                {FACE_KEYS.map(k => (
                  <button key={k} className={`sp3d-face-btn ${activeFace === k ? 'has-art' : ''}`}
                    onClick={() => setActiveFace(faces[k].assetId ? k : k)}
                    title={`${FACE_LABEL[k]} face${faces[k].assetId ? ' — artwork mapped' : ' — solid colour'}`}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: faces[k].fill, display: 'inline-block' }} />
                    {FACE_LABEL[k]}
                  </button>
                ))}
              </div>
              <div className="inline-flex" style={{ marginTop: 10 }}>
                <button className="btn btn-sm" onClick={() => setFreeCam({ yaw: 0, pitch: 0, roll: 0 })}><Icon name="rotate" size={13} /> Reset angle</button>
                <button className="btn btn-sm btn-ghost" onClick={() => setSpin(s => !s)}>
                  <Icon name={spin ? 'x' : 'rotate'} size={13} /> {spin ? 'Stop turntable' : 'Spin turntable'}
                </button>
                <button className="btn btn-sm btn-ghost" onClick={exportPackFrame}><Icon name="download" size={13} /> Export frame</button>
              </div>
            </div>
          )}

          {tool === 'mock' && (
            <div className="subview">
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>{mockSurface.name}</h3>
                  <span className="pill pill-muted">{mockSurface.note}</span>
                </div>
                <div className="sp-mock-grid">
                  <div className="sp-mock">
                    <div className="sp-mock-body">
                      <canvas ref={mockCanvasRef} className="sp-mock-canvas" />
                    </div>
                    <div className="sp-mock-foot">
                      <button className="btn btn-sm btn-primary" onClick={() => exportMockup(mockSurfaceId)}>
                        <Icon name="download" size={13} /> Export 1024²
                      </button>
                      <span className="pill pill-muted">{mockBlend} blend</span>
                    </div>
                  </div>
                  <div>
                    <div className="card-head"><h3 className="card-title" style={{ fontSize: 14 }}>Surfaces</h3></div>
                    <div className="sp-mock-grid">
                      {MOCKUP_SURFACES.map(s => (
                        <button key={s.id} className={`sp-format ${mockSurfaceId === s.id ? 'active' : ''}`}
                          onClick={() => setMockSurfaceId(s.id)} title={s.note}>
                          <span className="sp-format-label">{s.name}</span>
                        </button>
                      ))}
                    </div>
                    {!mockArtId && (
                      <div className="alert alert-warn" style={{ marginTop: 12, marginBottom: 0 }}>
                        <div className="alert-text">Attach artwork in the inspector. Empty surfaces render an honest
                          &ldquo;NO ARTWORK&rdquo; frame instead of a fake preview.</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {tool === 'gen' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <ProviderBoundary kind={genPurposeObj.family === 'Video' ? 'video' : 'image'} />
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Generation request</h3>
                  <button className="btn btn-sm btn-ghost" onClick={checkEngine} disabled={engineChecking}>
                    <Icon name="refresh" size={13} /> {engineChecking ? 'Checking…' : 'Check engine'}
                  </button>
                </div>
                {engineStatus && (
                  <div className={`alert ${engineStatus.ok ? '' : 'alert-warn'}`} style={{ marginBottom: 12 }}>
                    <div className="alert-title">
                      <span className={`pill ${engineStatus.ok ? 'pill-forest' : 'pill-unknown'}`}>
                        {engineStatus.ok ? 'ARMED' : 'NOT ARMED'}
                      </span> Media engine status
                    </div>
                    <div className="alert-text">
                      {engineStatus.ok
                        ? 'The engine reports it is armed. Rendering is still a separate, named operator action — this room does not auto-generate.'
                        : `Not armed${engineStatus.reason ? ` (${engineStatus.reason})` : ''}. Nothing will generate from this room.`}
                    </div>
                  </div>
                )}
                <div className="field-group">
                  <span className="label">Purpose</span>
                  <SegmentedControl value={genPurpose} onChange={setGenPurpose}
                    options={GEN_PURPOSES.map(p => ({ value: p.id, label: p.label, note: p.note }))} />
                </div>
                <div className="field-group">
                  <span className="label">Request brief</span>
                  <TextInput rows={4} value={genPrompt} onChange={setGenPrompt}
                    placeholder="Describe the product, the scene, the lighting, the mood, and what must be legible. This text is yours." />
                  <span className="sp-field-hint">{genPurposeObj.note}</span>
                </div>
                <div className="grid-3">
                  <div className="field-group">
                    <span className="label">Tier</span>
                    <Select value={genTier} onChange={setGenTier}
                      options={GEN_TIERS.map(x => ({ value: x.id, label: `${x.label} — ${x.note}` }))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Output format</span>
                    <Select value={genFormatId} onChange={setGenFormatId}
                      options={ALL_FORMATS.map(f => ({ value: f.id, label: `${f.label} (${f.w}×${f.h})` }))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Copies</span>
                    <NumberInput value={genCount} onChange={setGenCount} min={1} max={8} />
                  </div>
                </div>
                <div className="field-group">
                  <span className="label">Reference artwork</span>
                  <ChipRow options={artAssets.slice(0, 10).map(a => ({ value: a.id, label: a.name }))}
                    value={genRefIds} onToggle={(v) => setGenRefIds(prev => prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v])} />
                </div>
                <div className="inline-flex">
                  <button className="btn btn-sm btn-primary" onClick={submitGen}><Icon name="plus" size={13} /> Record request</button>
                  <span className="pill pill-warn">records a local request · renders nothing</span>
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Request queue</h3>
                  <span className="pill pill-muted">{requests.length} local records</span>
                </div>
                <DataTable columns={[
                  { key: 'id', label: 'Request' },
                  { key: 'purpose', label: 'Purpose' },
                  { key: 'brief', label: 'Brief', render: (v, r) => <span title={r.prompt}>{r.prompt.length > 44 ? `${r.prompt.slice(0, 44)}…` : r.prompt}</span> },
                  { key: 'tier', label: 'Tier' },
                  { key: 'format', label: 'Format' },
                  { key: 'state', label: 'State', render: (v) => <span className="pill pill-unknown">{v}</span> },
                  { key: 'at', label: 'Recorded', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                  { key: 'act', label: '', render: (v, r) => <button className="btn btn-sm btn-ghost" onClick={() => dropRequest(r.id)}>Remove</button> },
                ]} rows={requests.map(r => ({ ...r, purpose: GEN_PURPOSES.find(p => p.id === r.purpose)?.label || r.purpose, tier: GEN_TIERS.find(x => x.id === r.tier)?.label || r.tier, at: r.createdAt }))}
                  emptyText="No requests recorded yet." />
              </div>
            </div>
          )}

          {tool === 'brand' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Brand kits</h3>
                  <span className="pill pill-muted">local · operator-owned</span>
                </div>
                <div className="sp-tpl-grid">
                  {kits.map(k => (
                    <button key={k.id} className={`sp-tpl ${activeKitId === k.id ? 'active' : ''}`} onClick={() => setActiveKitId(k.id)}>
                      <div className="sp-scene-swatch" style={{ background: `linear-gradient(135deg, ${k.palette.join(', ')})` }} />
                      <div className="sp-tpl-body">
                        <div className="sp-tpl-name">{k.name}</div>
                        <div className="sp-tpl-note">{k.note}</div>
                      </div>
                    </button>
                  ))}
                  <button className="sp-tpl" onClick={() => {
                    const id = uid('kit')
                    setKits(prev => [{ id, name: 'New kit', note: 'Edit the palette and type below.', palette: ['#f5f0e8', '#1d4a1d', '#c4941a'], ink: '#1a1a1a', paper: '#f5f0e8', accent: '#c4941a', headingFont: 'Libre Baskerville', bodyFont: 'DM Sans', voice: '' }, ...prev])
                    setActiveKitId(id)
                    t('New brand kit created locally.', 'info')
                  }}>
                    <div className="sp-tpl-body"><div className="sp-tpl-name">+ New kit</div></div>
                  </button>
                </div>
              </div>

              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Active kit — {kit.name}</h3></div>
                <div className="grid-2">
                  <div className="field-group">
                    <span className="label">Kit name</span>
                    <TextInput value={kit.name} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, name: v } : k))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Voice</span>
                    <TextInput value={kit.voice || ''} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, voice: v } : k))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Ink</span>
                    <ColorInput value={kit.ink} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, ink: v } : k))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Accent</span>
                    <ColorInput value={kit.accent} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, accent: v } : k))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Heading font</span>
                    <TextInput value={kit.headingFont} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, headingFont: v } : k))} />
                  </div>
                  <div className="field-group">
                    <span className="label">Body font</span>
                    <TextInput value={kit.bodyFont} onChange={(v) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, bodyFont: v } : k))} />
                  </div>
                </div>
                <div className="field-group" style={{ marginTop: 12 }}>
                  <span className="label">Palette</span>
                  <div className="inline-flex">
                    {kit.palette.map((c, i) => (
                      <input aria-label={`Palette colour ${i + 1}`} key={i} type="color" value={/^#[0-9a-f]{6}$/i.test(c) ? c : '#000000'}
                        onChange={(e) => setKits(prev => prev.map(k => k.id === kit.id ? { ...k, palette: k.palette.map((p, j) => (j === i ? e.target.value : p)) } : k))}
                        style={{ width: 34, height: 34, border: '1px solid var(--divider-mid)', borderRadius: 6, background: 'none', padding: 0, cursor: 'pointer' }} />
                    ))}
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Scene recipes</h3>
                  <span className="pill pill-muted">{SCENES.length} built in</span>
                </div>
                <div className="sp-scene-grid">
                  {SCENES.map(s => (
                    <button key={s.id} className={`sp-scene ${sceneId === s.id ? 'active' : ''}`} onClick={() => { setSceneId(s.id); go('scene') }}>
                      <div className="sp-scene-swatch" style={{ background: `linear-gradient(180deg, ${s.bg[0]}, ${s.bg[1]})` }} />
                      <div className="sp-scene-body">
                        <div className="sp-scene-name">{s.name}</div>
                        <div className="sp-scene-note">{s.note}</div>
                        <div className="text-mono" style={{ fontSize: 9, marginTop: 4 }}>
                          key {s.key.intensity} · ambient {s.ambient} · {s.backdrop}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tool === 'lib' && (
            <div className="subview stack" style={{ gap: 14 }}>
              <div className="card">
                <div className="card-head">
                  <h3 className="card-title" style={{ fontSize: 15 }}>Saved renders</h3>
                  <span className="pill pill-muted">{renderAssets.length} in store</span>
                </div>
                <div className="sp-asset-grid">
                  {renderAssets.map(a => (
                    <AssetThumb key={a.id} asset={a} height={72}
                      actions={<button className="btn btn-sm btn-ghost" title="Remove"
                        onClick={() => store.remove(a.id)}>×</button>} />
                  ))}
                  {!renderAssets.length && <ThumbPlaceholder height={72} label="no renders saved yet" />}
                </div>
              </div>
              <div className="card">
                <div className="card-head"><h3 className="card-title" style={{ fontSize: 15 }}>Export log</h3></div>
                <DataTable columns={[
                  { key: 'name', label: 'Export' },
                  { key: 'kind', label: 'Type' },
                  { key: 'note', label: 'Source' },
                  { key: 'at', label: 'When', render: (v) => <span className="text-low">{fmtTime(v)}</span> },
                ]} rows={exports} emptyText="Nothing exported from this browser yet." />
              </div>
            </div>
          )}
        </div>

        {/* ── Inspector ── */}
        <div className="sp-inspector">
          <div className="sp-inspector-head">
            <span className="sp-inspector-title">{TOOLS.find(x => x.id === tool)?.label}</span>
            <span className="pill pill-muted">{mode === 'simple' ? 'Simple' : 'Advanced'}</span>
          </div>
          <div className="sp-inspector-body">

            {tool === 'scene' && (<>
              <Section title="Scene" hint="Built-in backdrop recipes.">
                <div className="sp-scene-grid">
                  {SCENES.map(s => (
                    <button key={s.id} className={`sp-scene ${sceneId === s.id ? 'active' : ''}`} onClick={() => setSceneId(s.id)} title={s.note}>
                      <div className="sp-scene-swatch" style={{ background: `linear-gradient(180deg, ${s.bg[0]}, ${s.bg[1]})`, height: 44 }} />
                      <div className="sp-scene-body"><div className="sp-scene-name">{s.name}</div></div>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Output format">
                <FormatGrid groups={FORMAT_GROUPS.filter(g => g.id !== 'video')} value={sceneFormatId} onChange={(f) => setSceneFormatId(f.id)} />
              </Section>

              <ArtworkPicker value={artId} onChange={setArtId} />

              {mode === 'simple' ? (
                <Section title="Composition" hint="Curated controls.">
                  <Field label="Headline" hint="Optional. Your own copy.">
                    <TextInput value={sceneCopy.headline} onChange={(v) => setSceneCopy(c => ({ ...c, headline: v }))} placeholder="One line, upper-case friendly" />
                  </Field>
                  <Field label="Sub-head">
                    <TextInput value={sceneCopy.subhead} onChange={(v) => setSceneCopy(c => ({ ...c, subhead: v }))} placeholder="One line of support copy" />
                  </Field>
                  <Field label="Camera angle" hint="2D tilt simulation — not a 3D render.">
                    <SegmentedControl value={String(Math.round(cam.pitch))} onChange={(v) => setCam({ yaw: v === '40' ? 12 : v === '-10' ? -12 : 0, pitch: Number(v) })}
                      options={[{ value: '-10', label: 'Low' }, { value: '6', label: 'Eye' }, { value: '40', label: 'High' }]} />
                  </Field>
                  <Field label="Product scale">
                    <Slider value={placement.w} min={0.2} max={0.9} step={0.02} suffix="%"
                      onChange={(v) => setPlacement(p => ({ ...p, w: v, h: Math.min(0.86, v * 1.34) }))} />
                  </Field>
                </Section>
              ) : (
                <Section title="Composition (advanced)">
                  <Field label="Headline">
                    <TextInput value={sceneCopy.headline} onChange={(v) => setSceneCopy(c => ({ ...c, headline: v }))} />
                  </Field>
                  <Field label="Sub-head">
                    <TextInput value={sceneCopy.subhead} onChange={(v) => setSceneCopy(c => ({ ...c, subhead: v }))} />
                  </Field>
                  <Field label="Yaw (°)">
                    <Slider value={cam.yaw} min={-45} max={45} step={1} suffix="°" onChange={(v) => setCam(c => ({ ...c, yaw: v }))} />
                  </Field>
                  <Field label="Pitch (°)">
                    <Slider value={cam.pitch} min={-15} max={70} step={1} suffix="°" onChange={(v) => setCam(c => ({ ...c, pitch: v }))} />
                  </Field>
                  <Field label="Product X">
                    <Slider value={placement.x} min={0} max={0.8} step={0.01} suffix="%" onChange={(v) => setPlacement(p => ({ ...p, x: v }))} />
                  </Field>
                  <Field label="Product Y">
                    <Slider value={placement.y} min={0} max={0.6} step={0.01} suffix="%" onChange={(v) => setPlacement(p => ({ ...p, y: v }))} />
                  </Field>
                  <Field label="Product width">
                    <Slider value={placement.w} min={0.1} max={1} step={0.01} suffix="%" onChange={(v) => setPlacement(p => ({ ...p, w: v }))} />
                  </Field>
                  <Field label="Product height">
                    <Slider value={placement.h} min={0.1} max={1} step={0.01} suffix="%" onChange={(v) => setPlacement(p => ({ ...p, h: v }))} />
                  </Field>
                </Section>
              )}

              {mode === 'advanced' && (
                <Section title={`Layers (${sceneDoc.layers.length})`}>
                  <div className="sp-layers">
                    {[...sceneDoc.layers].reverse().map(l => (
                      <button key={l.id} className={`sp-layer ${selectedLayerId === l.id ? 'active' : ''}`} onClick={() => setSelectedLayerId(l.id)} data-testid="pd-layer-row">
                        <Icon name="layers" size={12} />
                        <span className="sp-layer-name">{l.name || l.role || l.kind}</span>
                        <span className="sp-layer-kind">{KIND_LABEL[l.kind]}</span>
                        <span className="sp-layer-btn" title="Move up" data-testid="pd-layer-up"
                          onClick={(e) => { e.stopPropagation(); setSceneDoc(d => reorderLayer(d, l.id, 1)) }}>
                          <Icon name="chevronDown" size={12} />
                        </span>
                        <span className="sp-layer-btn" title="Move down" data-testid="pd-layer-down"
                          onClick={(e) => { e.stopPropagation(); setSceneDoc(d => reorderLayer(d, l.id, -1)) }}>
                          <Icon name="chevronRight" size={12} />
                        </span>
                        <span className="sp-layer-btn" title="Remove layer" data-testid="pd-layer-remove"
                          onClick={(e) => { e.stopPropagation(); setSceneDoc(d => removeLayer(d, l.id)) }}>
                          <Icon name="trash" size={12} />
                        </span>
                      </button>
                    ))}
                  </div>
                  {selectedLayer && (
                    <Field label={`Selected — ${KIND_LABEL[selectedLayer.kind]}`}>
                      <div className="inline-flex">
                        <span className="pill pill-muted">drag on canvas to move</span>
                      </div>
                    </Field>
                  )}
                </Section>
              )}

              <Section title="Export">
                <div className="inline-flex">
                  <button className="btn btn-sm btn-primary" onClick={exportScene} disabled={!sceneReady}>
                    <Icon name="download" size={13} /> PNG {sceneFormat.w}×{sceneFormat.h}
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={saveSceneToLibrary} disabled={!sceneReady}>
                    <Icon name="save" size={13} /> Save to library
                  </button>
                </div>
                <span className="sp-field-hint">Exports the local render. No provider is contacted and no file leaves this browser.</span>
              </Section>
            </>)}

            {tool === 'pack' && (<>
              <Section title="Pack shape">
                <div className="sp-scene-grid">
                  {BOX_PRESETS.map(b => (
                    <button key={b.id} className={`sp-scene ${packPresetId === b.id ? 'active' : ''}`} onClick={() => setPackPresetId(b.id)} title={b.note}>
                      <div className="sp-scene-body">
                        <div className="sp-scene-name">{b.name}</div>
                        <div className="sp-scene-note">{b.note}</div>
                        <div className="text-mono" style={{ fontSize: 9, marginTop: 3 }}>{b.size.join(' × ')}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Lighting">
                <div className="inline-flex">
                  {LIGHTING.map(l => (
                    <button key={l.id} className={`filter-pill ${lightingId === l.id ? 'active' : ''}`} onClick={() => setLightingId(l.id)} title={l.note}>{l.name}</button>
                  ))}
                </div>
              </Section>

              <Section title="Camera" hint="Yaw / pitch are degrees.">
                <Field label="Yaw">
                  <Slider value={freeCam.yaw} min={-180} max={180} step={1} suffix="°" onChange={(v) => { setCamPresetId(''); setFreeCam(c => ({ ...c, yaw: v })) }} />
                </Field>
                <Field label="Pitch">
                  <Slider value={freeCam.pitch} min={-70} max={80} step={1} suffix="°" onChange={(v) => { setCamPresetId(''); setFreeCam(c => ({ ...c, pitch: v })) }} />
                </Field>
                {mode === 'advanced' && (
                  <Field label="Roll" hint="Use sparingly — a rolled product shot reads as an error.">
                    <Slider value={freeCam.roll} min={-25} max={25} step={1} suffix="°" onChange={(v) => setFreeCam(c => ({ ...c, roll: v }))} />
                  </Field>
                )}
                <div className="inline-flex">
                  {CAMERA_PRESETS.map(c => (
                    <button key={c.id} className={`filter-pill ${camPresetId === c.id ? 'active' : ''}`}
                      onClick={() => { setCamPresetId(c.id); setFreeCam({ yaw: c.yaw, pitch: c.pitch, roll: 0 }) }} title={c.note}>{c.name}</button>
                  ))}
                </div>
              </Section>

              <Section title={`${FACE_LABEL[activeFace]} face`}>
                <Field label="Base colour">
                  <ColorInput value={faces[activeFace].fill} onChange={(v) => setFaces(f => ({ ...f, [activeFace]: { ...f[activeFace], fill: v } }))} />
                </Field>
                <Field label="Artwork" hint="Your own image, mapped with an affine transform.">
                  <div className="sp-asset-grid">
                    {artAssets.slice(0, 10).map(a => (
                      <AssetThumb key={a.id} asset={a} height={44} selected={faces[activeFace].assetId === a.id}
                        onClick={() => setFaces(f => ({ ...f, [activeFace]: { ...f[activeFace], assetId: f[activeFace].assetId === a.id ? '' : a.id } }))} />
                    ))}
                  </div>
                  {!artAssets.length && <ThumbPlaceholder height={44} label="upload artwork to map a face" />}
                </Field>
                {faces[activeFace].assetId && <button className="btn btn-sm btn-ghost" onClick={() => setFaces(f => ({ ...f, [activeFace]: { ...f[activeFace], assetId: '' } }))}>Clear face art</button>}
              </Section>

              <Section title="Stage">
                <Field label="Backdrop">
                  <Select value={bgId} onChange={setBgId} options={SCENES.map(s => ({ value: s.id, label: s.name }))} />
                </Field>
                <Toggle checked={showFloor} onChange={setShowFloor} label="Contact shadow" />
                <Toggle checked={showGuide} onChange={setShowGuide} label="Turntable guide ring" />
                {mode === 'advanced' && (
                  <>
                    <Field label="Turntable speed">
                      <Slider value={spinSpeed} min={4} max={90} step={2} suffix="°/s" onChange={setSpinSpeed} />
                    </Field>
                    <Toggle checked={spin} onChange={setSpin} label="Spin continuously" />
                  </>
                )}
              </Section>

              <Section title="Export">
                <button className="btn btn-sm btn-primary" onClick={exportPackFrame}><Icon name="download" size={13} /> Export frame PNG</button>
                <span className="sp-field-hint">Renders the current view to a PNG at the pane resolution — a rendered 3D view, not a photograph.</span>
              </Section>
            </>)}

            {tool === 'mock' && (<>
              <ArtworkPicker value={mockArtId} onChange={setMockArtId} label="Artwork to place" />
              <Section title="Surface">
                <div className="inline-flex">
                  {MOCKUP_SURFACES.map(s => (
                    <button key={s.id} className={`filter-pill ${mockSurfaceId === s.id ? 'active' : ''}`} onClick={() => setMockSurfaceId(s.id)} title={s.note}>{s.name}</button>
                  ))}
                </div>
                <span className="sp-field-hint">{mockSurface.note}</span>
              </Section>
              {mode === 'advanced' && (
                <Section title="Blend">
                  <SegmentedControl value={mockBlend} onChange={setMockBlend}
                    options={[{ value: 'multiply', label: 'Multiply' }, { value: 'normal', label: 'Normal' }, { value: 'screen', label: 'Screen' }]} />
                  <span className="sp-field-hint">Multiply keeps the fabric texture showing through the print. Normal ignores it.</span>
                </Section>
              )}
              <Section title="Export">
                <button className="btn btn-sm btn-primary" onClick={() => exportMockup(mockSurfaceId)} disabled={!mockArtId}>
                  <Icon name="download" size={13} /> Export 1024² PNG
                </button>
              </Section>
            </>)}

            {tool === 'gen' && (<>
              <Section title="Tier" hint="A tier is a local cost model, not a price quote.">
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
              <Section title="Copy roles" hint="What each field is for.">
                <div className="stack" style={{ gap: 8 }}>
                  {COPY_ROLES.map(r => (
                    <div key={r.id}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--pine)' }}>{r.label}</div>
                      <div className="sp-field-hint">{r.note} · ≤ {r.maxWords} words</div>
                    </div>
                  ))}
                </div>
              </Section>
              <Section title="What happens next">
                <div className="alert" style={{ margin: 0 }}>
                  <div className="alert-text">
                    Requests are recorded locally with an honest blocked state. Connecting an engine is an operator action
                    outside this room; when one is armed the readiness probe above reports it, and rendering still requires a
                    fresh, named approval.
                  </div>
                </div>
              </Section>
            </>)}

            {tool === 'brand' && (<>
              <Section title="Active kit">
                <div className="sp-stats">
                  <Stat label="Kit" value={kit.name} />
                  <Stat label="Colours" value={kit.palette.length} />
                </div>
                <div className="inline-flex" style={{ marginTop: 10 }}>
                  {kit.palette.map((c, i) => (
                    <span key={i} title={c} style={{ width: 22, height: 22, borderRadius: 5, background: c, border: '1px solid var(--divider-mid)' }} />
                  ))}
                </div>
              </Section>
              <Section title="Scene parameters">
                <div className="stack" style={{ gap: 6 }}>
                  <div className="inline-flex"><span className="sp-field-label" style={{ width: 74 }}>Key</span><span className="text-mono">{scene.key.intensity} @ {scene.key.angle}°</span></div>
                  <div className="inline-flex"><span className="sp-field-label" style={{ width: 74 }}>Ambient</span><span className="text-mono">{scene.ambient}</span></div>
                  <div className="inline-flex"><span className="sp-field-label" style={{ width: 74 }}>Rim</span><span className="text-mono">{scene.rim.intensity} {scene.rim.color}</span></div>
                  <div className="inline-flex"><span className="sp-field-label" style={{ width: 74 }}>Backdrop</span><span className="text-mono">{scene.backdrop}</span></div>
                </div>
                <span className="sp-field-hint">These are the exact values the renderer uses. Nothing is estimated.</span>
              </Section>
              <Section title="Apply kit">
                <button className="btn btn-sm" onClick={() => { setSceneDoc(d => ({ ...d, kitId: kit.id })); go('scene') }}>
                  <Icon name="palette" size={13} /> Use in the scene designer
                </button>
              </Section>
            </>)}

            {tool === 'lib' && (<>
              <Section title="Store health">
                <div className="sp-stats">
                  <Stat label="Assets" value={store.assets.length} />
                  <Stat label="Size" value={fmtBytes(store.totalBytes)} />
                  <Stat label="Persistence" value={store.persistent ? 'Local' : 'Session'} tone={store.persistent ? 'forest' : 'ochre'} />
                </div>
              </Section>
              <Section title="Upload">
                <label className="sp-dropzone">
                  <Icon name="upload" size={14} /> Add images to the store
                  <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                    onChange={async (e) => { await store.add(e.target.files, { role: 'reference', tags: ['upload'] }); e.target.value = '' }} />
                </label>
              </Section>
            </>)}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}



