import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'
import foundationApi from '../../foundation/api.js'

// ═══ Live work queues (real foundation reads) ═══
function WorkQueues({ navigate }) {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [gg, ap] = await Promise.all([
        settle(foundationApi.goldenGooseQueue()),
        settle(foundationApi.approvals()),
      ])
      if (alive) setSt({ loaded: true, gg, ap })
    })()
    return () => { alive = false }
  }, [])
  const ggItems = st.gg && st.gg.ok ? (st.gg.value.items || []) : null
  const apItems = st.ap && st.ap.ok ? (st.ap.value.items || []) : null
  const pending = apItems ? apItems.filter(a => (a.state || '') === 'REQUESTED').length : null
  const row = (label, value, tone, route, note) => (
    <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: '1px solid var(--divider)' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
        <div className="text-low" style={{ fontSize: 11 }}>{note}</div>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <span className={`pill ${tone}`}>{value}</span>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate(route)}>Open</button>
      </div>
    </div>
  )
  return (
    <div className="card" data-testid="cc-work-queues" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Work queues</h3>
        <span className="pill pill-muted">live · foundation</span>
      </div>
      {!st.loaded && <p style={{ fontSize: 13 }}>Reading work queues…</p>}
      {st.loaded && (
        <>
          {row('Golden Goose persisted queue',
            ggItems == null ? 'unavailable' : String(ggItems.length),
            ggItems == null ? 'pill-unknown' : 'pill-muted',
            '/golden-goose',
            st.gg && st.gg.ok ? `basis: ${st.gg.value.basis || 'UNKNOWN'}` : 'not readable')}
          {row('Foundation approvals pending',
            pending == null ? 'unavailable' : String(pending),
            pending == null ? 'pill-unknown' : (pending > 0 ? 'pill-ochre' : 'pill-muted'),
            '/commerce-ops?view=approvals',
            apItems == null ? 'not readable' : `${apItems.length} total request${apItems.length === 1 ? '' : 's'}`)}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Live counts from the foundation service. Empty is a valid, honest state.</div>
        </>
      )}
    </div>
  )
}

// ═══ Live local system signals (real reads, honest states) ═══
// Real read-only signals from the running local backend. Absent/unreachable
// signals render as "unavailable" — never fabricated. The sample briefing
// below (tasks/exceptions/activity) is separate and clearly labelled.
function SignalRow({ label, source, result, render }) {
  const err = result && !result.ok
  return (
    <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderBottom: '1px solid var(--divider)' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
        <div className="text-low" style={{ fontSize: 11 }}>{source}</div>
      </div>
      {!result
        ? <span className="pill pill-muted">Loading…</span>
        : err
          ? <span className="pill pill-unknown" title={`Live read failed${err && result.error && result.error.status ? ' (' + result.error.status + ')' : ''} — not fabricated`}>unavailable</span>
          : render(result.value)}
    </div>
  )
}

function SystemSignals() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [status, catalog, monitoring, gg] = await Promise.all([
        settle(signals.systemStatus()),
        settle(signals.sourceScoutSummary()),
        settle(signals.monitoringAlerts()),
        settle(signals.goldenGooseHealth()),
      ])
      if (alive) setSt({ loaded: true, status, catalog, monitoring, gg })
    })()
    return () => { alive = false }
  }, [])

  const data = (r) => (r && r.ok ? (r.value && r.value.data ? r.value.data : r.value) : null)

  return (
    <div className="card" data-testid="cc-system-signals" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">System signals</h3>
        <span className="pill pill-muted" title="Live, read-only local backend reads — not sample data">live local read</span>
      </div>
      <SignalRow
        label="Data mode &amp; warehouse"
        source="GET /api/v1/status"
        result={st.status}
        render={(v) => {
          const d = data({ ok: true, value: v }) || {}
          const wh = d.warehouse || {}
          return (
            <span className="inline-flex" style={{ gap: 6 }}>
              <span className={`pill ${d.mode === 'live' ? 'pill-ok' : 'pill-muted'}`} title="live = warehouse has live rows; demo = no live rows">{d.mode || 'UNKNOWN'}</span>
              <span className="pill pill-muted" title="Live-stocked warehouse rows (fresh only)">{wh.fresh_rows ?? 'UNKNOWN'} fresh</span>
              <span className="pill pill-muted" title="Total live warehouse rows">{wh.live_rows ?? 'UNKNOWN'} live</span>
            </span>
          )
        }}
      />
      <SignalRow
        label="Catalog coverage (quantity match)"
        source="GET /api/sourcescout/summary"
        result={st.catalog}
        render={(v) => (
          <span className="inline-flex" style={{ gap: 6 }}>
            <span className="pill pill-muted" title="Total cached catalog items">{v.total ?? 'UNKNOWN'} items</span>
            <span className="pill pill-ok" title="Amazon quantity matches Costco SKU">{v.pass ?? 0} pass</span>
            <span className="pill pill-warn" title="Amazon quantity differs from Costco SKU">{v.fail ?? 0} fail</span>
            <span className="pill pill-ochre" title="Costco SKU not found or ambiguous — needs review">{v.review ?? 0} review</span>
          </span>
        )}
      />
      <SignalRow
        label="API error rate"
        source="GET /api/monitoring/error-alerts"
        result={st.monitoring}
        render={(v) => {
          const s = (v && ((v.data && v.data.summary) || v.summary)) || {}
          const rate = s.five_xx_rate == null ? 'UNKNOWN' : `${(s.five_xx_rate * 100).toFixed(1)}%`
          return (
            <span className="inline-flex" style={{ gap: 6 }}>
              <span className={`pill ${s.breached ? 'pill-warn' : 'pill-ok'}`} title="5xx fraction over the rolling window vs threshold">{s.breached ? 'breached' : 'within threshold'}</span>
              <span className="pill pill-muted" title="5xx rate · window · sample size">{rate} · {s.total_requests ?? 0} req</span>
            </span>
          )
        }}
      />
      <SignalRow
        label="Golden Goose service"
        source="GET /api/golden-goose/health"
        result={st.gg}
        render={(v) => {
          const s = (v && ((v.data && v.data.status) || v.status)) || 'UNKNOWN'
          return <span className={`pill ${s === 'ok' ? 'pill-ok' : 'pill-warn'}`} title="Service health envelope">{s}</span>
        }}
      />
      <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Provenance rule">
        These are live local reads. When the backend is unreachable the row reads <em>unavailable</em> — it is never substituted with sample numbers.
      </div>
    </div>
  )
}

