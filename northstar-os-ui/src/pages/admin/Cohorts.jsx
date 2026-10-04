import { PageLayout, DataTable, DataNotice, MetricTiles, AuthorizationNote } from '../../components/Shared.jsx'
import BetaOpsNav from './BetaOpsNav.jsx'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real support queue (org-scoped, tester view) ═══
function FoundationSupportQueue() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.supportTickets()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="bo-support-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation support queue</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading support tickets…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in as a platform admin to read support tickets.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Support queue unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'id', label: 'Ticket' },
          { key: 'subject', label: 'Subject', render: (v, row) => v || row.title || row.category || 'UNKNOWN' },
          { key: 'category', label: 'Category', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
          { key: 'severity', label: 'Severity', render: (v, row) => { const s = v || row.priority || 'normal'; return <span className={`pill ${s === 'blocker' || s === 'high' ? 'pill-error' : s === 'low' ? 'pill-muted' : 'pill-warn'}`}>{s}</span> } },
          { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'open' ? 'pill-warn' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
          { key: 'created_at', label: 'Created' },
        ]} rows={st.items} />
      ) : (
        <p data-testid="bo-support-empty" style={{ fontSize: 13 }}>No support tickets for this organization. Honest empty state.</p>
      ))}
    </div>
  )
}

