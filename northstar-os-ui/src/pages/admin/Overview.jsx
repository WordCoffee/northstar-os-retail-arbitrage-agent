import { PageLayout, DataTable, MetricTiles } from '../../components/Shared.jsx'

export default function BetaOpsOverview() {
  return (
    <PageLayout
      title="Beta Operations"
      subtitle="Exception-led admin surface — organizations, invites, cohorts, support operations, lifecycle controls."
      actions={<><button className="btn btn-sm">Export Report</button><button className="btn btn-sm btn-ghost">Audit Log</button></>}
    >
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <MetricTiles metrics={[
          { label: 'Organizations', value: '14', sub: 'Active' },
          { label: 'Pending Invites', value: '7', sub: 'Unaccepted' },
          { label: 'Cohorts', value: '3', sub: 'Active' },
          { label: 'Exceptions', value: '2', sub: 'Action required' },
        ]} />
      </div>

      <div className="alert alert-error" style={{ marginBottom: 24 }}>
        <div className="alert-title">2 Exceptions Require Immediate Attention</div>
        <div className="alert-text">Organization #0838 lifecycle blocked (suspended). Invite INV-2026-09-25-0192 expired.</div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Recent Activity</h3>
            <span className="pill pill-muted">3 events</span>
          </div>
          <DataTable columns={[
            { key: 'date', label: 'Date' },
            { key: 'event', label: 'Event' },
            { key: 'detail', label: 'Detail' },
            { key: 'status', label: 'Status' },
          ]} rows={[
            { date: '2026-09-26', event: 'Org suspended', detail: '#0838 lifecycle blocked', status: 'Error' },
            { date: '2026-09-25', event: 'Invite expired', detail: 'INV-2026-09-25-0192', status: 'Warn' },
            { date: '2026-09-25', event: 'Cohort created', detail: 'Cohort 3 — Q4', status: 'Ok' },
          ]} />
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Organization Readiness</h3>
          </div>
          <Table rows={[
            { label: 'Verified Orgs', value: '10', tone: 'normal' },
            { label: 'Suspended', value: '2', tone: 'warn' },
            { label: 'Pending Verification', value: '2', tone: 'normal' },
            { label: 'Avg Readiness Score', value: '78%', tone: 'normal' },
          ]} />
        </div>
      </div>

      <div className="stack" style={{ gap: 20, marginTop: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Cohorts</h3>
            <span className="pill pill-forest">3 active</span>
          </div>
          <DataTable columns={[
            { key: 'name', label: 'Cohort' },
            { key: 'orgs', label: 'Orgs' },
            { key: 'date', label: 'Created' },
            { key: 'status', label: 'Status' },
          ]} rows={[
            { name: 'Cohort 1 — Q3 Onboarding', orgs: '5', date: '2026-07-15', status: 'Active' },
            { name: 'Cohort 2 — Q3 Expansion', orgs: '4', date: '2026-08-20', status: 'Active' },
            { name: 'Cohort 3 — Q4 Pilot', orgs: '3', date: '2026-09-25', status: 'Active' },
          ]} />
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Support Operations</h3>
            <span className="pill pill-warn">4 tickets</span>
          </div>
          <DataTable columns={[
            { key: 'id', label: 'Ticket' },
            { key: 'org', label: 'Organization' },
            { key: 'type', label: 'Type' },
            { key: 'status', label: 'Status' },
          ]} rows={[
            { id: '#4471', org: '#0838', type: 'Lifecycle', status: 'Open' },
            { id: '#4470', org: '#0521', type: 'Access', status: 'Open' },
            { id: '#4469', org: '#0788', type: 'Billing', status: 'Resolved' },
            { id: '#4468', org: '#0412', type: 'Integration', status: 'Resolved' },
          ]} />
        </div>
      </div>
    </PageLayout>
  )
}

function Table({ rows }) {
  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: i < rows.length - 1 ? '1px solid var(--divider)' : 'none' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-mid)' }}>{r.label}</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: r.tone === 'warn' ? 'var(--ochre)' : 'var(--pine-deep)' }}>{r.value}</div>
        </div>
      ))}
    </div>
  )
}
