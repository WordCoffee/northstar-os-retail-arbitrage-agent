import { PageLayout, DataTable, DataNotice, AuthorizationNote } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

const ORG_PILL = { Active: 'pill-muted', Suspended: 'pill-warn', 'Pending Verification': 'pill-ochre' }

const ORGS = [
  { id: '0001', org: 'T2 Holdings LLC', plan: 'AutothinK', members: 2, status: 'Active' },
  { id: '0521', org: 'Northstar Labs', plan: 'Beta', members: 5, status: 'Active' },
  { id: '0838', org: 'Kirkland Ventures', plan: 'Starter', members: 1, status: 'Suspended' },
  { id: '0788', org: 'Word Coffee Co', plan: 'AutothinK', members: 3, status: 'Active' },
]

function useAdminDashboard() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.adminDashboard()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else {
        const code = r.error && r.error.status
        setSt({ phase: code === 401 ? 'auth' : code === 403 ? 'forbidden' : 'error', error: r.error })
      }
    })
    return () => { alive = false }
  }, [])
  return st
}

// Real organization roster from the foundation dashboard (platform-admin read).
function FoundationRoster() {
  const st = useAdminDashboard()
  const navigate = useNavigate()
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'forbidden' ? { l: 'platform-admin only', t: 'unknown' }
        : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
          : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="bo-roster" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation organization roster</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading organizations…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in as a platform admin to read organizations.</p>}
      {st.phase === 'forbidden' && <p style={{ fontSize: 13 }}>Platform-admin role required for this read.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Organization read unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'organization_id', label: 'ID' },
          { key: 'organization_name', label: 'Organization' },
          { key: 'plan_tier', label: 'Plan', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
          { key: 'seats_used', label: 'Members', render: (v, row) => <span className="pill pill-muted">{v ?? '?'} / {row.seat_limit ?? '?'}</span> },
          { key: 'invite_status', label: 'Invite', render: (v) => <span className="pill pill-muted">{v || 'none'}</span> },
          { key: 'lifecycle_state', label: 'Status', render: (v) => <span className={`pill ${v === 'active' ? 'pill-muted' : v === 'suspended' ? 'pill-warn' : 'pill-ochre'}`} title="Lifecycle record — not an authorization">{v || 'UNKNOWN'}</span> },
          { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate(`/beta-ops/orgs/${row.organization_id}`)}>Open</button> },
        ]} rows={st.items} />
      ) : (
        <p data-testid="bo-roster-empty" style={{ fontSize: 13 }}>No organizations in the foundation yet. Honest empty state — no organizations are fabricated.</p>
      ))}
    </div>
  )
}

// Local-only note draft. Posting an internal note is a real write and is NOT
// performed here — this keeps drafts in the browser and says so plainly.
function NoteDraft() {
  const [text, setText] = useState('')
  const [drafts, setDrafts] = useState([])
  const save = () => {
    if (!text.trim()) return
    setDrafts(d => [...d, { text: text.trim(), at: new Date().toISOString() }])
    setText('')
  }
  return (
    <div data-testid="org-note-draft" style={{ marginTop: 10 }}>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Draft internal note <span className="pill pill-muted" style={{ fontSize: 10 }}>local only · not posted</span></div>
      <textarea className="field" value={text} onChange={e => setText(e.target.value)} placeholder="Draft a note… it stays in this browser and is not sent." rows={2} />
      <div className="inline-flex" style={{ gap: 8, marginTop: 6, alignItems: 'center' }}>
        <button className="btn btn-sm btn-ghost" onClick={save}>Save local draft</button>
        <span className="pill pill-unknown" title="Drafting is local-only; posting is a real audited write requiring owner approval">not posted</span>
      </div>
      {drafts.length > 0 && (
        <div className="stack" style={{ gap: 4, marginTop: 8 }}>
          {drafts.map((d, i) => <div key={i} className="text-low" style={{ fontSize: 12 }}>draft · {d.at.slice(0, 19).replace('T', ' ')} — {d.text}</div>)}
        </div>
      )}
      <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
        Posting an internal note is a real write (POST /api/v1/foundation/admin/orgs/&lt;id&gt;/notes, PERM_PLATFORM_ADMIN, audit <span style={{ fontFamily: 'var(--font-mono)' }}>admin.note.add</span>) and requires owner approval. This composer never posts.
      </div>
    </div>
  )
}

// ═══ Activated lifecycle controls: suspend / resume (platform-admin only) ═══
const SUSPEND_ELIGIBLE = ['onboarding', 'active', 'paused', 'downgraded']
const RESUME_ELIGIBLE = ['suspended', 'paused']

