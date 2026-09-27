import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function OrgsList() {
  return (
    <PageLayout title="Organizations" subtitle="All registered organizations.">
      <DataTable columns={[
        { key: 'org', label: 'Organization' },
        { key: 'plan', label: 'Plan' },
        { key: 'members', label: 'Members' },
        { key: 'status', label: 'Status' },
      ]} rows={[
        { org: 'T2 Holdings LLC', plan: 'AutothinK', members: 2, status: 'Active' },
        { org: 'Northstar Labs', plan: 'Beta', members: 5, status: 'Active' },
        { org: 'Kirkland Ventures', plan: 'Starter', members: 1, status: 'Suspended' },
        { org: 'Word Coffee Co', plan: 'AutothinK', members: 3, status: 'Active' },
      ]} />
    </PageLayout>
  )
}

export function OrgDetail() {
  return (
    <PageLayout title="Organization #0001" subtitle="T2 Holdings LLC — Detailed view.">
      <div className="stack" style={{ gap: 20 }}>
        <div className="grid-2">
          <div className="card">
            <h3 className="card-title">Profile</h3>
            <div className="stack" style={{ gap: 8, marginTop: 12 }}>
              <div className="list-row"><span className="text-low" style={{ width: 80 }}>ID:</span><span>#0001</span></div>
              <div className="list-row"><span className="text-low" style={{ width: 80 }}>Plan:</span><span>AutothinK (Annual)</span></div>
              <div className="list-row"><span className="text-low" style={{ width: 80 }}>Status:</span><span className="pill pill-ok">Active</span></div>
            </div>
          </div>
          <div className="card">
            <h3 className="card-title">Membership</h3>
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