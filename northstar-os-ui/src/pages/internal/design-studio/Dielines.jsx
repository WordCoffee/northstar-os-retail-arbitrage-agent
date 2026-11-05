// ============================================================================
// DESIGN STUDIO - SECTION: DIELINES & PRINT
//
// RE build 2026-10-16: parametric dieline/label drafts rendered by the local
// print engine (/api/design-studio/print/*), plus the mockup scene/product
// planner (/api/design-studio/scenes, /api/design-studio/mockup/plan).
//
// HONESTY CONTRACT (this section):
//   - Outputs are DRAFT geometry. Confirm dimensions, flap depths and bleeds
//     with the manufacturer before production.
//   - Nothing generates here by itself: previews are free local renders, and a
//     queued generation only runs when the operator clicks it AND the local
//     engine (ComfyUI) is armed. Gate messages come straight from the API.
// ============================================================================

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useToast } from '../../../components/ToastContext.jsx'
import {
  GUIDE_KINDS, describeOverlay, guidesForPanel, panelIds, panelLabel, panelRect,
} from '../../../lib/dielineOverlay.js'

const API = '/api/design-studio'

// Guide colours, one per kind. They are deliberately loud: a guide that looks
// like artwork is a guide somebody ships by mistake.
const GUIDE_STYLE = {
  bleed: { stroke: '#c0392b', dash: '4 3', width: 0.6 },
  trim: { stroke: '#1f2a24', dash: '', width: 0.8 },
  fold: { stroke: '#2b6cb0', dash: '6 4', width: 0.6 },
  safe: { stroke: '#2f855a', dash: '3 3', width: 0.5 },
}

function viewBoxOf(svgText) {
  const match = /viewBox\s*=\s*"([^"]+)"/i.exec(svgText || '')
  if (!match) return null
  const parts = match[1].trim().split(/[\s,]+/).map(Number)
  if (parts.length !== 4 || parts.some(n => !Number.isFinite(n)) || parts[2] <= 0 || parts[3] <= 0) return null
  return parts
}

// The guides are DOM only. They are drawn over the preview in the dieline's own
// viewBox so they cannot disagree with it, and they are never part of the `svg`
// string that Download SVG / PDF hands out.
function GuideOverlay({ geometry, panelId, svgText }) {
  const viewBox = viewBoxOf(svgText)
  if (!geometry || !viewBox) return null
  const box = panelRect(geometry, panelId)
  if (!box) return null
  const [px, py, pw, ph] = box
  const { rects, lines } = guidesForPanel(geometry, panelId)
  const toX = (n) => px + n * pw
  const toY = (n) => py + n * ph
  return (
    <svg
      viewBox={viewBox.join(' ')}
      preserveAspectRatio="xMidYMid meet"
      data-testid="dieline-guides"
      aria-hidden="true"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
    >
      {rects.map((r, i) => {
        const style = GUIDE_STYLE[r.kind] || GUIDE_STYLE.trim
        return (
          <rect key={`r${i}`} x={toX(r.x)} y={toY(r.y)} width={r.w * pw} height={r.h * ph}
            fill="none" stroke={style.stroke} strokeWidth={style.width}
            strokeDasharray={style.dash || undefined} vectorEffect="non-scaling-stroke" />
        )
      })}
      {lines.map((l, i) => {
        const style = GUIDE_STYLE[l.kind] || GUIDE_STYLE.trim
        return (
          <line key={`l${i}`} x1={toX(l.x1)} y1={toY(l.y1)} x2={toX(l.x2)} y2={toY(l.y2)}
            stroke={style.stroke} strokeWidth={style.width}
            strokeDasharray={style.dash || undefined} vectorEffect="non-scaling-stroke" />
        )
      })}
    </svg>
  )
}


function errText(d, r) {
  if (d && typeof d.detail === 'string' && d.detail) return d.detail
  if (d && Array.isArray(d.detail) && d.detail.length && d.detail[0] && d.detail[0].msg) return d.detail[0].msg
  if (d && d.detail && typeof d.detail === 'object' && d.detail.message) return d.detail.message
  return `HTTP ${r.status}`
}

