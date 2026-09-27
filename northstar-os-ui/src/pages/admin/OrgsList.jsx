import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate } from 'react-router-dom'

const ORG_PILL = { Active: 'pill-muted', Suspended: 'pill-warn', 'Pending Verification': 'pill-ochre' }

const ORGS = [
  { id: '0001', org: 'T2 Holdings LLC', plan: 'AutothinK', members: 2, status: 'Active' },
  { id: '0521', org: 'Northstar Labs', plan: 'Beta', members: 5, status: 'Active' },
  { id: '0838', org: 'Kirkland Ventures', plan: 'Starter', members: 1, status: 'Suspended' },
  { id: '0788', org: 'Word Coffee Co', plan: 'AutothinK', members: 3, status: 'Active' },
]

export default function OrgsList() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Organizations" subtitle="All registered organizations in the private beta.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Organization records are internal">
        Organization, plan, and membership records are sample/internal until the beta backend is connected. Lifecycle state shown here is a record, not an authorization.
      </DataNotice>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Organization Roster</h3>
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
  return (
    <PageLayout title="Organization #0001" subtitle="T2 Holdings LLC — profile and membership.">
      <BetaOpsNav />
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
