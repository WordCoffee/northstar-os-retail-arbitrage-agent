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

const API = '/api/design-studio'

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
  const [busy, setBusy] = useState(false)
  const [projects, setProjects] = useState([])
  const [projectId, setProjectId] = useState('')
  const [scenes, setScenes] = useState([])
  const [products, setProducts] = useState([])
  const [sceneId, setSceneId] = useState('')
  const [productId, setProductId] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')
  const [plan, setPlan] = useState(null)

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
    const t = templates.find(x => x.id === id)
    setParams({ ...((t && t.params) || {}) })
  }

  const render = useCallback(async (opts = {}) => {
    setBusy(true)
    try {
      const r = await fetch(`${API}/print/dielines`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: templateId,
          params: Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)),
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
  }, [templateId, params, projectId, toast])

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
          {projectId && (
            <a className="btn btn-sm" href={`${API}/print/projects/${encodeURIComponent(projectId)}/export.zip`}>Export project ZIP</a>
          )}
        </div>
        {meta && (
          <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
            {meta.title} - {meta.size_mm && meta.size_mm.width} x {meta.size_mm && meta.size_mm.height} mm
            {meta.assets && meta.assets.length ? ` - ${meta.assets.length} file(s) saved` : ''}
          </div>
        )}
        {svg && (
          <div
            style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 8, padding: 12, overflow: 'auto', background: '#fff' }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
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
