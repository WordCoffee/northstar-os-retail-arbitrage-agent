import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate } from 'react-router-dom'

const SEV_PILL = { Critical: 'pill-error', High: 'pill-warn', Medium: 'pill-ochre' }
const STATE_PILL = { Active: 'pill-muted', Suspended: 'pill-warn', 'Pending Verification': 'pill-ochre', Complete: 'pill-muted' }
const ACTIVITY_PILL = { Error: 'pill-error', Warn: 'pill-warn', Ok: 'pill-muted' }

const EXCEPTIONS = [
  { id: 'EX-01', org: '#0838', title: 'Organization lifecycle blocked (suspended)', severity: 'Critical', age: '2d', route: '/beta-ops/lifecycle', action: 'Review lifecycle' },
  { id: 'EX-02', org: '#0192', title: 'Invite INV-2026-09-25-0192 expired', severity: 'High', age: '2d', route: '/beta-ops/invites/INV-2026-09-25-0192', action: 'Reissue invite' },
]

const ACTIVITY = [
  { date: '2026-09-26', event: 'Org suspended', detail: '#0838 lifecycle blocked', status: 'Error' },
  { date: '2026-09-25', event: 'Invite expired', detail: 'INV-2026-09-25-0192', status: 'Warn' },
  { date: '2026-09-25', event: 'Cohort created', detail: 'Cohort 3 — Q4', status: 'Ok' },
]

const READINESS = [
  { label: 'Verified Orgs', value: '10', tone: 'pill-muted' },
  { label: 'Suspended', value: '2', tone: 'pill-warn' },
  { label: 'Pending Verification', value: '2', tone: 'pill-ochre' },
  { label: 'Avg Readiness Score', value: '78%', tone: 'pill-muted' },
]

const COHORTS = [
  { name: 'Cohort 1 — Q3 Onboarding', orgs: '5', date: '2026-07-15', status: 'Complete' },
  { name: 'Cohort 2 — Q3 Expansion', orgs: '4', date: '2026-08-20', status: 'Complete' },
  { name: 'Cohort 3 — Q4 Pilot', orgs: '3', date: '2026-09-25', status: 'Active' },
]

const SUPPORT = [
  { id: '#4471', org: '#0838', type: 'Lifecycle', status: 'Open' },
  { id: '#4470', org: '#0521', type: 'Access', status: 'Open' },
  { id: '#4469', org: '#0788', type: 'Billing', status: 'Resolved' },
  { id: '#4468', org: '#0412', type: 'Integration', status: 'Resolved' },
]

export default function BetaOpsOverview() {
  const navigate = useNavigate()

  return (
    <PageLayout
      title="Beta Operations"
      subtitle="Operating queue for the private-beta program — organizations, invites, cohorts, support, lifecycle, and exceptions."
      actions={<><button className="btn btn-sm" onClick={() => navigate('/beta-ops/reports')}>Export Report</button><button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/audit')}>Audit Log</button></>}
    >
      <BetaOpsNav />

      <DataNotice tone="internal" title="Beta Operations — internal operating queue">
        Organizations, invites, cohorts, and support records are sample/internal until the beta backend is connected. Lifecycle actions are logged and require operator approval — no action here is autonomous. Not cross-org data for testers.
      </DataNotice>

      <MetricTiles columns={4} metrics={[
        { label: 'Organizations', value: '14', sub: '4 in beta · sample' },
        { label: 'Pending Invites', value: '7', sub: 'Unaccepted' },
        { label: 'Cohorts', value: '3', sub: '1 active' },
        { label: 'Exceptions', value: String(EXCEPTIONS.length), sub: 'Action required' },
      ]} />

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <h3 className="card-title">Exception Queue</h3>
          <span className="pill pill-clay">{EXCEPTIONS.length} open</span>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {EXCEPTIONS.map((e, i) => (
            <div key={e.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderBottom: i < EXCEPTIONS.length - 1 ? '1px solid var(--divider)' : 'none' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{e.title}</div>
                <div className="text-low" style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{e.id} · org {e.org} · {e.age} open</div>
              </div>
              <span className={`pill ${SEV_PILL[e.severity]}`}>{e.severity}</span>
              <button className="btn btn-sm" onClick={() => navigate(e.route)}>{e.action}</button>
            </div>
          ))}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Recent Activity</h3>
            <span className="pill pill-muted">3 events · sample</span>
          </div>
          <DataTable columns={[
            { key: 'date', label: 'Date' },
            { key: 'event', label: 'Event' },
            { key: 'detail', label: 'Detail' },
            { key: 'status', label: 'Status', render: (v) => <span className={`pill ${ACTIVITY_PILL[v] || 'pill-muted'}`}>{v}</span> },
          ]} rows={ACTIVITY} />
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Organization Readiness</h3>
            <span className="pill pill-muted">sample</span>
          </div>
          <div className="stack" style={{ gap: 8 }}>
            {READINESS.map((r, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: i < READINESS.length - 1 ? '1px solid var(--divider)' : 'none' }}>
                <div style={{ fontSize: 13, color: 'var(--ink-mid)' }}>{r.label}</div>
                <span className={`pill ${r.tone}`}>{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="stack" style={{ gap: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Cohorts</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/cohorts')}>Manage cohorts</button>
          </div>
          <DataTable columns={[
            { key: 'name', label: 'Cohort' },
            { key: 'orgs', label: 'Orgs' },
            { key: 'date', label: 'Created' },
            { key: 'status', label: 'Status', render: (v) => <span className={`pill ${STATE_PILL[v] || 'pill-muted'}`}>{v}</span> },
          ]} rows={COHORTS} />
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Support Operations</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/support')}>Open support queue</button>
          </div>
          <DataTable columns={[
            { key: 'id', label: 'Ticket' },
            { key: 'org', label: 'Organization' },
            { key: 'type', label: 'Type' },
            { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Open' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
          ]} rows={SUPPORT} />
        </div>
      </div>
    </PageLayout>
  )
}
