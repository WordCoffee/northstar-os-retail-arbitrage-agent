import { PageLayout, DataNotice } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'

export default function InviteCreate() {
  return (
    <PageLayout title="Create Invitation" subtitle="Issue an invitation for a new organization to the private beta.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Invitations are operator-issued">
        Creating an invitation is an operator action and is logged. In this sample surface nothing is emailed or granted automatically; invite states are internal records, not entitlements.
      </DataNotice>
      <div style={{ maxWidth: 500 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Invitation Details</h3>
            <span className="pill pill-muted">sample</span>
          </div>
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button className="btn btn-primary" disabled title="Sample surface — no invite is sent">Send Invitation</button>
              <span className="text-low" style={{ fontSize: 11 }}>Disabled in sample mode — no invite is issued.</span>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export function InviteDetail() {
  return (
    <PageLayout title="Invite #INV-2026-09-25-0192" subtitle="Invitation details and status.">
      <BetaOpsNav />
      <div className="stack" style={{ gap: 20 }}>
        <div className="evidence">
          <div className="evidence-header">
            <span className="pill pill-warn">Expired</span>
            <span className="evidence-source">INV-2026-09-25-0192</span>
            <span className="evidence-freshness">Sent: 2026-09-25</span>
          </div>
          <p className="evidence-body">Invitation to T2 Holdings LLC for Operator role. <span className="evidence-unknown">This invite has expired and requires reissuance before it can be accepted.</span></p>
        </div>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Actions</h3>
            <span className="pill pill-muted">internal · logged</span>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <button className="btn btn-primary" disabled title="Sample surface — no invite is reissued">Reissue Invitation</button>
            <button className="btn btn-danger" disabled title="Sample surface — no invite is revoked">Revoke</button>
            <div className="text-low" style={{ fontSize: 11 }}>Actions are disabled in sample mode. Reissuing or revoking is an operator action and is always logged.</div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
