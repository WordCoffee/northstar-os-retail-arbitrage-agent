import { PageLayout, DataTable, DataNotice, MetricTiles } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate } from 'react-router-dom'

const COHORT_PILL = { Complete: 'pill-muted', Active: 'pill-ochre' }

const COHORTS = [
  { name: 'Cohort 1', orgs: 5, status: 'Complete', date: 'Q3 2026' },
  { name: 'Cohort 2', orgs: 6, status: 'Complete', date: 'Q3 2026' },
  { name: 'Cohort 3', orgs: 3, status: 'Active', date: 'Q4 2026' },
]

export default function Cohorts() {
  return (
    <PageLayout title="Cohorts" subtitle="Batch groupings for onboarding and management.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Cohort records are internal">
        Cohort membership and status are sample/internal records. A cohort assignment does not by itself grant entitlements or access.
      </DataNotice>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Beta Cohorts</h3>
          <span className="pill pill-muted">{COHORTS.length} cohorts · sample</span>
        </div>
        <DataTable columns={[
          { key: 'name', label: 'Cohort' },
          { key: 'orgs', label: 'Organizations' },
          { key: 'status', label: 'Status', render: (v) => <span className={`pill ${COHORT_PILL[v] || 'pill-muted'}`}>{v}</span> },
          { key: 'date', label: 'Period' },
        ]} rows={COHORTS} />
      </div>
    </PageLayout>
  )
}

const SUPPORT = [
  { ticket: 'SUP-001', org: 'T2 Holdings', category: 'Sync', status: 'Open', age: '1d' },
  { ticket: 'SUP-002', org: 'Northstar Labs', category: 'Billing', status: 'Resolved', age: '3d' },
  { ticket: 'SUP-003', org: 'Word Coffee Co', category: 'Access', status: 'Open', age: '4h' },
]

export function SupportOps() {
  const navigate = useNavigate()
  const open = SUPPORT.filter(s => s.status === 'Open').length
  return (
    <PageLayout title="Support Operations" subtitle="Operational support and escalation queue for beta organizations.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Support queue is internal">
        Support records are sample/internal until the beta backend is connected. Responding to a ticket is an operator action and is logged.
      </DataNotice>
      <MetricTiles columns={2} metrics={[
        { label: 'Open Tickets', value: String(open), sub: 'Require a response', tone: 'warn' },
        { label: 'Resolved', value: String(SUPPORT.length - open), sub: 'Closed this period' },
      ]} />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Ticket Queue</h3>
          <span className="pill pill-warn">{open} open</span>
        </div>
        <DataTable columns={[
          { key: 'ticket', label: 'Ticket' },
          { key: 'org', label: 'Organization' },
          { key: 'category', label: 'Category', render: (v) => <span className="pill pill-muted">{v}</span> },
          { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Open' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
          { key: 'age', label: 'Age' },
          { key: 'action', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/audit')}>Open audit trail</button> },
        ]} rows={SUPPORT} />
      </div>
    </PageLayout>
  )
}

export function ReportsExports() {
  return (
    <PageLayout title="Reports & Exports" subtitle="Operational reports and data exports.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Exports use the safe field set only">
        Exports contain operational fields only — no secrets, card data, tokens, provider credentials, or cross-org data. Downloaded files are sample until a backend is connected.
      </DataNotice>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Available Reports</h3>
          <span className="pill pill-muted">sample</span>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {[
            { name: 'Q3 Performance Summary', type: 'PDF', date: '2026-09-26' },
            { name: 'Organization Roster', type: 'CSV', date: '2026-09-25' },
            { name: 'Invite Audit Trail', type: 'CSV', date: '2026-09-24' },
          ].map((r, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderBottom: i < 2 ? '1px solid var(--divider)' : 'none' }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13 }}>{r.name}</div>
                <div className="text-low" style={{ fontSize: 11 }}>{r.type} — {r.date}</div>
              </div>
              <span className="pill pill-muted" style={{ fontSize: 10 }} title="Export is disabled in sample mode">sample only</span>
              <button className="btn btn-sm" disabled title="Export disabled in sample mode">Download</button>
            </div>
          ))}
        </div>
      </div>
    </PageLayout>
  )
}

