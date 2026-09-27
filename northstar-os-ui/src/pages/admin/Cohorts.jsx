import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function Cohorts() {
  return (
    <PageLayout title="Cohorts" subtitle="Batch groupings for onboarding and management.">
      <DataTable columns={[
        { key: 'name', label: 'Cohort' },
        { key: 'orgs', label: 'Organizations' },
        { key: 'status', label: 'Status' },
        { key: 'date', label: 'Period' },
      ]} rows={[
        { name: 'Cohort 1', orgs: 5, status: 'Complete', date: 'Q3 2026' },
        { name: 'Cohort 2', orgs: 6, status: 'Complete', date: 'Q3 2026' },
        { name: 'Cohort 3', orgs: 3, status: 'Active', date: 'Q4 2026' },
      ]} />
    </PageLayout>
  )
}

export function SupportOps() {
  return (
    <PageLayout title="Support Operations" subtitle="Operational support and escalation management.">
      <DataTable columns={[
        { key: 'ticket', label: 'Ticket' },
        { key: 'org', label: 'Organization' },
        { key: 'category', label: 'Category' },
        { key: 'status', label: 'Status' },
      ]} rows={[
        { ticket: 'SUP-001', org: 'T2 Holdings', category: 'Sync', status: 'Open' },
        { ticket: 'SUP-002', org: 'Northstar Labs', category: 'Billing', status: 'Resolved' },
      ]} />
    </PageLayout>
  )
}

export function ReportsExports() {
  return (
    <PageLayout title="Reports & Exports" subtitle="Operational reports and data exports.">
      <div className="stack" style={{ gap: 16 }}>
        {[
          { name: 'Q3 Performance Summary', type: 'PDF', date: '2026-09-26' },
          { name: 'Organization Roster', type: 'CSV', date: '2026-09-25' },
          { name: 'Invite Audit Trail', type: 'CSV', date: '2026-09-24' },
        ].map((r, i) => (
          <div key={i} className="list-row">
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{r.name}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{r.type} — {r.date}</div>
            </div>
            <button className="btn btn-sm">Download</button>
          </div>
        ))}
      </div>
    </PageLayout>
  )
}

export function AuditNotes() {
  return (
    <PageLayout title="Audit & Notes" subtitle="Operational audit trail and internal notes.">
      <div className="card">
        <h3 className="card-title">Audit Log</h3>
        <div className="timeline" style={{ marginTop: 16 }}>
          {[
            { time: '2026-09-26 09:14', event: 'Organization #0838 suspended', type: 'error' },
            { time: '2026-09-25 14:30', event: 'Invite INV-2026-09-25-0192 expired', type: 'warn' },
            { time: '2026-09-25 11:00', event: 'Cohort 3 created', type: 'info' },
            { time: '2026-09-24 16:45', event: 'Plan updated for #0001', type: 'info' },
          ].map((item, i) => (
            <div key={i} className="timeline-item">
              <div className={`timeline-dot timeline-dot-${item.type}`}>{item.type === 'error' ? '!' : item.type === 'warn' ? '⚑' : 'i'}</div>
              <div className="timeline-content">
                <div className="timeline-text">{item.event}</div>
                <div className="timeline-date">{item.time}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  )
}

export function LifecycleModal() {
  return (
    <PageLayout title="Lifecycle Action" subtitle="Confirm the impact of lifecycle operations.">
      <div className="alert-error" style={{ marginBottom: 20 }}>
        <div className="alert-title">This action is irreversible</div>
        <div className="alert-text">Suspending an organization will block all product features. This action is logged and requires operator approval.</div>
      </div>
      <div className="stack" style={{ gap: 16 }}>
        <div className="field-group">
          <label className="label">Target Organization</label>
          <input className="field" defaultValue="#0838 — Kirkland Ventures" readOnly />
        </div>
        <div className="field-group">
          <label className="label">Action</label>
          <select className="field">
            <option>Suspend</option>
            <option>Cancel</option>
            <option>Downgrade</option>
          </select>
        </div>
        <div className="field-group">
          <label className="label">Reason</label>
          <textarea className="field" placeholder="Provide reason for this action..." />
        </div>
        <button className="btn btn-danger btn-block">Confirm Lifecycle Action</button>
      </div>
    </PageLayout>
  )
}

export function EligibilityChecklist() {
  return (
    <PageLayout title="Eligibility Checklist" subtitle="Verify criteria before cohort admission.">
      <div className="stack" style={{ gap: 16 }}>
        {[
          { text: 'Organization registration complete', checked: true },
          { text: 'Terms accepted', checked: true },
          { text: 'DPA signed', checked: true },
          { text: 'Billing verified', checked: false },
          { text: 'Operator assigned', checked: false },
        ].map((item, i) => (
          <div key={i} className="check-row">
            <input type="checkbox" checked={item.checked} readOnly />
            <label>{item.text}</label>
          </div>
        ))}
        <button className="btn btn-primary" style={{ marginTop: 8 }}>Verify Eligibility</button>
      </div>
    </PageLayout>
  )
}