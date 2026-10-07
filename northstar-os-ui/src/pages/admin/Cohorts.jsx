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
        <button className="btn btn-primary" disabled={!confirmed || state.phase === 'submitting'} onClick={download} title={!confirmed ? 'Confirm before exporting' : 'Download the safe-set CSV'}>
          {state.phase === 'submitting' ? 'Exporting…' : 'Download CSV'}
        </button>
        {state.phase === 'success' && <span className="pill pill-ok" data-testid="bo-export-success">Exported {state.filename} ({state.bytes} bytes)</span>}
        {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required — session expired.</span>}
        {state.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin access required.</span>}
        {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
      </div>
    </div>
  )
}

// ═══ Cohorts — no dedicated backend; honest, no fabricated rows ═══
export default function Cohorts() {
  return (
    <PageLayout title="Cohorts" subtitle="Batch groupings for onboarding and management.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Cohort management is not connected">
        There is no cohort backend yet, so no cohort records are shown. Cohorts are a naming convention over plan assignment today — assign a plan on an organization&apos;s detail page instead. Nothing is fabricated here.
      </DataNotice>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Beta Cohorts</h3>
          <span className="pill pill-muted">not connected</span>
        </div>
        <p data-testid="bo-cohorts-empty" style={{ fontSize: 13 }}>No cohort data source is wired. Honest empty state.</p>
      </div>
    </PageLayout>
  )
}

const TRIAGE_STATUSES = ['new', 'acknowledged', 'investigating', 'resolved', 'closed']

// ═══ ACTIVATED: support triage write (platform-admin only) ═══
function SupportTriage() {
  const [form, setForm] = useState({ ticket_id: '', status: 'acknowledged', assignee: '', internal_note: '', tester_visible_note: '' })
  const [confirmed, setConfirmed] = useState(false)
  const [st, setSt] = useState({ phase: 'idle' })
  const can = !!form.ticket_id.trim() && confirmed && st.phase !== 'submitting'
  const submit = async (e) => {
    e.preventDefault()
    if (!can) return
    setSt({ phase: 'submitting' })
    const r = await settle(foundationApi.supportTriage(form.ticket_id.trim(), {
      status: form.status,
      assignee: form.assignee.trim() || undefined,
      internal_note: form.internal_note.trim() || undefined,
      tester_visible_note: form.tester_visible_note.trim() || undefined,
    }))
    if (r.ok) { setSt({ phase: 'success' }); setConfirmed(false) }
    else {
      const s = r.error && r.error.status
      setSt({ phase: s === 401 ? 'auth' : s === 403 ? 'forbidden' : s === 404 ? 'not_found' : 'error', message: (r.error && r.error.message) || 'Triage failed.' })
    }
  }
  return (
    <div className="card" data-testid="bo-support-triage" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Triage ticket</h3>
        <span className="pill pill-ochre">active · platform admin</span>
      </div>
      <AuthorizationNote
        title="Support triage"
        status="Active — platform-admin only"
        route="POST /api/v1/foundation/support/tickets/{id}/triage"
        permission="PERM_PLATFORM_ADMIN"
        audit="support triage (status/notes)"
      >
        Updates a ticket&apos;s status, assignee, internal note, and tester-visible note. Internal notes are never exposed to testers. Audited.
      </AuthorizationNote>
      <form className="stack" style={{ gap: 10 }} onSubmit={submit}>
        <div className="grid-2" style={{ gap: 12 }}>
          <label className="stack" style={{ gap: 4 }}>
            <span className="text-low" style={{ fontSize: 11 }}>Ticket id</span>
            <input className="field" value={form.ticket_id} onChange={e => setForm(f => ({ ...f, ticket_id: e.target.value }))} placeholder="ticket id from the queue" />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="text-low" style={{ fontSize: 11 }}>Status</span>
            <select className="field" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
              {TRIAGE_STATUSES.map(x => <option key={x} value={x}>{x}</option>)}
            </select>
          </label>
        </div>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Assignee (optional)</span>
          <input className="field" value={form.assignee} onChange={e => setForm(f => ({ ...f, assignee: e.target.value }))} placeholder="operator id" />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Internal note (not shown to testers)</span>
          <input className="field" value={form.internal_note} onChange={e => setForm(f => ({ ...f, internal_note: e.target.value }))} placeholder="internal" />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Tester-visible note (optional)</span>
          <input className="field" value={form.tester_visible_note} onChange={e => setForm(f => ({ ...f, tester_visible_note: e.target.value }))} placeholder="shared with tester" />
        </label>
        <div className="check-row"><input type="checkbox" id="tri-confirm" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /><label htmlFor="tri-confirm">I understand this updates the ticket and is logged.</label></div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" type="submit" disabled={!can}>{st.phase === 'submitting' ? 'Saving…' : 'Save triage'}</button>
          {st.phase === 'success' && <span className="pill pill-ok">Triage saved — audited</span>}
          {st.phase === 'auth' && <span className="pill pill-unknown">Sign in required.</span>}
          {st.phase === 'forbidden' && <span className="pill pill-warn">Not permitted — platform-admin required.</span>}
          {st.phase === 'not_found' && <span className="pill pill-warn">Ticket not found.</span>}
          {st.phase === 'error' && <span className="pill pill-warn">{st.message}</span>}
        </div>
      </form>
    </div>
  )
}

