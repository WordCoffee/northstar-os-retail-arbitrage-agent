import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import signals, { settle } from '../../services/signals.js'

// ═══ Real identity/pack resolution workflow (local read-only) ═══
function RealWorkflowQueue() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncCommerceOpsQueue()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const items = v && Array.isArray(v.items) ? v.items : []
  const runs = v && v.summary && Array.isArray(v.summary.recent_runs) ? v.summary.recent_runs : []
  return (
    <div className="card" data-testid="co-real-queue" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Identity resolution queue</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${items.length} items · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Queue unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (items.length > 0 ? (
        <DataTable columns={[
          { key: 'costco_item_number', label: 'Item' },
          { key: 'missing_identity_fields', label: 'Missing identity', render: (x) => <span className="pill pill-ochre">{x || '—'}</span> },
          { key: 'missing_physical_fields', label: 'Missing physical', render: (x) => <span className="pill pill-ochre">{x || '—'}</span> },
          { key: 'possible_next_source', label: 'Next source', render: (x) => x || '—' },
          { key: 'created_at', label: 'Queued', render: (x) => x ? String(x).slice(0, 19).replace('T', ' ') : '—' },
        ]} rows={items} />
      ) : <p className="text-low" style={{ fontSize: 13 }}>No identity-resolution items queued. Honest empty state.</p>)}
      {runs.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Recent pipeline runs</div>
          <div className="stack" style={{ gap: 4 }}>
            {runs.map((r, i) => (
              <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
                <span style={{ fontSize: 12 }}>{r.run_name || r.run_id}</span>
                <span className={`pill ${r.status === 'completed' ? 'pill-muted' : 'pill-warn'}`}>{r.status || 'UNKNOWN'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Real local workflow data (read-only). No provider call is made.</div>
    </div>
  )
}

// ═══ Foundation approval checkpoints (real, org-scoped) ═══
// Reads the real approval_requests for this organization. Approving is an
// operator action elsewhere; this panel is a read-only queue. Empty locally
// until an approval is requested — shown honestly, never fabricated.
function FoundationApprovals() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.approvals()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])

  const statePill = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'read-only · foundation', t: 'muted' }

  return (
    <div className="card" data-testid="co-foundation-approvals" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation approvals</h3>
        <span className={`pill pill-${statePill.t}`}>{statePill.l}</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 8 }}>
        Live, organization-scoped approval requests from the foundation service. Recording a decision is an operator action; this panel never auto-approves and no approval implies purchase authorization on its own.
      </p>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading approval requests…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in and select an organization to read foundation approval requests.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Approval queue unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        st.items.length > 0 ? (
          <DataTable columns={[
            { key: 'id', label: 'Request' },
            { key: 'capability', label: 'Capability' },
            { key: 'safety_class', label: 'Safety Class' },
            { key: 'risk_level', label: 'Risk', render: (v) => <span className={`pill ${v === 'high' ? 'pill-warn' : v === 'critical' ? 'pill-error' : 'pill-muted'}`} title="Foundation risk level">{v || 'UNKNOWN'}</span> },
            { key: 'required_approver_role', label: 'Required Approver' },
            { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'REQUESTED' ? 'pill-ochre' : v === 'GRANTED' ? 'pill-ok' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
            { key: 'expires_at', label: 'Expires' },
          ]} rows={st.items} />
        ) : (
          <p data-testid="co-approvals-empty" style={{ fontSize: 13 }}>No foundation approval requests for your organization yet.</p>
        )
      )}
    </div>
  )
}

const TABS = [
  { id: 'workflow', label: 'Workflow', count: 5 },
  { id: 'tasks', label: 'Tasks' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'blockers', label: 'Blockers' },
  { id: 'history', label: 'History' },
]

