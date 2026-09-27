import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'exceptions', label: 'Exceptions', count: 2 },
  { id: 'activity', label: 'Activity' },
  { id: 'exposure', label: 'Exposure' },
  { id: 'handoffs', label: 'Handoffs' },
]

const ROOM_ROUTE = (room, id) => ({
  SourceScout: id ? `/product-finder/${id}` : '/product-finder',
  'Golden Goose': id ? `/golden-goose/${id}` : '/golden-goose',
  'Commerce Ops': '/commerce-ops',
  ListingForge: '/listingforge',
  AdPilot: '/adpilot',
  Profitability: '/profitability',
  Admin: '/admin',
}[room] || '/home')

const TASKS = [
  { id: 'T-01', title: 'Review SourceScout B08L5VJQ7T', type: 'decision', urgency: 'high', owner: 'Operator A', room: 'SourceScout', target: 'B08L5VJQ7T' },
  { id: 'T-02', title: 'Approve Commerce Ops handoff #4471', type: 'approval', urgency: 'high', owner: 'Operator B', room: 'Commerce Ops' },
  { id: 'T-03', title: 'Investigate GG-001 opportunity', type: 'research', urgency: 'medium', owner: 'Operator A', room: 'Golden Goose', target: 'GG-001' },
  { id: 'T-04', title: 'Verify invoice for Lot #8823', type: 'sourcing', urgency: 'medium', owner: 'Operator C', room: 'Commerce Ops' },
  { id: 'T-05', title: 'Review Q3 profitability report', type: 'report', urgency: 'low', owner: 'Operator A', room: 'Profitability' },
]

const EXCEPTIONS = [
  { id: 'EX-01', title: 'Org #0838 lifecycle blocked (suspended)', severity: 'Critical', owner: 'Operator A', room: 'Admin', age: '2d', tone: 'pill-error' },
  { id: 'EX-02', title: 'Invite INV-2026-09-25-0192 expired', severity: 'High', owner: 'Operator A', room: 'Admin', age: '2d', tone: 'pill-warn' },
]

const ACTIVITY = [
  { date: '2026-09-26', days: 1, text: 'Set #47: 2 new ASINs added to research queue', room: 'SourceScout', state: 'CACHED' },
  { date: '2026-09-25', days: 2, text: 'Organization #0838 lifecycle blocked — review required', room: 'Admin', state: 'OBSERVED' },
  { date: '2026-09-25', days: 2, text: 'Invite INV-2026-09-25-0192 expired', room: 'Admin', state: 'OBSERVED' },
  { date: '2026-09-24', days: 3, text: 'Golden Goose opportunity GG-001 surfaced', room: 'Golden Goose', state: 'CACHED' },
  { date: '2026-09-23', days: 4, text: 'ListingForge revision v3.2 opened for editing', room: 'ListingForge', state: 'OBSERVED' },
  { date: '2026-09-19', days: 8, text: 'AdPilot weekly budget rule reviewed (no change applied)', room: 'AdPilot', state: 'HISTORICAL' },
  { date: '2026-09-17', days: 10, text: 'Commerce Ops handoff #4471 created', room: 'Commerce Ops', state: 'OBSERVED' },
]

const PORTFOLIO = [
  { set: 'Set A', asins: 12, margin: '~18%', status: 'Active', basis: 'Observed · sample' },
  { set: 'Set B', asins: 8, margin: 'UNKNOWN', status: 'Research', basis: 'Fee basis assumed' },
  { set: 'Set C', asins: 15, margin: '~22%', status: 'Approved', basis: 'Observed · sample' },
]

const SCOPE_DAYS = { Today: 1, '7d': 7, '30d': 30 }

