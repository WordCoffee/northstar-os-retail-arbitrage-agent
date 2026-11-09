// Jobs & Schedules — 1C-04 durable execution UI.
// Reads REAL foundation data only; never fabricates metrics. Mutations use
// explicit buttons (no side effects on page load).
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../../ui.jsx'
import foundationApi from '../api.js'
import { useSession, hasPerm } from '../session.jsx'
import { StateMessage } from '../components/StatusPrimitives.jsx'

const JOB_TYPES = ['immediate_success', 'slow_success', 'transient_failure',
                   'permanent_failure', 'timeout', 'rate_limit',
                   'malformed_output', 'cancellable', 'cost_variance',
                   'needs_approval', 'fixture_reader', 'keyword_import']

export default function Jobs({ toast }) {
  const session = useSession()
  const canRun = hasPerm(session, 'request_refresh')
  const [state, setState] = useState({ status: 'loading' })
  const [posture, setPosture] = useState(null)
  const [jobs, setJobs] = useState([])
  const [schedules, setSchedules] = useState([])
  const [registry, setRegistry] = useState([])
  const [selected, setSelected] = useState(null)
  const [audit, setAudit] = useState([])
  const [schedulePosture, setSchedulePosture] = useState(null)
  const [form, setForm] = useState({ job_type: 'immediate_success', payload: '{}' })

  const load = async () => {
    setState({ status: 'loading' })
    try {
      const [p, j, s, r, sp] = await Promise.all([
        foundationApi.queuePosture(),
        foundationApi.durableJobs({ limit: 50 }),
        foundationApi.schedules(false),
        foundationApi.handlerRegistry(),
        foundationApi.schedulePosture(),
      ])
      setPosture(p); setJobs(j.items || []); setSchedules(s.items || [])
      setRegistry(r.handlers || []); setSchedulePosture(sp)
      setState({ status: 'ready' })
    } catch (e) {
      setState({ status: 'error', error: e })
    }
  }

  useEffect(() => { load() }, [])

  const select = async (id) => {
    try {
      const d = await foundationApi.durableJob(id)
      const a = await foundationApi.durableJobAudit(id)
      setSelected(d); setAudit(a.items || [])
    } catch (e) { toast(e.message, 'err') }
  }

  const submit = async () => {
    let payload = {}
    try { payload = JSON.parse(form.payload || '{}') } catch { payload = {} }
    try {
      const r = await foundationApi.createDurableJob({
        job_type: form.job_type, payload, payload_schema_version: '1.0',
      })
      toast(`Job ${r.id.slice(0, 8)} → ${r.state}`, 'ok')
      load()
    } catch (e) { toast(e.message, 'err') }
  }

  const cancel = async (id) => {
    try { await foundationApi.cancelDurableJob(id, 'operator cancelled from UI'); toast('Cancel requested', 'ok'); load() }
    catch (e) { toast(e.message, 'err') }
  }

  const retry = async (id) => {
    try { await foundationApi.retryDurableJob(id, 'operator retry from UI'); toast('Retry scheduled', 'ok'); load() }
    catch (e) { toast(e.message, 'err') }
  }

  const toggleSchedule = async (id, enabled) => {
    try {
      await (enabled ? foundationApi.scheduleEnable(id) : foundationApi.scheduleDisable(id))
      toast(enabled ? 'Schedule enabled' : 'Schedule disabled', 'ok'); load()
    } catch (e) { toast(e.message, 'err') }
  }

  if (state.status === 'loading') return <div className="page" data-testid="jobs-status"><StateMessage state="loading" /></div>
  if (state.status === 'error') return (
    <div className="page" data-testid="jobs-status"><StateMessage state="error" title="Backend unavailable"
      detail={state.error?.message} onRetry={load} /></div>
  )

  const blocked = (posture?.by_state && Object.entries(posture.by_state)
    .filter(([k]) => k.startsWith('blocked')).map(([k, v]) => `${k}=${v}`).join(' ')) || 'none'

  return (
    <div className="page" data-testid="jobs-status">
      <PageHead title="Jobs & Schedules"
        sub="Durable execution — queue, workers, retries, approvals, schedules"
        badges={[{ label: session.environment, tone: session.environment === 'sandbox' ? 'demo' : 'live' }]}
        right={<button className="btn" onClick={load}>Refresh</button>} />

      <div className="metric" style={{ marginTop: 14 }}>
        <Metric k="Queued" v={posture?.queued || 0} d="eligible for claim" />
        <Metric k="Leased" v={posture?.leased || 0} d="claimed by a worker" />
        <Metric k="Running" v={posture?.running || 0} d="executing locally" />
        <Metric k="Retry wait" v={posture?.retry_wait || 0} d="backoff" />
        <Metric k="Dead letter" v={posture?.dead_letter || 0} d="requires review" />
        <Metric k="Blocked" v={blocked} d="budget/provider/auth" />
      </div>

      <div className="stack" style={{ marginTop: 18 }}>
        {canRun && (
          <Card title="Submit a job" icon="plus">
            <div className="stack">
              <label className="field-label" htmlFor="job-type-select">Job type</label>
              <select id="job-type-select" className="field" value={form.job_type}
                      onChange={(e) => setForm({ ...form, job_type: e.target.value })}>
                {registry.map((r) => (
                  <option key={r.job_type} value={r.job_type}>{r.job_type}</option>
                ))}
                {JOB_TYPES.filter((t) => !registry.some((r) => r.job_type === t)).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <label className="field-label" htmlFor="job-payload">Payload (JSON)</label>
              <textarea id="job-payload" className="field" rows={3} value={form.payload}
                        onChange={(e) => setForm({ ...form, payload: e.target.value })} />
              <button className="btn btn-primary" onClick={submit}>Submit job</button>
              <div className="text-low" style={{ fontSize: 11 }}>
                Submission creates a queued job; it never executes in the request.
              </div>
            </div>
          </Card>
        )}

        <Card title="Jobs" icon="jobs">
          {jobs.length === 0 ? <StateMessage state="empty" title="No jobs yet" /> : (
            <table className="table">
              <thead><tr><th>Job</th><th>Type</th><th>State</th><th>Est.</th><th>Created</th><th>Actions</th></tr></thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td><button className="link" onClick={() => select(j.id)}>{j.id.slice(0, 8)}</button></td>
                    <td>{j.job_type}</td>
                    <td><span className={`status-pill ${j.state === 'succeeded' ? 'on' : j.state === 'dead_letter' || j.state === 'failed' ? 'warn' : ''}`}>{j.state}</span></td>
                    <td>{j.estimated_cost}</td>
                    <td>{j.created_at ? j.created_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                    <td>
                      {canRun && (j.state === 'queued' || j.state === 'retry_wait' || j.state === 'pending_approval') &&
                        <button className="btn btn-ghost" onClick={() => cancel(j.id)}>Cancel</button>}
                      {canRun && (j.state === 'failed' || j.state === 'dead_letter' || (j.state || '').startsWith('blocked')) &&
                        <button className="btn btn-ghost" onClick={() => retry(j.id)}>Retry</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {selected && (
          <Card title={`Job ${selected.id.slice(0, 8)} — audit timeline`} icon="audit">
            <div className="stack">
              {audit.length === 0 ? <StateMessage state="empty" title="No transitions" /> : audit.map((a) => (
                <div key={`${a.job_id}-${a.new_state}-${a.occurred_at}`} className="list-row">
                  <span className={`status-pill`}>{a.previous_state} → {a.new_state}</span>
                  <span style={{ flex: 1 }}>{a.reason}</span>
                  <span className="mono text-low">{a.actor} · {a.occurred_at ? a.occurred_at.slice(11, 19) : ''}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card title="Schedules" icon="clock">
          {schedules.length === 0 ? <StateMessage state="empty" title="No schedules" /> : (
            <table className="table">
              <thead><tr><th>Schedule</th><th>Type</th><th>Enabled</th><th>Next run</th><th>Actions</th></tr></thead>
              <tbody>
                {schedules.map((s) => (
                  <tr key={s.id}>
                    <td>{s.id.slice(0, 8)}</td>
                    <td>{s.cron_expression || (s.interval_seconds ? `every ${s.interval_seconds}s` : '—')}</td>
                    <td><span className={`status-pill ${s.enabled ? 'on' : 'off'}`}>{s.enabled ? 'enabled' : 'disabled'}</span></td>
                    <td>{s.next_run_at ? s.next_run_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                    <td>
                      {canRun && <button className="btn btn-ghost"
                        onClick={() => toggleSchedule(s.id, !s.enabled)}>{s.enabled ? 'Disable' : 'Enable'}</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="text-low" style={{ fontSize: 11 }}>
            Scheduler {schedulePosture ? `— ${schedulePosture.schedule_count} schedules, ${schedulePosture.enabled_count} enabled, ${schedulePosture.due_now} due now` : '— unavailable'}.
            Schedules enqueue jobs; they never execute them.
          </div>
        </Card>

        <Card title="Worker posture" icon="gauge">
          <div className="text-low" style={{ fontSize: 11 }}>
            Workers are org-scoped loopback processes that atomically claim queued
            jobs and execute registered LOCAL/fake handlers. Lease recovery
            reclaims expired leases. No remote system is contacted.
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
            {registry.length} registered handler types (local/fake only).
          </div>
        </Card>
      </div>
    </div>
  )
}