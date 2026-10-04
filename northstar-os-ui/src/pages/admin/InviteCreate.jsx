import { PageLayout, DataTable, DataNotice, AuthorizationNote } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'
import { useSession } from '../../foundation/session.jsx'

// ═══ Real, org-scoped invite list (no invite code in the list read) ═══
function inviteStatus(inv) {
  const expired = inv.expires_at ? (new Date(inv.expires_at).getTime() < Date.now()) : false
  if (inv.status === 'pending' && expired) return { label: 'expired', tone: 'pill-warn' }
  if (inv.status === 'pending') return { label: 'pending', tone: 'pill-ochre' }
  if (inv.status === 'used') return { label: 'used', tone: 'pill-muted' }
  if (inv.status === 'revoked') return { label: 'revoked', tone: 'pill-warn' }
  return { label: inv.status || 'UNKNOWN', tone: 'pill-muted' }
}

export function FoundationInviteList({ reloadKey = 0 }) {
  const navigate = useNavigate()
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.invitesList()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [reloadKey])

  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }

  return (
    <div className="card" data-testid="bo-invite-list" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation invitation list</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading invitations…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in as a platform admin to read invitations.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Invitation list unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'email', label: 'Email' },
          { key: 'role', label: 'Role', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
          { key: 'status', label: 'Status', render: (v, row) => { const s = inviteStatus(row); return <span className={`pill ${s.tone}`} title="Invite lifecycle record — not an entitlement">{s.label}</span> } },
          { key: 'expires_at', label: 'Expires', render: (v) => v || 'UNKNOWN' },
          { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate(`/beta-ops/invites/${row.invite_id}`)}>Open</button> },
        ]} rows={st.items} />
      ) : (
        <p data-testid="bo-invite-empty" style={{ fontSize: 13 }}>No invitations issued for this organization yet. Honest empty state.</p>
      ))}
    </div>
  )
}

// Backend-valid invitation roles (foundation InviteService.issue).
const INVITE_ROLES = [
  { value: 'operator', label: 'Operator' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'analyst', label: 'Analyst' },
  { value: 'organization_admin', label: 'Organization Admin' },
  { value: 'organization_owner', label: 'Organization Owner' },
]

const ISSUE_ERRORS = {
  invalid_email: 'That email address is not valid.',
  invite_pending: 'An invitation is already pending for that email.',
  no_organization: 'No active organization context for this admin session — issuing is not possible.',
  invalid_role: 'That role is not permitted for invitations.',
}

