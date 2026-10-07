import { PageLayout, MetricTiles, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'
import { useSession } from '../../foundation/session.jsx'

// ═══ Real account condition (foundation entitlements + plan/usage) ═══
function AccountLive() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [ent, plan] = await Promise.all([
        settle(foundationApi.entitlements()),
        settle(foundationApi.planUsage()),
      ])
      if (alive) setSt({ phase: 'loaded', ent, plan })
    })()
    return () => { alive = false }
  }, [])
  const ent = st.ent && st.ent.ok ? st.ent.value : null
  const plan = st.plan && st.plan.ok ? st.plan.value : null
  const anyAuth = st.phase === 'loaded' && [st.ent, st.plan].every(r => r && !r.ok && r.error && r.error.status === 401)
  const noOrg = plan && plan.error === 'no_organization'
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : anyAuth ? { l: 'sign-in required', t: 'unknown' }
      : noOrg ? { l: 'no organization', t: 'unknown' }
        : (ent || plan) ? { l: 'live · foundation', t: 'muted' }
          : { l: 'unavailable', t: 'unknown' }
  const seats = plan && plan.seats ? plan.seats : null
  return (
    <div className="card" data-testid="acct-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Account condition</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading account condition…</p>}
      {anyAuth && <p style={{ fontSize: 13 }}>Sign in to view your account condition.</p>}
      {noOrg && <p style={{ fontSize: 13 }}>No organization is associated with this session.</p>}
      {st.phase === 'loaded' && !anyAuth && !noOrg && (
        <>
          <MetricTiles metrics={[
            { label: 'Lifecycle', value: (plan && plan.lifecycle_state) || 'UNKNOWN' },
            { label: 'Plan tier', value: (ent && ent.tier) || (plan && plan.tier) || 'UNKNOWN' },
            { label: 'Seats', value: seats && seats.limit != null ? `${seats.used} / ${seats.limit}` : 'UNKNOWN' },
            { label: 'Export', value: ent ? (ent.export_enabled ? 'enabled' : 'disabled') : 'UNKNOWN' },
          ]} columns={4} />
          <div className="text-low" style={{ fontSize: 11 }}>Lifecycle state is a server-side record; a suspended/cancelled state blocks access on the next request.</div>
        </>
      )}
    </div>
  )
}

export default function AccountStatus() {
  const session = useSession()
  return (
    <PageLayout title="Account Status" subtitle="Your current account condition and entitlements.">
      <DataNotice tone="internal" title="Live account condition and session identity">
        “Account condition” is a live foundation read; the session identity below is the current resolved session. No fabricated account details.
      </DataNotice>

      <AccountLive />

      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Session identity</h3>
          <span className="pill pill-muted">live · session</span>
        </div>
        <DataTable columns={[
          { key: 'field', label: 'Field' },
          { key: 'value', label: 'Value' },
        ]} rows={[
          { field: 'User', value: session.userId || 'UNKNOWN' },
          { field: 'Role', value: session.role || 'UNKNOWN' },
          { field: 'Active organization', value: session.activeOrganizationId || 'none' },
          { field: 'Environment', value: session.environment || 'UNKNOWN' },
          { field: 'UI mode', value: session.uiMode || 'UNKNOWN' },
        ]} />
      </div>
    </PageLayout>
  )
}