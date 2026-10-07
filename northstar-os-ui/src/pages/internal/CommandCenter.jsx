import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate } from 'react-router-dom'
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

export default function CommandCenter() {
  const { toast } = useToast()
  const navigate = useNavigate()
  return (
    <PageLayout
      title="Command Center"
      subtitle="Suite briefing — live system signals, work queues, and local activity."
      actions={<>
        <button className="btn btn-sm" onClick={() => { navigate('/commerce-ops'); toast('Opening the priority workflow queue in Commerce Ops.', 'info') }}>Open Priority Queue</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('New scan requires a connected provider — gated.', 'info')}>New Scan</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Briefing settings are not connected yet.', 'info')}>Briefing Settings</button>
      </>}
    >
      <DataNotice tone="internal" title="Live operational briefing">
        Every panel below is a live local read (system signals, work queues, activity). When a read is unavailable it says so — nothing is fabricated. No summary implies purchase authorization.
      </DataNotice>
      <SystemSignals />
      <WorkQueues navigate={navigate} />
      <RealActivity />
      <LaunchGrid navigate={navigate} />
    </PageLayout>
  )
}
