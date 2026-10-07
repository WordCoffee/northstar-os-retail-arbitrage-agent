import { useState } from 'react'
import { DataNotice } from './Shared.jsx'

// ListingForge — local lane. Calls the real /api/listing-forge/* backend
// (listing_forge.py): title, bullets, description, backend/search terms, score,
// compliance. Runs offline via the deterministic template fallback and upgrades
// to the local LLM when it is present. Generated copy is never final until a
// human approves it (review_required).

const API = '/api/listing-forge'

// Defensive coercion — the module returns arrays for some fields and a joined
// string for others; render both without crashing.
const asList = (v) => Array.isArray(v) ? v : (typeof v === 'string' ? v.split(/[,\s]+/).filter(Boolean) : [])
const asText = (v) => Array.isArray(v) ? v.join(', ') : (v == null ? '' : String(v))

export default function ListingForgeLane() {
  const [f, setF] = useState({
    title: 'Mogra Organics Organic Turmeric Powder',
    brand: 'Mogra Organics',
    price: '24.99',
    category: 'Grocery & Gourmet Food',
    keywords: 'turmeric powder, organic turmeric, golden spice',
    useLlm: false,
  })
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function run() {
    setBusy(true); setErr(''); setRes(null)
    try {
      const body = {
        product: {
          title: f.title, brand: f.brand,
          price: Number(f.price) || 0, category: f.category,
        },
        top_keywords: f.keywords.split(',').map((s) => s.trim()).filter(Boolean),
        use_llm: f.useLlm,
      }
      const r = await fetch(`${API}/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : (j.detail?.message || `HTTP ${r.status}`))
      setRes(j)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="subview ns-lane">
      <DataNotice tone="internal" title="Local lane — generated copy is a draft, not final">
        This lane calls the local ListingForge engine (template fallback offline; local
        LLM when available). Nothing is published. Every draft requires operator review
        before it is treated as final, and compliance findings are surfaced, not hidden.
      </DataNotice>

      <div className="split-aside-l">
        <div className="card">
          <div className="card-head"><h3 className="card-title">Inputs</h3></div>
          <label htmlFor="lf-title">Product title</label>
          <input id="lf-title" type="text" value={f.title} onChange={set('title')} />
          <div className="ms-grid">
            <div>
              <label htmlFor="lf-brand">Brand</label>
              <input id="lf-brand" type="text" value={f.brand} onChange={set('brand')} />
            </div>
            <div>
              <label htmlFor="lf-price">Price</label>
              <input id="lf-price" type="text" value={f.price} onChange={set('price')} />
            </div>
          </div>
          <label htmlFor="lf-cat">Category</label>
          <input id="lf-cat" type="text" value={f.category} onChange={set('category')} />
          <label htmlFor="lf-kw">Top keywords (comma separated)</label>
          <textarea id="lf-kw" value={f.keywords} onChange={set('keywords')} />
          <div className="ms-check">
            <input id="lf-llm" type="checkbox" checked={f.useLlm} onChange={(e) => setF({ ...f, useLlm: e.target.checked })} />
            <label htmlFor="lf-llm" style={{ margin: 0 }}>use local LLM (slower; off = instant template draft)</label>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={run}>
              {busy ? 'Generating…' : 'Generate Local Draft'}
            </button>
          </div>
          {err && <div className="alert alert-error" style={{ marginTop: 12 }}><div className="alert-text">{err}</div></div>}
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Draft</h3>
            {res && <span className={`pill ${res.compliance?.ok ? 'pill-ok' : 'pill-error'}`}>
              compliance {res.compliance?.ok ? 'clear' : 'issues'}
            </span>}
          </div>
          {!res && <div className="ms-empty">Generate a draft to see title, bullets, description, terms, score and compliance.</div>}
          {res && (
            <>
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 12 }}>
                <span className="pill pill-muted">score {res.score?.composite}</span>
                <span className="pill pill-muted">title {res.score?.title}</span>
                <span className="pill pill-muted">bullets {res.score?.bullets}</span>
                <span className="pill pill-muted">desc {res.score?.description}</span>
                {res.review_required && <span className="pill pill-ochre">review required</span>}
              </div>
              <label>Title</label>
              <div className="card" style={{ margin: 0, padding: 10 }}>{res.title?.title}</div>
              <label>Bullets</label>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {(res.bullets?.bullets || []).map((b, i) => <li key={i} style={{ marginBottom: 6 }}>{b}</li>)}
              </ul>
              <label>Description</label>
              <div className="card" style={{ margin: 0, padding: 10 }}>{res.description?.description}</div>
              <div className="ms-grid" style={{ marginTop: 10 }}>
                <div>
                  <label>Backend terms</label>
                  <div className="text-low" style={{ fontSize: 12 }}>{asList(res.backend_terms?.backend_terms || res.backend_terms?.terms).join(', ') || '—'}</div>
                </div>
                <div>
                  <label>Search terms</label>
                  <div className="text-low" style={{ fontSize: 12 }}>{asText(res.search_terms?.search_terms || res.search_terms?.terms) || '—'}</div>
                </div>
              </div>
              {res.compliance && !res.compliance.ok && (
                <div className="alert alert-warn" style={{ marginTop: 12 }}>
                  <div className="alert-title">Compliance findings</div>
                  <div className="alert-text">
                    {(res.compliance.violations || []).map((v, i) => <div key={i}>{v.rule || v.message || JSON.stringify(v)}</div>)}
                  </div>
                </div>
              )}
              <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>{res.basis}</div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