function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export default function Dielines() {
  const { toast } = useToast()
  const [templates, setTemplates] = useState([])
  const [templateId, setTemplateId] = useState('')
  const [params, setParams] = useState({})
  const [svg, setSvg] = useState('')
  const [meta, setMeta] = useState(null)
  // U8 overlay: the guide geometry for the CURRENT dieline, fetched from the
  // same builder the print lane uses, so a guide can never disagree with the art.
  const [geometry, setGeometry] = useState(null)
  const [showGuides, setShowGuides] = useState(true)
  const [guidePanel, setGuidePanel] = useState('front')
  const [busy, setBusy] = useState(false)
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [scenes, setScenes] = useState([])
  const [products, setProducts] = useState([])
  const [sceneId, setSceneId] = useState('')
  const [productId, setProductId] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')
  const [plan, setPlan] = useState(null)
  // Box library (2026-10-16): Boxes.py external generator.
  const [boxLib, setBoxLib] = useState(null)
  const [boxGen, setBoxGen] = useState('ClosedBox')
  const [boxParams, setBoxParams] = useState({ x: 100, y: 80, h: 60, thickness: 3 })
  const [boxSvg, setBoxSvg] = useState('')
  const [boxBusy, setBoxBusy] = useState(false)

  useEffect(() => {
    let gone = false
    ;(async () => {
      try {
        const r = await fetch(`${API}/print/box-library`, { credentials: 'include' })
        if (!r.ok) return
        const d = await r.json()
        if (!gone) setBoxLib(d)
      } catch { /* library is optional; the card says unavailable */ }
    })()
    return () => { gone = true }
  }, [])

  const generateBox = async () => {
    setBoxBusy(true)
    try {
      const r = await fetch(`${API}/print/box-generate`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ generator: boxGen, ...boxParams }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(errText(d, r))
      setBoxSvg(d.svg || '')
      toast(`Generated ${boxGen} locally (${Math.round((d.size_bytes || 0) / 1024)} KB SVG).`, 'success')
    } catch (e) {
      toast(`Box generation failed: ${e.message}`, 'error')
    } finally {
      setBoxBusy(false)
    }
  }

  const template = useMemo(() => templates.find(t => t.id === templateId), [templates, templateId])
  const hasPlanInput = !!(sceneId || productId || customPrompt.trim())

  useEffect(() => {
    let gone = false
    ;(async () => {
      try {
        const r = await fetch(`${API}/print/templates`, { credentials: 'include' })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const d = await r.json()
        if (gone) return
        const list = d.templates || []
        setTemplates(list)
        if (list.length) {
          setTemplateId(list[0].id)
          setParams({ ...(list[0].params || {}) })
        }
      } catch (e) {
        toast(`Dieline templates unavailable: ${e.message}`, 'error')
      }
      try {
        const r = await fetch(`${API}/projects`, { credentials: 'include' })
        if (r.ok && !gone) {
          const d = await r.json()
          setProjects(Array.isArray(d) ? d : (d.projects || []))
        }
      } catch { /* project list is optional */ }
      try {
        const r = await fetch(`${API}/scenes`, { credentials: 'include' })
        if (r.ok && !gone) {
          const d = await r.json()
          setScenes(d.scenes || [])
          setProducts(d.products || [])
        }
      } catch { /* scene catalog is optional */ }
    })()
    return () => { gone = true }
  }, [toast])

  const onPick = (id) => {
    setTemplateId(id)
    setSvg('')
    setMeta(null)
    setGeometry(null)
    const t = templates.find(x => x.id === id)
    setParams({ ...((t && t.params) || {}) })
  }

  const loadGeometry = useCallback(async (tid, prms) => {
    try {
      const r = await fetch(`${API}/print/dielines/geometry`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: tid, params: prms || {} }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const g = await r.json()
      setGeometry(g)
      const ids = panelIds(g)
      setGuidePanel(prev => (ids.includes(prev) ? prev : (ids[0] || 'front')))
    } catch (e) {
      // The overlay is an aid; the dieline is the deliverable. Losing the guides
      // must never lose the preview, so this degrades and says why.
      setGeometry(null)
      toast(`Guide overlay unavailable: ${e.message}`, 'error')
    }
  }, [toast])

  const render = useCallback(async (opts = {}) => {
    setBusy(true)
    const cleanParams = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined))
    try {
      const r = await fetch(`${API}/print/dielines`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: templateId,
          params: cleanParams,
          persist: !!opts.persist,
          include_svg: true,
          include_pdf: !!opts.pdf,
          project_id: opts.persist && projectId ? projectId : null,
        }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(errText(d, r))
      setSvg(d.svg || '')
      setMeta(d)
      // Guides come from the same builder as the art, so fetch them for the
      // exact template/params that were just rendered.
      loadGeometry(templateId, cleanParams)
      if (opts.persist) {
        const n = (d.assets || []).length
        toast(n ? `Saved ${n} dieline file${n === 1 ? '' : 's'} to the asset library.` : 'Saved.', 'success')
      }
      if (opts.pdf && d.pdf_base64) {
        const bytes = Uint8Array.from(atob(d.pdf_base64), c => c.charCodeAt(0))
        downloadBlob(new Blob([bytes], { type: 'application/pdf' }), `${d.title || 'dieline'}.pdf`)
      }
      return d
    } catch (e) {
      toast(`Dieline request failed: ${e.message}`, 'error')
      return null
    } finally {
      setBusy(false)
    }
  }, [templateId, params, projectId, toast, loadGeometry])

  const downloadSvg = () => {
    if (svg) downloadBlob(new Blob([svg], { type: 'image/svg+xml' }), `${(meta && meta.title) || 'dieline'}.svg`)
  }

  const planMockup = async (enqueue) => {
    setBusy(true)
    try {
      const r = await fetch(`${API}/mockup/plan`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_id: sceneId || null,
          product_id: productId || null,
          custom_prompt: customPrompt || null,
          enqueue,
        }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(errText(d, r))
      setPlan(d)
      if (enqueue && d.enqueued && d.enqueued.job) {
        toast(`Queued job ${d.enqueued.job.id} on the local engine.`, 'success')
      }
    } catch (e) {
      toast(`Mockup plan failed: ${e.message}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div data-testid="dielines-workspace" style={{ display: 'grid', gap: 16, marginTop: 16 }}>
      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontWeight: 600, color: 'var(--pine-deep)', marginBottom: 4 }}>Dieline builder</div>
        <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
          Parametric label/carton drafts from the local print engine: layered SVG
          (bleed/trim/fold/safe) plus a print PDF. Draft geometry only - confirm
          dimensions, flap depths and bleeds with the manufacturer before production.
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ fontSize: 12 }}>Template
            <select value={templateId} onChange={e => onPick(e.target.value)}
              style={{ display: 'block', marginTop: 4, minWidth: 230 }}>
              {templates.map(t => <option key={t.id} value={t.id}>{t.name} ({t.kind})</option>)}
            </select>
          </label>
          {(template ? template.editable : []).map(key => (
            <label key={key} style={{ fontSize: 12 }}>{key}
              <input type="number" step="0.5" value={params[key] === undefined ? '' : params[key]}
                onChange={e => setParams(p => ({ ...p, [key]: e.target.value === '' ? '' : Number(e.target.value) }))}
                style={{ display: 'block', marginTop: 4, width: 104 }} />
            </label>
          ))}
          <label style={{ fontSize: 12 }}>Save to project
            <select value={projectId} onChange={e => setProjectId(e.target.value)}
              style={{ display: 'block', marginTop: 4, minWidth: 190 }}>
              <option value="">(download only)</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
            </select>
          </label>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-sm btn-primary" disabled={busy || !templateId} onClick={() => render({})}>Preview</button>
          <button className="btn btn-sm" disabled={busy || !templateId} onClick={() => render({ pdf: true })}>Download PDF</button>
          <button className="btn btn-sm" disabled={busy || !svg} onClick={downloadSvg}>Download SVG</button>
          <button className="btn btn-sm" disabled={busy || !templateId} onClick={() => render({ persist: true })}>Save to library</button>
          <button
            type="button"
            className="btn btn-sm"
            data-testid="dieline-guides-toggle"
            aria-pressed={showGuides}
            disabled={!geometry}
            onClick={() => setShowGuides(v => !v)}
            title={geometry ? 'Bleed, trim, fold and safe guides (never exported)' : 'Render a dieline to see its guides'}
          >
            {showGuides ? 'Hide guides' : 'Show guides'}
          </button>
          {projectId && (
            <a className="btn btn-sm" href={`${API}/print/projects/${encodeURIComponent(projectId)}/export.zip`}>Export project ZIP</a>
          )}
        </div>
        {geometry && panelIds(geometry).length > 1 && (
          <label style={{ fontSize: 12, display: 'inline-block', marginTop: 8 }}>Guides for
            <select value={guidePanel} onChange={e => setGuidePanel(e.target.value)}
              data-testid="dieline-guide-panel"
              style={{ display: 'block', marginTop: 4, minWidth: 170 }}>
              {panelIds(geometry).map(id => <option key={id} value={id}>{panelLabel(id)}</option>)}
            </select>
          </label>
        )}
        {meta && (
          <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
            {meta.title} - {meta.size_mm && meta.size_mm.width} x {meta.size_mm && meta.size_mm.height} mm
            {meta.assets && meta.assets.length ? ` - ${meta.assets.length} file(s) saved` : ''}
          </div>
        )}
        {geometry && (
          <div className="text-low" style={{ fontSize: 12, marginTop: 4 }} data-testid="dieline-guide-caption">
            {describeOverlay(geometry, guidePanel)}
          </div>
        )}
        {svg && (
          <div
            style={{ position: 'relative', marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, padding: 12, overflow: 'auto', background: '#fff' }}
          >
            <div dangerouslySetInnerHTML={{ __html: svg }} />
            {showGuides && geometry && (
              <GuideOverlay geometry={geometry} panelId={guidePanel} svgText={svg} />
            )}
          </div>
        )}
      </div>

      <div className="card" style={{ padding: 16 }} data-testid="box-library">
        <div style={{ fontWeight: 600, color: 'var(--pine-deep)', marginBottom: 4 }}>Box library</div>
        <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
          Real box structures generated locally by <strong>Boxes.py</strong> (GPL-3.0, an external
          tool run as a separate process — its output is yours; nothing is sent anywhere).
          {boxLib && boxLib.available === false && (
            <span> The tool is not installed on this machine, so generation is refused.</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ fontSize: 12 }}>Structure
            <select value={boxGen} onChange={e => setBoxGen(e.target.value)}
              style={{ display: 'block', marginTop: 4, minWidth: 220 }} data-testid="box-gen-select">
              {((boxLib && boxLib.generators) || [{ id: 'ClosedBox', label: 'Closed box' }]).map(g => (
                <option key={g.id} value={g.id}>{g.label}</option>
              ))}
            </select>
          </label>
          {['x', 'y', 'h', 'thickness'].map(k => (
            <label key={k} style={{ fontSize: 12 }}>{(boxLib && boxLib.params && boxLib.params[k] && boxLib.params[k].label) || k}
              <input type="number" step="0.5" value={boxParams[k]}
                onChange={e => setBoxParams(p => ({ ...p, [k]: e.target.value === '' ? '' : Number(e.target.value) }))}
                style={{ display: 'block', marginTop: 4, width: 118 }} />
            </label>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-sm btn-primary" disabled={boxBusy} onClick={generateBox} data-testid="box-generate">
            Generate structure
          </button>
          <button className="btn btn-sm" disabled={!boxSvg}
            onClick={() => downloadBlob(new Blob([boxSvg], { type: 'image/svg+xml' }), `${boxGen}-${boxParams.x}x${boxParams.y}x${boxParams.h}.svg`)}>
            Download SVG
          </button>
        </div>
        {boxSvg && (
          <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, padding: 12, overflow: 'auto', background: '#fff' }}
            data-testid="box-preview">
            <img src={`data:image/svg+xml;utf8,${encodeURIComponent(boxSvg)}`} alt={`${boxGen} dieline`} style={{ maxWidth: '100%' }} />
          </div>
        )}
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontWeight: 600, color: 'var(--pine-deep)', marginBottom: 4 }}>Mockup planner</div>
        <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
          Structured [PRODUCT] / [SCENE] prompt assembly for the local engine.
          Queueing runs on your machine only; if the engine is not armed the API
          returns the exact gate message and nothing is charged.
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ fontSize: 12 }}>Product
            <select value={productId} onChange={e => setProductId(e.target.value)}
              style={{ display: 'block', marginTop: 4, minWidth: 180 }}>
              <option value="">(none)</option>
              {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 12 }}>Scene
            <select value={sceneId} onChange={e => setSceneId(e.target.value)}
              style={{ display: 'block', marginTop: 4, minWidth: 230 }}>
              <option value="">(none)</option>
              {scenes.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 12, flex: '1 1 280px' }}>Custom scene prompt
            <input value={customPrompt} onChange={e => setCustomPrompt(e.target.value)}
              placeholder="e.g. rustic wooden shelf, morning light"
              style={{ display: 'block', marginTop: 4, width: '100%' }} />
          </label>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-sm btn-primary" disabled={busy || !hasPlanInput} onClick={() => planMockup(false)}>Build prompt</button>
          <button className="btn btn-sm" disabled={busy || !hasPlanInput} onClick={() => planMockup(true)}>Build + queue generation</button>
          {!hasPlanInput && (
            <span className="text-low" style={{ fontSize: 12, alignSelf: 'center' }}>Pick a product or scene, or write a custom prompt first.</span>
          )}
          {plan && plan.prompt && (
            <button className="btn btn-sm" onClick={() => { if (navigator.clipboard) { navigator.clipboard.writeText(plan.prompt); toast('Prompt copied.', 'info') } }}>Copy prompt</button>
          )}
        </div>
        {plan && plan.prompt && (
          <pre style={{ marginTop: 12, whiteSpace: 'pre-wrap', fontSize: 12, background: 'var(--surface-subtle, #f8f7f2)', padding: 12, borderRadius: 8 }}>{plan.prompt}</pre>
        )}
        {plan && plan.enqueued && plan.enqueued.job && (
          <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
            Queued job {plan.enqueued.job.id} - poll GET /api/design-studio/generate-async/{plan.enqueued.job.id}
          </div>
        )}
      </div>
    </div>
  )
}
