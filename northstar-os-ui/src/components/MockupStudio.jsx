import { useEffect, useRef, useState } from 'react'
import { DataNotice } from './Shared.jsx'

// Exact-Text Mockup Studio — the local, operator-driven lane of Creative Studio.
//
// Truth boundary (unchanged): the local ComfyUI lane generates/edits the SCENE;
// every final glyph is applied by the deterministic compositor on the backend
// (/api/creative/*). The AI is never the source of truth for packaging text.
// This surface only talks to that local backend; it is not a public service.

const API = '/api/creative'

const TONE = {
  ok: 'alert',
  warn: 'alert-warn',
  error: 'alert-error',
}

export default function MockupStudio() {
  const [catalog, setCatalog] = useState(null)
  const [health, setHealth] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [result, setResult] = useState(null)
  const [zone, setZone] = useState(null)
  const fileRef = useRef(null)

  const [container, setContainer] = useState('')
  const [product, setProduct] = useState('')
  const [surface, setSurface] = useState('front_label_panel')
  const [style, setStyle] = useState('mogra_label_panel')
  const [brand, setBrand] = useState('Mogra Organics')
  const [tagline, setTagline] = useState('Fuel Your Focus.')
  const [productName, setProductName] = useState('')
  const [descriptor, setDescriptor] = useState('')
  const [netWeight, setNetWeight] = useState('')
  const [ingredients, setIngredients] = useState('')
  const [rear, setRear] = useState('')
  const [generate, setGenerate] = useState(false)
  const [scenePrompt, setScenePrompt] = useState('')
  const [align, setAlign] = useState('auto')
  const [panelPrep, setPanelPrep] = useState(false)
  const [sourceB64, setSourceB64] = useState('')
  const [sourceName, setSourceName] = useState('')

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const r = await fetch(`${API}/presets`)
        if (!r.ok) throw new Error(`presets HTTP ${r.status}`)
        const j = await r.json()
        if (!alive) return
        setCatalog(j)
        const firstProduct = Object.keys(j.products || {})[0] || ''
        const firstContainer = Object.keys(j.containers || {})[0] || ''
        setProduct(firstProduct)
        setContainer(firstContainer)
        const p = j.products?.[firstProduct]
        if (p) {
          if (p.brand) setBrand(p.brand)
          if (p.tagline) setTagline(p.tagline)
          setProductName(p.product_name || '')
          setDescriptor(p.descriptor || '')
          setNetWeight(p.net_weight || '')
        }
        const c = j.containers?.[firstContainer]
        if (c?.default_style) setStyle(c.default_style)
      } catch (e) {
        if (alive) setLoadError(
          `Could not reach the local creative lane (${e.message}). ` +
          'Start the Northstar backend on this host; this lane is local-only.',
        )
      }
      try {
        const h = await (await fetch(`${API}/health`)).json()
        if (alive) setHealth(h)
      } catch { /* health is optional context */ }
    })()
    return () => { alive = false }
  }, [])

  function pickProduct(key) {
    setProduct(key)
    const p = catalog?.products?.[key]
    if (!p) return
    if (p.brand) setBrand(p.brand)
    if (p.tagline) setTagline(p.tagline)
    setProductName(p.product_name || '')
    setDescriptor(p.descriptor || '')
    setNetWeight(p.net_weight || '')
  }

  function pickContainer(key) {
    setContainer(key)
    const c = catalog?.containers?.[key]
    if (c?.default_style) setStyle(c.default_style)
  }

  function onFile(f) {
    if (!f) return
    const rd = new FileReader()
    rd.onload = (e) => {
      setSourceB64(String(e.target.result || ''))
      setSourceName(f.name)
      setResult(null)
      setZone(null)
    }
    rd.readAsDataURL(f)
  }

  async function detectZone() {
    if (!sourceB64) { setNotice({ tone: 'warn', text: 'Upload a base image first.' }); return }
    try {
      const r = await fetch(`${API}/detect-zone`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_base64: sourceB64 }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setZone(j.zone || null)
      setNotice(j.found
        ? { tone: 'ok', text: `Blank label zone detected (confidence ${j.zone.confidence}).` }
        : { tone: 'warn', text: 'No blank label zone detected — the preset quad will be used.' })
    } catch (e) {
      setNotice({ tone: 'error', text: `Detect failed: ${e.message}` })
    }
  }

  async function generateMockup() {
    if (!sourceB64 && !generate) {
      setNotice({ tone: 'warn', text: 'Upload a base image, or tick “generate a base scene”.' })
      return
    }
    setBusy(true)
    setNotice(null)
    const body = {
      product, container: container || null, surface, style,
      brand, tagline, product_name: productName, descriptor, net_weight: netWeight,
      ingredients,
      rear_placeholders: rear.split('\n').map((s) => s.trim()).filter(Boolean),
      generate, scene_prompt: scenePrompt || null,
      align, panel_prep: panelPrep ? 'edit_blank' : null,
    }
    if (sourceB64) body.source_base64 = sourceB64
    try {
      const r = await fetch(`${API}/mockup`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setResult(j)
      setZone(j.align?.zone || null)
      setNotice({ tone: 'ok', text: `Final mockup generated on the ${j.lane} lane.` })
    } catch (e) {
      setNotice({ tone: 'error', text: e.message })
    } finally {
      setBusy(false)
    }
  }

  if (loadError) {
    return (
      <div className="subview ns-lane">
        <DataNotice tone="unknown" title="Local lane unavailable">{loadError}</DataNotice>
      </div>
    )
  }

  const P = catalog?.products || {}
  const C = catalog?.containers || {}
  const S = catalog?.surfaces || {}
  const Y = catalog?.styles || {}

  return (
    <div className="subview ns-lane">
      <DataNotice tone="internal" title="Local lane — exact text is deterministic">
        The scene is generated or edited by the local Qwen lane; every final glyph is applied by the
        deterministic text compositor. AI text is never treated as final packaging copy. This lane is
        local-only and is not a public production service.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="pill pill-muted">local-only</span>
          <span className={`pill ${health?.comfyui?.up ? 'pill-ok' : 'pill-unknown'}`}>
            comfyui {health?.comfyui?.up ? 'up' : 'down'}
          </span>
          <span className={`pill ${health?.qwen_ready ? 'pill-ok' : 'pill-warn'}`}>
            qwen t2i {health?.qwen_ready ? 'ready' : 'missing'}
          </span>
          <span className={`pill ${health?.qwen_edit_ready ? 'pill-ok' : 'pill-warn'}`}>
            qwen edit {health?.qwen_edit_ready ? 'ready' : 'missing'}
          </span>
          <span className={`pill ${health?.fonts?.bundled ? 'pill-ok' : 'pill-warn'}`}>
            fonts {health?.fonts?.bundled ? (health.fonts.source) : 'system fallback'}
          </span>
        </div>
      </div>

      <div className="split-aside-l">
        <div>
          <div className="card">
            <div className="card-head"><h3 className="card-title">1 · Base image</h3></div>
            <div className="ms-drop" onClick={() => fileRef.current?.click()}>
              <strong>Click to upload a product image</strong>
              <small>{sourceName || 'PNG / JPG — used as the base for the label'}</small>
              <input ref={fileRef} type="file" accept="image/*" hidden
                onChange={(e) => onFile(e.target.files?.[0])} />
            </div>
            <div className="ms-check">
              <input id="ms-gen" type="checkbox" checked={generate}
                onChange={(e) => setGenerate(e.target.checked)} />
              <label htmlFor="ms-gen" style={{ margin: 0 }}>or generate a base scene with the local model</label>
            </div>
            <label htmlFor="ms-prompt">Scene prompt (optional)</label>
            <textarea id="ms-prompt" value={scenePrompt}
              placeholder="leave blank to auto-build from container + product"
              onChange={(e) => setScenePrompt(e.target.value)} />

            <div className="card-head" style={{ marginTop: 18 }}><h3 className="card-title">2 · Presets</h3></div>
            <label htmlFor="ms-container">Container</label>
            <select id="ms-container" value={container} onChange={(e) => pickContainer(e.target.value)}>
              <option value="">— none / use surface zone —</option>
              {Object.entries(C).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <label htmlFor="ms-product">Product</label>
            <select id="ms-product" value={product} onChange={(e) => pickProduct(e.target.value)}>
              {Object.entries(P).map(([k, v]) => <option key={k} value={k}>{v.label || v.product_name}</option>)}
            </select>
            <label htmlFor="ms-surface">Surface zone</label>
            <select id="ms-surface" value={surface} onChange={(e) => setSurface(e.target.value)}>
              {Object.entries(S).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
            <label htmlFor="ms-style">Label style</label>
            <select id="ms-style" value={style} onChange={(e) => setStyle(e.target.value)}>
              {Object.entries(Y).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>

            <label htmlFor="ms-align">Panel alignment</label>
            <select id="ms-align" value={align} onChange={(e) => setAlign(e.target.value)}>
              <option value="auto">Auto — fit to detected blank label zone</option>
              <option value="preset">Preset quad</option>
            </select>
            <div className="ms-check">
              <input id="ms-prep" type="checkbox" checked={panelPrep}
                onChange={(e) => setPanelPrep(e.target.checked)} />
              <label htmlFor="ms-prep" style={{ margin: 0 }}>blank-panel repair (Edit-2511) before text</label>
            </div>
          </div>
        </div>

        <div>
          <div className="card">
            <div className="card-head"><h3 className="card-title">3 · Exact text</h3></div>
            <div className="ms-grid">
              <div>
                <label htmlFor="ms-brand">Brand</label>
                <input id="ms-brand" type="text" value={brand} onChange={(e) => setBrand(e.target.value)} />
              </div>
              <div>
                <label htmlFor="ms-tag">Tagline</label>
                <input id="ms-tag" type="text" value={tagline} onChange={(e) => setTagline(e.target.value)} />
              </div>
            </div>
            <label htmlFor="ms-name">Product name</label>
            <input id="ms-name" type="text" value={productName} onChange={(e) => setProductName(e.target.value)} />
            <div className="ms-grid">
              <div>
                <label htmlFor="ms-desc">Descriptor</label>
                <input id="ms-desc" type="text" value={descriptor} onChange={(e) => setDescriptor(e.target.value)} />
              </div>
              <div>
                <label htmlFor="ms-net">Net weight</label>
                <input id="ms-net" type="text" value={netWeight} onChange={(e) => setNetWeight(e.target.value)} />
              </div>
            </div>
            <label htmlFor="ms-ing">Ingredients (optional placeholder)</label>
            <input id="ms-ing" type="text" value={ingredients}
              placeholder="leave blank — nothing is invented"
              onChange={(e) => setIngredients(e.target.value)} />
            <label htmlFor="ms-rear">Rear-label placeholders (one per line, optional)</label>
            <textarea id="ms-rear" value={rear} onChange={(e) => setRear(e.target.value)} />

            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" disabled={busy} onClick={generateMockup}>
                {busy ? 'Generating…' : 'Generate Final Mockup'}
              </button>
              <button className="btn btn-ghost" disabled={busy || !sourceB64} onClick={detectZone}>
                Detect label zone
              </button>
            </div>

            {notice && (
              <div className={`${TONE[notice.tone] || 'alert'} mt-3`} style={{ marginTop: 12 }}>
                <div className="alert-text">{notice.text}</div>
              </div>
            )}
            {zone && (
              <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
                Detected zone {JSON.stringify(zone.quad_norm)} · confidence {zone.confidence}
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head"><h3 className="card-title">4 · Preview</h3></div>
            <div className="ms-preview">
              <div className="ms-pane">
                <h4>Base / source</h4>
                {sourceB64
                  ? <img src={sourceB64} alt="base" />
                  : <div className="ms-empty">No image yet</div>}
              </div>
              <div className="ms-pane">
                <h4>Final mockup</h4>
                {result?.url
                  ? <img src={result.url} alt="final mockup" />
                  : <div className="ms-empty">Nothing generated yet</div>}
              </div>
            </div>
            {result && (
              <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>
                lane <strong>{result.lane}</strong> · alignment {result.align?.source}
                {result.align?.confidence ? ` (${result.align.confidence})` : ''}
                {result.panel_prep?.applied ? ' · panel prep applied' : ''}
                {' · '}<a href={result.url} target="_blank" rel="noreferrer">open PNG</a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
