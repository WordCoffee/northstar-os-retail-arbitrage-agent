import { PageLayout } from '../../components/Shared.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useState, useEffect } from 'react'

const API_BASE = '/api/v1'

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const err = new Error(`http_${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

function Pill({ children, className = '' }) {
  return <span className={`pill ${className}`}>{children}</span>
}

function Card({ title, children }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {children}
    </div>
  )
}

export default function ChromeConnect() {
  const { toast } = useToast()
  const [status, setStatus] = useState(null)
  const [jobs, setJobs] = useState([])
  const [adapters, setAdapters] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, j, a, al] = await Promise.all([
        apiFetch('/chromeconnect/status').catch(() => null),
        apiFetch('/chromeconnect/jobs').catch(() => ({ jobs: [] })),
        apiFetch('/chromeconnect/adapters').catch(() => ({ adapters: [] })),
        apiFetch('/chromeconnect/alerts').catch(() => ({ alerts: [] })),
      ])
      setStatus(s)
      setJobs(j.jobs || [])
      setAdapters(a.adapters || [])
      setAlerts(al.alerts || [])
      setLastRefresh(new Date().toISOString())
    } catch (e) {
      setError(e.message || 'Failed to load ChromeConnect data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const pause = async () => {
    try {
      await apiFetch('/chromeconnect/pause', { method: 'POST' })
      toast('Runner paused', 'info')
      refresh()
    } catch (e) { toast('Failed to pause', 'error') }
  }

  const resume = async () => {
    try {
      await apiFetch('/chromeconnect/resume', { method: 'POST' })
      toast('Runner resumed', 'info')
      refresh()
    } catch (e) { toast('Failed to resume', 'error') }
  }

  const ackAlert = async (idx) => {
    try {
      await apiFetch('/chromeconnect/alerts/acknowledge', { method: 'POST', body: JSON.stringify({ index: idx }) })
      refresh()
    } catch (e) { toast('Failed to acknowledge', 'error') }
  }

  if (loading && !status) {
    return (
      <PageLayout title="ChromeConnect" subtitle="Loading...">
        <div className="card"><p>Loading ChromeConnect status...</p></div>
      </PageLayout>
    )
  }

  if (error) {
    return (
      <PageLayout title="ChromeConnect" subtitle="Error">
        <div className="card" style={{ borderColor: 'var(--color-error)' }}>
          <p style={{ color: 'var(--color-error)' }}>{error}</p>
          <button onClick={refresh}>Retry</button>
        </div>
      </PageLayout>
    )
  }

  const runner = status?.runner || {}
  const jobCounts = status?.jobs || {}

  return (
    <PageLayout title="ChromeConnect" subtitle="Browser automation control room">
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={refresh}>Refresh</button>
        <button onClick={pause} disabled={runner.paused}>Pause</button>
        <button onClick={resume} disabled={!runner.paused}>Resume</button>
        {lastRefresh && <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--color-muted)' }}>
          Last: {lastRefresh.slice(0, 19).replace('T', ' ')}
        </span>}
      </div>

      {/* Runner Status */}
      <Card title="Runner Status">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 }}>
          <div><strong>State:</strong> {runner.running ? 'Running' : 'Stopped'}</div>
          <div><strong>Paused:</strong> {runner.paused ? 'Yes' : 'No'}</div>
          <div><strong>Current Job:</strong> {runner.current_job || 'None'}</div>
          <div><strong>Completed:</strong> {runner.jobs_completed || 0}</div>
          <div><strong>Failed:</strong> {runner.jobs_failed || 0}</div>
          <div><strong>Last Heartbeat:</strong> {runner.last_heartbeat ? runner.last_heartbeat.slice(0, 19).replace('T', ' ') : 'Never'}</div>
        </div>
      </Card>

      {/* Job Counts */}
      <Card title="Job Queue">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8 }}>
          <div><strong>Total:</strong> {jobCounts.total || 0}</div>
          <div><strong>Queued:</strong> {jobCounts.queued || 0}</div>
          <div><strong>Running:</strong> {jobCounts.running || 0}</div>
          <div><strong>Succeeded:</strong> {jobCounts.succeeded || 0}</div>
          <div><strong>Failed:</strong> {jobCounts.failed || 0}</div>
          <div><strong>Needs Owner:</strong> {jobCounts.needs_owner || 0}</div>
        </div>
        {jobs.length === 0 && <p style={{ color: 'var(--color-muted)', marginTop: 8 }}>No jobs in queue.</p>}
        {jobs.length > 0 && (
          <table style={{ width: '100%', marginTop: 8, fontSize: 13 }}>
            <thead><tr><th>ID</th><th>Site</th><th>Task</th><th>State</th></tr></thead>
            <tbody>
              {jobs.slice(0, 20).map(j => (
                <tr key={j.id}>
                  <td>{j.id?.slice(0, 8)}</td>
                  <td>{j.site}</td>
                  <td>{j.task_type}</td>
                  <td><Pill className={j.state === 'SUCCEEDED' ? 'pill-ok' : j.state === 'FAILED' ? 'pill-error' : 'pill-warn'}>{j.state}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Adapter Health */}
      <Card title="Adapter Health">
        {adapters.length === 0 && <p style={{ color: 'var(--color-muted)' }}>No adapters registered.</p>}
        {adapters.length > 0 && (
          <table style={{ width: '100%', fontSize: 13 }}>
            <thead><tr><th>Name</th><th>Origin</th><th>State</th><th>Success</th><th>Failed</th><th>Avg Time</th></tr></thead>
            <tbody>
              {adapters.map(a => (
                <tr key={a.name}>
                  <td>{a.name}</td>
                  <td>{a.origin}</td>
                  <td><Pill className={a.state === 'green' ? 'pill-ok' : a.state === 'degraded' ? 'pill-warn' : 'pill-error'}>{a.state}</Pill></td>
                  <td>{a.success_count || 0}</td>
                  <td>{a.failure_count || 0}</td>
                  <td>{a.avg_time_s || 0}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Alerts */}
      <Card title="Alerts">
        {alerts.length === 0 && <p style={{ color: 'var(--color-muted)' }}>No unacknowledged alerts.</p>}
        {alerts.map((a, i) => (
          <div key={i} style={{ padding: 8, marginBottom: 4, border: '1px solid var(--color-border)', borderRadius: 4 }}>
            <Pill className={a.severity === 'critical' ? 'pill-error' : a.severity === 'error' ? 'pill-error' : a.severity === 'warning' ? 'pill-warn' : 'pill-muted'}>{a.severity}</Pill>
            <span style={{ marginLeft: 8 }}>{a.message}</span>
            <button style={{ marginLeft: 8, fontSize: 11 }} onClick={() => ackAlert(i)}>Ack</button>
          </div>
        ))}
      </Card>

      {/* Needs You Queue */}
      {jobs.filter(j => j.state === 'NEEDS_OWNER').length > 0 && (
        <Card title="Needs You">
          {jobs.filter(j => j.state === 'NEEDS_OWNER').map(j => (
            <div key={j.id} style={{ padding: 8, marginBottom: 4, border: '1px solid var(--color-warn)', borderRadius: 4 }}>
              <strong>{j.id?.slice(0, 8)}</strong> — {j.site} — {j.needs_owner_reason}
              <button style={{ marginLeft: 8 }} onClick={async () => {
                try {
                  await apiFetch(`/chromeconnect/jobs/${j.id}/resolve`, { method: 'POST', body: JSON.stringify({}) })
                  toast('Resolved', 'info')
                  refresh()
                } catch (e) { toast('Failed to resolve', 'error') }
              }}>I signed in</button>
            </div>
          ))}
        </Card>
      )}
    </PageLayout>
  )
}
