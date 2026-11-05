// Internal Beta Operations — platform-admin dashboard, org control, export.
// Wire-only to the Phase 1C admin API. Never exposes internal notes, secrets,
// tokens, provider credentials, or cross-org data to testers.
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../../ui.jsx'
import foundationApi from '../api.js'
import { useSession } from '../session.jsx'
import { StateMessage } from '../components/StatusPrimitives.jsx'

export default function BetaOps({ toast }) {
  const session = useSession()
  const [state, setState] = useState({ status: 'loading' })
  const [rows, setRows] = useState([])
  const [filters, setFilters] = useState({})
  const [detail, setDetail] = useState(null)
  const [notes, setNotes] = useState([])
  const [selectedOrg, setSelectedOrg] = useState(null)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('organization_owner')
  const [inviteResult, setInviteResult] = useState(null)
  const [inviting, setInviting] = useState(false)

  const createInvite = async () => {
    if (!inviteEmail) return
    setInviting(true); setInviteResult(null)
    try {
      const r = await foundationApi.invite({ email: inviteEmail.trim(), role: inviteRole })
      setInviteResult(r)
      setInviteEmail('')
      toast('Invite created', 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setInviting(false) }
  }

  const load = async (f = filters) => {
    setState({ status: 'loading' })
    try {
      const r = await foundationApi.adminDashboard(f)
      setRows(r.items || [])
      setState({ status: 'ready' })
    } catch (e) { setState({ status: 'error', error: e }) }
  }
  useEffect(() => { load({}) }, [])

  const open = async (orgId) => {
    try {
      const d = await foundationApi.adminOrg(orgId)
      setDetail(d); setNotes(d.notes || []); setSelectedOrg(orgId)
    } catch (e) { toast(e.message, 'err') }
  }

  const act = async (action, body = {}) => {
    if (!selectedOrg) return
    try { await foundationApi.adminOrgAction(selectedOrg, action, body); toast(`${action} ok`, 'ok'); open(selectedOrg); load() }
    catch (e) { toast(e.message, 'err') }
  }

  const addNote = async (note) => {
    if (!selectedOrg || !note) return
    try { await foundationApi.adminOrgNote(selectedOrg, note); toast('Note added', 'ok'); open(selectedOrg) }
    catch (e) { toast(e.message, 'err') }
  }

  const addOverride = async (feature, value) => {
    if (!selectedOrg) return
    try {
      await foundationApi.adminOrgOverride(selectedOrg, {
        feature, value, reason: 'operator override', permanent: true })
      toast('Override applied', 'ok'); load()
    } catch (e) { toast(e.message, 'err') }
  }

  const exportCsv = () => {
    const link = document.createElement('a')
    link.href = foundationApi.adminExportUrl
    link.download = 'tester-status.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast('Export started', 'ok')
  }

  if (state.status === 'loading') return <div className="page"><StateMessage state="loading" /></div>
  if (state.status === 'error') return (
    <div className="page"><StateMessage state="error" title="Beta Operations unavailable"
      detail={state.error?.message} onRetry={() => load({})} /></div>
  )

  return (
    <div className="page">
      <PageHead title="Beta Operations"
        sub="Internal tester dashboard — cohort control, lifecycle, support, export"
        badges={[{ label: 'internal', tone: 'ok' }]}
        right={<button className="btn" onClick={() => load({})}>Refresh</button>} />

      <div className="metric" style={{ marginTop: 14 }}>
        <Metric k="Organizations" v={rows.length} d={`cohort: ${rows.length} orgs`} />
        <Metric k="Active" v={rows.filter((r) => r.lifecycle_state === 'active').length} d="lifecycle active" />
        <Metric k="Suspended" v={rows.filter((r) => r.lifecycle_state === 'suspended').length} d="blocked" />
        <Metric k="Open tickets" v={rows.reduce((n, r) => n + (r.open_tickets || 0), 0)} d="across cohort" />
      </div>

      <div className="stack" style={{ marginTop: 16 }}>
        <Card title="Filters & export" icon="gauge">
          <div className="stack">
            <div className="field-row">
              <input aria-label="Filter by state" className="field" placeholder="state (active|suspended|onboarding|…)"
                     value={filters.state || ''}
                     onChange={(e) => setFilters({ ...filters, state: e.target.value })} />
              <input aria-label="Filter by tier" className="field" placeholder="tier (free|trial|pro|team)"
                     value={filters.tier || ''}
                     onChange={(e) => setFilters({ ...filters, tier: e.target.value })} />
              <button className="btn" onClick={() => load()}>Filter</button>
              <button className="btn" onClick={exportCsv}>Export CSV</button>
            </div>
            <div className="text-low" style={{ fontSize: 11 }}>
              Export uses the safe field set only — no secrets, card data, tokens, provider credentials, or cross-org data.
            </div>
          </div>
        </Card>

        <Card title="Invite tester" icon="mail">
          {inviteResult ? (
            <div className="stack">
              <div className="list-row">
                <span className="k">Email</span><span style={{ flex: 1 }}>{inviteResult.email}</span>
                <span className="k">Status</span><span className="status-pill on">{inviteResult.status || 'pending'}</span>
              </div>
              <div className="list-row">
                <span className="k">Code</span>
                <span className="mono" style={{ flex: 1 }}>{inviteResult.invite_code}</span>
                <span className="k">Expires</span><span>{inviteResult.expires_at ? String(inviteResult.expires_at).slice(0, 10) : '—'}</span>
              </div>
              <div className="text-low" style={{ fontSize: 11 }}>
                Share this code with the tester (only here — never logged). New tester signs up at
                <a href="#/beta-signup"> #/beta-signup</a> and accepts the beta documents.
              </div>
              <button className="btn btn-ghost" onClick={() => setInviteResult(null)}>Issue another</button>
            </div>
          ) : (
            <div className="stack">
              <div className="field-row">
                <input aria-label="Invite email" id="invite-email" className="field" placeholder="new-tester@example.com"
                       value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
                <select aria-label="Invite role" id="invite-role" className="field" value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}>
                  <option value="organization_owner">organization_owner</option>
                  <option value="organization_admin">organization_admin</option>
                  <option value="operator">operator</option>
                </select>
                <button className="btn" onClick={createInvite} disabled={inviting || !inviteEmail}>
                  {inviting ? 'Creating…' : 'Create invite'}
                </button>
              </div>
              <div className="text-low" style={{ fontSize: 11 }}>
                Issues a fresh invite code for this email via the existing admin invite endpoint.
              </div>
            </div>
          )}
        </Card>

        <Card title="Organizations" icon="team">
          {rows.length === 0 ? <StateMessage state="empty" title="No organizations match" /> : (
            <table className="table">
              <thead><tr><th>Org</th><th>State</th><th>Plan</th><th>Invite</th><th>Onboard</th><th>Usage</th><th>Seats</th><th>Tickets</th><th>Last activity</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.organization_id} onClick={() => open(r.organization_id)} style={{ cursor: 'pointer' }}>
                    <td>{r.organization_name}</td>
                    <td><span className={`status-pill ${r.lifecycle_state === 'active' ? 'on' : 'warn'}`}>{r.lifecycle_state}</span></td>
                    <td>{r.plan_tier}</td>
                    <td>{r.invite_status}</td>
                    <td>{r.onboarding_complete ? 'done' : 'todo'}</td>
                    <td>{`${r.monthly_jobs_used}/${r.max_jobs_per_month}`}</td>
                    <td>{`${r.seats_used}/${r.seat_limit}`}</td>
                    <td>{r.open_tickets}</td>
                    <td>{r.last_activity ? String(r.last_activity).slice(0, 10) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {detail && (
          <Card title={`${detail.organization_name} — control`} icon="account">
            <div className="stack">
              <div className="list-row">
                <span className="k">State</span><span style={{ flex: 1 }}>{detail.lifecycle_state}</span>
                <span className="k">Plan</span><span>{detail.plan?.tier}</span>
                <span className="k">Subscription</span><span>{detail.plan?.subscription}</span>
              </div>
              <div className="list-row">
                <span className="k">Usage</span><span style={{ flex: 1 }}>{`${detail.monthly_jobs_used}/${detail.max_jobs_per_month}`}</span>
                <span className="k">Seats</span><span>{`${detail.seats_used}/${detail.seat_limit}`}</span>
              </div>
              <div className="field-row">
                <button className="btn btn-ghost" onClick={() => act('grant', { reason: 'operator' })}>Grant</button>
                <button className="btn btn-ghost" onClick={() => act('resume', { reason: 'operator' })}>Resume</button>
                <button className="btn btn-ghost" onClick={() => act('suspend', { reason: 'operator' })}>Suspend</button>
                <button className="btn btn-ghost" onClick={() => act('downgrade', { reason: 'operator' })}>Downgrade</button>
                <button className="btn btn-ghost" onClick={() => act('cancel', { reason: 'operator' })}>Cancel</button>
                <button className="btn btn-ghost" onClick={() => act('archive', { reason: 'operator' })}>Archive</button>
              </div>
              <div className="field-row">
                <button className="btn btn-ghost" onClick={() => act('plan', { cohort: 'trial', reason: 'operator' })}>Plan: trial</button>
                <button className="btn btn-ghost" onClick={() => act('plan', { cohort: 'pro', reason: 'operator' })}>Plan: pro</button>
                <button className="btn btn-ghost" onClick={() => addOverride('export_enabled', true)}>Override export</button>
              </div>
              <input aria-label="Internal admin note" id="admin-note" className="field" placeholder="Internal note (never shown to testers)"
                     onKeyDown={(e) => e.key === 'Enter' && addNote(e.target.value)} />
              <div className="text-low" style={{ fontSize: 11 }}>
                Internal notes and audit history are visible only to platform admins.
              </div>
            </div>
          </Card>
        )}

        {notes.length > 0 && (
          <Card title="Internal notes" icon="audit">
            <div className="stack">
              {notes.map((n) => (
                <div key={n.id} className="list-row">
                  <span className="status-pill">internal</span>
                  <span style={{ flex: 1 }}>{n.note}</span>
                  <span className="mono text-low">{n.created_at ? String(n.created_at).slice(0, 16) : ''}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {detail && detail.lifecycle_history?.length > 0 && (
          <Card title="Lifecycle history" icon="audit">
            <div className="stack">
              {detail.lifecycle_history.map((h) => (
                <div key={`${h.new_state}-${h.occurred_at}`} className="list-row">
                  <span className="status-pill">{h.previous_state} → {h.new_state}</span>
                  <span style={{ flex: 1 }}>{h.reason}</span>
                  <span className="mono text-low">{(h.actor || '').slice(0, 8)} · {(h.occurred_at || '').slice(0, 16)}</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}