const QUEUE = [
  { id: 'CO-01', type: 'Sourcing Validation', asin: 'B08L5VJQ7T', owner: 'Operator A', status: 'In Progress', blocking: 'Invoice pending', priority: 'high', age: '2d' },
  { id: 'CO-02', type: 'Pack/Case Verification', asin: 'B09M8KJ4X2', owner: 'Operator B', status: 'Pending', blocking: 'Pack match UNKNOWN', priority: 'high', age: '1d' },
  { id: 'CO-03', type: 'Research Handoff', asin: 'B07XJ8C9F3', owner: 'Operator A', status: 'Ready for Review', blocking: 'None', priority: 'medium', age: '4h' },
  { id: 'CO-04', type: 'Invoice Readiness', asin: 'B08N5WRWNW', owner: 'Operator C', status: 'Blocked', blocking: 'Invoice expired', priority: 'high', age: '6d' },
  { id: 'CO-05', type: 'Operator Decision', asin: 'B08L5VJQ7T', owner: 'Pending', status: 'Awaiting Decision', blocking: 'Approval needed', priority: 'high', age: '12h' },
]

const STEPS = [
  { step: '1. Sourcing Validation', state: 'In Progress', basis: 'Invoice pending verification', tone: 'pill-warn' },
  { step: '2. Pack/Case Verification', state: 'Blocked', basis: 'Pack match UNKNOWN', tone: 'pill-error' },
  { step: '3. Cost / Fee Basis', state: 'Pending', basis: 'UNAVAILABLE', tone: 'pill-muted' },
  { step: '4. Operator Approval', state: 'Awaiting', basis: 'Explicit sign-off required', tone: 'pill-ochre' },
]

const STATUS_PILL = {
  'In Progress': 'pill-warn',
  'Pending': 'pill-muted',
  'Ready for Review': 'pill-muted',
  'Blocked': 'pill-error',
  'Awaiting Decision': 'pill-ochre',
}

const BLOCK_PILL = {
  'Pack match UNKNOWN': 'pill-unknown',
  'Invoice pending': 'pill-warn',
  'Invoice expired': 'pill-error',
  'Approval needed': 'pill-ochre',
  'None': 'pill-muted',
}

const PRIORITY_PILL = { high: 'pill-warn', medium: 'pill-muted', critical: 'pill-error' }

const BLOCKERS = [
  { id: 'CO-04', blocker: 'Invoice expired — valid, verified invoice documentation required', severity: 'Critical', age: '6d', tone: 'pill-error' },
  { id: 'CO-02', blocker: 'Pack/case match UNKNOWN — exact product identity must be confirmed', severity: 'High', age: '1d', tone: 'pill-warn' },
  { id: 'CO-01', blocker: 'Cost/fee basis — verified sourcing cost and fee structure required', severity: 'High', age: '2d', tone: 'pill-warn' },
  { id: 'CO-05', blocker: 'Operator approval — explicit sign-off before any purchase', severity: 'Required', age: '12h', tone: 'pill-ochre' },
]

const APPROVALS = [
  { id: 'CO-05', item: 'Operator Decision — B08L5VJQ7T', gate: 'Purchase authorization', state: 'Awaiting Decision', tone: 'pill-ochre' },
  { id: 'CO-01', item: 'Sourcing sign-off — invoice verification complete?', gate: 'Invoice readiness', state: 'In Progress', tone: 'pill-warn' },
  { id: 'CO-02', item: 'Pack identity sign-off — pack match confirmed?', gate: 'Pack/Case Verification', state: 'Pending', tone: 'pill-muted' },
]

const HISTORY = [
  { id: 'CO-03', event: 'Research handoff completed — docs uploaded', actor: 'Operator C', when: '4h ago', kind: 'Handoff' },
  { id: 'CO-02', event: 'Pack verification opened — pack match UNKNOWN', actor: 'Operator B', when: '1d ago', kind: 'Blocked' },
  { id: 'CO-01', event: 'Sourcing validation started — invoice pending', actor: 'Operator A', when: '2d ago', kind: 'Progress' },
  { id: 'CO-04', event: 'Invoice batch expired — readiness blocked', actor: 'System', when: '6d ago', kind: 'Expiry' },
]

