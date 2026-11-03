// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — SECTION: CANVAS WORKSPACE (U7)
//
// The Canva-like surface: a content-type selector, a tool rail, a neutral canvas
// zone, and a properties/layers panel. It is the studio's default section and it
// also runs inside the workbench tab, so it must never own the URL.
//
// Built on what the repo already ships:
//   • engine/doc.js      — the document model and the 2D renderer
//   • components/Stage   — hit-test, drag, selection, resize
//   • kit/Glass          — the tool rail and glass controls (U4 tokens)
//   • lib/studioCanvas   — content types, snapping, history, autosave, PDF
//
// HONESTY CONTRACT
//   • Nothing is seeded. A new design is one background layer.
//   • Sizes come from presets.js / specRegistry.js; the panel names the row.
//   • Autosave says what it saved, and names an image it had to leave out.
//   • Export reports the real byte count; a failed export says so and writes
//     nothing.
//   • Generation is not here. The library tool links to the sections that own
//     it instead of pretending this surface can render a product.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import Icon from '../../../components/Icon.jsx'
import { useToast } from '../../../components/ToastContext.jsx'
import Stage from '../../../studio/components/Stage.jsx'
import { ToolRail } from '../../../kit/Glass.jsx'
import { renderToCanvas } from '../../../studio/engine/doc.js'
import {
  updateLayer, removeLayer, duplicateLayer, reorderLayer,
} from '../../../studio/engine/doc.js'
import {
  CONTENT_TYPES, DEFAULT_CONTENT_TYPE, resolveContentType, contentTypeLabel,
  createDesign, addText, addImage, addShape, lastLayerId, resizeDesign, TEXT_PRESETS,
  initHistory, currentValue, pushHistory, undoHistory, redoHistory, canUndo, canRedo,
  serialiseDesign, parseDesign, assetsWithinBudget, exportFileName, base64ToBytes, pdfFromJpeg,
  switchPanel, panelCounts,
  DESIGN_STORE_KEY, MAX_ASSET_CHARS,
} from '../../../lib/studioCanvas.js'
import { parseInstruction, applyInstruction, describeCanvas } from '../../../lib/canvasCommands.js'
import {
  PANELS, GUIDE_KINDS, panelSize, guidesForPanel, describeOverlay,
} from '../../../lib/dielineOverlay.js'
import { useWorkspaceOptional } from '../../../shell/WorkspaceTabs.jsx'

const ZOOM_MIN = 0.2
const ZOOM_MAX = 4
const AUTOSAVE_MS = 400

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

function readStored() {
  try { return parseDesign(localStorage.getItem(DESIGN_STORE_KEY)) } catch { return null }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('the browser returned no image bytes'))), type, quality)
  })
}

function layerLabel(l) {
  if (!l) return ''
  if (l.kind === 'text') return `"${String(l.text || '').slice(0, 28)}"`
  if (l.kind === 'image') return l.name || 'Image'
  if (l.kind === 'bg') return 'Background'
  return l.name || l.kind
}

const TOOLS = [
  { id: 'text', label: 'Text', icon: <Icon name="type" size={15} /> },
  { id: 'image', label: 'Image', icon: <Icon name="image" size={15} /> },
  { id: 'shape', label: 'Shape', icon: <Icon name="shapes" size={15} /> },
  { id: 'assets', label: 'Assets', icon: <Icon name="stack" size={15} /> },
  { id: 'library', label: 'Library', icon: <Icon name="folder" size={15} /> },
]

const SHAPES = [
  { id: 'rect', label: 'Rectangle' },
  { id: 'ellipse', label: 'Ellipse' },
  { id: 'line', label: 'Line' },
]

