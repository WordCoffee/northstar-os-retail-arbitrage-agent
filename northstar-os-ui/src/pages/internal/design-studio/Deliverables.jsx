// Asset Dashboard — packages on disk, lane triggers, and the proposal queue.
//
// Honesty contract: every row is read from the filesystem through
// /api/design-studio/dashboard/*. A package without a manifest is shown as
// invalid, never hidden. Nothing here installs a proposal: a decision records
// the choice, and the note in the API says so.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { LOCAL_DEV } from '../../../foundation/dev.js'

const API = '/api/design-studio/dashboard'

// Same transport rules as the rest of the suite: same-origin, cookie auth,
// CSRF double-submit, dev identity shim gated on the compile-time LOCAL_DEV
// constant. The shim matters here: without X-User-Id the backend files these
// calls under the anonymous 30/min bucket, and a normal studio session tripped
// 429s that the dashboard reported as "no assets found".
function headers(method, extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (LOCAL_DEV) {
    try {
      const s = JSON.parse(localStorage.getItem('ns-dev-session') || 'null')
      if (s && s.userId) {
        h['X-User-Id'] = s.userId
        if (s.orgId) h['X-Org-Id'] = s.orgId
        if (s.role) h['X-Role'] = s.role
      }
    } catch { /* storage unavailable - hosted cookie auth is used */ }
  }
  const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes((method || 'GET').toUpperCase())
  if (unsafe) {
    try {
      const m = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
      if (m) h['X-CSRF-Token'] = decodeURIComponent(m[2])
    } catch { /* no cookies */ }
  }
  return h
}

async function getJSON(url) {
  const res = await fetch(url, { credentials: 'same-origin', headers: headers('GET') })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail?.message || body.detail || `HTTP ${res.status}`)
  return body
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: headers('POST'),
    body: JSON.stringify(payload),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = body.detail
    throw new Error(typeof detail === 'string' ? detail : (detail?.message || `HTTP ${res.status}`))
  }
  return body
}

const LANES = [
  { id: 'cutout', label: 'Cutout', endpoint: '/api/design-studio/lanes/cutout',
    note: 'BiRefNet matte on a framed white 2000px canvas',
    payload: a => ({ asset_id: a }) },
  { id: 'relight', label: 'Relight', endpoint: '/api/design-studio/relight',
    note: 'IC-Light studio relight, gated and refused if the decode is noise',
    payload: a => ({ asset_id: a, width: 768, height: 768, steps: 20 }) },
  { id: 'master', label: 'Print master', endpoint: '/api/design-studio/print/master',
    note: '4x Real-ESRGAN to a measured 300 DPI at the declared size',
    payload: a => ({ asset_id: a, width_mm: 100, height_mm: 100 }) },
  { id: 'shorts', label: 'Shorts 9:16', endpoint: '/api/design-studio/shorts',
    note: 'Wan 2.2 TI2V clip, frame-gated (about a minute)',
    payload: a => ({ asset_id: a, width: 480, height: 832, length: 17, steps: 12 }) },
]

function Preview({ file }) {
  if (!file) return <div className="text-low" style={{ fontSize: 12 }}>no preview</div>
  if (file.kind === 'video') {
    return (
      <video src={file.url} controls preload="metadata" data-testid="dash-video"
             style={{ width: '100%', maxHeight: 240, borderRadius: 8, background: '#000' }} />
    )
  }
  return (
    <img src={file.url} alt={file.name} loading="lazy" data-testid="dash-image"
         style={{ width: '100%', maxHeight: 240, objectFit: 'contain', borderRadius: 8,
                  background: 'var(--surface-2, #f4f0e8)' }} />
  )
}

function PackageCard({ row, onOpenManifest }) {
  return (
    <div className="card" style={{ padding: 12 }} data-testid="dash-package">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div><strong>{row.run_id}</strong></div>
          <div className="text-low" style={{ fontSize: 12, marginTop: 2 }}>
            {row.kind} · {row.created_at || 'time unknown'}
          </div>
        </div>
        <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
          <span className={row.ok ? 'pill pill-ok' : 'pill pill-warn'}>
            {row.manifest ? (row.ok ? `gate ${row.score || 'ok'}` : (row.ok === null ? 'no gate recorded' : 'gate failed')) : 'no manifest'}
          </span>
        </div>
      </div>
      <div style={{ marginTop: 10 }}><Preview file={row.preview} /></div>
      <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
        {row.files.map(f => f.name).join(' · ')}
      </div>
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        {row.files.filter(f => f.kind === 'image' || f.kind === 'video').slice(0, 3).map(f => (
          <a key={f.name} className="btn btn-sm" href={f.url} target="_blank" rel="noreferrer">
            {f.kind === 'video' ? 'video' : 'image'}
          </a>
        ))}
        <button type="button" className="btn btn-sm" onClick={() => onOpenManifest(row)}
                data-testid="dash-manifest">
          manifest
        </button>
      </div>
    </div>
  )
}

