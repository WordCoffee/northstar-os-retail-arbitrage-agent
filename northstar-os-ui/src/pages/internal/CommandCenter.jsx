import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
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
        <h3 className="card-title">Needs your review</h3>
        <span className="pill pill-muted">live · from your local data</span>
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
        source="local backend"
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
        source="catalog cache"
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
        source="local error tracker"
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
        source="Golden Goose service"
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

// ═══ Task-first entry (2026-10-16): what do you want to do today? ═══
const START = [
  { label: 'Design', note: 'Images, A+, print & mockups', route: '/design-studio', icon: 'brush' },
  { label: 'Listings', note: 'Write, review & version copy', route: '/listingforge', icon: 'list' },
  { label: 'Ads', note: 'Plan changes from your ad files', route: '/adpilot', icon: 'target' },
  { label: 'Social', note: 'Plan posts & export assets', route: '/socialpulse', icon: 'globe' },
  { label: 'Keywords', note: 'Track terms & movement', route: '/keyword-tracker', icon: 'search' },
  { label: 'Competitors', note: 'Watch local market evidence', route: '/competitor-monitor', icon: 'eye' },
]

function StartSomething({ navigate }) {
  return (
    <div className="card" data-testid="cc-start" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Start something</h3>
        <span className="pill pill-muted">your daily work</span>
      </div>
      <div className="grid-3" style={{ gap: 12 }}>
        {START.map(s => (
          <button
            key={s.route}
            className="card"
            onClick={() => navigate(s.route)}
            style={{ padding: 16, textAlign: 'left', cursor: 'pointer', fontFamily: 'var(--font-ui)', border: '1px solid var(--divider)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--pine-deep)' }}>{s.label}</span>
            </div>
            <div className="text-low" style={{ fontSize: 12, marginTop: 4 }}>{s.note}</div>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function CommandCenter() {
  const navigate = useNavigate()
  return (
    <PageLayout
      title="Command Center"
      subtitle="Your workspace — start something, then see what needs you."
      actions={<>
        <button className="btn btn-sm btn-primary" onClick={() => navigate('/design-studio')}>Open Design Studio</button>
        <button className="btn btn-sm" onClick={() => navigate('/design-studio?section=ads&view=amazon-files')}>Import an Amazon file</button>
      </>}
    >
      <StartSomething navigate={navigate} />
      <WorkQueues navigate={navigate} />
      <details style={{ marginBottom: 20 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-low)', marginBottom: 10 }}>
          System status &amp; local activity (advanced — read-only)
        </summary>
        <SystemSignals />
        <RealActivity />
      </details>
    </PageLayout>
  )
}