function LifecycleAction({ id, action, label, eligible, blockReason, auditEvent, consequence, onDone }) {
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [state, setState] = useState({ phase: 'idle' })
  const submit = async (e) => {
    e.preventDefault()
    if (!eligible || !confirmed) return
    setState({ phase: 'submitting' })
    const r = await settle(foundationApi.adminOrgAction(id, action, { reason: reason.trim() || undefined }))
    if (r.ok) {
      setState({ phase: 'success', value: r.value })
      setConfirmed(false); setReason('')
      if (onDone) onDone()
    } else {
      const s = r.error && r.error.status, code = r.error && r.error.code
      setState({
        phase: s === 401 ? 'auth' : s === 403 ? 'forbidden' : s === 404 ? 'not_found' : 'error',
        message: (r.error && r.error.message) || `Action failed${code ? ` (${code})` : ''}.`,
      })
    }
  }
  return (
    <div data-testid={`org-lifecycle-${action}`}>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{label}</div>
      {!eligible && blockReason && <div className="text-low" style={{ fontSize: 12, marginBottom: 6 }}>{blockReason}</div>}
      {eligible && consequence && <div className="text-low" style={{ fontSize: 12, marginBottom: 6 }}>{consequence}</div>}
      <form className="stack" style={{ gap: 8 }} onSubmit={submit}>
        <input className="field" value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason (optional)" disabled={!eligible} />
        <div className="check-row">
          <input type="checkbox" id={`lc-${action}-confirm`} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!eligible} />
          <label htmlFor={`lc-${action}-confirm`}>I understand this {action === 'suspend' ? 'suspends' : 'resumes'} the organization.</label>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className={`btn ${action === 'suspend' ? 'btn-danger' : 'btn-primary'}`}
            type="submit"
            disabled={!eligible || !confirmed || state.phase === 'submitting'}
            title={!eligible ? (blockReason || 'Unavailable') : !confirmed ? 'Confirm before proceeding' : label}
          >{state.phase === 'submitting' ? (action === 'suspend' ? 'Suspending…' : 'Resuming…') : label}</button>
          {state.phase === 'success' && <span className="pill pill-ok" data-testid={`org-lifecycle-${action}-success`}>{action === 'suspend' ? 'Suspended' : 'Resumed'} — audit event {auditEvent} recorded</span>}
          {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required — session expired.</span>}
          {state.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin access required.</span>}
          {state.phase === 'not_found' && <span className="pill pill-warn">Organization not found.</span>}
          {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
        </div>
      </form>
    </div>
  )
}