export default function AssetDashboard() {
  const [packages, setPackages] = useState({ loading: true, error: '', rows: [] })
  const [proposals, setProposals] = useState({ loading: true, error: '', rows: [], decided: {} })
  const [assets, setAssets] = useState([])
  const [assetId, setAssetId] = useState('')
  const [busy, setBusy] = useState('')
  const [lastRun, setLastRun] = useState(null)
  const [manifest, setManifest] = useState(null)

  const loadPackages = useCallback(async () => {
    setPackages(s => ({ ...s, loading: true, error: '' }))
    try {
      const data = await getJSON(`${API}/packages`)
      setPackages({ loading: false, error: '', rows: data.packages || [] })
    } catch (err) {
      setPackages({ loading: false, error: String(err.message || err), rows: [] })
    }
  }, [])

  const loadProposals = useCallback(async () => {
    setProposals(s => ({ ...s, loading: true, error: '' }))
    try {
      const data = await getJSON(`${API}/proposals`)
      setProposals({ loading: false, error: '', rows: data.proposals || [], decided: data.decided || {} })
    } catch (err) {
      setProposals({ loading: false, error: String(err.message || err), rows: [], decided: {} })
    }
  }, [])

  const loadAssets = useCallback(async () => {
    // The lane picker must not say "no assets found" for the life of the tab.
    // A stalled keep-alive (seen on WebKit through the Vite proxy) never rejects
    // and a throttled call returns 429, so every attempt has a hard 4 s ceiling
    // and a 429 is retried after the server's own Retry-After.
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
      const timer = ctrl ? setTimeout(() => ctrl.abort(), 4000) : null
      try {
        const res = await fetch('/api/design-studio/assets', {
          credentials: 'same-origin',
          headers: headers('GET'),
          signal: ctrl ? ctrl.signal : undefined,
        })
        if (!res.ok) {
          const err = new Error(`HTTP ${res.status}`)
          err.status = res.status
          err.retryAfter = Number(res.headers.get('Retry-After') || 0)
          throw err
        }
        const data = await res.json().catch(() => ({}))
        const rows = (data.assets || []).slice(0, 40)
        setAssets(rows)
        // Pick a default once, without re-running this callback (and the fetch
        // it performs) every time the selection changes.
        if (rows.length) setAssetId(prev => prev || rows[0].id)
        return
      } catch (err) {
        if (attempt === 3) setAssets([])
        else {
          const wait = err && err.retryAfter ? err.retryAfter * 1000 : 600 * (attempt + 1)
          await new Promise(resolve => setTimeout(resolve, Math.min(wait, 5000)))
        }
      } finally {
        if (timer) clearTimeout(timer)
      }
    }
  }, [])

  useEffect(() => { loadPackages(); loadProposals(); loadAssets() }, [loadPackages, loadProposals, loadAssets])

  const openManifest = useCallback(async row => {
    try {
      setManifest({ run_id: row.run_id, data: await getJSON(`${API}/packages/${row.run_id}/manifest`) })
    } catch (err) {
      setManifest({ run_id: row.run_id, error: String(err.message || err) })
    }
  }, [])

  const runLane = useCallback(async lane => {
    if (!assetId) return
    setBusy(lane.id)
    setLastRun({ lane: lane.label, state: 'running' })
    try {
      const result = await postJSON(lane.endpoint, lane.payload(assetId))
      setLastRun({ lane: lane.label, state: 'done', result })
      await loadPackages()
    } catch (err) {
      setLastRun({ lane: lane.label, state: 'failed', error: String(err.message || err) })
    } finally {
      setBusy('')
    }
  }, [assetId, loadPackages])

  const decide = useCallback(async (row, decision) => {
    setBusy(`decide:${row.id}`)
    try {
      await postJSON(`${API}/proposals/${row.id}/decide`, { decision })
      await loadProposals()
    } catch (err) {
      setProposals(s => ({ ...s, error: String(err.message || err) }))
    } finally {
      setBusy('')
    }
  }, [loadProposals])

  const assetLabel = useMemo(() => new Map(assets.map(a => [a.id, a.name || a.id])), [assets])

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="asset-dashboard">
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>Asset dashboard</h3>
            <div className="text-low" style={{ marginTop: 4 }}>
              Every package under <code>state/deliverables</code>, newest first, read from disk.
            </div>
          </div>
          <button type="button" className="btn btn-sm" onClick={loadPackages} disabled={packages.loading}
                  data-testid="dash-refresh">
            {packages.loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
        {packages.error && <div className="text-low" role="alert" style={{ marginTop: 10 }}>{packages.error}</div>}
        {!packages.loading && !packages.error && packages.rows.length === 0 && (
          <div className="text-low" style={{ marginTop: 10 }}>No packages yet.</div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                      gap: 12, marginTop: 12 }}>
          {packages.rows.map(row => <PackageCard key={row.run_id} row={row} onOpenManifest={openManifest} />)}
        </div>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>Run a lane</h3>
        <div className="text-low" style={{ marginTop: 4 }}>
          Fires the real local endpoint against the selected asset. Nothing leaves this machine.
        </div>
        <div className="field-group" style={{ marginTop: 10, maxWidth: 520 }}>
          <label className="label" htmlFor="dash-asset">Source asset</label>
          <select id="dash-asset" className="field" value={assetId} data-testid="dash-asset"
                  onChange={e => setAssetId(e.target.value)}>
            {assets.length === 0 && <option value="">no assets found</option>}
            {assets.map(a => (
              <option key={a.id} value={a.id}>
                {(assetLabel.get(a.id) || a.id).slice(0, 60)} · {a.asset_type || 'asset'}
              </option>
            ))}
          </select>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {LANES.map(lane => (
            <button key={lane.id} type="button" className="btn btn-sm"
                    title={lane.note} disabled={!assetId || busy === lane.id}
                    onClick={() => runLane(lane)} data-testid={`dash-run-${lane.id}`}>
              {busy === lane.id ? 'Running…' : lane.label}
            </button>
          ))}
        </div>
        {lastRun && (
          <div className="text-low" style={{ marginTop: 10, fontSize: 12 }} data-testid="dash-last-run">
            {lastRun.lane}: {lastRun.state}
            {lastRun.state === 'failed' && ` — ${lastRun.error}`}
            {lastRun.state === 'done' && ` — ${JSON.stringify(lastRun.result).slice(0, 220)}`}
          </div>
        )}
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>Proposal queue</h3>
            <div className="text-low" style={{ marginTop: 4 }}>
              Discovered repositories waiting for a decision. Approving records it — installing is a
              separate, logged step.
            </div>
          </div>
          <button type="button" className="btn btn-sm" onClick={loadProposals}
                  disabled={proposals.loading}>Refresh</button>
        </div>
        {proposals.error && <div className="text-low" role="alert" style={{ marginTop: 10 }}>{proposals.error}</div>}
        {!proposals.loading && proposals.rows.length === 0 && (
          <div className="text-low" style={{ marginTop: 10 }}>No undecided proposals.</div>
        )}
        {proposals.rows.map(row => (
          <div key={row.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12,
                                     alignItems: 'center', marginTop: 10, paddingTop: 10,
                                     borderTop: '1px solid var(--divider-mid, rgba(0,0,0,.08))' }}
               data-testid="dash-proposal">
            <div style={{ minWidth: 0 }}>
              <div><strong>{row.repo}</strong> <span className="text-low">{row.tag}</span></div>
              <div className="text-low" style={{ fontSize: 12 }}>
                {row.why || 'no reason recorded'} · licence {row.licence}
                {row.eligible === false && ' · not eligible'}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, whiteSpace: 'nowrap' }}>
              <button type="button" className="btn btn-sm" disabled={busy === `decide:${row.id}`}
                      onClick={() => decide(row, 'approved')} data-testid="dash-approve">Approve</button>
              <button type="button" className="btn btn-sm" disabled={busy === `decide:${row.id}`}
                      onClick={() => decide(row, 'rejected')}>Reject</button>
            </div>
          </div>
        ))}
        {(proposals.decided.approved || proposals.decided.rejected) ? (
          <div className="text-low" style={{ marginTop: 10, fontSize: 12 }}>
            Decided: {proposals.decided.approved || 0} approved · {proposals.decided.rejected || 0} rejected
          </div>
        ) : null}
      </div>

      {manifest && (
        <div className="card" style={{ padding: 16 }} data-testid="dash-manifest-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>Manifest · {manifest.run_id}</h3>
            <button type="button" className="btn btn-sm" onClick={() => setManifest(null)}>Close</button>
          </div>
          <pre style={{ marginTop: 10, maxHeight: 360, overflow: 'auto', fontSize: 12 }}>
            {manifest.error ? manifest.error : JSON.stringify(manifest.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