export default function CommerceOps() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()
  const [filter, setFilter] = useState('all')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'workflow' : 'workflow')

  const filtered = filter === 'all'
    ? QUEUE
    : filter === 'blocked'
      ? QUEUE.filter(q => q.status === 'Blocked' || q.blocking !== 'None')
      : QUEUE.filter(q => q.status.toLowerCase().replace(/\s/g, '-') === filter)

  const selected = QUEUE.find(q => q.id === (id || 'CO-01')) || QUEUE[0]

  return (
    <PageLayout
      title="Commerce Ops"
      subtitle="Workflow control room — sourcing validation, pack verification, invoice readiness, approvals, and operator decisions."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('New workflow requires a product set and operator owner — sample mode.', 'info')}>New Workflow</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Use the filter pills above to narrow the workflow queue.', 'info')}>Filter</button>
      </>}
    >
      <DataNotice tone="sample" title="Workflow items are sample records">
        Owners, blocking conditions, and statuses are demonstration data. Live approval steps require a connected Commerce Ops backend.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/commerce-ops" />

      {view === 'workflow' && (id ? (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">{selected.id} — {selected.type}</h3>
              <span className={`pill ${STATUS_PILL[selected.status] || 'pill-muted'}`}>{selected.status}</span>
            </div>
            <div className="grid-4" style={{ gap: 12 }}>
              {[
                { label: 'ASIN', v: selected.asin },
                { label: 'Owner', v: selected.owner },
                { label: 'Blocking', v: selected.blocking, tone: 'var(--clay)' },
                { label: 'Priority', v: selected.priority },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                  {d.label === 'Blocking'
                    ? <span className={`pill ${BLOCK_PILL[selected.blocking] || 'pill-muted'}`} title={selected.blocking === 'None' ? 'No blocking condition' : 'Blocking condition — must clear before proceeding'}>{selected.blocking}</span>
                    : d.label === 'Priority'
                      ? <span className={`pill ${PRIORITY_PILL[selected.priority] || 'pill-muted'}`} title="Sample priority — workflow ordering only">{selected.priority}</span>
                      : <div style={{ fontSize: 16, fontWeight: 700, color: d.tone || 'var(--pine-deep)' }}>{d.v}</div>}
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Validation Steps</h3>
              <span className="pill pill-unknown">Purchase NOT AUTHORIZED</span>
            </div>
            {STEPS.map(s => (
              <div key={s.step} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{s.step}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{s.basis}</div>
                </div>
                <span className={`pill ${s.tone}`}>{s.state}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="subview">
          <RealWorkflowQueue />
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Critical Next Actions</h3>
              <span className="pill pill-ochre">2 items</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>CO-04 — invoice expired, readiness blocked</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Owner: Operator C · aged 6d</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="pill pill-error">Critical</span>
                  <button className="btn btn-sm" onClick={() => navigate('/commerce-ops/CO-04')}>Open</button>
                </div>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>CO-05 — operator decision awaiting sign-off</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Owner: Pending · aged 12h</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="pill pill-ochre" title="Explicit operator sign-off required — never auto-approved">Required</span>
                  <button className="btn btn-sm" onClick={() => navigate('/commerce-ops/CO-05')}>Open</button>
                </div>
              </div>
            </div>
          </div>

          <div className="room-toolbar">
            {[['all', 'All'], ['blocked', 'Blocked'], ['in-progress', 'In Progress'], ['ready-for-review', 'Ready']].map(([key, label]) => (
              <button key={key} className={`filter-pill ${filter === key ? 'active' : ''}`} onClick={() => setFilter(key)}>{label}</button>
            ))}
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Workflow Queue</h3>
              <span className="pill pill-muted">{filtered.length} items · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'type', label: 'Task Type' },
              { key: 'asin', label: 'ASIN' },
              { key: 'owner', label: 'Owner' },
              { key: 'age', label: 'Age' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${STATUS_PILL[v] || 'pill-muted'}`} title="Sample workflow state">{v}</span> },
              { key: 'blocking', label: 'Blocking Condition', render: (v) => <span className={`pill ${BLOCK_PILL[v] || 'pill-muted'}`} title={v === 'None' ? 'No blocking condition' : 'Blocking condition — must clear before proceeding'}>{v}</span> },
              { key: 'priority', label: 'Priority', render: (v) => <span className={`pill ${PRIORITY_PILL[v] || 'pill-muted'}`} title="Sample priority — workflow ordering only">{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.id}`)}>Open</button> },
            ]} rows={filtered} />
          </div>
        </div>
      ))}

      {view === 'tasks' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Documentation Tasks</h3>
              <span className="pill pill-muted">4 items · sample</span>
            </div>
            <DataTable columns={[
              { key: 'task', label: 'Task' },
              { key: 'asin', label: 'ASIN' },
              { key: 'owner', label: 'Owner' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'In Progress' ? 'pill-warn' : v === 'Expired' ? 'pill-error' : v === 'Complete' ? 'pill-muted' : 'pill-muted'}`} title={v === 'Complete' ? 'Task marked complete in sample data — not a verified audit state' : 'Sample task state'}>{v}</span> },
            ]} rows={[
              { task: 'Verify supplier invoice', asin: 'B08L5VJQ7T', owner: 'Operator A', status: 'In Progress' },
              { task: 'Confirm pack/case identity', asin: 'B09M8KJ4X2', owner: 'Operator B', status: 'Pending' },
              { task: 'Upload sourcing docs', asin: 'B07XJ8C9F3', owner: 'Operator C', status: 'Complete' },
              { task: 'Review invoice batch', asin: 'B08N5WRWNW', owner: 'Operator A', status: 'Expired' },
            ]} />
          </div>
        </div>
      )}

      {view === 'approvals' && (
        <div className="subview">
          <DataNotice tone="internal" title="Approvals require explicit operator sign-off">
            No approval step auto-completes. A green or positive signal anywhere in NorthstarOS never implies purchase authorization.
          </DataNotice>
          <FoundationApprovals />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Approval Checkpoints</h3>
              <span className="pill pill-ochre">1 awaiting</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'item', label: 'Approval Item' },
              { key: 'gate', label: 'Gate' },
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${STATUS_PILL[v] || 'pill-muted'}`} title="Approval checkpoint state (sample)">{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.id}`)}>Open</button> },
            ]} rows={APPROVALS} />
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Validation Steps — CO-05 (Operator Decision)</h3>
              <span className="pill pill-unknown">Purchase NOT AUTHORIZED</span>
            </div>
            {STEPS.map(s => (
              <div key={s.step} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{s.step}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{s.basis}</div>
                </div>
                <span className={`pill ${s.tone}`}>{s.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'blockers' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Blocking Conditions</h3>
              <span className="pill pill-error">4 active · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'blocker', label: 'Blocker' },
              { key: 'age', label: 'Age', render: (v) => <span className={`pill ${v === '6d' ? 'pill-error' : 'pill-muted'}`} title="Time blocked — aging signals urgency, not auto-escalation">{v}</span> },
              { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${BLOCKERS.find(b => b.severity === v)?.tone || 'pill-muted'}`} title={v === 'Required' ? 'Explicit operator sign-off required' : 'Must clear before workflow proceeds'}>{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.id}`)}>Open</button> },
            ]} rows={BLOCKERS} />
          </div>
        </div>
      )}

      {view === 'history' && (
        <div className="subview">
          <DataNotice tone="sample" title="History is demonstration data">
            Decision notes and audit trail shown here are samples until a Commerce Ops backend is connected.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Decision Notes &amp; Audit Trail</h3>
              <span className="pill pill-muted">4 entries · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'event', label: 'Event' },
              { key: 'actor', label: 'Actor' },
              { key: 'when', label: 'When' },
              { key: 'kind', label: 'Kind', render: (v) => <span className={`pill ${v === 'Blocked' || v === 'Expiry' ? 'pill-ochre' : 'pill-muted'}`} title="Audit entry kind (sample)">{v}</span> },
            ]} rows={HISTORY} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}
