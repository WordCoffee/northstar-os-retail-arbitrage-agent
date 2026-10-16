import { PageLayout, MetricTiles, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real plan & usage (organization-scoped, role-aware foundation read) ═══
function FoundationPlanUsage() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [plan, ent] = await Promise.all([
        settle(foundationApi.planUsage()),
        settle(foundationApi.entitlements()),
      ])
      if (alive) setSt({ phase: 'loaded', plan, ent })
    })()
    return () => { alive = false }
  }, [])

  const plan = st.plan && st.plan.ok ? st.plan.value : null
  const ent = st.ent && st.ent.ok ? st.ent.value : null
  const anyAuth = st.phase === 'loaded' && [st.plan, st.ent].every(r => r && !r.ok && r.error && r.error.status === 401)
  const noOrg = plan && plan.error === 'no_organization'

  const badge = !st.phase || st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : anyAuth ? { l: 'sign-in required', t: 'unknown' }
      : noOrg ? { l: 'no organization', t: 'unknown' }
        : (plan || ent) ? { l: 'live · foundation', t: 'muted' }
          : { l: 'unavailable', t: 'unknown' }

  const usage = plan && plan.usage ? plan.usage : null
  const seats = plan && plan.seats ? plan.seats : null

  return (
    <div className="card" data-testid="pu-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Your plan &amp; usage</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading plan and usage…</p>}
      {anyAuth && <p style={{ fontSize: 13 }}>Sign in to view your plan and usage.</p>}
      {noOrg && <p style={{ fontSize: 13 }}>No organization is associated with this session.</p>}
      {!st.phase && <p style={{ fontSize: 13 }}>Loading…</p>}
      {st.phase === 'loaded' && !anyAuth && !noOrg && (
        <>
          {plan && plan.role_restricted && <p className="text-low" style={{ fontSize: 12, marginBottom: 8 }}>{plan.note}</p>}
          <MetricTiles columns={4} metrics={[
            { label: 'Plan tier', value: (plan && plan.tier) || (ent && ent.tier) || 'UNKNOWN' },
            { label: 'Jobs this period', value: usage && usage.max_jobs_per_month != null ? `${usage.monthly_jobs_used} / ${usage.max_jobs_per_month}` : 'UNKNOWN', sub: usage && usage.period ? `period ${usage.period}` : undefined },
            { label: 'Seats', value: seats && seats.limit != null ? `${seats.used} / ${seats.limit}` : 'UNKNOWN' },
            { label: 'Export', value: ent ? (ent.export_enabled ? 'enabled' : 'disabled') : 'UNKNOWN' },
          ]} />
          {plan && plan.reset_rule && <div className="text-low" style={{ fontSize: 12 }}>{plan.reset_rule}</div>}
          {ent && (
            <div className="inline-flex" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
              <span className="pill pill-muted">advanced reports: {ent.advanced_reports ? 'yes' : 'no'}</span>
              <span className="pill pill-muted">support: {ent.support_level || 'none'}</span>
              <span className="pill pill-muted">overrides: {ent.override_allowed ? 'allowed' : 'not allowed'}</span>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function PlanUsage() {
  return (
    <PageLayout title="Plan & Usage" subtitle="Track your usage against your entitlement.">
      <DataNotice tone="internal" title="Plan &amp; usage is a live foundation read">
        The “Your plan &amp; usage” card is a live, organization-scoped read from the foundation service. No usage-metering or billing backend is connected, so no usage or invoice figure is shown below; — no billing backend is connected yet.
      </DataNotice>

      <FoundationPlanUsage />

      <div className="card" data-testid="pu-usage-note">
        <div className="card-head">
          <h3 className="card-title">Usage Meter</h3>
          <span className="pill pill-muted">no metering backend</span>
        </div>
        <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
          No usage-metering backend is connected, so no usage figure is shown. The card above reads your plan from the
          foundation service; an unavailable read there says so rather than substituting a number.
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <h3 className="card-title">Billing History</h3>
          <span className="pill pill-muted">no billing backend</span>
        </div>
        <p className="text-low" style={{ fontSize: 12 }}>
          No billing backend is connected, so there is no invoice history to show. Honest empty state — no invented rows.
        </p>
      </div>
    </PageLayout>
  )
}