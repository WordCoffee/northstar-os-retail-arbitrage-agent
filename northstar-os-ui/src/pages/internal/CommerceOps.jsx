import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'queue', label: 'Queue', count: 5 },
  { id: 'workflow', label: 'Workflow Detail' },
  { id: 'docs', label: 'Documentation' },
]

const QUEUE = [
  { id: 'CO-01', type: 'Sourcing Validation', asin: 'B08L5VJQ7T', owner: 'Operator A', status: 'In Progress', blocking: 'Invoice pending', priority: 'high' },
  { id: 'CO-02', type: 'Pack/Case Verification', asin: 'B09M8KJ4X2', owner: 'Operator B', status: 'Pending', blocking: 'Pack match UNKNOWN', priority: 'high' },
  { id: 'CO-03', type: 'Research Handoff', asin: 'B07XJ8C9F3', owner: 'Operator A', status: 'Ready for Review', blocking: 'None', priority: 'medium' },
  { id: 'CO-04', type: 'Invoice Readiness', asin: 'B08N5WRWNW', owner: 'Operator C', status: 'Blocked', blocking: 'Invoice expired', priority: 'high' },
  { id: 'CO-05', type: 'Operator Decision', asin: 'B08L5VJQ7T', owner: 'Pending', status: 'Awaiting Decision', blocking: 'Approval needed', priority: 'high' },
]

const STEPS = [
  { step: '1. Sourcing Validation', state: 'In Progress', basis: 'Invoice pending verification', tone: 'pill-warn' },
  { step: '2. Pack/Case Verification', state: 'Blocked', basis: 'Pack match UNKNOWN', tone: 'pill-error' },
  { step: '3. Cost / Fee Basis', state: 'Pending', basis: 'UNAVAILABLE', tone: 'pill-muted' },
  { step: '4. Operator Approval', state: 'Awaiting', basis: 'Explicit sign-off required', tone: 'pill-ochre' },
]

export default function CommerceOps() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()
  const [filter, setFilter] = useState('all')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'workflow' : 'queue')

  const filtered = filter === 'all'
    ? QUEUE
    : filter === 'blocked'
      ? QUEUE.filter(q => q.status === 'Blocked' || q.blocking !== 'None')
      : QUEUE.filter(q => q.status.toLowerCase().replace(/\s/g, '-') === filter)

  const selected = QUEUE.find(q => q.id === (id || 'CO-01')) || QUEUE[0]

  return (
    <PageLayout
      title="Commerce Ops"
      subtitle="Workflow queue — sourcing validation, pack verification, invoice readiness, research handoffs, and operator decisions."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('New workflow requires a product set and operator owner — sample mode.', 'info')}>New Workflow</button>
        <button className="btn btn-sm btn-ghost">Filter</button>
      </>}
    >
      <DataNotice tone="sample" title="Workflow items are sample records">
        Owners, blocking conditions, and statuses are demonstration data. Live approval steps require a connected Commerce Ops backend.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/commerce-ops" />

      {view === 'queue' && (
        <div className="subview">
          <div className="room-toolbar">
            {[['all', 'All'], ['blocked', 'Blocked'], ['in-progress', 'In Progress'], ['ready-for-review', 'Ready']].map(([key, label]) => (
              <button key={key} className={`filter-pill ${filter === key ? 'active' : ''}`} onClick={() => setFilter(key)}>{label}</button>
            ))}
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Workflow Queue</h3>
              <span className="pill pill-clay">{filtered.length} items</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'type', label: 'Task Type' },
              { key: 'asin', label: 'ASIN' },
              { key: 'owner', label: 'Owner' },
              { key: 'status', label: 'Status' },
              { key: 'blocking', label: 'Blocking Condition' },
              { key: 'priority', label: 'Priority' },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/commerce-ops/${row.id}`)}>Open</button> },
            ]} rows={filtered} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Blocking Conditions</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Invoice readiness — must have valid, verified invoice documentation</div>
                <span className="pill pill-error">Critical</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Pack/case match — exact product identity must be confirmed</div>
                <span className="pill pill-warn">High</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Cost/fee basis — verified sourcing cost and fee structure required</div>
                <span className="pill pill-warn">High</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Operator approval — explicit sign-off before any purchase</div>
                <span className="pill pill-ochre">Required</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'workflow' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">{selected.id} — {selected.type}</h3>
              <span className="pill pill-warn">{selected.status}</span>
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
                  <div style={{ fontSize: 16, fontWeight: 700, color: d.tone || 'var(--pine-deep)' }}>{d.v}</div>
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
      )}

      {view === 'docs' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Documentation Tasks</h3>
              <span className="pill pill-forest">4 items</span>
            </div>
            <DataTable columns={[
              { key: 'task', label: 'Task' },
              { key: 'asin', label: 'ASIN' },
              { key: 'owner', label: 'Owner' },
              { key: 'status', label: 'Status' },
            ]} rows={[
              { task: 'Verify supplier invoice', asin: 'B08L5VJQ7T', owner: 'Operator A', status: 'In Progress' },
              { task: 'Confirm pack/case identity', asin: 'B09M8KJ4X2', owner: 'Operator B', status: 'Pending' },
              { task: 'Upload sourcing docs', asin: 'B07XJ8C9F3', owner: 'Operator C', status: 'Complete' },
              { task: 'Review invoice batch', asin: 'B08N5WRWNW', owner: 'Operator A', status: 'Expired' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}