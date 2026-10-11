import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import signals, { settle } from '../../services/signals.js'
import MasterBrainPanel from '../../studio/components/MasterBrainPanel.jsx'

const TABS = [
  { id: 'workflow', label: 'Workflow' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'blockers', label: 'Blockers' },
  { id: 'history', label: 'History' },
]

const BLOCK_PILL = { 'Pack match UNKNOWN': 'pill-unknown', 'Invoice pending': 'pill-warn', 'Approval needed': 'pill-ochre' }

const ts = (x) => (x ? String(x).slice(0, 19).replace('T', ' ') : '—')

// ═══ One real read set: identity-resolution queue + approvals + runs ═══
function useCommerceOps() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [queue, approvals] = await Promise.all([
        settle(signals.ncCommerceOpsQueue()),
        settle(foundationApi.approvals()),
      ])
      if (alive) setSt({ loaded: true, queue, approvals })
    })()
    return () => { alive = false }
  }, [])
  const q = st.queue && st.queue.ok ? st.queue.value : null
  const items = q && Array.isArray(q.items) ? q.items : []
  const runs = q && q.summary && Array.isArray(q.summary.recent_runs) ? q.summary.recent_runs : []
  const apItems = st.approvals && st.approvals.ok ? (st.approvals.value.items || []) : []
  const apPending = apItems.filter(a => (a.state || '') === 'REQUESTED')
  return { loaded: st.loaded, queueOk: !!(st.queue && st.queue.ok), items, runs, apItems, apPending }
}