export default function CommandCenter() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [scope, setScope] = useState('7d')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'

  const activity = ACTIVITY.filter(a => a.days <= SCOPE_DAYS[scope])
  const urgent = TASKS.filter(t => t.urgency === 'high')

  const openRoom = (room, target) => {
    navigate(ROOM_ROUTE(room, target))
    toast(`Opening ${room} — uncertainty is preserved on handoff.`, 'info')
  }
  const openPriorityQueue = () => {
    navigate('/commerce-ops')
    toast('Opening the priority workflow queue in Commerce Ops.', 'info')
  }

  const statePill = (s) => <span className="pill pill-muted" title={s === 'CACHED' ? 'Derived from cached sample data — may be stale' : s === 'HISTORICAL' ? 'Historical record — not current state' : 'Directly observed event (sample data)'}>{s}</span>

  return (
    <PageLayout
      title="Command Center"
      subtitle="Suite briefing — what changed, what needs attention, what is blocked, and where to go next."
      actions={<>
        <button className="btn btn-sm" onClick={openPriorityQueue} title="Open the priority workflow queue in Commerce Ops">Open Priority Queue</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('New scan requires a connected provider — sample mode.', 'info')}>New Scan</button>
        <button className="btn btn-sm btn-ghost">Briefing Settings</button>
      </>}
    >
      <DataNotice tone="sample" title="Briefing is demonstration data">
        Metrics, exceptions, and activity below are sample records with basis labels. No summary state implies purchase authorization or autonomous action.
      </DataNotice>

      <div className="card" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', padding: '10px 14px' }}>
        <span className="pill pill-muted" title="Active organization (sample)">Active org: Northstar Operations</span>
        <span style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Briefing: Sep 21–27, 2026</span>
        <div className="room-toolbar" style={{ margin: 0, marginLeft: 'auto' }}>
          {Object.keys(SCOPE_DAYS).map(s => (
            <button key={s} className={`filter-pill ${scope === s ? 'active' : ''}`} onClick={() => setScope(s)}>{s}</button>
          ))}
        </div>
        <span className="pill pill-muted" style={{ fontSize: 10 }}>Sample scope</span>
      </div>

      <RoomTabs tabs={TABS} base="/home" />

      {view === 'overview' && (
        <div className="subview">
          <div className="grid-4" style={{ marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Urgent Decisions</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{urgent.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Require review</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample task list, not live data">Basis: sample task list</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Research Queue</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{TASKS.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Active tasks</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample queue, not live data">Basis: sample queue</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Exceptions</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--clay)' }}>{EXCEPTIONS.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Require attention</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample exception feed">Basis: sample exception feed</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Portfolio Exposure</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{PORTFOLIO.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Active sets</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample portfolio">Basis: sample portfolio</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Exception Stack</h3>
              <span className="pill pill-clay">{EXCEPTIONS.length} items</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {EXCEPTIONS.map(e => (
                <div key={e.id} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{e.title}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>Owner: {e.owner} · {e.room} · aged {e.age}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`pill ${e.tone}`}>{e.severity}</span>
                    <button className="btn btn-sm" onClick={() => openRoom(e.room)}>Open in room</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Urgent Decisions</h3>
                <span className="pill pill-clay">{urgent.length} items</span>
              </div>
              <div className="stack" style={{ gap: 10 }}>
                {urgent.map(t => (
                  <div className="list-row" key={t.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{t.title}</div>
                      <div className="text-low" style={{ fontSize: 11 }}>Owner: {t.owner}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className={`pill ${t.type === 'approval' ? 'pill-ochre' : 'pill-warn'}`}>{t.type}</span>
                      <button className="btn btn-sm" onClick={() => openRoom(t.room, t.target)}>Open in room</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Priority Routes</h3>
                <span className="pill pill-muted">uncertainty preserved</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {['SourceScout', 'Golden Goose', 'Commerce Ops', 'ListingForge', 'AdPilot'].map(room => (
                  <div key={room} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                    <div style={{ fontSize: 13 }}>{room}</div>
                    <button className="btn btn-sm btn-ghost" onClick={() => openRoom(room)}>Open in room</button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="stack" style={{ gap: 20, marginTop: 20 }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">What Changed</h3>
                <span className="pill pill-muted">{activity.length} events · {scope}</span>
              </div>
              <Timeline items={activity} statePill={statePill} />
            </div>
          </div>
        </div>
      )}

      {view === 'exceptions' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Exception Stack</h3>
              <span className="pill pill-clay">{EXCEPTIONS.length} items · sample</span>
            </div>
            <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Owners and aging shown for routing — sample records.</div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Exception' },
              { key: 'severity', label: 'Severity', render: (v, row) => <span className={`pill ${row.tone}`} title="Must be reviewed by an operator before proceeding">{v}</span> },
              { key: 'owner', label: 'Owner' },
              { key: 'room', label: 'Room' },
              { key: 'age', label: 'Age', render: (v) => <span className="pill pill-muted" title="Time open — aging signals urgency, not auto-escalation">{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => openRoom(row.room)}>Open in room</button> },
            ]} rows={EXCEPTIONS} />
          </div>
        </div>
      )}

      {view === 'activity' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Cross-Suite Activity</h3>
              <span className="pill pill-muted">{activity.length} events · {scope}</span>
            </div>
            <Timeline items={activity} statePill={statePill} />
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Assigned-Owner Visibility</h3>
              <span className="pill pill-muted">sample</span>
            </div>
            <DataTable columns={[
              { key: 'owner', label: 'Owner' },
              { key: 'task', label: 'Task' },
              { key: 'urgency', label: 'Priority', render: (v) => <span className={`pill ${v === 'high' ? 'pill-warn' : v === 'medium' ? 'pill-ochre' : 'pill-muted'}`}>{v}</span> },
            ]} rows={TASKS.map(t => ({ owner: t.owner, task: t.title, urgency: t.urgency }))} />
          </div>
        </div>
      )}

      {view === 'exposure' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Margin and status are not authorizations">
            Margin figures are sample estimates; set status is an internal review state, never a purchase authorization.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Portfolio Exposure</h3>
              <span className="pill pill-muted">{PORTFOLIO.length} sets · sample</span>
            </div>
            <DataTable columns={[
              { key: 'set', label: 'Set' },
              { key: 'asins', label: 'ASINs' },
              { key: 'margin', label: 'Margin', render: (v) => v === 'UNKNOWN'
                ? <span className="pill pill-unknown" title="Fee basis assumed and cost data missing — margin not computable">UNKNOWN</span>
                : <span className="pill pill-muted" title="Sample estimate — not a verified calculation">{v}</span> },
              { key: 'status', label: 'Status', render: (v) => v === 'Research'
                ? <span className="pill pill-warn" title="In research — no sourcing decision made">Research</span>
                : <span className="pill pill-muted" title="Internal review state — not an authorization to purchase">{v}</span> },
              { key: 'basis', label: 'Basis', render: (v) => <span className="pill pill-muted" title="Data basis for this row">{v}</span> },
            ]} rows={PORTFOLIO} />
          </div>
        </div>
      )}

      {view === 'handoffs' && (
        <div className="subview">
          <DataNotice tone="internal" title="Handoffs preserve uncertainty">
            Forwarding a task to a room carries its UNKNOWN/UNVERIFIED state with it. No handoff implies purchase authorization or autonomous action.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Handoff Queue</h3>
              <span className="pill pill-muted">{TASKS.length} items · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'title', label: 'Task' },
              { key: 'room', label: 'Target Room' },
              { key: 'owner', label: 'Owner' },
              { key: 'urgency', label: 'Priority', render: (v) => <span className={`pill ${v === 'high' ? 'pill-warn' : v === 'medium' ? 'pill-ochre' : 'pill-muted'}`}>{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => openRoom(row.room, row.target)}>Open in room</button> },
            ]} rows={TASKS} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}

function Timeline({ items, statePill }) {
  return (
    <div className="timeline" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {items.map((item, i) => (
        <div key={i} className="timeline-item" style={{ display: 'flex', gap: 12, padding: '8px 0', position: 'relative' }}>
          <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, background: 'rgba(138,138,122,0.12)', color: '#8a8a7a' }}>
            ·
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: 'var(--ink)' }}>{item.text}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--ink-soft)', fontFamily: 'var(--font-mono)' }}>{item.date}</span>
              <span className="pill pill-muted" style={{ fontSize: 10 }}>{item.room}</span>
              {statePill(item.state)}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
