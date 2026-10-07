import { useEffect, useState } from 'react'
import { DataNotice } from './Shared.jsx'

// Creative Studio — Asset Registry & Export Bundles (local lane).
// Real local asset index over the creative media root: list/generate mockups,
// group them into variant sets, and package selections into a downloadable ZIP
// bundle (manifest + files). No external service.

const API = '/api/creative'

export default function AssetRegistry() {
  const [assets, setAssets] = useState([])
  const [sets, setSets] = useState([])
  const [storage, setStorage] = useState(null)
  const [sel, setSel] = useState([])
  const [name, setName] = useState('mogra-bundle')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)
  const [bundle, setBundle] = useState(null)
  const [err, setErr] = useState('')

  async function load() {
    try {
      const r = await fetch(`${API}/assets`)
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setAssets(j.assets || [])
      setSets(j.sets || [])
      setStorage(j.storage || null)
      setErr('')
    } catch (e) {
      setErr(`Asset registry unavailable (${e.message}). The local backend must be running.`)
    }
  }
  useEffect(() => { load() }, [])

  const toggle = (id) => setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  async function scan() {
    setBusy(true); setNotice(null)
    try {
      const r = await fetch(`${API}/assets/scan`, { method: 'POST' })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setNotice({ tone: 'ok', text: `Scanned media root: ${j.added} new asset(s), ${j.total} total.` })
      await load()
    } catch (e) { setNotice({ tone: 'error', text: e.message }) } finally { setBusy(false) }
  }

  async function createBundle() {
    if (!sel.length) { setNotice({ tone: 'warn', text: 'Select at least one asset.' }); return }
    setBusy(true); setNotice(null); setBundle(null)
    try {
      const r = await fetch(`${API}/bundles`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_ids: sel, name }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      setBundle(j)
      setNotice({ tone: 'ok', text: `Bundle created with ${j.included} asset(s).` })
      await load()
    } catch (e) { setNotice({ tone: 'error', text: e.message }) } finally { setBusy(false) }
  }

  return (
    <div className="subview ns-lane">
      <DataNotice tone="internal" title="Local asset registry — real files on this machine">
        Assets are the real mockups/renders produced by the exact-text lane on this
        host. Bundles are packaged here (manifest + files) and downloaded from the
        local file route. Nothing is uploaded to any external service.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="pill pill-muted">storage {storage?.backend || 'local'}</span>
          <span className="pill pill-muted">{assets.length} asset(s)</span>
          <span className="pill pill-muted">{sets.length} variant set(s)</span>
          <button className="btn btn-sm" disabled={busy} onClick={scan} style={{ marginLeft: 'auto' }}>
            Scan media root
          </button>
        </div>
      </div>

      {err && <div className="alert alert-error" style={{ marginBottom: 16 }}><div className="alert-text">{err}</div></div>}

      {sets.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-head"><h3 className="card-title">Variant sets</h3></div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {sets.map((s) => (
              <span key={s.set} className="pill pill-muted" title={s.set}>{s.set} · {s.count}</span>
            ))}
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head"><h3 className="card-title">Create export bundle</h3></div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ minWidth: 220 }}>
            <label htmlFor="ar-name">Bundle name</label>
            <input id="ar-name" type="text" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <button className="btn btn-primary" disabled={busy || !sel.length} onClick={createBundle}>
            {busy ? 'Working…' : `Create Bundle (${sel.length} selected)`}
          </button>
          {sel.length > 0 && (
            <button className="btn btn-ghost" disabled={busy} onClick={() => setSel([])}>Clear selection</button>
          )}
        </div>
        {notice && (
          <div className={`alert${notice.tone === 'error' ? ' alert-error' : notice.tone === 'warn' ? ' alert-warn' : ''}`} style={{ marginTop: 12 }}>
            <div className="alert-text">{notice.text}</div>
          </div>
        )}
        {bundle && (
          <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>
            {bundle.included}/{bundle.requested} packaged · {bundle.bytes} bytes ·{' '}
            <a href={bundle.bundle.url} target="_blank" rel="noreferrer">download ZIP</a> ·
            manifest lists {bundle.manifest.assets.length} asset(s)
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-head"><h3 className="card-title">Assets</h3></div>
        {assets.length === 0 && (
          <div className="ms-empty">
            No assets indexed yet. Generate a mockup (Exact-Text Mockups tab) or press “Scan media root”.
          </div>
        )}
        {assets.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
            {assets.map((a) => (
              <div key={a.id} className="card" style={{ margin: 0, padding: 10 }}>
                <label style={{ display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer', marginBottom: 6 }}>
                  <input type="checkbox" checked={sel.includes(a.id)} onChange={() => toggle(a.id)} />
                  <span className="pill pill-muted" style={{ fontSize: 11 }}>{a.kind}</span>
                </label>
                {a.kind === 'bundle'
                  ? <div className="ms-empty" style={{ minHeight: 60 }}>ZIP bundle
                      <div><a href={a.url} target="_blank" rel="noreferrer">download</a></div>
                    </div>
                  : <img src={a.url} alt={a.key} style={{ width: '100%', borderRadius: 6 }} />}
                <div className="text-low" style={{ fontSize: 11, marginTop: 6, wordBreak: 'break-all' }}>{a.key}</div>
                {(a.product || a.container) && (
                  <div className="text-low" style={{ fontSize: 11 }}>
                    {a.product || ''}{a.container ? ` · ${a.container}` : ''}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
