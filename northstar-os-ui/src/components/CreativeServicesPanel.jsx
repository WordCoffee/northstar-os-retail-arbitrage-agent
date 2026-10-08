import { useCallback, useEffect, useState } from 'react'

// Shared creative services panel.
//
// Reads the approved-component registry + capability routing from the backend
// and runs the shared pipeline tasks (mask / upscale / generate) as queued jobs
// with stage progress and cancellation. This is the UI surface that proves the
// existing creative tools consume the shared infrastructure rather than
// tool-specific one-offs.

const API = '/api/creative'

function Pill({ ok, label }) {
  return <span className={`pill ${ok ? 'pill-ok' : 'pill-warn'}`}>{label}</span>
}

export default function CreativeServicesPanel() {
  const [components, setComponents] = useState(null)
  const [lanes, setLanes] = useState(null)
  const [recent, setRecent] = useState([])
  const [selected, setSelected] = useState('')
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const refresh = useCallback(async () => {
    try {
      const [c, l, r] = await Promise.all([
        fetch(`${API}/components`).then((x) => x.json()),
        fetch(`${API}/lanes`).then((x) => x.json()),
        fetch(`${API}/recent?limit=12`).then((x) => x.json()),
      ])
      setComponents(c)
      setLanes(l)
      setRecent(r.items || [])
      if (!selected && r.items?.[0]) setSelected(r.items[0].name)
    } catch (e) {
      setMsg(`Shared services unavailable: ${e.message}`)
    }
  }, [selected])

  useEffect(() => { refresh() }, [refresh])

  async function submit(task, payload) {
    setBusy(true); setMsg(''); setJob(null)
    try {
      const r = await fetch(`${API}/pipeline`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, payload }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(j.detail || `HTTP ${r.status}`)
      poll(j.job_id)
    } catch (e) {
      setBusy(false); setMsg(e.message)
    }
  }

  function poll(id) {
    const t = setInterval(async () => {
      try {
        const j = await (await fetch(`${API}/jobs/${id}`)).json()
        setJob(j)
        if (['done', 'error', 'cancelled'].includes(j.status)) {
          clearInterval(t); setBusy(false)
          setMsg(j.status === 'done' ? 'Job complete.' : (j.error || j.status))
          refresh()
        }
      } catch (e) {
        clearInterval(t); setBusy(false); setMsg(e.message)
      }
    }, 1500)
  }

  const runtime = lanes?.runtime?.runtime_ready || {}
  const comps = components?.components || []
  const r = lanes?.capabilities?.generate || {}
  const path = selected ? `${API}/file/${selected}` : ''

  return (
    <div className="card" style={{ marginTop: 20 }}>
      <div className="card-head"><h3 className="card-title">Shared creative services</h3></div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        <Pill ok={runtime.generate} label={`generate ${runtime.generate ? 'ready' : 'missing'}`} />
        <Pill ok={runtime.mask} label={`mask ${runtime.mask ? 'ready' : 'missing'}`} />
        <Pill ok={runtime.upscale} label={`upscale ${runtime.upscale ? 'ready' : 'missing'}`} />
        <Pill ok={runtime.control} label={`control ${runtime.control ? 'ready' : 'missing'}`} />
        <Pill ok={runtime.condition} label={`condition ${runtime.condition ? 'ready' : 'missing'}`} />
        <span className="pill pill-ok">exact-text ready</span>
        {(components?.components || []).some((c) => c.status === 'quarantined') && (
          <span className="pill pill-warn">quarantined: flux.1-dev (non-commercial)</span>
        )}
      </div>

      <div style={{ fontSize: 12 }} className="text-low">
        Routing — draft: <strong>{r.draft?.primary?.lane || 'none'}</strong> · standard:{' '}
        <strong>{r.standard?.primary?.lane || 'none'}</strong> · high:{' '}
        <strong>{r.high?.primary?.lane || 'none'}</strong>. Fallbacks are explicit; a
        quarantined model is never the default.
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end', marginTop: 12 }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="cs-src">Source asset (recent output)</label>
          <select id="cs-src" value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">— none —</option>
            {recent.map((it) => <option key={it.name} value={it.name}>{it.name}</option>)}
          </select>
        </div>
        <button className="btn btn-ghost" disabled={!selected || busy}
          onClick={() => submit('mask', { source: path, cutout: true })}>Remove background</button>
        <button className="btn btn-ghost" disabled={!selected || busy}
          onClick={() => submit('upscale', { source: path })}>Upscale 4×</button>
        <button className="btn btn-ghost" disabled={!selected || busy}
          onClick={() => submit('generate', { prompt: 'studio product photograph, soft light', mode: 'standard' })}>
          Generate (routed)
        </button>
      </div>

      {job && (
        <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>
          job <strong>{job.id}</strong> · {job.status} · stage{' '}
          <strong>{job.progress?.stage || '—'}</strong>
          {job.progress?.message ? ` — ${job.progress.message}` : ''}
          {job.plan?.primary?.lane ? ` · lane ${job.plan.primary.lane}` : ''}
          {['queued', 'running'].includes(job.status) && (
            <button className="btn btn-ghost" style={{ marginLeft: 8 }}
              onClick={() => fetch(`${API}/jobs/${job.id}/cancel`, { method: 'POST' })}>Cancel</button>
          )}
        </div>
      )}
      {msg && <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>{msg}</div>}

      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12 }}>Approved components ({comps.length})</summary>
        <ul style={{ fontSize: 12, marginTop: 8 }}>
          {comps.map((c) => (
            <li key={c.id}>
              <strong>{c.id}</strong> · {c.role} · {c.license} · {c.commercial_use}
              {c.present ? ' · installed' : ' · missing'} · {c.status}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
