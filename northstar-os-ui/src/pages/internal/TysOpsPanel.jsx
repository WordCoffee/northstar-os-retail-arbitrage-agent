// Tys Assistant — live operator panel.
//
// It polls the admin state, the task list and memory stats. The only write it
// performs is the two operator switches (assistant, then its eyes); it never
// submits, runs or cancels a task. Every value comes from the API; an unavailable
// endpoint is shown as unavailable, never as a fabricated row.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { getDevSession } from '../../foundation/api.js'

const POLL_MS = 5000

function devHeaders() {
  if (!import.meta.env.DEV) return {}
  try {
    const s = getDevSession()
    if (!s || !s.userId) return {}
    return { 'X-User-Id': s.userId, 'X-Org-Id': s.orgId || 'org-t2',
             'X-Role': s.role || 'operator' }
  } catch { return {} }
}

async function getJSON(path) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { Accept: 'application/json', ...devHeaders() },
  })
  if (!res.ok) {
    let detail = null
    try { detail = (await res.json()).detail } catch { /* non-JSON */ }
    const err = new Error((detail && (detail.message || detail.code)) || `HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...devHeaders() },
    body: JSON.stringify(body || {}),
  })
  if (!res.ok) {
    let detail = null
    try { detail = (await res.json()).detail } catch { /* non-JSON */ }
    const err = new Error((detail && (detail.message || detail.code)) || `HTTP ${res.status}`)
    err.status = res.status
    err.code = detail && detail.code
    throw err
  }
  return res.json()
}

const STATUS_TONE = {
  done: 'pill-ok', running: 'pill-warn', paused: 'pill-warn',
  queued: 'pill-muted', cancelled: 'pill-muted', blocked: 'pill-err',
  interrupted: 'pill-warn',
}

function LanePill({ name, lane }) {
  const ok = lane && lane.available
  return (
    <span className={`pill ${ok ? 'pill-ok' : 'pill-warn'}`}
          title={(lane && lane.detail) || ''}>
      {name}{ok ? '' : ' · offline'}
    </span>
  )
}

function QueueCard({ state }) {
  const queue = (state && state.queue) || {}
  const counts = queue.by_status || {}
  return (
    <div className="card" style={{ padding: 16 }} data-testid="tys-queue">
      <div className="card-head">
        <h3 className="card-title">Queue</h3>
        <span className="pill pill-muted">{queue.total || 0} total</span>
      </div>
      <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
        {Object.entries(counts).map(([status, n]) => (
          <span key={status} className={`pill ${STATUS_TONE[status] || 'pill-muted'}`}>
            {status}: {n}
          </span>
        ))}
        {Object.keys(counts).length === 0 && <span className="text-low">No tasks recorded.</span>}
      </div>
      {queue.next && (
        <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
          next: <code>{queue.next}</code>
        </div>
      )}
    </div>
  )
}

function MemoryCard({ memory, error }) {
  return (
    <div className="card" style={{ padding: 16 }} data-testid="tys-memory">
      <div className="card-head">
        <h3 className="card-title">Long-term memory</h3>
        <span className={`pill ${memory && memory.semantic ? 'pill-ok' : 'pill-warn'}`}>
          {memory && memory.semantic ? 'semantic' : 'hashed fallback'}
        </span>
      </div>
      {error ? <div className="text-low" style={{ fontSize: 12 }}>{error}</div> : (
        <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
          <span className="pill pill-muted">{memory?.chunks ?? 0} chunks</span>
          <span className="pill pill-muted">{memory?.chunk_tokens ?? 0} tokens</span>
          <span className="pill pill-muted">{memory?.live_facts ?? 0} live facts</span>
        </div>
      )}
      {memory && memory.semantic_reason && (
        <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
          fallback reason: {memory.semantic_reason}
        </div>
      )}
    </div>
  )
}

function TaskRow({ task }) {
  const steps = Array.isArray(task.steps) ? task.steps.length : 0
  const cursor = Number(task.cursor || 0)
  const pct = steps > 0 ? Math.min(100, Math.round((cursor / steps) * 100))
    : (task.status === 'done' ? 100 : 0)
  const blockers = Array.isArray(task.blockers) ? task.blockers : []
  return (
    <details className="card" style={{ padding: 14 }} data-testid="tys-task">
      <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className={`pill ${STATUS_TONE[task.status] || 'pill-muted'}`}>{task.status}</span>
          <strong style={{ fontSize: 13, flex: 1, minWidth: 180 }}>{task.title || task.id}</strong>
          <span className="text-low" style={{ fontSize: 11 }}>{cursor}/{steps} steps</span>
          {blockers.length > 0 && <span className="pill pill-warn">{blockers.length} blocker(s)</span>}
        </div>
        <div style={{ height: 4, background: 'var(--divider)', borderRadius: 2, marginTop: 8 }}>
          <div style={{ height: 4, width: `${pct}%`, background: 'var(--pine-deep)',
                        borderRadius: 2, transition: 'width 300ms ease' }} />
        </div>
      </summary>
      <div style={{ marginTop: 10, fontSize: 12 }}>
        <div className="text-low" style={{ marginBottom: 6 }}>{task.objective}</div>
        <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
          {task.next_action && <span className="pill pill-muted">next: {task.next_action}</span>}
          {task.owner && <span className="pill pill-muted">owner: {task.owner}</span>}
          {task.stop_reason && <span className="pill pill-muted">stop: {task.stop_reason}</span>}
        </div>
        {blockers.length > 0 && (
          <ul style={{ margin: '6px 0 0 18px', padding: 0 }}>
            {blockers.slice(0, 3).map((b, i) => (
              <li key={i} className="text-low">{b.code}: {String(b.detail || '').slice(0, 160)}</li>
            ))}
          </ul>
        )}
      </div>
    </details>
  )
}

function SwitchesCard({ switches, eyes, busy, error, onToggle }) {
  const assistantOn = Boolean(switches && switches.assistant)
  const visionOn = Boolean(switches && switches.vision)
  const counts = (eyes && eyes.counts) || {}
  const last = (eyes && eyes.last) || null
  return (
    <div className="card" style={{ padding: 16 }} data-testid="tys-switches">
      <div className="card-head">
        <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="eye" size={16} /> Tys Assistant &amp; its eyes
        </h3>
        <span className="pill pill-muted">{visionOn ? 'eyes on' : 'eyes off'}</span>
      </div>

      <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
        <button
          type="button"
          className={`pill ${assistantOn ? 'pill-ok' : 'pill-muted'}`}
          aria-pressed={assistantOn}
          disabled={busy}
          onClick={() => onToggle({ assistant: !assistantOn })}
          data-testid="tys-toggle-assistant"
          title="Turn Tys Assistant itself on or off"
        >
          Tys Assistant: {assistantOn ? 'on' : 'off'}
        </button>
        <button
          type="button"
          className={`pill ${visionOn ? 'pill-ok' : 'pill-muted'}`}
          aria-pressed={visionOn}
          disabled={busy || !assistantOn}
          onClick={() => onToggle({ vision: !visionOn })}
          data-testid="tys-toggle-vision"
          title={assistantOn
            ? 'Turn Ty’s Vision (the eyes) on or off — a cobalt ring appears while it is on'
            : 'Enable Tys Assistant first: the eyes are part of it'}
          style={visionOn ? { boxShadow: '0 0 0 1px var(--spark, #2f6fed)' } : undefined}
        >
          Ty’s Vision: {visionOn ? 'on' : 'off'}
        </button>
      </div>

      {error && (
        <div className="text-low" style={{ fontSize: 12, color: 'var(--warn)', marginBottom: 8 }}>
          {error}
        </div>
      )}

      <div className="text-low" style={{ fontSize: 11, lineHeight: 1.5 }}>
        The eyes judge appearance — renders, product shots, screenshots — and never
        claim a pass they did not see. ARM: {visionOn ? 'a cobalt ring sits around the screen.' : 'no ring, no looking.'}
      </div>

      {eyes && eyes.model && (
        <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
          model {eyes.model} · looks {eyes.looks_recorded || 0}
          {Object.keys(counts).length > 0 && (
            <> · {Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(' · ')}</>
          )}
        </div>
      )}

      {last && (
        <div style={{ marginTop: 8, fontSize: 12 }} data-testid="tys-eye-last">
          <strong>My eyes, last look:</strong>{' '}
          {last.status === 'on_track' && 'on track.'}
          {last.status === 'off_track' && (
            <>off goal — {((last.reasons || []).map(r => String(r).replace(/[. ]+$/, '')).join('; ')
              || last.reason || 'constraint not met')}.
              {' '}That is what I fix next.</>
          )}
          {last.status === 'unverified' && (
            <>could not look ({last.reason || 'no verdict'}). Unverified, not a pass.</>
          )}
          <span className="text-low" style={{ fontSize: 11 }}>
            {' '}{last.image_path ? String(last.image_path).split(/[\\/]/).pop() : ''}
          </span>
        </div>
      )}
    </div>
  )
}

function VoiceCard({ identity }) {
  if (!identity) return null
  const learning = identity.learning || {}
  const eyes = identity.eyes || {}
  return (
    <div className="card" style={{ padding: 16 }} data-testid="tys-voice">
      <div className="card-head">
        <h3 className="card-title">In its own words</h3>
        <span className="pill pill-muted">{eyes.enabled ? 'eyes on' : 'eyes off'}</span>
      </div>
      <p style={{ fontSize: 12, lineHeight: 1.6, marginTop: 0 }}>{identity.persona}</p>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>
        Judges: {(eyes.contract?.judges || []).join(', ')}. Does not: {(eyes.contract?.does_not || []).join(', ')}.
        Unavailable reads as <strong>{eyes.contract?.on_unavailable || 'unverified'}</strong>.
      </div>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>How it learns (REA)</div>
      <div className="stack" style={{ gap: 4 }}>
        {Object.entries(learning).map(([key, lane]) => (
          <div key={key} style={{ fontSize: 11, lineHeight: 1.5 }}>
            <span className="pill pill-muted" style={{ marginRight: 6 }}>{key}</span>
            <code>{lane.tool}</code>
            <span className="text-low"> — {lane.use}. Never: {lane.never}.</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TysOpsPanel() {
  const [state, setState] = useState(null)
  const [tasks, setTasks] = useState([])
  const [memory, setMemory] = useState(null)
  const [memoryError, setMemoryError] = useState('')
  const [switches, setSwitches] = useState(null)
  const [eyes, setEyes] = useState(null)
  const [switchBusy, setSwitchBusy] = useState(false)
  const [switchError, setSwitchError] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  // A panel that keeps showing yesterday's queue counts under a green pill is
  // worse than one that admits it lost the feed. lastGoodAt is the last
  // SUCCESSFUL read; tick forces a re-render each poll so the age keeps moving
  // even when the error string is unchanged (React bails out of identical sets).
  const [lastGoodAt, setLastGoodAt] = useState(0)
  const [tick, setTick] = useState(0)
  const inFlight = useRef(false)

  const load = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const [s, t] = await Promise.all([
        getJSON('/api/admin/tys/state'),
        getJSON('/api/admin/tys/tasks?limit=8'),
      ])
      setState(s)
      setTasks((t && t.tasks) || [])
      setError('')
      setLastGoodAt(Date.now())
    } catch (err) {
      setError(`${err.status ? `HTTP ${err.status}: ` : ''}${err.message}`)
    } finally {
      setLoading(false)
      setTick(n => n + 1)
      inFlight.current = false
    }
    try {
      const sw = await getJSON('/api/admin/tys/switches')
      setSwitches(sw.switches || null)
      setEyes(sw.eyes || null)
    } catch { /* the state card already reports an unavailable API */ }
    try {
      setMemory(await getJSON('/api/admin/tys/memory/stats?account=operator'))
      setMemoryError('')
    } catch (err) {
      setMemoryError(`memory unavailable: ${err.message}`)
    }
  }, [])

  useEffect(() => {
    let alive = true
    const tick = () => { if (alive) load() }
    tick()
    const timer = setInterval(tick, POLL_MS)
    return () => { alive = false; clearInterval(timer) }
  }, [load])

  const lanes = (state && state.lanes) || {}

  const ageMs = useMemo(
    () => (lastGoodAt ? Date.now() - lastGoodAt : null),
    [lastGoodAt, tick])
  const stale = ageMs !== null && ageMs > POLL_MS * 3
  const statusLabel = loading ? 'connecting…' : error ? 'unavailable' : stale ? 'stale' : 'live'
  const statusTone = error || stale ? 'pill-warn' : 'pill-ok'
  const ageLabel = ageMs === null
    ? 'no successful read yet'
    : ageMs < 2000 ? 'updated just now'
      : ageMs < 60000 ? `updated ${Math.round(ageMs / 1000)}s ago`
        : `updated ${Math.round(ageMs / 60000)}m ago`

  const toggle = useCallback(async (patch) => {
    setSwitchBusy(true)
    setSwitchError('')
    try {
      const res = await postJSON('/api/admin/tys/switches', patch)
      setSwitches(res.switches || null)
      setEyes(res.eyes || null)
    } catch (err) {
      setSwitchError(err.code === 'vision_requires_assistant'
        ? 'Enable Tys Assistant before enabling its eyes.'
        : `${err.status ? `HTTP ${err.status}: ` : ''}${err.message}`)
    } finally {
      setSwitchBusy(false)
    }
  }, [])
  return (
    <div className="card" data-testid="tys-ops" style={{ marginBottom: 20, padding: 18 }}>
      <div className="card-head">
        <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="cpu" size={16} /> Tys Assistant
        </h3>
        <span className={`pill ${statusTone}`}
              aria-live="polite"
              data-testid="tys-status-pill"
              title={stale ? 'The last successful read is older than three polls.' : ''}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {!error && !stale && !loading && <span className="tys-live-dot" aria-hidden="true" />}
          {statusLabel}
        </span>
      </div>
      <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Operator view: switches, queue, lanes, task progress and long-term memory. Polls every 5 s.
        <span data-testid="tys-age" style={{ marginLeft: 6 }}>· {ageLabel}</span>
      </div>

      {error && (
        <div className="card" style={{ padding: 12, borderColor: 'var(--warn)' }} data-testid="tys-error">
          <strong style={{ fontSize: 12 }}>Tys API unavailable.</strong>{' '}
          <span className="text-low" style={{ fontSize: 12 }}>{error}</span>
        </div>
      )}

      {state && (
        <>
          <div style={{ marginBottom: 12 }}>
            <SwitchesCard
              switches={switches || state.switches}
              eyes={eyes || state.eyes}
              busy={switchBusy}
              error={switchError}
              onToggle={toggle}
            />
          </div>
          <div className="grid-3" style={{ gap: 12, marginBottom: 12 }}>
            <QueueCard state={state} />
            <MemoryCard memory={memory} error={memoryError} />
            <div className="card" style={{ padding: 16 }}>
              <div className="card-head"><h3 className="card-title">Orchestrator</h3></div>
              <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
                <span className={`pill ${state.orchestrator?.available ? 'pill-ok' : 'pill-warn'}`}>
                  {state.orchestrator?.model || 'unknown'}
                </span>
                <span className="pill pill-muted">{state.identity?.name || 'Tys'}</span>
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <VoiceCard identity={state.identity} />
          </div>

          <div style={{ marginBottom: 12 }}>
            <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Lanes</div>
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
              {Object.entries(lanes).map(([name, lane]) => (
                <LanePill key={name} name={name} lane={lane} />
              ))}
            </div>
          </div>

          <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Recent work orders</div>
          <div className="stack" style={{ gap: 8 }}>
            {tasks.length === 0 && <div className="text-low" style={{ fontSize: 12 }}>No work orders recorded.</div>}
            {tasks.map(task => <TaskRow key={task.id} task={task} />)}
          </div>
        </>
      )}
      {!state && !loading && !error && (
        <div className="text-low" style={{ fontSize: 12 }}>No state returned.</div>
      )}
    </div>
  )
}
