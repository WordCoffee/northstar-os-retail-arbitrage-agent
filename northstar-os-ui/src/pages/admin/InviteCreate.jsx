import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function InviteCreate() {
  return (
    <PageLayout title="Create Invitation" subtitle="Invite a new organization to NorthstarOS.">
      <div style={{ maxWidth: 500 }}>
        <div className="card">
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
            <button className="btn btn-primary">Send Invitation</button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export function InviteDetail() {
  return (
    <PageLayout title="Invite #INV-2026-09-25-0192" subtitle="Invitation details and status.">
      <div className="stack" style={{ gap: 20 }}>
        <div className="evidence">
          <div className="evidence-header">
            <span className="pill pill-ochre">Pending</span>
            <span className="evidence-source">INV-2026-09-25-0192</span>
            <span className="evidence-freshness">Sent: 2026-09-25</span>
          </div>
          <p className="evidence-body">Invitation to T2 Holdings LLC for Operator role. <span className="evidence-unknown">This invite has expired and requires reissuance.</span></p>
        </div>
        <div className="card">
          <h3 className="card-title">Actions</h3>
          <div className="stack" style={{ gap: 10, marginTop: 12 }}>
            <button className="btn btn-primary">Reissue Invitation</button>
            <button className="btn btn-danger">Revoke</button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}