// ACTIVATED (owner-approved, platform-admin only): issue a real single-use invite.
export default function InviteCreate() {
  const session = useSession()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('operator')
  const [confirmed, setConfirmed] = useState(false)
  const [state, setState] = useState({ phase: 'idle' })
  const [reloadKey, setReloadKey] = useState(0)

  const orgName = session.activeOrganizationId
    || (session.organizations && session.organizations[0] && session.organizations[0].name) || ''
  const hasOrg = !!session.activeOrganizationId

  const issue = async (e) => {
    e.preventDefault()
    if (!hasOrg) { setState({ phase: 'error', message: ISSUE_ERRORS.no_organization }); return }
    if (!email.trim()) { setState({ phase: 'error', message: ISSUE_ERRORS.invalid_email }); return }
    if (!confirmed) { setState({ phase: 'error', message: 'Confirm that this creates a real invitation.' }); return }
    setState({ phase: 'submitting' })
    const r = await settle(foundationApi.invite({ email: email.trim(), role }))
    if (r.ok) {
      setState({ phase: 'success', invite: r.value })
      setEmail(''); setConfirmed(false)
      setReloadKey(k => k + 1)
    } else {
      const status = r.error && r.error.status
      const code = r.error && r.error.code
      const phase = status === 401 ? 'auth' : status === 403 ? 'forbidden' : 'error'
      setState({ phase, message: ISSUE_ERRORS[code] || (r.error && r.error.message) || `Issue failed${code ? ` (${code})` : ''}.` })
    }
  }

  const canSubmit = hasOrg && !!email.trim() && confirmed && state.phase !== 'submitting'

  return (
    <PageLayout title="Create Invitation" subtitle="Issue an invitation for a new organization to the private beta.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Invitations are operator-issued">
        Issuing an invitation is a real, audited operator action (platform-admin only). The “Foundation invitation list” is a live read. The email send is stubbed — no email is sent — and the invite code is shown once to the issuing admin.
      </DataNotice>
      <FoundationInviteList reloadKey={reloadKey} />
      <div style={{ maxWidth: 520 }}>
        <div className="card" data-testid="bo-invite-issue">
          <div className="card-head">
            <h3 className="card-title">Issue an invitation</h3>
            <span className="pill pill-ochre">active · platform admin</span>
          </div>
          <AuthorizationNote
            title="Issuing an invitation"
            status="Active — platform-admin only"
            route="POST /api/v1/foundation/invites"
            permission="PERM_MANAGE_ORG"
            audit="invite.issue"
          >
            This creates a real, single-use invitation scoped to your active organization. It is audited (`invite.issue`; email domain only). No email is sent; share the code securely. All other write actions remain disabled.
          </AuthorizationNote>

          <div className="inline-flex" style={{ gap: 8, marginBottom: 12 }}>
            <span className="text-low" style={{ fontSize: 11 }}>Active organization</span>
            {hasOrg
              ? <span className="pill pill-muted" title="Invite is issued for this organization">{orgName || session.activeOrganizationId}</span>
              : <span className="pill pill-warn" title="No active organization — issuing will be denied">none — issuing unavailable</span>}
          </div>

          <form className="stack" style={{ gap: 14 }} onSubmit={issue}>
            <div className="field-group">
              <label className="label">Invitee email</label>
              <input className="field" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="person@example.com" />
            </div>
            <div className="field-group">
              <label className="label">Role</label>
              <select className="field" value={role} onChange={e => setRole(e.target.value)}>
                {INVITE_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </div>
            <div className="check-row">
              <input type="checkbox" id="invite-confirm" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
              <label htmlFor="invite-confirm">I understand this creates a real, single-use invitation that grants future access.</label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={!canSubmit}
                title={!hasOrg ? 'No active organization context' : !confirmed ? 'Confirm before issuing' : 'Issue a real single-use invitation'}
              >{state.phase === 'submitting' ? 'Issuing…' : 'Issue Invitation'}</button>
              {!hasOrg && <span className="text-low" style={{ fontSize: 11 }}>No active organization — issuing is denied.</span>}
              {hasOrg && !confirmed && <span className="text-low" style={{ fontSize: 11 }}>Confirmation required.</span>}
            </div>

            {state.phase === 'success' && state.invite && (
              <div className="alert" data-testid="bo-invite-success" style={{ marginBottom: 0 }}>
                <div className="alert-title"><span className="pill pill-ok">Issued</span> Invitation created</div>
                <div className="alert-text">
                  Invite for <strong>{state.invite.email}</strong> ({state.invite.role}) · status {state.invite.status}{state.invite.expires_at ? ` · expires ${state.invite.expires_at}` : ''}.
                  <div style={{ marginTop: 8 }}>
                    <span className="text-low" style={{ fontSize: 11 }}>Invite code (shown once — share securely):</span>
                    <div className="inline-flex" style={{ gap: 8, marginTop: 4 }}>
                      <span className="pill pill-muted" style={{ fontFamily: 'var(--font-mono)' }} data-testid="bo-invite-code">{state.invite.invite_code || 'UNKNOWN'}</span>
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => { try { navigator.clipboard.writeText(state.invite.invite_code || '') } catch { /* clipboard unavailable */ } }}>Copy</button>
                    </div>
                  </div>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Audit event <span style={{ fontFamily: 'var(--font-mono)' }}>invite.issue</span> recorded. The list above now shows this pending invite (without the code).</div>
                </div>
              </div>
            )}
            {state.phase === 'auth' && <span className="pill pill-unknown" data-testid="bo-invite-auth">Sign in required — session expired.</span>}
            {state.phase === 'forbidden' && <span className="pill pill-warn" data-testid="bo-invite-forbidden">Not permitted — platform-admin access required.</span>}
            {state.phase === 'error' && <span className="pill pill-warn" data-testid="bo-invite-error">{state.message}</span>}
          </form>
        </div>
      </div>
    </PageLayout>
  )
}

// Real invite status for a real invite id (matched from the org-scoped list).
function FoundationInviteDetail({ id, reloadKey = 0, onRecord }) {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.invitesList()).then(r => {
      if (!alive) return
      if (r.ok) {
        const item = (r.value.items || []).find(i => i.invite_id === id)
        setSt({ phase: item ? 'loaded' : 'not_found', item })
        if (onRecord) onRecord(item || null)
      } else {
        setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
        if (onRecord) onRecord(null)
      }
    })
    return () => { alive = false }
  }, [id, reloadKey])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'not_found' ? { l: 'not found', t: 'unknown' }
      : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
        : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
          : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="bo-invite-detail" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation invite record</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loaded' && st.item ? (
        <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
          <span className="pill pill-muted">{st.item.email}</span>
          <span className="pill pill-muted">role: {st.item.role || 'UNKNOWN'}</span>
          <span className={`pill ${inviteStatus(st.item).tone}`}>{inviteStatus(st.item).label}</span>
          <span className="pill pill-muted">expires: {st.item.expires_at || 'UNKNOWN'}</span>
        </div>
      ) : (
        <p style={{ fontSize: 13 }}>
          {st.phase === 'loading' ? 'Loading invite record…'
            : st.phase === 'not_found' ? 'No foundation invitation with this id — nothing is fabricated.'
              : st.phase === 'auth' ? 'Sign in as a platform admin to read this invite.'
                : `Read unavailable${st.error && st.error.code ? ` (${st.error.code})` : ''}.`}
        </p>
      )}
    </div>
  )
}

