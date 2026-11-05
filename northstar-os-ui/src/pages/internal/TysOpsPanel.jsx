// Tys Assistant — live operator panel.
//
// Read-only: it polls the admin state, the task list and memory stats. It never
// submits, runs or cancels a task. Every value comes from the API; an unavailable
// endpoint is shown as unavailable, never as a fabricated row.
import { useCallback, useEffect, useRef, useState } from 'react'
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

export default function TysOpsPanel() {
  const [state, setState] = useState(null)
  const [tasks, setTasks] = useState([])
  const [memory, setMemory] = useState(null)
  const [memoryError, setMemoryError] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
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
    } catch (err) {
      setError(`${err.status ? `HTTP ${err.status}: ` : ''}${err.message}`)
    } finally {
      setLoading(false)
      inFlight.current = false
    }
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
  return (
    <div className="card" data-testid="tys-ops" style={{ marginBottom: 20, padding: 18 }}>
      <div className="card-head">
        <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="cpu" size={16} /> Tys Assistant
        </h3>
        <span className={`pill ${error ? 'pill-warn' : 'pill-ok'}`}
              aria-live="polite"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {!error && !loading && <span className="tys-live-dot" aria-hidden="true" />}
          {loading ? 'connecting…' : error ? 'unavailable' : 'live'}
        </span>
      </div>
      <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Read-only operator view: queue, lanes, task progress and long-term memory. Polls every 5 s.
      </div>

      {error && (
        <div className="card" style={{ padding: 12, borderColor: 'var(--warn)' }} data-testid="tys-error">
          <strong style={{ fontSize: 12 }}>Tys API unavailable.</strong>{' '}
          <span className="text-low" style={{ fontSize: 12 }}>{error}</span>
        </div>
      )}

      {state && (
        <>
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
