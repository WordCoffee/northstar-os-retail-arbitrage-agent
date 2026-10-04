import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
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

// Real organization detail (platform-admin read) for real org ids.
function FoundationOrgDetail({ id }) {
  const navigate = useNavigate()
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
  }, [id])
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
          {Array.isArray(o.notes) && o.notes.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Internal notes</div>
              {o.notes.map((n, i) => <div key={i} style={{ fontSize: 12 }}>{n.note || n.text || JSON.stringify(n)}</div>)}
            </div>
          )}
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