// ═══ Real audit log (org-scoped, observed) ═══
function FoundationAuditLog() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.audit()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="bo-audit-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation audit log</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading audit entries…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in as a platform admin to read the audit log.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Audit log unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'occurred_at', label: 'When', render: (v) => v || 'UNKNOWN' },
          { key: 'action', label: 'Action', render: (v) => v || 'UNKNOWN' },
          { key: 'actor_user_id', label: 'Actor', render: (v) => v || 'UNKNOWN' },
          { key: 'resource_type', label: 'Resource', render: (v, row) => <span className="pill pill-muted">{v || '—'}{row.resource_id ? ' / ' + row.resource_id : ''}</span> },
          { key: 'result', label: 'Result', render: (v) => <span className={`pill ${v === 'denied' || v === 'failure' ? 'pill-warn' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
        ]} rows={st.items} />
      ) : (
        <p data-testid="bo-audit-empty" style={{ fontSize: 13 }}>No audit entries for this organization yet. Honest empty state.</p>
      ))}
    </div>
  )
}

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
        The “Foundation support queue” is a live read. The sample queue below is demonstration data. Responding to a ticket is an operator action and is logged.
      </DataNotice>
      <FoundationSupportQueue />
      <MetricTiles columns={2} metrics={[
        { label: 'Open Tickets', value: String(open), sub: 'Require a response', tone: 'warn' },
        { label: 'Resolved', value: String(SUPPORT.length - open), sub: 'Closed this period' },
      ]} />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Sample queue (preview)</h3>
          <span className="pill pill-warn">{open} open · sample</span>
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

const EXPORT_FIELDS = ['organization_id', 'organization_name', 'lifecycle_state', 'plan_tier',
  'subscription_status', 'invite_status', 'acceptance_complete', 'onboarding_complete',
  'monthly_jobs_used', 'max_jobs_per_month', 'seats_used', 'seat_limit', 'open_tickets',
  'blocker_tickets', 'last_activity', 'flags']
const EXPORT_EXCLUDES = ['secret', 'token', 'password', 'card', 'credential', 'provider_key', 'api_key']

// ACTIVATED (owner-approved, platform-admin only): dashboard export CSV (read-only).
function DashboardExport() {
  const [confirmed, setConfirmed] = useState(false)
  const [state, setState] = useState({ phase: 'idle' })

  const download = async () => {
    if (!confirmed) return
    setState({ phase: 'submitting' })
    const r = await settle(foundationApi.adminExportCsv())
    if (r.ok) {
      const { filename, text } = r.value
      try {
        const blob = new Blob([text], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = filename
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
      } catch { /* download trigger unavailable */ }
      setState({ phase: 'success', filename, bytes: text.length })
      setConfirmed(false)
    } else {
      const s = r.error && r.error.status, code = r.error && r.error.code
      setState({
        phase: s === 401 ? 'auth' : s === 403 ? 'forbidden' : 'error',
        message: code === 'export_contains_excluded_data'
          ? 'Export blocked: the payload contained a disallowed field (safe-set guard).'
          : (r.error && r.error.message) || `Export failed${code ? ` (${code})` : ''}.`,
      })
    }
  }

  return (
    <div className="card" data-testid="bo-dashboard-export" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Dashboard export (CSV)</h3>
        <span className="pill pill-ochre">active · platform admin</span>
      </div>
      <AuthorizationNote
        title="Dashboard export"
        status="Active — platform-admin only"
        route="GET /api/v1/foundation/admin/dashboard/export"
        permission="PERM_PLATFORM_ADMIN"
        audit="read-only (no write)"
      >
        Exports the safe field set only. Secrets, tokens, card data, credentials, provider keys, and API keys are hard-excluded by the backend. This is a read — no write and no audit event.
      </AuthorizationNote>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Safe fields</div>
      <div className="inline-flex" style={{ gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
        {EXPORT_FIELDS.map(f => <span key={f} className="pill pill-muted" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{f}</span>)}
      </div>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Hard-excluded</div>
      <div className="inline-flex" style={{ gap: 4, flexWrap: 'wrap', marginBottom: 12 }}>
        {EXPORT_EXCLUDES.map(f => <span key={f} className="pill pill-warn" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{f}</span>)}
      </div>
      <div className="check-row" style={{ marginBottom: 10 }}>
        <input type="checkbox" id="export-confirm" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
        <label htmlFor="export-confirm">I understand this exports the safe field set only.</label>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button
          className="btn btn-primary"
          disabled={!confirmed || state.phase === 'submitting'}
          onClick={download}
          title={!confirmed ? 'Confirm before exporting' : 'Download the safe-set CSV'}
        >{state.phase === 'submitting' ? 'Exporting…' : 'Download CSV'}</button>
        {state.phase === 'success' && <span className="pill pill-ok" data-testid="bo-export-success">Exported {state.filename} ({state.bytes} bytes)</span>}
        {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required — session expired.</span>}
        {state.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin access required.</span>}
        {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
      </div>
    </div>
  )
}

export function ReportsExports() {
  return (
    <PageLayout title="Reports & Exports" subtitle="Operational reports and data exports.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Safe-set export + sample reports">
        The “Dashboard export (CSV)” card is a live, platform-admin export of the safe field set only — no secrets, card data, tokens, provider credentials, or cross-org data. The “Available Reports” rows below are sample until their backends exist.
      </DataNotice>
      <DashboardExport />
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
        The “Foundation audit log” is a live, read-only read. The sample timeline below is demonstration data. Audit entries are never edited and are visible only to platform admins.
      </DataNotice>
      <FoundationAuditLog />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Sample audit log (preview)</h3>
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
      <AuthorizationNote
        title="Lifecycle transitions"
        status="Suspend/resume active on organization detail — this modal stays disabled"
        route="POST /api/v1/foundation/admin/orgs/{id}/{grant,suspend,resume,downgrade,cancel}"
        permission="PERM_PLATFORM_ADMIN"
        audit="org.lifecycle.<state> (append-only, actor + reason)"
      >
        Transitions are validated server-side; blocking states (suspended/paused/cancelled/archived) set the org inactive so the next authenticated request is denied. <strong>Suspend</strong> and <strong>Resume</strong> are now activated per-organization on the organization detail page (confirmation-gated). Grant, plan/tier, <strong>downgrade</strong>, <strong>cancel</strong>, and <strong>archive</strong> remain disabled.
      </AuthorizationNote>
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
            <label className="label">Reason <span className="text-low" style={{ fontSize: 11 }}>(required for any enabled transition)</span></label>
            <textarea className="field" placeholder="Provide reason for this action..." />
          </div>
          <div className="field-group">
            <label className="label">Typed confirmation <span className="text-low" style={{ fontSize: 11 }}>(scaffold — enablement pending owner approval)</span></label>
            <input className="field" placeholder="Type the action name to confirm" disabled title="Confirmation is scaffolded; the action cannot be applied until owner approval" />
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
          <AuthorizationNote
            title="Eligibility → activation"
            status="Grant/activate active on organization detail — this checklist stays disabled"
            route="POST /api/v1/foundation/admin/orgs/{id}/grant"
            permission="PERM_PLATFORM_ADMIN"
            audit="org.lifecycle.onboarding / org.lifecycle.active"
          >
            Verifying eligibility does not admit an organization by itself. Admission is now performed per-organization on the organization detail page (checklist-gated, confirmation-gated, audited). This checklist remains a non-authoritative surface and stays disabled.
          </AuthorizationNote>
          <button className="btn btn-primary" disabled title="Sample surface — eligibility is not applied">Verify Eligibility</button>
          <span className="text-low" style={{ fontSize: 11, marginLeft: 10 }}>Disabled in sample mode.</span>
        </div>
      </div>
    </PageLayout>
  )
}