// ═══ Real foundation approvals (read-only) ═══
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
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="co-foundation-approvals" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation approvals</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 8 }}>
        Live, organization-scoped approval requests. Recording a decision is an operator action; no approval implies purchase authorization on its own.
      </p>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading approval requests…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in and select an organization to read foundation approval requests.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Approval queue unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'id', label: 'Request' },
          { key: 'capability', label: 'Capability' },
          { key: 'safety_class', label: 'Safety Class' },
          { key: 'risk_level', label: 'Risk', render: (v) => <span className={`pill ${v === 'high' ? 'pill-warn' : v === 'critical' ? 'pill-error' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
          { key: 'required_approver_role', label: 'Required Approver' },
          { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'REQUESTED' ? 'pill-ochre' : v === 'GRANTED' ? 'pill-ok' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
          { key: 'expires_at', label: 'Expires' },
        ]} rows={st.items} />
      ) : <p data-testid="co-approvals-empty" style={{ fontSize: 13 }}>No foundation approval requests for your organization yet.</p>)}
    </div>
  )
}

export default function CommerceOps() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()
  const d = useCommerceOps()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'workflow'

  const selected = d.items.find(q => (q.costco_item_number || q.id) === id) || null
  const blockers = d.items.filter(q => q.missing_identity_fields || q.missing_physical_fields)
  const failedRuns = d.runs.filter(r => String(r.status || '').toLowerCase() !== 'completed')

  const queueCols = [
    { key: 'costco_item_number', label: 'Item' },
    { key: 'missing_identity_fields', label: 'Missing identity', render: (v) => v ? <span className="pill pill-ochre">{v}</span> : <span className="pill pill-muted">none</span> },
    { key: 'missing_physical_fields', label: 'Missing physical', render: (v) => v ? <span className="pill pill-ochre">{v}</span> : <span className="pill pill-muted">none</span> },
    { key: 'possible_next_source', label: 'Next source', render: (v) => v || '—' },
    { key: 'created_at', label: 'Queued', render: (v) => ts(v) },
    { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.costco_item_number || row.id}`)}>Open</button> },
  ]

  return (
    <PageLayout
      title="Commerce Ops"
      subtitle="Workflow control room — identity/pack resolution, approvals, blockers, and pipeline history from real local data."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('New workflow requires a product set and operator owner — creation is not connected in this beta.', 'info')}>New Workflow</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Use the filter pills / tabs to narrow the queue.', 'info')}>Filter</button>
      </>}
    >
      <DataNotice tone="internal" title="Real local workflow data">
        The identity-resolution queue, pipeline history, and foundation approvals are live local reads. When the queue is empty it is shown honestly — no fabricated workflow items.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/commerce-ops" />

      {view === 'workflow' && (
        <div className="subview">
          {id && selected ? (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-head">
                <h3 className="card-title">{selected.costco_item_number || selected.id} — resolution</h3>
                <span className="pill pill-ochre">queued</span>
              </div>
              <div className="grid-4" style={{ gap: 12 }}>
                {[
                  { label: 'Costco item', v: selected.costco_item_number || 'UNKNOWN' },
                  { label: 'Run', v: selected.run_id || 'UNKNOWN' },
                  { label: 'Title-only insufficient', v: selected.title_only_insufficient ? 'yes' : 'no' },
                  { label: 'Physical pack missing', v: selected.physical_pack_missing ? 'yes' : 'no' },
                ].map(x => (
                  <div key={x.label}>
                    <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{x.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{x.v}</div>
                  </div>
                ))}
              </div>
              <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                {selected.missing_identity_fields && <span className="pill pill-ochre">missing identity: {selected.missing_identity_fields}</span>}
                {selected.missing_physical_fields && <span className="pill pill-ochre">missing physical: {selected.missing_physical_fields}</span>}
                {selected.possible_next_source && <span className="pill pill-muted">next source: {selected.possible_next_source}</span>}
              </div>
              <div style={{ marginTop: 14 }}>
                <button className="btn btn-sm btn-ghost" onClick={() => navigate('/commerce-ops')}>Back to queue</button>
              </div>
            </div>
          ) : id ? (
            <div className="card" style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 13 }}>No queue item “{id}” in the local data — nothing is fabricated.</p>
              <button className="btn btn-sm btn-ghost" onClick={() => navigate('/commerce-ops')}>Back to queue</button>
            </div>
          ) : null}

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Identity resolution queue</h3>
              <span className={`pill pill-${d.queueOk ? 'muted' : 'unknown'}`}>{d.loaded ? (d.queueOk ? `${d.items.length} items · local` : 'unavailable') : 'Loading…'}</span>
            </div>
            {d.items.length > 0 ? <DataTable columns={queueCols} rows={d.items} />
              : <p data-testid="co-queue-empty" style={{ fontSize: 13 }}>No identity-resolution items queued. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'tasks' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Documentation &amp; identity tasks</h3>
              <span className="pill pill-muted">{d.items.length} from queue · local</span>
            </div>
            {d.items.length > 0 ? (
              <DataTable columns={[
                { key: 'costco_item_number', label: 'Item' },
                { key: 'missing_identity_fields', label: 'Identity task', render: (v) => v ? <span className="pill pill-ochre">{v}</span> : <span className="pill pill-muted">—</span> },
                { key: 'missing_physical_fields', label: 'Physical task', render: (v) => v ? <span className="pill pill-ochre">{v}</span> : <span className="pill pill-muted">—</span> },
                { key: 'possible_next_source', label: 'Suggested source', render: (v) => v || '—' },
                { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.costco_item_number || row.id}`)}>Open</button> },
              ]} rows={d.items} />
            ) : <p style={{ fontSize: 13 }}>No documentation tasks. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'approvals' && (
        <div className="subview">
          <DataNotice tone="internal" title="Approvals require explicit operator sign-off">
            No approval step auto-completes. A positive signal anywhere in NorthstarOS never implies purchase authorization.
          </DataNotice>
          <FoundationApprovals />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Approval Checkpoints</h3>
              <span className="pill pill-ochre">{d.apPending.length} awaiting</span>
            </div>
            {d.apItems.length > 0 ? (
              <DataTable columns={[
                { key: 'id', label: 'Request' },
                { key: 'capability', label: 'Item' },
                { key: 'safety_class', label: 'Gate' },
                { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'REQUESTED' ? 'pill-ochre' : v === 'GRANTED' ? 'pill-ok' : 'pill-muted'}`}>{v || 'UNKNOWN'}</span> },
              ]} rows={d.apItems} />
            ) : <p data-testid="co-checkpoints-empty" style={{ fontSize: 13 }}>No approval checkpoints for this organization. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'blockers' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Blocking Conditions</h3>
              <span className={`pill ${blockers.length ? 'pill-error' : 'pill-muted'}`}>{blockers.length} active · local</span>
            </div>
            {blockers.length > 0 ? (
              <DataTable columns={[
                { key: 'costco_item_number', label: 'Item' },
                { key: 'blocker', label: 'Blocker', render: (v, row) => [row.missing_identity_fields, row.missing_physical_fields].filter(Boolean).join(' · ') || 'UNKNOWN' },
                { key: 'created_at', label: 'Since', render: (v) => ts(v) },
                { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.costco_item_number || row.id}`)}>Open</button> },
              ]} rows={blockers} />
            ) : <p data-testid="co-blockers-empty" style={{ fontSize: 13 }}>No blocking conditions in the queue. Honest empty state.</p>}
            {failedRuns.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Failed / partial pipeline runs</div>
                {failedRuns.map((r, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{r.run_name || r.run_id}</span>
                    <span className="pill pill-warn">{r.status || 'UNKNOWN'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'history' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Pipeline History</h3>
              <span className="pill pill-muted">{d.runs.length} runs · local</span>
            </div>
            {d.runs.length > 0 ? (
              <DataTable columns={[
                { key: 'run_name', label: 'Run' },
                { key: 'status', label: 'Status', render: (v) => <span className={`pill ${String(v).toLowerCase() === 'completed' ? 'pill-muted' : 'pill-warn'}`}>{v || 'UNKNOWN'}</span> },
                { key: 'discovered', label: 'Discovered', render: (v) => v == null ? '—' : v },
                { key: 'eligible', label: 'Eligible', render: (v) => v == null ? '—' : v },
                { key: 'created_at', label: 'Started', render: (v) => ts(v) },
              ]} rows={d.runs} />
            ) : <p style={{ fontSize: 13 }}>No pipeline runs recorded. Honest empty state.</p>}
          </div>
        </div>
      )}
    <MasterBrainPanel title="Studio evidence for operations (read-only)" />
    </PageLayout>
  )
}
