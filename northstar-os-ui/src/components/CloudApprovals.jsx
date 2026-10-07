import { useEffect, useState } from 'react'
import { DataNotice, EmptyState, MiniBars, SectionHeader } from './Shared.jsx'

// Creative Studio — Cloud Providers & Write-Action Approvals (Batch D surface).
// Shows the arming posture (local + cloud), a video cost estimator, and the
// local approval queue for write actions (publish / ad spend). Execution is
// honest: it reports exactly why a write did or did not run.

const API = '/api/creative'

export default function CloudApprovals() {
  const [caps, setCaps] = useState(null)
  const [approvals, setApprovals] = useState([])
  const [posture, setPosture] = useState(null)
  const [videoModels, setVideoModels] = useState({})
  const [est, setEst] = useState({ model: 'wan-2.5', seconds: '15', audio: false })
  const [estOut, setEstOut] = useState(null)
  const [req, setReq] = useState({ kind: 'social_publish', payload: '{\n  "post": "Organic turmeric launch"\n}' })
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState(null)

  async function load() {
    try {
      const c = await (await fetch(`${API}/capabilities`)).json()
      setCaps(c)
      const v = await (await fetch(`${API}/video/models`)).json()
      setVideoModels(v.models || {})
      const a = await (await fetch(`${API}/approvals`)).json()
      setApprovals(a.requests || [])
      setPosture(a.posture || null)
    } catch (e) {
      setNotice({ tone: 'error', text: `Could not reach the local creative backend (${e.message}).` })
    }
  }
  useEffect(() => { load() }, [])

  async function estimate() {
    try {
      const q = `model=${encodeURIComponent(est.model)}&seconds=${encodeURIComponent(est.seconds)}&audio=${est.audio}`
      const j = await (await fetch(`${API}/video/estimate?${q}`)).json()
      setEstOut(j)
    } catch (e) { setNotice({ tone: 'error', text: e.message }) }
  }

  async function createRequest() {
    setBusy(true); setNotice(null)
    try {
      let payload = {}
      try { payload = JSON.parse(req.payload || '{}') } catch { throw new Error('payload must be valid JSON') }
      const r = await fetch(`${API}/approvals`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: req.kind, payload }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setNotice({ tone: 'ok', text: `Approval ${j.request.id} recorded (pending).` })
      await load()
    } catch (e) { setNotice({ tone: 'error', text: e.message }) } finally { setBusy(false) }
  }

  async function decide(id, approve) {
    await fetch(`${API}/approvals/${id}/decide`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve, by: 'operator' }),
    })
    await load()
  }

  async function execute(id) {
    setNotice(null)
    const j = await (await fetch(`${API}/approvals/${id}/execute`, { method: 'POST' })).json()
    setNotice({
      tone: j.executed ? 'ok' : 'warn',
      text: j.executed
        ? `Executed ${id}.`
        : `Not executed: ${j.reason}${j.arm_env ? ` (requires ${j.arm_env}=1)` : ''}${j.note ? ` — ${j.note}` : ''}`,
    })
    await load()
  }

  const cloud = caps?.providers?.cloud || {}
  const local = caps?.providers?.local || {}
  const write = caps?.providers?.write || {}
  const armed = caps?.providers?.media_live_armed

  return (
    <div className="subview ns-lane fade-in">
      <DataNotice tone="internal" title="Local + cloud lanes — arming posture and approvals">
        Local generation is always available. Cloud image/video and write actions
        (publishing, ad spend) are <b>default-off</b>: they run only when their key is
        present, <code>MEDIA_GEN_LIVE=1</code> is set for media, and a write flag is armed.
        Every write also needs a recorded human approval. Nothing here spends money or
        posts publicly unless both hold.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px' }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`pill ${local.up ? 'pill-ok' : 'pill-unknown'}`}>local comfyui {local.up ? 'up' : 'down'}</span>
          <span className={`pill ${armed ? 'pill-ok' : 'pill-muted'}`}>media {armed ? 'armed' : 'disarmed'}</span>
          {Object.entries(cloud).map(([k, v]) => (
            <span key={k} className={`pill ${v.armed ? 'pill-ok' : v.present ? 'pill-ochre' : 'pill-muted'}`}
              title={`${v.role} · ${v.key_env}`}>{k} {v.armed ? 'armed' : v.present ? 'key set' : 'no key'}</span>
          ))}
          {Object.entries(write).map(([k, v]) => (
            <span key={k} className={`pill ${v.armed ? 'pill-ok' : 'pill-muted'}`}
              title={`${v.approval_kind} · ${v.env}`}>{k} {v.armed ? 'armed' : 'off'}</span>
          ))}
        </div>
      </div>

      {notice && (
        <div className={`alert${notice.tone === 'error' ? ' alert-error' : notice.tone === 'warn' ? ' alert-warn' : ''}`} style={{ marginBottom: 16 }}>
          <div className="alert-text">{notice.text}</div>
        </div>
      )}

      <div className="split-aside" style={{ marginBottom: 16 }}>
        <div className="card">
          <SectionHeader title="Video cost estimator" sub="fal per-second list rates (planning values)" />
          <div className="ms-grid">
            <div>
              <label htmlFor="ca-model">Model</label>
              <select id="ca-model" value={est.model} onChange={(e) => setEst({ ...est, model: e.target.value })}>
                {Object.entries(videoModels).map(([k, v]) => (
                  <option key={k} value={k}>{k} (${v.cost_per_s}/s)</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="ca-sec">Seconds</label>
              <input id="ca-sec" type="text" value={est.seconds} onChange={(e) => setEst({ ...est, seconds: e.target.value })} />
            </div>
          </div>
          <div className="ms-check">
            <input id="ca-audio" type="checkbox" checked={est.audio} onChange={(e) => setEst({ ...est, audio: e.target.checked })} />
            <label htmlFor="ca-audio" style={{ margin: 0 }}>with native audio (Kling)</label>
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={estimate}>Estimate cost</button>
          </div>
          {estOut && (
            <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>
              {estOut.model} · {estOut.seconds}s → <b>${estOut.cost_estimate ?? 'n/a'}</b>
            </div>
          )}
          {Object.keys(videoModels).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 2 }}>
                cost for {est.seconds}s across models
              </div>
              <MiniBars
                data={Object.entries(videoModels).map(([k, v]) => ({
                  label: k.replace(/-/g, ' '),
                  value: Math.round((est.audio && v.cost_per_s_audio ? v.cost_per_s_audio : v.cost_per_s) * (Number(est.seconds) || 0) * 100) / 100,
                }))}
                tone="var(--ochre)"
                valueFormat={(v) => `$${v}`}
              />
            </div>
          )}
        </div>

        <div className="card">
          <SectionHeader title="Request a write action" sub="Recorded approval before any publish/spend" />
          <label htmlFor="ca-kind">Kind</label>
          <select id="ca-kind" value={req.kind} onChange={(e) => setReq({ ...req, kind: e.target.value })}>
            <option value="social_publish">social_publish (public exposure)</option>
            <option value="ads_write">ads_write (real money)</option>
          </select>
          <label htmlFor="ca-payload">Payload (JSON)</label>
          <textarea id="ca-payload" value={req.payload} onChange={(e) => setReq({ ...req, payload: e.target.value })} />
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-primary" disabled={busy} onClick={createRequest}>Record Approval Request</button>
          </div>
        </div>
      </div>

      <div className="card">
        <SectionHeader title="Write-action approvals" sub={posture ? `${posture.pending} pending` : ''} />
        {approvals.length === 0 && (
          <EmptyState icon="🗂" title="No approval requests yet">
            Record a request above. Executing it will report exactly whether it ran — and why.
          </EmptyState>
        )}
        {approvals.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>ID</th><th>Kind</th><th>Status</th><th>Armed</th><th>Payload</th><th></th></tr>
            </thead>
            <tbody>
              {approvals.map((a) => (
                <tr key={a.id}>
                  <td className="mono-cell">{a.id}</td>
                  <td>{a.label}</td>
                  <td><span className={`pill ${a.status === 'approved' ? 'pill-ok' : a.status === 'rejected' ? 'pill-error' : 'pill-muted'}`}>{a.status}</span></td>
                  <td>{a.armed ? 'yes' : 'no'}</td>
                  <td className="mono-cell" style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{JSON.stringify(a.payload)}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {a.status === 'pending' && (
                      <>
                        <button className="btn btn-sm" onClick={() => decide(a.id, true)}>Approve</button>{' '}
                        <button className="btn btn-sm btn-ghost" onClick={() => decide(a.id, false)}>Reject</button>
                      </>
                    )}
                    <button className="btn btn-sm btn-ghost" onClick={() => execute(a.id)}>Execute</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
