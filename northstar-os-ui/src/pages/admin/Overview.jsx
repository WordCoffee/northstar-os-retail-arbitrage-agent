import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import signals, { settle } from '../../services/signals.js'

// ═══ Foundation admin dashboard (real, platform-admin read) ═══
function FoundationAdminDashboard({ onItems }) {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.adminDashboard()).then(r => {
      if (!alive) return
      if (r.ok) {
        const items = r.value.items || []
        setSt({ phase: 'loaded', items })
        if (onItems) onItems(items)
      } else {
        const code = r.error && r.error.status
        setSt({ phase: code === 401 ? 'auth' : code === 403 ? 'forbidden' : 'error', error: r.error })
      }
    })
    return () => { alive = false }
  }, [])

  const pill = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'forbidden' ? { l: 'platform-admin only', t: 'unknown' }
        : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
          : { l: 'live · foundation', t: 'muted' }

  let body = null
  if (st.phase === 'loading') body = <p style={{ fontSize: 13 }}>Loading foundation organization data…</p>
  else if (st.phase === 'auth') body = <p style={{ fontSize: 13 }}>Sign in as a platform admin to read the foundation dashboard.</p>
  else if (st.phase === 'forbidden') body = <p style={{ fontSize: 13 }}>Platform-admin role required for this read.</p>
  else if (st.phase === 'error') body = <p style={{ fontSize: 13 }}>Foundation dashboard unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>
  else {
    const items = st.items
    const byState = items.reduce((m, o) => { const k = o.lifecycle_state || 'unknown'; m[k] = (m[k] || 0) + 1; return m }, {})
    const openTickets = items.reduce((s, o) => s + (o.open_tickets || 0), 0)
    const blockers = items.reduce((s, o) => s + (o.blocker_tickets || 0), 0)
    const flagged = items.filter(o => (o.flags || []).length > 0)
    body = (
      <>
        <MetricTiles columns={4} metrics={[
          { label: 'Organizations', value: String(items.length) },
          { label: 'Open tickets', value: String(openTickets), tone: openTickets ? 'warn' : undefined },
          { label: 'Blocker tickets', value: String(blockers), tone: blockers ? 'error' : undefined },
          { label: 'Flagged orgs', value: String(flagged.length), tone: flagged.length ? 'warn' : undefined },
        ]} />
        {items.length > 0 && (
          <DataTable columns={[
            { key: 'organization_id', label: 'Org' },
            { key: 'organization_name', label: 'Name' },
            { key: 'plan_tier', label: 'Plan', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
            { key: 'lifecycle_state', label: 'Lifecycle', render: (v) => <span className={`pill ${v === 'active' ? 'pill-muted' : v === 'suspended' ? 'pill-warn' : 'pill-ochre'}`}>{v || 'UNKNOWN'}</span> },
            { key: 'seats_used', label: 'Seats', render: (v, row) => <span className="pill pill-muted">{v ?? '?'} / {row.seat_limit ?? '?'}</span> },
            { key: 'open_tickets', label: 'Tickets', render: (v) => <span className={`pill ${v ? 'pill-warn' : 'pill-muted'}`}>{v || 0}</span> },
            { key: 'flags', label: 'Flags', render: (v) => (v && v.length) ? <span className="inline-flex" style={{ gap: 4, flexWrap: 'wrap' }}>{v.map(f => <span key={f} className="pill pill-ochre" style={{ fontSize: 10 }}>{f}</span>)}</span> : <span className="pill pill-muted">none</span> },
          ]} rows={items} />
        )}
        {items.length === 0 && <p data-testid="bo-admin-empty" style={{ fontSize: 13 }}>No organizations in the foundation yet. Honest empty state.</p>}
        {items.length > 0 && (
          <div className="inline-flex" style={{ gap: 6, marginTop: 12 }}>
            {Object.entries(byState).map(([k, n]) => <span key={k} className="pill pill-muted">{k}: {n}</span>)}
          </div>
        )}
      </>
    )
  }

  return (
    <div className="card" data-testid="bo-admin-dashboard" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation admin dashboard</h3>
        <span className={`pill pill-${pill.t}`}>{pill.l}</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Live, platform-admin read of organization lifecycle, plan, seats, usage and ticket flags. Lifecycle state is a record, not an authorization.
      </p>
      {body}
    </div>
  )
}

// ═══ Real exceptions derived from dashboard rows ═══
function Exceptions({ items }) {
  const navigate = useNavigate()
  const flagged = items.filter(o => (o.flags || []).length > 0 || (o.blocker_tickets || 0) > 0)
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Exception Queue</h3>
        <span className={`pill ${flagged.length ? 'pill-clay' : 'pill-muted'}`}>{flagged.length} open · derived</span>
      </div>
      {flagged.length > 0 ? (
        <div className="stack" style={{ gap: 8 }}>
          {flagged.map((o, i) => (
            <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{o.organization_name || o.organization_id}</div>
                <div className="text-low" style={{ fontSize: 11 }}>{(o.flags || []).join(', ') || 'blocker tickets'} · lifecycle {o.lifecycle_state || 'UNKNOWN'}</div>
              </div>
              <button className="btn btn-sm" onClick={() => navigate(`/beta-ops/orgs/${o.organization_id}`)}>Open</button>
            </div>
          ))}
        </div>
      ) : <p data-testid="bo-exceptions-empty" style={{ fontSize: 13 }}>No exceptions flagged. Honest empty state.</p>}
    </div>
  )
}

// ═══ Real invite/account counts (local read) ═══
function InviteAccounts() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncAccounts()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error' })
    })
    return () => { alive = false }
  }, [])
  const s = st.phase === 'loaded' ? (st.value.summary || {}) : null
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Local accounts</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : 'live · local'}</span>
      </div>
      {s && (
        <MetricTiles columns={3} metrics={[
          { label: 'Users', value: String(s.users ?? 0) },
          { label: 'Sessions', value: String(s.sessions ?? 0) },
          { label: 'Invites', value: String(s.invites ?? 0) },
        ]} />
      )}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Account counts unavailable.</p>}
    </div>
  )
}

export default function BetaOpsOverview() {
  const navigate = useNavigate()
  const [items, setItems] = useState(null)
  return (
    <PageLayout
      title="Beta Operations"
      subtitle="Operating queue for the private-beta program — organizations, invites, cohorts, support, lifecycle, and exceptions."
      actions={<><button className="btn btn-sm" onClick={() => navigate('/beta-ops/reports')}>Export Report</button><button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/audit')}>Audit Log</button></>}
    >
      <BetaOpsNav />

      <DataNotice tone="internal" title="Beta Operations — live local reads">
        Organization lifecycle, support, audit, and invites are live reads. Cohorts are not connected (shown honestly on their page). Lifecycle actions are logged and require operator approval — none are autonomous.
      </DataNotice>

      <FoundationAdminDashboard onItems={setItems} />
      <InviteAccounts />
      {items && <Exceptions items={items} />}
    </PageLayout>
  )
}
