import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate, useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real, org-scoped invite list (no invite code in the list read) ═══
function inviteStatus(inv) {
  const expired = inv.expires_at ? (new Date(inv.expires_at).getTime() < Date.now()) : false
  if (inv.status === 'pending' && expired) return { label: 'expired', tone: 'pill-warn' }
  if (inv.status === 'pending') return { label: 'pending', tone: 'pill-ochre' }
  if (inv.status === 'used') return { label: 'used', tone: 'pill-muted' }
  if (inv.status === 'revoked') return { label: 'revoked', tone: 'pill-warn' }
  return { label: inv.status || 'UNKNOWN', tone: 'pill-muted' }
}

export function FoundationInviteList() {
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
  }, [])

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

export default function InviteCreate() {
  return (
    <PageLayout title="Create Invitation" subtitle="Issue an invitation for a new organization to the private beta.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Invitations are operator-issued">
        Creating an invitation is an operator action and is logged. The “Foundation invitation list” is a live read. In the sample form below nothing is emailed or granted automatically; invite states are internal records, not entitlements.
      </DataNotice>
      <FoundationInviteList />
      <div style={{ maxWidth: 500 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Invitation Details</h3>
            <span className="pill pill-muted">sample</span>
          </div>
          <div className="stack" style={{ gap: 16 }}>
            <div className="field-group">
              <label className="label">Organization Name</label>
              <input className="field" placeholder="Enter organization name" />
            </div>
            <div className="field-group">
              <label className="label">Role</label>
              <select className="field">
                <option>Operator</option>
                <option>Platform Admin</option>
                <option>Customer</option>
              </select>
            </div>
            <div className="field-group">
              <label className="label">Cohort</label>
              <select className="field">
                <option>Cohort 1 — Q3</option>
                <option>Cohort 2 — Q4</option>
                <option>Cohort 3 — Q4</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button className="btn btn-primary" disabled title="Sample surface — no invite is sent">Send Invitation</button>
              <span className="text-low" style={{ fontSize: 11 }}>Disabled in sample mode — no invite is issued.</span>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

// Real invite status for a real invite id (matched from the org-scoped list).
function FoundationInviteDetail({ id }) {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.invitesList()).then(r => {
      if (!alive) return
      if (r.ok) {
        const item = (r.value.items || []).find(i => i.invite_id === id)
        setSt({ phase: item ? 'loaded' : 'not_found', item })
      } else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [id])
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

export function InviteDetail() {
  const { id } = useParams()
  return (
    <PageLayout title={`Invite #${id || 'INV-2026-09-25-0192'}`} subtitle="Invitation details and status.">
      <BetaOpsNav />
      <div className="stack" style={{ gap: 20 }}>
        <FoundationInviteDetail id={id || 'INV-2026-09-25-0192'} />
        <div className="evidence">
          <div className="evidence-header">
            <span className="pill pill-warn">Expired</span>
            <span className="evidence-source">INV-2026-09-25-0192</span>
            <span className="evidence-freshness">Sent: 2026-09-25</span>
          </div>
          <p className="evidence-body">Invitation to T2 Holdings LLC for Operator role. <span className="evidence-unknown">This invite has expired and requires reissuance before it can be accepted.</span></p>
        </div>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Actions</h3>
            <span className="pill pill-muted">internal · logged</span>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <button className="btn btn-primary" disabled title="Sample surface — no invite is reissued">Reissue Invitation</button>
            <button className="btn btn-danger" disabled title="Sample surface — no invite is revoked">Revoke</button>
            <div className="text-low" style={{ fontSize: 11 }}>Actions are disabled in sample mode. Reissuing or revoking is an operator action and is always logged.</div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