const REVOKE_ERRORS = {
  not_found: 'Invitation not found for your organization.',
}

// ACTIVATED (owner-approved, platform-admin only): revoke a pending invite.
function RevokeControl({ id, record, onDone }) {
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [state, setState] = useState({ phase: 'idle' })
  const status = record && record.status
  const canRevoke = !!record && status === 'pending'
  const blockReason = !record ? 'No matching invitation record — revoke unavailable.'
    : status === 'used' ? 'This invitation was already redeemed — it cannot be un-redeemed.'
      : status === 'revoked' ? 'This invitation is already revoked.'
        : null

  const submit = async (e) => {
    e.preventDefault()
    if (!canRevoke || !confirmed) return
    setState({ phase: 'submitting' })
    const r = await settle(foundationApi.inviteRevoke(id, reason.trim()))
    if (r.ok) {
      setState({ phase: 'success' })
      setConfirmed(false); setReason('')
      if (onDone) onDone()
    } else {
      const s = r.error && r.error.status, code = r.error && r.error.code
      setState({ phase: s === 401 ? 'auth' : s === 403 ? 'forbidden' : 'error',
        message: REVOKE_ERRORS[code] || (r.error && r.error.message) || `Revoke failed${code ? ` (${code})` : ''}.` })
    }
  }

  return (
    <div data-testid="bo-invite-revoke">
      <AuthorizationNote
        title="Revoke invitation"
        status="Active — platform-admin only"
        route="POST /api/v1/foundation/invites/{id}/revoke"
        permission="PERM_MANAGE_ORG"
        audit="invite.revoke"
      >
        Revoking invalidates a pending invitation for your organization. Audited as <span style={{ fontFamily: 'var(--font-mono)' }}>invite.revoke</span> with the reason. All other write actions remain disabled.
      </AuthorizationNote>
      {blockReason && <div className="text-low" style={{ fontSize: 12, marginBottom: 8 }}>{blockReason}</div>}
      <form className="stack" style={{ gap: 10 }} onSubmit={submit}>
        <div className="field-group">
          <label className="label">Reason (optional)</label>
          <input className="field" value={reason} onChange={e => setReason(e.target.value)} placeholder="Why this invite is being revoked" disabled={!canRevoke} />
        </div>
        <div className="check-row">
          <input type="checkbox" id="revoke-confirm" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!canRevoke} />
          <label htmlFor="revoke-confirm">I understand this revokes the invitation.</label>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn btn-danger"
            type="submit"
            disabled={!canRevoke || !confirmed || state.phase === 'submitting'}
            title={!canRevoke ? (blockReason || 'Revoke unavailable') : !confirmed ? 'Confirm before revoking' : 'Revoke this invitation'}
          >{state.phase === 'submitting' ? 'Revoking…' : 'Revoke Invitation'}</button>
          {state.phase === 'success' && <span className="pill pill-ok" data-testid="bo-revoke-success">Revoked — audit event invite.revoke recorded</span>}
          {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required — session expired.</span>}
          {state.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin access required.</span>}
          {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
        </div>
      </form>
    </div>
  )
}

export function InviteDetail() {
  const { id } = useParams()
  const inviteId = id || 'INV-2026-09-25-0192'
  const [record, setRecord] = useState(undefined)
  const [reloadKey, setReloadKey] = useState(0)
  return (
    <PageLayout title={`Invite #${inviteId}`} subtitle="Invitation details and status.">
      <BetaOpsNav />
      <div className="stack" style={{ gap: 20 }}>
        <FoundationInviteDetail id={inviteId} reloadKey={reloadKey} onRecord={setRecord} />
        <div className="evidence">
          <div className="evidence-header">
            <span className="pill pill-muted">sample</span>
            <span className="evidence-source">INV-2026-09-25-0192</span>
            <span className="evidence-freshness">Sent: 2026-09-25</span>
          </div>
          <p className="evidence-body">Sample invite preview (T2 Holdings LLC · Operator). Live invite state is shown in the record above.</p>
        </div>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Actions</h3>
            <span className="pill pill-muted">internal · logged</span>
          </div>
          <div className="stack" style={{ gap: 14 }}>
            <RevokeControl id={inviteId} record={record} onDone={() => setReloadKey(k => k + 1)} />
            <AuthorizationNote
              title="Reissue invitation"
              status="Out of scope — no backend route"
              audit="—"
            >
              There is no single reissue route. Reissue would compose revoke + issue; it stays disabled until that path is designed and separately authorized.
            </AuthorizationNote>
            <button className="btn btn-primary" disabled title="Sample surface — no invite is reissued">Reissue Invitation</button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