// ═══ Activated grant/activate (platform-admin only; checklist-gated) ═══
function GrantControl({ id, record, onDone }) {
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [state, setState] = useState({ phase: 'idle' })

  const lc = record ? record.lifecycle_state : undefined
  const eligible = lc === 'invited' || lc === 'onboarding'
  const legal = record ? record.acceptance_complete : undefined
  const inviteStatus = record ? record.invite_status : undefined
  const inviteOk = !!(inviteStatus && inviteStatus !== 'none' && inviteStatus !== 'revoked')
  const mandatoryPass = eligible && legal === true && inviteOk
  const target = lc === 'invited' ? 'onboarding' : 'active'
  const auditEvent = target === 'onboarding' ? 'org.lifecycle.onboarding' : 'org.lifecycle.active'
  const label = lc === 'invited' ? 'Admit to onboarding' : 'Activate organization'

  const blockReason = !record ? 'No organization record loaded.'
    : !eligible ? (lc === 'active' ? 'Already active.'
      : (lc === 'suspended' || lc === 'paused') ? 'Use resume for suspended/paused organizations.'
        : (lc === 'cancelled' || lc === 'archived') ? 'Terminal state — activation is not available.'
          : `Not in an eligible onboarding state (${lc || 'UNKNOWN'}).`)
      : legal !== true ? 'Legal acceptance is missing or unknown — activation is blocked.'
        : !inviteOk ? 'No active invite record — activation is blocked.' : null

  const rows = [
    { label: 'Eligible lifecycle state', value: eligible, note: `state: ${lc || 'UNKNOWN'}` },
    { label: 'Legal acceptance complete', value: legal === true ? true : legal === false ? false : undefined },
    { label: 'Invite recorded (not revoked)', value: inviteOk ? true : (record && (inviteStatus === 'none' || inviteStatus === 'revoked')) ? false : undefined, note: `invite: ${inviteStatus || 'UNKNOWN'}` },
    { label: 'Onboarding checklist complete', value: record && record.onboarding_complete === true ? true : record && record.onboarding_complete === false ? false : undefined, informational: true },
    { label: 'Audit trail present', value: record && Array.isArray(record.audit) ? record.audit.length > 0 : undefined, informational: true },
  ]

  const submit = async (e) => {
    e.preventDefault()
    if (!mandatoryPass || !confirmed) return
    setState({ phase: 'submitting' })
    const r = await settle(foundationApi.adminOrgAction(id, 'grant', { reason: reason.trim() || undefined }))
    if (r.ok) {
      setState({ phase: 'success', value: r.value })
      setConfirmed(false); setReason('')
      if (onDone) onDone()
    } else {
      const s = r.error && r.error.status, code = r.error && r.error.code
      setState({
        phase: s === 401 ? 'auth' : s === 403 ? 'forbidden' : s === 404 ? 'not_found' : 'error',
        message: (r.error && r.error.message) || `Activation failed${code ? ` (${code})` : ''}.`,
      })
    }
  }

  const pill = (v) => v === true ? <span className="pill pill-muted">pass</span>
    : v === false ? <span className="pill pill-warn">fail</span>
      : <span className="pill pill-unknown">UNKNOWN</span>

  return (
    <div className="card" data-testid="org-grant" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Admission (grant / activate)</h3>
        <span className="pill pill-ochre">active · platform admin</span>
      </div>
      <AuthorizationNote
        title="Grant / activate organization"
        status="Active — platform-admin only"
        route="POST /api/v1/foundation/admin/orgs/{id}/grant"
        permission="PERM_PLATFORM_ADMIN"
        audit={auditEvent}
      >
        Admits an eligible onboarding organization to the private beta. It changes lifecycle state only — it does not change plan, billing, credits, or entitlements. Append-only audited. All other lifecycle actions remain disabled.
      </AuthorizationNote>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Admission checklist (read-only)</div>
      <div className="stack" style={{ gap: 4, marginBottom: 12 }}>
        {rows.map((r, i) => (
          <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--divider)' }}>
            <div>
              <span style={{ fontSize: 12 }}>{r.label}</span>
              {r.note && <span className="text-low" style={{ fontSize: 11 }}> · {r.note}</span>}
              {r.informational && <span className="text-low" style={{ fontSize: 10 }}> (informational)</span>}
            </div>
            {pill(r.value)}
          </div>
        ))}
      </div>
      {blockReason && <div className="text-low" style={{ fontSize: 12, marginBottom: 8 }}>{blockReason}</div>}
      <form className="stack" style={{ gap: 8 }} onSubmit={submit}>
        <input className="field" value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason (optional)" disabled={!mandatoryPass} />
        <div className="check-row">
          <input type="checkbox" id="grant-confirm" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!mandatoryPass} />
          <label htmlFor="grant-confirm">I understand this admits the organization to the private beta and activates access.</label>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={!mandatoryPass || !confirmed || state.phase === 'submitting'}
            title={!mandatoryPass ? (blockReason || 'Checklist incomplete') : !confirmed ? 'Confirm before activating' : label}
          >{state.phase === 'submitting' ? 'Activating…' : label}</button>
          {state.phase === 'success' && <span className="pill pill-ok" data-testid="org-grant-success">Activated → {target} — audit event {auditEvent} recorded</span>}
          {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required — session expired.</span>}
          {state.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin access required.</span>}
          {state.phase === 'not_found' && <span className="pill pill-warn">Organization not found.</span>}
          {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
        </div>
      </form>
    </div>
  )
}