// ═══ Real local activity (pipeline runs + audit + campaigns) ═══
function RealActivity() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.ncActivity()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const runs = v && Array.isArray(v.items) ? v.items : []
  const s = (v && v.summary) || {}
  const audit = Array.isArray(s.audit) ? s.audit.slice(0, 5) : []
  const campaigns = Array.isArray(s.campaigns) ? s.campaigns.slice(0, 5) : []
  return (
    <div className="card" data-testid="cc-real-activity" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Local activity</h3>
        <span className={`pill pill-${st.phase === 'error' ? 'unknown' : 'muted'}`}>{st.phase === 'loading' ? 'Loading…' : st.phase === 'error' ? 'unavailable' : `${runs.length} runs · local`}</span>
      </div>
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Activity unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (
        <>
          {runs.length > 0 ? (
            <DataTable columns={[
              { key: 'run_name', label: 'Run' },
              { key: 'status', label: 'Status', render: (x) => <span className={`pill ${x === 'completed' ? 'pill-muted' : 'pill-warn'}`}>{x || 'UNKNOWN'}</span> },
              { key: 'created_at', label: 'Started', render: (x) => x ? String(x).slice(0, 19).replace('T', ' ') : '—' },
            ]} rows={runs} />
          ) : <p className="text-low" style={{ fontSize: 13 }}>No pipeline runs recorded. Honest empty state.</p>}
          <div className="grid-2" style={{ gap: 16, marginTop: 12 }}>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Recent audit</div>
              <div className="stack" style={{ gap: 4 }}>
                {audit.length > 0 ? audit.map((a, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{a.action}</span>
                    <span className="pill pill-muted" style={{ fontSize: 10 }}>{a.entity_type || '—'}</span>
                  </div>
                )) : <span className="text-low" style={{ fontSize: 12 }}>No audit entries.</span>}
              </div>
            </div>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Campaigns</div>
              <div className="stack" style={{ gap: 4 }}>
                {campaigns.length > 0 ? campaigns.map((c, i) => (
                  <div key={i} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <span style={{ fontSize: 12 }}>{c.campaign_name}</span>
                    <span className={`pill ${c.status === 'enabled' ? 'pill-muted' : 'pill-warn'}`} style={{ fontSize: 10 }}>{c.status || 'UNKNOWN'}</span>
                  </div>
                )) : <span className="text-low" style={{ fontSize: 12 }}>No campaigns.</span>}
              </div>
            </div>
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Real local activity (read-only). No provider call.</div>
        </>
      )}
    </div>
  )
}

const LAUNCH = [
  { label: 'SourceScout', route: '/product-finder', note: 'Cached product sourcing' },
  { label: 'Golden Goose', route: '/golden-goose', note: 'Opportunity review desk' },
  { label: 'Profitability', route: '/profitability', note: 'Economics & scenarios' },
  { label: 'Commerce Ops', route: '/commerce-ops', note: 'Workflow & approvals' },
  { label: 'Listing Guardian', route: '/listings', note: 'Listing watchtower' },
  { label: 'Monitoring', route: '/monitoring', note: 'System observability' },
]

function LaunchGrid({ navigate }) {
  return (
    <div className="card" data-testid="cc-launch-grid" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Launch a service</h3>
        <span className="pill pill-muted">6 rooms</span>
      </div>
      <div className="grid-3" style={{ gap: 12 }}>
        {LAUNCH.map(l => (
          <button
            key={l.route}
            className="card"
            onClick={() => navigate(l.route)}
            style={{ padding: 14, textAlign: 'left', cursor: 'pointer', fontFamily: 'var(--font-ui)', border: '1px solid var(--divider)' }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--pine-deep)' }}>{l.label}</div>
            <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>{l.note}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

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
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Briefing settings are not connected yet.', 'info')}>Briefing Settings</button>
      </>}
    >
      <DataNotice tone="sample" title="Live system signals + sample briefing">
        The “System signals” card is a live, read-only read from the local backend. Everything below it — briefing metrics, exceptions, activity, portfolio, handoffs — is demonstration data with basis labels. No summary state implies purchase authorization or autonomous action.
      </DataNotice>

      <SystemSignals />
      <WorkQueues navigate={navigate} />
      <RealActivity />
      <LaunchGrid navigate={navigate} />

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