export function SupportOps() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Support Operations" subtitle="Operational support and escalation queue for beta organizations.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Support queue is live">
        Tickets are read live from the foundation support service. Triage and responses are operator actions and are logged.
      </DataNotice>
      <FoundationSupportQueue />
      <SupportTriage />
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Escalation routing</h3>
        </div>
        <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-sm" onClick={() => navigate('/beta-ops/audit')}>Open audit trail</button>
          <button className="btn btn-sm btn-ghost" onClick={() => navigate('/beta-ops/orgs')}>Open organizations</button>
        </div>
      </div>
    </PageLayout>
  )
}

export function ReportsExports() {
  return (
    <PageLayout title="Reports & Exports" subtitle="Operational reports and data exports.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Safe-set export only">
        The “Dashboard export (CSV)” card is a live, platform-admin export of the safe field set only — no secrets, card data, tokens, provider credentials, or cross-org data. No other report backends are connected, so no sample report rows are shown.
      </DataNotice>
      <DashboardExport />
    </PageLayout>
  )
}

export function AuditNotes() {
  return (
    <PageLayout title="Audit & Notes" subtitle="Operational audit trail and internal notes.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Audit trail is internal and observed">
        The “Foundation audit log” is a live, read-only read. Audit entries are never edited and are visible only to platform admins.
      </DataNotice>
      <FoundationAuditLog />
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
        status="Suspend/resume/grant/plan active on organization detail — this modal stays disabled"
        route="POST /api/v1/foundation/admin/orgs/{id}/{grant,suspend,resume,plan,downgrade,cancel}"
        permission="PERM_PLATFORM_ADMIN"
        audit="org.lifecycle.<state> (append-only, actor + reason)"
      >
        Grant/activate, plan/tier, suspend, and resume are activated per-organization on the organization detail page (confirmation-gated, audited). This generic modal stays disabled; <strong>downgrade</strong> and <strong>cancel</strong> remain disabled.
      </AuthorizationNote>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-head">
          <h3 className="card-title">Change Lifecycle State</h3>
          <span className="pill pill-muted">internal · logged</span>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          <div className="field-group">
            <label className="label">Target Organization</label>
            <input className="field" placeholder="Select an organization from the roster" readOnly />
          </div>
          <div className="field-group">
            <label className="label">Action</label>
            <select className="field" disabled>
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
            <span className="text-low" style={{ fontSize: 11 }}>Disabled — use the organization detail page for enabled actions.</span>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export function EligibilityChecklist() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Eligibility Checklist" subtitle="Verify criteria before cohort admission.">
      <BetaOpsNav />
      <DataNotice tone="internal" title="Eligibility is per-organization">
        Admission eligibility is evaluated per organization from its live record (legal acceptance, invite, lifecycle). Open an organization to run the real, checklist-gated admission. No global checklist is fabricated here.
      </DataNotice>
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-head">
          <h3 className="card-title">Admission Criteria</h3>
          <span className="pill pill-muted">per-organization</span>
        </div>
        <p style={{ fontSize: 13 }}>Eligibility (legal acceptance complete, invite recorded, eligible lifecycle state) is shown on the organization detail page. This page is a non-authoritative pointer and stays disabled.</p>
        <div style={{ marginTop: 14 }}>
          <button className="btn btn-primary" disabled title="Sample surface — eligibility is not applied">Verify Eligibility</button>
          <button className="btn btn-sm btn-ghost" style={{ marginLeft: 10 }} onClick={() => navigate('/beta-ops/orgs')}>Open organizations</button>
        </div>
      </div>
    </PageLayout>
  )
}