export default function CanvasWorkspace({ onNavigateSection }) {
  const { toast } = useToast()
  // Present inside the workbench, null on /design-studio (no provider there).
  const workspace = useWorkspaceOptional()

  // One read of the autosave record decides the whole first render: document,
  // assets, content type and the message the status line shows.
  const [restored] = useState(readStored)
  const [history, setHistory] = useState(() => initHistory(
    restored?.doc || createDesign(DEFAULT_CONTENT_TYPE),
  ))
  const [draft, setDraft] = useState(null)
  const draftRef = useRef(null)
  // Only a real edit writes the autosave record. Restoring one must not
  // immediately re-save it, or the status line would say "Saved" a heartbeat
  // after saying "Restored" and the user could not tell which happened.
  const dirtyRef = useRef(false)
  const doc = draft || currentValue(history)

  const [assets, setAssets] = useState(() => restored?.assets || [])
  const [images, setImages] = useState(() => new Map())
  const [selected, setSelected] = useState('')
  const [tool, setTool] = useState('text')
  const [panel, setPanel] = useState('properties')
  const [panelOpen, setPanelOpen] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [guides, setGuides] = useState([])
  const [showGuides, setShowGuides] = useState(true)
  // U8: package panels + the dieline overlay. The overlay is DOM-only, so it can
  // never reach an exported PNG/PDF (the export path renders the document only).
  const [dieline, setDieline] = useState(null)
  const [showDieline, setShowDieline] = useState(true)
  const [guideKinds, setGuideKinds] = useState(GUIDE_KINDS.map((k) => k.id))
  const [loadingDieline, setLoadingDieline] = useState(false)
  const [exporting, setExporting] = useState('')
  const [lastExport, setLastExport] = useState(null)
  const [saveState, setSaveState] = useState(
    restored ? `Restored from ${new Date(restored.savedAt).toLocaleString()}` : 'Not saved yet',
  )

  const type = useMemo(() => resolveContentType(doc.contentType), [doc.contentType])
  const selectedLayer = doc.layers.find((l) => l.id === selected) || null

  // Always-current snapshot for the harness hook, so `view()` never reports a
  // document from a previous render. Declared after every useState: an
  // initialiser that reads `selected` before its own useState is a TDZ crash.
  const liveRef = useRef({ doc, selected, assets })
  liveRef.current = { doc, selected, assets }

  // ── U8: what Bojo is told about this canvas ──────────────────────────────
  // Published only when the description actually changes: the shell re-renders
  // on every publish, and a keystroke must not re-render the whole dock.
  const canvasView = useMemo(() => describeCanvas(doc, { selected, assets }), [doc, selected, assets])
  const viewKey = useMemo(() => (canvasView ? JSON.stringify(canvasView) : ''), [canvasView])
  const publishCanvas = workspace && workspace.publishCanvas

  useEffect(() => {
    if (typeof publishCanvas !== 'function') return
    publishCanvas(canvasView)
  }, [viewKey, publishCanvas])

  // ── assets → decoded images (the renderer wants elements, not URLs) ──────
  useEffect(() => {
    let cancelled = false
    if (!assets.length) {
      setImages(new Map())
      return undefined
    }
    const map = new Map()
    let pending = assets.length
    const settle = (asset, img) => {
      if (img && img.naturalWidth) map.set(asset.id, img)
      pending -= 1
      if (pending === 0 && !cancelled) setImages(new Map(map))
    }
    for (const asset of assets) {
      const img = new Image()
      img.onload = () => settle(asset, img)
      img.onerror = () => settle(asset, null)
      img.src = asset.dataUrl
    }
    return () => { cancelled = true }
  }, [assets])

  // ── autosave ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!dirtyRef.current) return undefined
    const t = setTimeout(() => {
      const { ok, oversized } = assetsWithinBudget(assets)
      try {
        localStorage.setItem(DESIGN_STORE_KEY, serialiseDesign(doc, assets))
        dirtyRef.current = false
        setSaveState(ok
          ? `Saved ${new Date().toLocaleTimeString()}`
          : `Saved without ${oversized.join(', ')} - too large to keep`)
      } catch {
        setSaveState('Autosave unavailable in this browser')
      }
    }, AUTOSAVE_MS)
    return () => clearTimeout(t)
  }, [doc, assets])

  // ── document mutation ────────────────────────────────────────────────────
  const applyDoc = useCallback((next) => {
    dirtyRef.current = true
    draftRef.current = null
    setDraft(null)
    setHistory((h) => pushHistory(h, next))
  }, [])

  // The safe form: the reducer reads the CURRENT document, so two events in one
  // frame cannot both be applied to the same stale snapshot.
  const mutate = useCallback((fn) => {
    dirtyRef.current = true
    draftRef.current = null
    setDraft(null)
    setHistory((h) => pushHistory(h, fn(currentValue(h))))
  }, [])

  const livePatch = useCallback((id, patch) => {
    dirtyRef.current = true
    const base = draftRef.current || currentValue(history)
    const next = {
      ...base,
      layers: base.layers.map((l) => (l.id === id ? { ...l, ...patch } : l)),
      updatedAt: new Date().toISOString(),
    }
    draftRef.current = next
    setDraft(next)
  }, [history])

  const commitLayer = useCallback(() => {
    const next = draftRef.current
    if (!next) return
    dirtyRef.current = true
    draftRef.current = null
    setDraft(null)
    setHistory((h) => pushHistory(h, next))
  }, [])

  const patchLayer = useCallback((id, patch) => {
    // Functional update: a fast typist (or a range slider) can fire twice before
    // React re-renders, and a closure over `history` would then drop a change.
    mutate((d) => updateLayer(d, id, patch))
  }, [mutate])

  const undo = useCallback(() => {
    dirtyRef.current = true
    draftRef.current = null
    setDraft(null)
    setHistory(undoHistory)
  }, [])

  const redo = useCallback(() => {
    dirtyRef.current = true
    draftRef.current = null
    setDraft(null)
    setHistory(redoHistory)
  }, [])

  // ── U8: one instruction, one bounded edit ────────────────────────────────
  // This is the only entry point a chat turn may use. It parses, applies and
  // reports; a sentence it does not understand changes nothing.
  const instruct = useCallback((text) => {
    const instruction = parseInstruction(text)
    if (!instruction) {
      return {
        ok: false,
        recognised: false,
        error: 'I did not understand that as a canvas instruction. Nothing was changed.',
      }
    }
    const result = applyInstruction(doc, instruction, { selected, assets })
    if (!result.ok) return { ok: false, recognised: true, error: result.error }
    if (result.doc !== doc) applyDoc(result.doc)
    if (result.layerId) setSelected(result.layerId)
    return { ok: true, recognised: true, summary: result.summary, layerId: result.layerId || '' }
  }, [doc, selected, assets, applyDoc])

  const instructRef = useRef(instruct)
  instructRef.current = instruct
  const registerCommand = workspace && workspace.registerCanvasCommand

  useEffect(() => {
    if (typeof registerCommand !== 'function') return undefined
    registerCommand((text) => instructRef.current(text))
    return () => registerCommand(null)
  }, [registerCommand])

  // Opt-in harness hook, same contract as ?engine=1 in DesignStudio: dev and
  // test builds only, folded out of production.
  useEffect(() => {
    if (!(import.meta.env.DEV || import.meta.env.VITE_TEST_HOOKS === '1')) return undefined
    window.__northstarCanvas = {
      instruct: (text) => instructRef.current(text),
      view: () => {
        const live = liveRef.current
        return describeCanvas(live.doc, { selected: live.selected, assets: live.assets })
      },
    }
    return () => { delete window.__northstarCanvas }
  }, [])

  // ── keyboard: undo / redo ────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const key = String(e.key || '').toLowerCase()
      if (key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((key === 'z' && e.shiftKey) || key === 'y') { e.preventDefault(); redo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  // ── add layers ───────────────────────────────────────────────────────────
  const doAddText = (preset = 'headline') => {
    const next = addText(currentValue(history), { text: preset === 'headline' ? 'Your headline' : 'Supporting copy', preset })
    applyDoc(next)
    setSelected(lastLayerId(next))
    setPanel('properties')
    setTool('text')
    toast('Text added as a vector layer. It is drawn by the canvas, never generated.', 'info')
  }

  const doAddShape = (shape) => {
    const next = addShape(currentValue(history), { shape })
    applyDoc(next)
    setSelected(lastLayerId(next))
    setPanel('properties')
  }

  const placeAsset = (asset) => {
    const next = addImage(currentValue(history), asset)
    applyDoc(next)
    setSelected(lastLayerId(next))
    setPanel('properties')
    toast(`${asset.name} placed on the canvas.`, 'info')
  }

  const onPickImage = (file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      const img = new Image()
      img.onload = () => {
        const asset = {
          id: `A-${Date.now().toString(36)}`,
          name: file.name || 'image',
          dataUrl,
          w: img.naturalWidth,
          h: img.naturalHeight,
        }
        dirtyRef.current = true
        setAssets((prev) => [...prev, asset])
        placeAsset(asset)
        if (dataUrl.length > MAX_ASSET_CHARS) {
          toast(`${asset.name} is too large for autosave (over 2.5 MB). It is placed, but it will not survive a reload.`, 'warn')
        }
      }
      img.onerror = () => toast('That file could not be read as an image. Nothing was placed.', 'warn')
      img.src = dataUrl
    }
    reader.onerror = () => toast('The browser could not read that file.', 'warn')
    reader.readAsDataURL(file)
  }

  const doResize = (id) => {
    if (id === doc.contentType) return
    const next = resizeDesign(currentValue(history), id)
    applyDoc(next)
    setPan({ x: 0, y: 0 })
    setZoom(1)
    toast(`${contentTypeLabel(id)} - ${next.w}x${next.h}. Layers keep their relative positions.`, 'info')
  }

  // ── U8: dieline overlay + package panels ─────────────────────────────────
  const loadDieline = async () => {
    setLoadingDieline(true)
    try {
      const send = () => fetch('/api/design-studio/print/dielines/geometry', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(import.meta.env.DEV ? { 'X-User-Id': 'demo-t2' } : {}) },
        body: JSON.stringify({
          template_id: 'doypack',
          params: { width_mm: 150, height_mm: 210, gusset_mm: 40 },
        }),
      })
      let res = await send()
      // Anonymous callers sit in a 30/min bucket; one bounded retry, then say so.
      if (res.status === 429) {
        const wait = Math.min(2000, Math.max(400, (Number(res.headers.get('Retry-After')) || 1) * 1000))
        await new Promise((resolve) => setTimeout(resolve, wait))
        res = await send()
      }
      if (!res.ok) {
        throw new Error(res.status === 429
          ? 'the API is rate-limiting this browser (30 calls a minute); wait a moment and try again'
          : `HTTP ${res.status}`)
      }
      const geometry = await res.json()
      if (!geometry || geometry.ok === false) throw new Error(geometry?.detail || 'the print lane refused')
      setDieline({ geometry })
      setShowDieline(true)
      const size = panelSize(geometry, currentValue(history).activePanel || 'front')
      if (size) applyDoc({ ...currentValue(history), w: size.w, h: size.h })
      toast(`Dieline attached: ${describeOverlay(geometry, 'front')}. Guides are never exported.`, 'info')
    } catch (e) {
      toast(`Could not load the dieline: ${e.message}. Nothing was attached.`, 'warn')
    } finally {
      setLoadingDieline(false)
    }
  }

  const switchToPanel = (panelId) => {
    const base = currentValue(history)
    let next = switchPanel(base, panelId)
    if (next === base) return
    if (dieline) {
      const size = panelSize(dieline.geometry, panelId)
      if (size) next = { ...next, w: size.w, h: size.h }
    }
    applyDoc(next)
    setSelected('')
  }

  const toggleGuideKind = (kind) => {
    setGuideKinds((prev) => (prev.includes(kind) ? prev.filter((k) => k !== kind) : [...prev, kind]))
  }

  const activePanel = doc.activePanel || 'front'
  const dielineGuides = dieline ? guidesForPanel(dieline.geometry, activePanel, { kinds: guideKinds }) : null
  const dielineOverlay = (dieline && showDieline && dielineGuides) ? (
    <svg className="cw-dieline" data-testid="cw-dieline" viewBox="0 0 1 1"
         preserveAspectRatio="none" aria-hidden="true">
      {dielineGuides.rects.map((r, i) => (
        <rect key={`r${i}`} x={r.x} y={r.y} width={r.w} height={r.h} fill="none"
              stroke={(GUIDE_KINDS.find((k) => k.id === r.kind) || GUIDE_KINDS[1]).colour}
              strokeWidth="1" vectorEffect="non-scaling-stroke" />
      ))}
      {dielineGuides.lines.map((l, i) => (
        <line key={`l${i}`} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
              stroke={(GUIDE_KINDS.find((k) => k.id === l.kind) || GUIDE_KINDS[2]).colour}
              strokeWidth="1" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  ) : null

  // ── export ───────────────────────────────────────────────────────────────
  const doExport = async (kind) => {
    if (exporting) return
    setExporting(kind)
    try {
      const canvas = renderToCanvas(doc, { assets: images, scale: 1 })
      if (kind === 'png') {
        const blob = await canvasToBlob(canvas, 'image/png')
        const name = exportFileName(doc, 'png')
        downloadBlob(blob, name)
        setLastExport({ kind: 'PNG', bytes: blob.size, name, at: new Date().toISOString() })
        toast(`Exported ${name} - ${blob.size.toLocaleString()} bytes.`, 'info')
      } else {
        const dataUrl = canvas.toDataURL('image/jpeg', 0.92)
        const jpeg = base64ToBytes(String(dataUrl).split(',')[1] || '')
        if (!jpeg.length) throw new Error('the browser produced no JPEG bytes')
        const pdf = pdfFromJpeg(jpeg, doc.w, doc.h)
        const name = exportFileName(doc, 'pdf')
        downloadBlob(new Blob([pdf], { type: 'application/pdf' }), name)
        setLastExport({ kind: 'PDF', bytes: pdf.length, name, at: new Date().toISOString() })
        toast(`Exported ${name} - ${pdf.length.toLocaleString()} bytes, 1 pt per pixel.`, 'info')
      }
    } catch (e) {
      setLastExport({ kind: kind.toUpperCase(), bytes: 0, name: '', error: String(e.message || e) })
      toast(`Export failed: ${e.message || e}. Nothing was written.`, 'warn')
    } finally {
      setExporting('')
    }
  }

  // ── pan / pinch on the neutral zone ──────────────────────────────────────
  const pointers = useRef(new Map())
  const pinch = useRef(null)

  const onZonePointerDown = (e) => {
    if (e.target !== e.currentTarget && !e.target.classList?.contains('cw-zone-inner')) return
    // Capture so a drag that leaves the zone still ends here: a pointer left in
    // the map would otherwise pan the canvas with no button held.
    e.currentTarget.setPointerCapture?.(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), zoom }
    }
  }

  const onZonePointerMove = (e) => {
    if (!pointers.current.has(e.pointerId)) return
    const prev = pointers.current.get(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()]
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      if (pinch.current.dist > 0) {
        setZoom(clamp(pinch.current.zoom * (dist / pinch.current.dist), ZOOM_MIN, ZOOM_MAX))
      }
      return
    }
    if (pointers.current.size === 1) {
      setPan((p) => ({ x: p.x + (e.clientX - prev.x), y: p.y + (e.clientY - prev.y) }))
    }
  }

  const onZonePointerUp = (e) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinch.current = null
  }

  return (
    <div
      className="cw-root"
      data-testid="canvas-workspace"
      data-content-type={doc.contentType}
      data-last-export={lastExport && lastExport.bytes ? `${lastExport.kind} ${lastExport.bytes}` : ''}
    >
      <div className="cw-topbar glass" data-testid="cw-topbar">
        <div className="cw-types" role="tablist" aria-label="Content type">
          {CONTENT_TYPES.map((t) => {
            const r = resolveContentType(t.id)
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={doc.contentType === t.id}
                className={`glass-tab ${doc.contentType === t.id ? 'is-active' : ''}`}
                data-testid={`cw-type-${t.id}`}
                title={`${t.note} - ${r.w}x${r.h} from ${r.registryId}`}
                onClick={() => doResize(t.id)}
              >
                {t.label}
              </button>
            )
          })}
        </div>
        <div className="cw-actions">
          {doc.contentType === 'package' && (
            <div className="cw-panels" role="tablist" aria-label="Package panel">
              {PANELS.map((p) => (
                <button key={p.id} type="button" role="tab" aria-selected={activePanel === p.id}
                        className={`glass-tab ${activePanel === p.id ? 'is-active' : ''}`}
                        data-testid={`cw-panel-${p.id}`} onClick={() => switchToPanel(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
          )}
          <button type="button" className={`glass-btn is-ghost cw-icon ${showDieline ? 'is-on' : ''}`}
                  data-testid="cw-dieline-toggle" aria-pressed={showDieline}
                  disabled={!dieline} onClick={() => setShowDieline((v) => !v)}
                  title={dieline ? 'Show the dieline guides (never exported)' : 'Load a dieline first'}
                  aria-label="Dieline guides">
            <Icon name="grid" size={14} />
          </button>
          <button type="button" className="glass-btn is-ghost cw-icon" data-testid="cw-undo"
                  onClick={undo} disabled={!canUndo(history)} title="Undo (Ctrl+Z)" aria-label="Undo">
            <Icon name="rotate" size={14} />
          </button>
          <button type="button" className="glass-btn is-ghost cw-icon" data-testid="cw-redo"
                  onClick={redo} disabled={!canRedo(history)} title="Redo (Ctrl+Shift+Z)" aria-label="Redo">
            <Icon name="rotate" size={14} />
          </button>
          <button type="button" className={`glass-btn is-ghost cw-icon ${showGuides ? 'is-on' : ''}`}
                  data-testid="cw-guides" aria-pressed={showGuides}
                  onClick={() => setShowGuides((v) => !v)} title="Show snapping guides" aria-label="Guides">
            <Icon name="grid" size={14} />
          </button>
          <button type="button" className="glass-btn is-ghost cw-icon cw-panel-toggle"
                  data-testid="cw-panel-toggle" aria-expanded={panelOpen}
                  onClick={() => setPanelOpen((v) => !v)} title="Properties and layers" aria-label="Properties">
            <Icon name="layers" size={14} />
          </button>
          <button type="button" className="glass-btn is-ghost" data-testid="cw-export-png"
                  onClick={() => doExport('png')} disabled={!!exporting} title="Export a PNG at the canvas size">
            <Icon name="download" size={13} /> {exporting === 'png' ? 'Exporting...' : 'PNG'}
          </button>
          <button type="button" className="glass-btn is-primary" data-testid="cw-export-pdf"
                  onClick={() => doExport('pdf')} disabled={!!exporting} title="Export a one-page PDF (1 pt per pixel)">
            <Icon name="file" size={13} /> {exporting === 'pdf' ? 'Exporting...' : 'PDF'}
          </button>
        </div>
      </div>

      <div className="cw-body">
        <aside className="cw-side glass" data-testid="cw-side">
          <ToolRail items={TOOLS} active={tool} onSelect={setTool} label="Canvas tools" />
          <div className="cw-tool-body">
            {tool === 'text' && (
              <div className="cw-tool" data-testid="cw-tool-text">
                <div className="cw-tool-title">Text</div>
                <button type="button" className="glass-btn is-ghost" data-testid="cw-add-text"
                        onClick={() => doAddText('headline')}>Add headline</button>
                <button type="button" className="glass-btn is-ghost" data-testid="cw-add-subhead"
                        onClick={() => doAddText('subhead')}>Add subhead</button>
                <button type="button" className="glass-btn is-ghost" data-testid="cw-add-body"
                        onClick={() => doAddText('body')}>Add body copy</button>
                <p className="cw-note">
                  Vector text, drawn by the canvas. Sizes are fractions of the canvas height
                  ({Math.round(TEXT_PRESETS.headline.size * 100)}% for a headline), so the same
                  document reads correctly at any raster size.
                </p>
              </div>
            )}
            {tool === 'image' && (
              <div className="cw-tool" data-testid="cw-tool-image">
                <div className="cw-tool-title">Image</div>
                <label className="cw-file">
                  <span>Upload an image</span>
                  <input type="file" accept="image/*" data-testid="cw-image-input"
                         onChange={(e) => onPickImage(e.target.files?.[0])} />
                </label>
                {assets.length === 0 && <p className="cw-note">No images yet. Uploaded pixels are your own; nothing here is generated.</p>}
                {assets.map((a) => (
                  <button key={a.id} type="button" className="cw-asset" data-testid="cw-asset"
                          onClick={() => placeAsset(a)} title={`Place ${a.name} on the canvas`}>
                    <img src={a.dataUrl} alt="" />
                    <span className="cw-asset-name">{a.name}</span>
                    <span className="cw-asset-dims">{a.w}x{a.h}</span>
                  </button>
                ))}
              </div>
            )}
            {tool === 'shape' && (
              <div className="cw-tool" data-testid="cw-tool-shape">
                <div className="cw-tool-title">Shape</div>
                {SHAPES.map((s) => (
                  <button key={s.id} type="button" className="glass-btn is-ghost"
                          data-testid={`cw-add-shape-${s.id}`} onClick={() => doAddShape(s.id)}>
                    Add {s.label.toLowerCase()}
                  </button>
                ))}
              </div>
            )}
            {tool === 'assets' && (
              <div className="cw-tool" data-testid="cw-tool-assets">
                <div className="cw-tool-title">Assets in this design</div>
                {assets.length === 0
                  ? <p className="cw-note">Nothing uploaded yet. The canvas autosaves each image it holds.</p>
                  : assets.map((a) => (
                    <div key={a.id} className="cw-asset is-static">
                      <img src={a.dataUrl} alt="" />
                      <span className="cw-asset-name">{a.name}</span>
                      <span className="cw-asset-dims">{a.w}x{a.h}</span>
                    </div>
                  ))}
              </div>
            )}
            {tool === 'library' && (
              <div className="cw-tool" data-testid="cw-tool-library">
                <div className="cw-tool-title">Library</div>
                <p className="cw-note">
                  This surface composes pixels it was given. Rendering, cutouts and print packs
                  live in the sections that already own them.
                </p>
                <button type="button" className="glass-btn is-ghost" data-testid="cw-open-dashboard"
                        onClick={() => onNavigateSection && onNavigateSection('deliverables')}>
                  <Icon name="folder" size={13} /> Asset dashboard
                </button>
                <button type="button" className="glass-btn is-ghost" data-testid="cw-open-dielines"
                        onClick={() => onNavigateSection && onNavigateSection('dielines')}>
                  <Icon name="grid" size={13} /> Dielines &amp; print
                </button>
              </div>
            )}
          </div>
        </aside>
        <div
          className="cw-zone glass-panel-canvas"
          data-testid="cw-canvas-zone"
          onPointerDown={onZonePointerDown}
          onPointerMove={onZonePointerMove}
          onPointerUp={onZonePointerUp}
          onPointerCancel={onZonePointerUp}
        >
          <div className="cw-zone-inner" style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}>
            <Stage
              doc={doc}
              assets={images}
              selectedId={selected}
              zoom={zoom}
              onZoomChange={setZoom}
              grid={showGuides ? { cols: 3, safe: 0.06 } : null}
              onSelectLayer={setSelected}
              onChangeLayer={livePatch}
              onCommitLayer={commitLayer}
              snap={showGuides}
              onGuides={setGuides}
              guides={showGuides ? guides : []}
              overlay={dielineOverlay}
              minHeight={260}
              maxHeight={640}
              footer={(
                <span className="cw-stage-foot">
                  {doc.layers.length} layer{doc.layers.length === 1 ? '' : 's'} · drag to move, snaps to the
                  centre and edges · {type.missing ? 'size unknown' : `${type.w}x${type.h} from ${type.registryId}`}
                </span>
              )}
            />
          </div>
        </div>

        <aside className={`cw-panel glass ${panelOpen ? 'is-open' : ''}`} data-testid="cw-panel">
          <div className="cw-panel-tabs" role="tablist" aria-label="Inspector">
            <button type="button" role="tab" aria-selected={panel === 'properties'}
                    className={`glass-tab ${panel === 'properties' ? 'is-active' : ''}`}
                    data-testid="cw-panel-properties" onClick={() => setPanel('properties')}>Properties</button>
            <button type="button" role="tab" aria-selected={panel === 'layers'}
                    className={`glass-tab ${panel === 'layers' ? 'is-active' : ''}`}
                    data-testid="cw-panel-layers" onClick={() => setPanel('layers')}>Layers</button>
          </div>

          {panel === 'properties' && (
            <div className="cw-panel-body" data-testid="cw-properties">
              <label className="cw-field">
                <span>Design name</span>
                <input type="text" className="glass-input" data-testid="cw-doc-name"
                       value={doc.name}
                       onChange={(e) => mutate((d) => ({ ...d, name: e.target.value }))} />
              </label>
              <div className="cw-field">
                <span>Canvas</span>
                <div className="cw-readonly" data-testid="cw-doc-size">
                  {doc.w}x{doc.h} · {doc.channel || 'no channel'} · {type.registrySource || 'registry'} {type.registryId}
                </div>
              </div>

              <div className="cw-field">
                <span>Dieline</span>
                <div className="cw-readonly" data-testid="cw-dieline-state">
                  {dieline ? describeOverlay(dieline.geometry, activePanel) : 'No dieline attached.'}
                </div>
                <div className="cw-dieline-actions">
                  <button type="button" className="glass-btn is-ghost" data-testid="cw-load-dieline"
                          onClick={loadDieline} disabled={loadingDieline}>
                    {loadingDieline ? 'Loading...' : dieline ? 'Reload the dieline' : 'Attach a doypack dieline'}
                  </button>
                  {dieline && GUIDE_KINDS.map((k) => (
                    <button key={k.id} type="button"
                            className={`cw-guide-chip ${guideKinds.includes(k.id) ? 'is-on' : ''}`}
                            data-testid={`cw-guide-${k.id}`} aria-pressed={guideKinds.includes(k.id)}
                            onClick={() => toggleGuideKind(k.id)} title={`${k.label} guides`}>
                      <span className="cw-guide-dot" style={{ background: k.colour }} /> {k.label}
                    </button>
                  ))}
                </div>
                <span className="cw-note">
                  Guides are drawn on the artboard only — they are never rasterised into the PNG or PDF.
                </span>
              </div>

              {!selectedLayer && (
                <p className="cw-note">Select a layer on the canvas or in the Layers tab to edit it.</p>
              )}

              {selectedLayer && (
                <div className="cw-selected" data-testid="cw-selected">
                  <div className="cw-selected-head">
                    <Icon name={selectedLayer.kind === 'text' ? 'type' : selectedLayer.kind === 'image' ? 'image' : 'shapes'} size={13} />
                    <span>{layerLabel(selectedLayer)}</span>
                  </div>

                  {selectedLayer.kind === 'text' && (
                    <>
                      <label className="cw-field">
                        <span>Text</span>
                        <input type="text" className="glass-input" data-testid="cw-text-input"
                               value={selectedLayer.text || ''}
                               onChange={(e) => patchLayer(selectedLayer.id, { text: e.target.value })} />
                      </label>
                      <label className="cw-field">
                        <span data-testid="cw-text-size">Size ({(selectedLayer.size * 100).toFixed(1)}% of height = {Math.round((selectedLayer.size || 0) * doc.h)} px)</span>
                        <input type="range" min="0.01" max="0.2" step="0.002"
                               value={selectedLayer.size || 0.03}
                               onChange={(e) => patchLayer(selectedLayer.id, { size: Number(e.target.value) })} />
                      </label>
                      <label className="cw-field">
                        <span>Colour</span>
                        <input type="color" value={selectedLayer.color || '#1a1a1a'}
                               onChange={(e) => patchLayer(selectedLayer.id, { color: e.target.value })} />
                      </label>
                    </>
                  )}

                  {selectedLayer.kind === 'image' && (
                    <label className="cw-field">
                      <span>Fit</span>
                      <select className="glass-input" value={selectedLayer.fit || 'contain'}
                              onChange={(e) => patchLayer(selectedLayer.id, { fit: e.target.value })}>
                        <option value="contain">Contain (no crop)</option>
                        <option value="cover">Cover (crops)</option>
                      </select>
                    </label>
                  )}

                  {selectedLayer.kind === 'shape' && (
                    <label className="cw-field">
                      <span>Fill</span>
                      <input type="color" value={selectedLayer.fill || '#1d4a1d'}
                             onChange={(e) => patchLayer(selectedLayer.id, { fill: e.target.value })} />
                    </label>
                  )}

                  <div className="cw-boxrow">
                    {['x', 'y', 'w', 'h'].map((k) => (
                      <label key={k} className="cw-field">
                        <span>{k.toUpperCase()}</span>
                        <input type="number" min="-0.5" max="1.5" step="0.01"
                               value={Number(selectedLayer[k] ?? 0).toFixed(2)}
                               onChange={(e) => patchLayer(selectedLayer.id, { [k]: Number(e.target.value) })} />
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {panel === 'layers' && (
            <div className="cw-panel-body" data-testid="cw-layers">
              {[...doc.layers].reverse().map((l, i) => (
                <div
                  key={l.id}
                  className={`cw-layer ${selected === l.id ? 'is-active' : ''}`}
                  data-testid="cw-layer"
                  data-kind={l.kind}
                  data-layer-id={l.id}
                  onClick={() => { setSelected(l.id); setPanel('properties') }}
                >
                  <button type="button" className="cw-mini" title={l.visible === false ? 'Show layer' : 'Hide layer'}
                          aria-label="Toggle visibility"
                          onClick={(e) => { e.stopPropagation(); patchLayer(l.id, { visible: l.visible === false }) }}>
                    <Icon name="eye" size={12} />
                  </button>
                  <span className="cw-layer-name">{layerLabel(l)}</span>
                  <button type="button" className="cw-mini" title="Move up" aria-label="Move up"
                          onClick={(e) => { e.stopPropagation(); mutate((d) => reorderLayer(d, l.id, -1)) }}>^</button>
                  <button type="button" className="cw-mini" title="Move down" aria-label="Move down"
                          onClick={(e) => { e.stopPropagation(); mutate((d) => reorderLayer(d, l.id, 1)) }}>v</button>
                  <button type="button" className="cw-mini" title="Duplicate" aria-label="Duplicate"
                          onClick={(e) => { e.stopPropagation(); mutate((d) => duplicateLayer(d, l.id)) }}><Icon name="copy" size={11} /></button>
                  <button type="button" className="cw-mini" title="Delete" aria-label="Delete"
                          onClick={(e) => {
                            e.stopPropagation()
                            mutate((d) => removeLayer(d, l.id))
                            if (selected === l.id) setSelected('')
                          }}><Icon name="trash" size={11} /></button>
                </div>
              ))}
              <p className="cw-note">
                {doc.layers.length} layer{doc.layers.length === 1 ? '' : 's'} · history {history.index + 1}/{history.stack.length}
              </p>
            </div>
          )}
        </aside>

      </div>

      <div className="cw-status" data-testid="cw-status">
        <span data-testid="cw-save-state">{saveState}</span>
        <span className="cw-status-sep">·</span>
        <span>{doc.layers.length} layer{doc.layers.length === 1 ? '' : 's'}</span>
        <span className="cw-status-sep">·</span>
        <span>{Math.round(zoom * 100)}%</span>
        {lastExport && (
          <>
            <span className="cw-status-sep">·</span>
            <span data-testid="cw-export-status">
              {lastExport.error
                ? `${lastExport.kind} export failed: ${lastExport.error}`
                : `${lastExport.kind} ${lastExport.bytes.toLocaleString()} bytes - ${lastExport.name}`}
            </span>
          </>
        )}
      </div>
    </div>
  )
}