function LifecycleControls({ id, state, onDone }) {
  const suspendEligible = SUSPEND_ELIGIBLE.includes(state)
  const resumeEligible = RESUME_ELIGIBLE.includes(state)
  const suspendBlock = !state ? 'No lifecycle record loaded.'
    : state === 'suspended' ? 'Already suspended.'
      : state === 'invited' ? 'Organization is not yet active (invite stage).'
        : (state === 'cancelled' || state === 'archived') ? 'Terminal state — suspend is not available.' : null
  const resumeBlock = !state ? 'No lifecycle record loaded.'
    : state === 'downgraded' ? 'Resume does not restore plan/entitlements; downgrade is unchanged.'
      : state === 'active' ? 'Already active.'
        : (state === 'invited' || state === 'cancelled' || state === 'archived') ? 'Resume is not available from this state.' : null
  return (
    <div className="card" data-testid="org-lifecycle-controls" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Lifecycle controls</h3>
        <span className="pill pill-ochre">active · platform admin</span>
      </div>
      <AuthorizationNote
        title="Lifecycle suspend / resume"
        status="Active — platform-admin only"
        route="POST /api/v1/foundation/admin/orgs/{id}/{suspend,resume}"
        permission="PERM_PLATFORM_ADMIN"
        audit="org.lifecycle.suspended / org.lifecycle.active"
      >
        Suspend sets the org inactive so the next authenticated request is denied. Resume restores access only — it does not restore plans, entitlements, jobs, or credits. Both are append-only audited. All other lifecycle actions remain disabled.
      </AuthorizationNote>
      <div className="grid-2" style={{ gap: 16 }}>
        <LifecycleAction id={id} action="suspend" label="Suspend organization" eligible={suspendEligible} blockReason={suspendBlock} auditEvent="org.lifecycle.suspended" consequence="Suspending immediately blocks the organization on its next request. Reversible via resume." onDone={onDone} />
        <LifecycleAction id={id} action="resume" label="Resume organization" eligible={resumeEligible} blockReason={resumeBlock} auditEvent="org.lifecycle.active" consequence="Resume restores access only; it does not restore plans, entitlements, jobs, or credits." onDone={onDone} />
      </div>
    </div>
  )
}