export function AuditNotes() {
  return (
    <PageLayout title="Audit & Notes" subtitle="Operational audit trail and internal notes.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Audit trail is internal and observed">
        Audit entries are internal observed records (sample until a backend is connected). They are never edited and are visible only to platform admins.
      </DataNotice>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Audit Log</h3>
          <span className="pill pill-muted">OBSERVED · sample</span>
        </div>
        <div className="timeline">
          {[
            { time: '2026-09-26 09:14', event: 'Organization #0838 suspended', type: 'error', tag: 'OBSERVED' },
            { time: '2026-09-25 14:30', event: 'Invite INV-2026-09-25-0192 expired', type: 'warn', tag: 'OBSERVED' },
            { time: '2026-09-25 11:00', event: 'Cohort 3 created', type: 'info', tag: 'OBSERVED' },
            { time: '2026-09-24 16:45', event: 'Plan updated for #0001', type: 'info', tag: 'HISTORICAL' },
          ].map((item, i) => (
            <div key={i} className="timeline-item">
              <div className={`timeline-dot timeline-dot-${item.type}`}>{item.type === 'error' ? '!' : item.type === 'warn' ? '⚑' : 'i'}</div>
              <div className="timeline-content">
                <div className="timeline-text">{item.event}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
                  <span className="timeline-date">{item.time}</span>
                  <span className="pill pill-muted" style={{ fontSize: 10 }} title="Provenance — observed/historical, not live-verified">{item.tag}</span>
                </div>
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
      <BetaOpsNav />
      <div className="alert alert-error" style={{ marginBottom: 16 }}>
        <div className="alert-title">This action is irreversible</div>
        <div className="alert-text">Suspending an organization blocks all product features. The action is logged and requires operator approval — it is never automated.</div>
      </div>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-head">
          <h3 className="card-title">Change Lifecycle State</h3>
          <span className="pill pill-muted">internal · logged</span>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn btn-danger" disabled title="Sample surface — no lifecycle action is applied">Confirm Lifecycle Action</button>
            <span className="text-low" style={{ fontSize: 11 }}>Disabled in sample mode — no state is changed.</span>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export function EligibilityChecklist() {
  const items = [
    { text: 'Organization registration complete', checked: true },
    { text: 'Terms accepted', checked: true },
    { text: 'DPA signed', checked: true },
    { text: 'Billing verified', checked: false },
    { text: 'Operator assigned', checked: false },
  ]
  const done = items.filter(i => i.checked).length
  return (
    <PageLayout title="Eligibility Checklist" subtitle="Verify criteria before cohort admission.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Eligibility is an operator decision">
        Checklist state is a sample/internal record. Passing the checklist does not auto-admit an organization; admission is an explicit operator decision.
      </DataNotice>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-head">
          <h3 className="card-title">Admission Criteria</h3>
          <span className={`pill ${done === items.length ? 'pill-muted' : 'pill-ochre'}`}>{done}/{items.length} complete</span>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          {items.map((item, i) => (
            <div key={i} className="check-row">
              <input type="checkbox" checked={item.checked} readOnly />
              <label>{item.text}</label>
              <span className={`pill ${item.checked ? 'pill-muted' : 'pill-ochre'}`} style={{ marginLeft: 'auto', fontSize: 10 }}>{item.checked ? 'Verified' : 'Pending'}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14 }}>
          <button className="btn btn-primary" disabled title="Sample surface — eligibility is not applied">Verify Eligibility</button>
          <span className="text-low" style={{ fontSize: 11, marginLeft: 10 }}>Disabled in sample mode.</span>
        </div>
      </div>
    </PageLayout>
  )
}
