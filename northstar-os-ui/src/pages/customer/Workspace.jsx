import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'services', label: 'Entitled Services' },
  { id: 'plan', label: 'Plan & Usage' },
  { id: 'activity', label: 'What Changed' },
]

// Capability map — what the suite offers (NOT entitlement-derived).
const SERVICES = [
  { name: 'SourceScout', route: '/product-finder', status: 'Available', tone: 'forest' },
  { name: 'Golden Goose Finder', route: '/golden-goose', status: 'Available', tone: 'forest' },
  { name: 'Profitability Dashboard', route: '/profitability', status: 'Available', tone: 'forest' },
  { name: 'Commerce Ops', route: '/commerce-ops', status: 'Available', tone: 'forest' },
  { name: 'Monitoring', route: '/monitoring', status: 'Available', tone: 'forest' },
  { name: 'Listing Guardian', route: '/listings', status: 'Limited', tone: 'ochre' },
  { name: 'Keyword Tracker', route: '/keyword-tracker', status: 'Available', tone: 'forest' },
]

// ═══ Real organization entitlements + plan/usage (foundation read) ═══
function useAccount() {
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
  return { phase: st.phase, ent, plan, anyAuth }
}

function StateLine({ phase, anyAuth, children }) {
  if (phase === 'loading') return <p style={{ fontSize: 13 }}>Loading…</p>
  if (anyAuth) return <p style={{ fontSize: 13 }}>Sign in to view your workspace.</p>
  return children
}

export default function CustomerWorkspace() {
  const navigate = useNavigate()
  const location = useLocation()
  const a = useAccount()
  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'
  const ent = a.ent
  const plan = a.plan
  const usage = plan && plan.usage ? plan.usage : null
  const seats = plan && plan.seats ? plan.seats : null

  return (
    <PageLayout
      title="Customer Workspace"
      subtitle="Your NorthstarOS briefing — entitlements, usage, service access, and account state."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/plan')}>View Plan Details</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/support')}>Contact Support</button>
      </>}
    >
      <DataNotice tone="internal" title="Live entitlements — no fabricated figures">
        Entitlements, lifecycle, usage, and seats are live, organization-scoped reads. Empty/unknown is shown honestly; no sample usage or task figures are invented.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/customer-workspace" />

      {view === 'overview' && (
        <div className="subview">
          <StateLine phase={a.phase} anyAuth={a.anyAuth}>
            <MetricTiles metrics={[
              { label: 'Plan tier', value: (ent && ent.tier) || (plan && plan.tier) || 'UNKNOWN' },
              { label: 'Lifecycle', value: (plan && plan.lifecycle_state) || 'UNKNOWN' },
              { label: 'Jobs this period', value: usage && usage.max_jobs_per_month != null ? `${usage.monthly_jobs_used} / ${usage.max_jobs_per_month}` : 'UNKNOWN' },
              { label: 'Seats', value: seats && seats.limit != null ? `${seats.used} / ${seats.limit}` : 'UNKNOWN' },
            ]} columns={4} />
            <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
              <span className={`pill ${ent && ent.export_enabled ? 'pill-muted' : 'pill-unknown'}`}>export: {ent ? (ent.export_enabled ? 'enabled' : 'disabled') : 'UNKNOWN'}</span>
              <span className="pill pill-muted">advanced reports: {ent ? (ent.advanced_reports ? 'yes' : 'no') : 'UNKNOWN'}</span>
              <span className="pill pill-muted">support: {ent ? (ent.support_level || 'none') : 'UNKNOWN'}</span>
            </div>
            <p className="text-low" style={{ fontSize: 11, marginTop: 10 }}>No per-user task backend is connected, so no open-tasks list is shown.</p>
          </StateLine>
        </div>
      )}

      {view === 'services' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Entitled Services</h3>
              <span className="pill pill-muted">capability map · not entitlement-derived</span>
            </div>
            {SERVICES.map(s => (
              <div key={s.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Launch the {s.name} room</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className={`pill pill-${s.tone}`}>{s.status}</span>
                  <button className="btn btn-sm btn-ghost" onClick={() => navigate(s.route)}>Open</button>
                </div>
              </div>
            ))}
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Service availability is a capability map. Your actual entitlements are shown on the Overview and Plan tabs.</div>
          </div>
        </div>
      )}

      {view === 'plan' && (
        <div className="subview">
          <StateLine phase={a.phase} anyAuth={a.anyAuth}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Plan &amp; Usage</h3>
                <span className="pill pill-muted">{plan ? (plan.tier || 'UNKNOWN') : 'UNKNOWN'}</span>
              </div>
              <DataTable columns={[
                { key: 'label', label: 'Item' },
                { key: 'value', label: 'Value' },
              ]} rows={[
                { label: 'Lifecycle state', value: (plan && plan.lifecycle_state) || 'UNKNOWN' },
                { label: 'Jobs this period', value: usage && usage.max_jobs_per_month != null ? `${usage.monthly_jobs_used} / ${usage.max_jobs_per_month}` : 'UNKNOWN' },
                { label: 'Period', value: (usage && usage.period) || 'UNKNOWN' },
                { label: 'Seats', value: seats && seats.limit != null ? `${seats.used} / ${seats.limit}` : 'UNKNOWN' },
                { label: 'Reset rule', value: (plan && plan.reset_rule) || 'UNKNOWN' },
              ]} />
            </div>
          </StateLine>
        </div>
      )}

      {view === 'activity' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">What Changed</h3>
              <span className="pill pill-muted">not connected</span>
            </div>
            <p style={{ fontSize: 13 }}>No customer activity feed backend is connected. Honest empty state.</p>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