// Real organization detail (platform-admin read) for real org ids.
function FoundationOrgDetail({ id }) {
  const navigate = useNavigate()
  const [reloadKey, setReloadKey] = useState(0)
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.adminOrg(id)).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', org: r.value })
      else {
        const code = r.error && r.error.status
        setSt({ phase: code === 404 ? 'not_found' : code === 403 ? 'forbidden' : code === 401 ? 'auth' : 'error', error: r.error })
      }
    })
    return () => { alive = false }
  }, [id, reloadKey])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'not_found' ? { l: 'not found', t: 'unknown' }
      : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
        : st.phase === 'forbidden' ? { l: 'platform-admin only', t: 'unknown' }
          : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
            : { l: 'live · foundation', t: 'muted' }
  const o = st.phase === 'loaded' ? st.org : null
  return (
    <div className="card" data-testid="bo-org-detail" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation record</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loaded' && o ? (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <span className="pill pill-muted">{o.lifecycle_state || 'UNKNOWN'}</span>
            <span className="pill pill-muted">{o.plan_tier || 'UNKNOWN'}</span>
            <span className="pill pill-muted">sub: {o.subscription_status || 'none'}</span>
            <span className="pill pill-muted">invite: {o.invite_status || 'none'}</span>
            <span className="pill pill-muted">seats {o.seats_used ?? '?'} / {o.seat_limit ?? '?'}</span>
            <span className="pill pill-muted">jobs {o.monthly_jobs_used ?? '?'} / {o.max_jobs_per_month ?? '?'}</span>
            <span className="pill pill-muted">onboarding {o.onboarding_complete ? 'complete' : 'incomplete'}</span>
            <span className="pill pill-muted">acceptance {o.acceptance_complete ? 'complete' : 'incomplete'}</span>
          </div>
          <GrantControl id={id} record={o} onDone={() => setReloadKey(k => k + 1)} />
          <LifecycleControls id={id} state={o.lifecycle_state} onDone={() => setReloadKey(k => k + 1)} />
          {Array.isArray(o.notes) && o.notes.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Internal notes</div>
              {o.notes.map((n, i) => <div key={i} style={{ fontSize: 12 }}>{n.note || n.text || JSON.stringify(n)}</div>)}
            </div>
          )}
          <NoteDraft />
          {Array.isArray(o.lifecycle_history) && o.lifecycle_history.length > 0 && (
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Lifecycle history</div>
              {o.lifecycle_history.map((h, i) => <div key={i} style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{h.to_state || h.state || JSON.stringify(h)} · {h.created_at || h.occurred_at || ''}</div>)}
            </div>
          )}

          <div style={{ marginTop: 14 }}>
            <div className="card-head" style={{ marginBottom: 8 }}>
              <h4 style={{ fontSize: 13, color: 'var(--pine)' }}>Support tickets {Array.isArray(o.tickets) ? `(${o.tickets.length})` : ''}</h4>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/support')}>Open support ops</button>
            </div>
            {Array.isArray(o.tickets) && o.tickets.length > 0 ? (
              <DataTable columns={[
                { key: 'reference_id', label: 'Reference', render: (v, row) => v || row.id },
                { key: 'subject', label: 'Subject' },
                { key: 'category', label: 'Category', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${v === 'blocker' || v === 'high' ? 'pill-error' : v === 'low' ? 'pill-muted' : 'pill-warn'}`}>{v || 'UNKNOWN'}</span> },
                { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'resolved' || v === 'closed' ? 'pill-muted' : 'pill-warn'}`}>{v || 'UNKNOWN'}</span> },
              ]} rows={o.tickets} />
            ) : <p className="text-low" style={{ fontSize: 12 }}>No support tickets for this organization.</p>}
          </div>

          <div style={{ marginTop: 14 }}>
            <div className="card-head" style={{ marginBottom: 8 }}>
              <h4 style={{ fontSize: 13, color: 'var(--pine)' }}>Recent audit {Array.isArray(o.audit) ? `(${o.audit.length})` : ''}</h4>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/audit')}>Open audit log</button>
            </div>
            {Array.isArray(o.audit) && o.audit.length > 0 ? (
              <DataTable columns={[
                { key: 'occurred_at', label: 'When', render: (v) => v || 'UNKNOWN' },
                { key: 'action', label: 'Action', render: (v) => v || 'UNKNOWN' },
                { key: 'actor_user_id', label: 'Actor', render: (v) => v || 'UNKNOWN' },
                { key: 'result', label: 'Result', render: (v) => <span className={`pill ${v === 'denied' || v === 'failure' ? 'pill-warn' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
              ]} rows={o.audit} />
            ) : <p className="text-low" style={{ fontSize: 12 }}>No audit entries for this organization yet.</p>}
          </div>
        </>
      ) : (
        <p style={{ fontSize: 13 }}>
          {st.phase === 'loading' ? 'Loading foundation record…'
            : st.phase === 'not_found' ? 'No foundation organization with this id — nothing is fabricated.'
              : st.phase === 'auth' ? 'Sign in as a platform admin to read this organization.'
                : st.phase === 'forbidden' ? 'Platform-admin role required for this read.'
                  : `Read unavailable${st.error && st.error.code ? ` (${st.error.code})` : ''}.`}
        </p>
      )}
    </div>
  )
}

export default function OrgsList() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Organizations" subtitle="All registered organizations in the private beta.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Organization records are internal">
        The “Foundation organization roster” is a live platform-admin read. The sample roster below it is demonstration data. Lifecycle state is a record, not an authorization.
      </DataNotice>
      <FoundationRoster />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Sample roster (preview)</h3>
          <span className="pill pill-muted">{ORGS.length} orgs · sample</span>
        </div>
        <DataTable columns={[
          { key: 'id', label: 'ID', render: (v) => <span style={{ fontFamily: 'var(--font-mono)' }}>#{v}</span> },
          { key: 'org', label: 'Organization' },
          { key: 'plan', label: 'Plan' },
          { key: 'members', label: 'Members' },
          { key: 'status', label: 'Status', render: (v) => <span className={`pill ${ORG_PILL[v] || 'pill-muted'}`} title="Lifecycle record — not an authorization">{v}</span> },
          { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate(`/beta-ops/orgs/${row.id}`)}>Open</button> },
        ]} rows={ORGS} />
      </div>
    </PageLayout>
  )
}

export function OrgDetail() {
  const navigate = useNavigate()
  const { id } = useParams()
  return (
    <PageLayout title={`Organization #${id || '0001'}`} subtitle="Lifecycle record, plan, usage and membership.">
      <BetaOpsNav />
      <FoundationOrgDetail id={id || '0001'} />
      <div className="stack" style={{ gap: 20 }}>
        <div className="grid-2">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Profile</h3>
              <span className="pill pill-muted">internal · sample</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--divider)' }}><span className="text-low" style={{ width: 80 }}>ID</span><span style={{ fontFamily: 'var(--font-mono)' }}>#0001</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--divider)' }}><span className="text-low" style={{ width: 80 }}>Plan</span><span>AutothinK (Annual)</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}><span className="text-low" style={{ width: 80 }}>Status</span><span className="pill pill-muted" title="Lifecycle record — not an authorization">Active</span></div>
            </div>
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/orgs')}>Back to organizations</button>
              <button className="btn btn-sm" style={{ marginLeft: 8 }} onClick={() => navigate('/beta-ops/lifecycle')}>Lifecycle action</button>
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Membership</h3>
              <span className="pill pill-muted">2 members</span>
            </div>
            <DataTable columns={[{ key: 'name', label: 'User' }, { key: 'role', label: 'Role' }]} rows={[
              { name: 'Tyrone Johnson', role: 'Owner' },
              { name: 'Ops User', role: 'Operator' },
            ]} />
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
