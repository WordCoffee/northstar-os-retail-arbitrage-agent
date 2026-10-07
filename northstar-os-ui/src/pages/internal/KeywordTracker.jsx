import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import KeywordLane from '../../components/KeywordLane.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'

// ═══ Foundation keyword data (truth-first, read-only) ═══
// Reads the real, organization-scoped foundation keyword routes. Missing
// metrics stay UNKNOWN — nothing is fabricated. When the local foundation DB
// has no imported keyword data, honest empty/unavailable states are shown.
function KwSection({ title, result, columns, emptyText }) {
  const rows = result && result.ok ? (result.value.items || []) : []
  const err = result && !result.ok
    ? String((result.error && (result.error.code || result.error.status)) || 'error')
    : null
  return (
    <div style={{ marginTop: 14 }}>
      <div className="card-head" style={{ marginBottom: 8 }}>
        <h4 style={{ fontSize: 13, color: 'var(--pine)' }}>{title}</h4>
        {err
          ? <span className="pill pill-unknown" title="Foundation route not available for this session/organization">{err}</span>
          : <span className="pill pill-muted">{rows.length}</span>}
      </div>
      {err
        ? <p className="text-low" style={{ fontSize: 12 }}>Not available for this session or organization.</p>
        : <DataTable columns={columns} rows={rows} emptyText={emptyText} />}
    </div>
  )
}

function FoundationKeywordPanel() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    const settle = async (p) => {
      try { return { ok: true, value: await p } } catch (e) { return { ok: false, error: e } }
    }
    ;(async () => {
      const [keywords, gaps, terms] = await Promise.all([
        settle(foundationApi.keywordSearch('')),
        settle(foundationApi.keywordGaps()),
        settle(foundationApi.searchTerms()),
      ])
      if (alive) setSt({ loaded: true, keywords, gaps, terms })
    })()
    return () => { alive = false }
  }, [])

  const results = [st.keywords, st.gaps, st.terms]
  const anyAuth = st.loaded && results.every(r => r && !r.ok && r.error && r.error.status === 401)
  const badge = !st.loaded
    ? { label: 'Loading…', tone: 'muted' }
    : anyAuth
      ? { label: 'Sign-in required', tone: 'unknown' }
      : { label: 'Read-only · foundation', tone: 'muted' }

  const confCol = (label = 'Confidence') => ({
    key: 'confidence', label,
    render: (v) => v == null
      ? <span className="pill pill-unknown" title="No confidence recorded — not inferred">UNKNOWN</span>
      : <span className="pill pill-muted">{v}</span>,
  })
  const matchCol = { key: 'match_type', label: 'Match', render: (v) => v ? <span className="pill pill-muted">{v}</span> : <span className="pill pill-unknown">UNKNOWN</span> }
  const phraseCol = { key: 'normalized_phrase', label: 'Keyword' }

  return (
    <div className="card" data-testid="kw-foundation" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Foundation keyword data</h3>
        <span className={`pill pill-${badge.tone}`}>{badge.label}</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 6 }}>
        Live, organization-scoped read from the foundation keyword service. Absent metrics stay UNKNOWN — nothing is fabricated. Keyword import is an operator action; there is no live provider call here.
      </p>

      {!st.loaded ? (
        <p data-testid="kw-foundation-loading" style={{ fontSize: 13 }}>Loading foundation keyword data…</p>
      ) : anyAuth ? (
        <p data-testid="kw-foundation-auth" style={{ fontSize: 13 }}>Sign in and select an organization to read foundation keyword data.</p>
      ) : (
        <>
          <KwSection
            title="Tracked keywords"
            result={st.keywords}
            emptyText="No keyword data ingested for your organization yet."
            columns={[
              phraseCol, matchCol, confCol(),
              { key: 'link_count', label: 'Coverage', render: (v, row) => v
                ? <span className="pill pill-muted" title={`${row.target_count || 0} targets · ${v} linked listings`}>{v} linked</span>
                : <span className="pill pill-unknown" title="No listing links recorded">No listing</span> },
              { key: 'freshness_state', label: 'Freshness', render: (v) => v ? <span className="pill pill-muted">{v}</span> : <span className="pill pill-unknown">UNKNOWN</span> },
            ]}
          />
          <KwSection
            title="Coverage gaps (untargeted keywords)"
            result={st.gaps}
            emptyText="No untargeted keywords — no coverage gaps recorded."
            columns={[phraseCol, matchCol, confCol()]}
          />
          <KwSection
            title="Search terms"
            result={st.terms}
            emptyText="No search-term data ingested for your organization yet."
            columns={[
              { key: 'normalized_term', label: 'Search term', render: (v, row) => v || row.raw_term || 'UNKNOWN' },
              { key: 'impressions', label: 'Impressions', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
              { key: 'clicks', label: 'Clicks', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
              { key: 'orders', label: 'Orders', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
              { key: 'source', label: 'Source', render: (v) => v ? <span className="pill pill-muted">{v}</span> : <span className="pill pill-unknown">UNKNOWN</span> },
            ]}
          />
        </>
      )}
    </div>
  )
}

const TABS = [
  { id: 'sets', label: 'Sets', count: 4 },
  { id: 'lane', label: 'Live Lane' },
  { id: 'trends', label: 'Trends' },
  { id: 'coverage', label: 'Coverage' },
  { id: 'alerts', label: 'Alerts', count: 2 },
]

const SETS = [
  { id: 'S-01', name: 'Water Filter Core', terms: 34, asins: 1, health: 'Strong', tone: 'pill-muted' },
  { id: 'S-02', name: 'Kitchen Utility', terms: 28, asins: 1, health: 'Mixed', tone: 'pill-warn' },
  { id: 'S-03', name: 'Car Accessories', terms: 22, asins: 1, health: 'Weak', tone: 'pill-ochre' },
  { id: 'S-04', name: 'Audio', terms: 41, asins: 1, health: 'Strong', tone: 'pill-muted' },
]

const TRENDS = [
  { term: 'water filter', set: 'Water Filter Core', series: [14, 15, 17, 16, 14], position: '#14', change: '↑ 3', dir: 'up' },
  { term: 'water purifier', set: 'Water Filter Core', series: [27, 29, 30, 31, 32], position: '#32', change: '↓ 5', dir: 'down' },
  { term: 'countertop filter', set: 'Water Filter Core', series: [10, 9, 9, 8, 8], position: '#8', change: '↑ 1', dir: 'up' },
  { term: 'BPA free water filter', set: 'Water Filter Core', series: [33, 38, 41, 43, 45], position: '#45', change: '↓ 12', dir: 'down' },
  { term: 'desk lamp', set: 'Kitchen Utility', series: [12, 12, 11, 10, 9], position: '#9', change: '↑ 2', dir: 'up' },
]

const DIR_PILL = { up: 'pill-muted', down: 'pill-ochre' }

const COVERAGE = [
  { asin: 'B08L5VJQ7T', title: 'Premium Water Filter', covered: 24, partial: 7, gap: 3 },
  { asin: 'B09M8KJ4X2', title: 'LED Desk Lamp', covered: 18, partial: 6, gap: 4 },
  { asin: 'B07XJ8C9F3', title: 'Car Phone Mount', covered: 12, partial: 5, gap: 5 },
  { asin: 'B08N5WRWNW', title: 'Bluetooth Speaker', covered: 30, partial: 8, gap: 3 },
]

const ALERTS = [
  { id: 'KA-01', term: 'BPA free water filter', asin: 'B08L5VJQ7T', type: 'Position Drop', severity: 'High', date: '2026-09-25' },
  { id: 'KA-02', term: 'water purifier', asin: 'B08L5VJQ7T', type: 'Position Drop', severity: 'Medium', date: '2026-09-24' },
]

const UNCOVERED = [
  { term: 'under sink water filter', asin: 'B08L5VJQ7T', product: 'Premium Water Filter', set: 'Water Filter Core', gaps: 3, severity: 'High' },
  { term: 'car vent phone holder', asin: 'B07XJ8C9F3', product: 'Car Phone Mount', set: 'Car Accessories', gaps: 5, severity: 'High' },
  { term: 'dimmable desk lamp', asin: 'B09M8KJ4X2', product: 'LED Desk Lamp', set: 'Kitchen Utility', gaps: 2, severity: 'Medium' },
  { term: 'portable bluetooth speaker', asin: 'B08N5WRWNW', product: 'Bluetooth Speaker', set: 'Audio', gaps: 2, severity: 'Medium' },
]

const SEV_PILL = { High: 'pill-ochre', Medium: 'pill-warn', Low: 'pill-muted' }

function Sparkline({ series }) {
  const max = Math.max(...series, 1)
  const min = Math.min(...series)
  const range = Math.max(max - min, 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 24 }} title={`Last ${series.length} snapshots — position trend (lower is better)`}>
      {series.map((v, i) => (
        <div key={i} style={{ width: 5, height: 6 + ((v - min) / range) * 16, background: 'var(--ochre)', opacity: 0.5 + (i / series.length) * 0.5, borderRadius: 1 }} />
      ))}
    </div>
  )
}

export default function KeywordTracker() {
  const { toast } = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const [set, setSet] = useState('Water Filter Core')

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'sets'

  const verifyInTrends = (term) => {
    navigate('/keyword-tracker?view=trends')
    toast(`Opened “${term}” in Trends — verify against the cached snapshot before acting.`, 'info')
  }

  return (
    <PageLayout
      title="Keyword Tracker"
      subtitle="Search-visibility lab — keyword sets, rank trends, coverage health, and flagged movement."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Track New — add terms to the selected set (sample).', 'info')}>Track New</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Reports export uses cached snapshot data.', 'info')}>Reports</button>
      </>}
    >
      <DataNotice tone="cached" title="Sample preview — plus a live foundation read">
        The rankings, trends, coverage and alerts below are a cached sample preview. The “Foundation keyword data” card is a live, organization-scoped read from the foundation keyword service (empty until an operator import exists). Search volume is estimated and must not be treated as verified traffic. Position changes are indications — verify in Trends before acting.
      </DataNotice>

      <FoundationKeywordPanel />

      <div className="card" style={{ marginBottom: 16, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span className="text-low" style={{ fontSize: 11 }}>Keyword set</span>
        {SETS.map(s => (
          <button key={s.id} className={`filter-pill ${set === s.name ? 'active' : ''}`} onClick={() => setSet(s.name)}>{s.name}</button>
        ))}
        <span className="pill pill-muted" style={{ marginLeft: 'auto' }}>snapshot 2h ago</span>
      </div>

      <RoomTabs tabs={TABS} base="/keyword-tracker" />

      {view === 'lane' && <KeywordLane />}

      {view === 'sets' && (
        <div className="subview">
          <div className="grid-3" style={{ gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Terms in set</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{(SETS.find(s => s.name === set) || SETS[0]).terms}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{set}</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Improving</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{TRENDS.filter(t => t.dir === 'up').length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Rank trend summary</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Declining</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ochre)' }}>{TRENDS.filter(t => t.dir === 'down').length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Needs review</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Coverage Status</h3>
              <span className="pill pill-muted">covered / partial / gap</span>
            </div>
            <div className="stack" style={{ gap: 10 }}>
              {COVERAGE.map(c => {
                const total = c.covered + c.partial + c.gap
                return (
                  <div key={c.asin}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span>{c.asin} · {c.title}</span>
                      <span className="text-low">{c.covered}/{total} covered · {c.gap} gaps</span>
                    </div>
                    <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ width: `${(c.covered / total) * 100}%`, background: 'var(--pine)' }} />
                      <div style={{ width: `${(c.partial / total) * 100}%`, background: 'var(--ochre)', opacity: 0.6 }} />
                      <div style={{ width: `${(c.gap / total) * 100}%`, background: 'rgba(160,64,32,0.5)' }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Flagged Movement</h3>
              <span className="pill pill-ochre">{ALERTS.length} alerts</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {ALERTS.map(a => (
                <div key={a.id} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{a.term} — {a.type}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>{a.asin} · {a.date}</div>
                  </div>
                  <span className={`pill ${SEV_PILL[a.severity]}`}>{a.severity}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Keyword Sets</h3>
              <span className="pill pill-muted">{SETS.length} sets</span>
            </div>
            <DataTable columns={[
              { key: 'name', label: 'Set' },
              { key: 'terms', label: 'Terms' },
              { key: 'asins', label: 'ASINs' },
              { key: 'health', label: 'Health', render: (v, row) => <span className={`pill ${row.tone}`} title="Set health from coverage + movement — indication, not verified">{v}</span> },
            ]} rows={SETS} />
          </div>
        </div>
      )}

      {view === 'trends' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Rank Trend Summary</h3>
              <span className="pill pill-muted">{set} · cached snapshot</span>
            </div>
            <DataTable columns={[
              { key: 'term', label: 'Keyword' },
              { key: 'series', label: 'Trend', render: (v) => <Sparkline series={v} /> },
              { key: 'position', label: 'Position', render: (v) => <span className="pill pill-muted" title="Estimated position — cached snapshot">{v}</span> },
              { key: 'change', label: 'Change', render: (v, row) => <span className={`pill ${DIR_PILL[row.dir]}`} title="Movement — indication, not verified">{v}</span> },
              { key: 'set', label: 'Set' },
            ]} rows={TRENDS} />
          </div>
        </div>
      )}

      {view === 'coverage' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Coverage Gaps</h3>
              <span className="pill pill-muted">sample</span>
            </div>
            <DataTable columns={[
              { key: 'asin', label: 'ASIN' },
              { key: 'title', label: 'Product' },
              { key: 'covered', label: 'Covered', render: (v) => <span className="pill pill-muted">{v}</span> },
              { key: 'partial', label: 'Partial', render: (v) => <span className="pill pill-warn">{v}</span> },
              { key: 'gap', label: 'Gaps', render: (v) => <span className={`pill ${v > 3 ? 'pill-ochre' : 'pill-muted'}`} title="Missing coverage — a gap to address, not a failure">{v}</span> },
            ]} rows={COVERAGE} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Top Uncovered Terms</h3>
              <span className="pill pill-ochre">{UNCOVERED.length} gaps · sample</span>
            </div>
            <DataTable columns={[
              { key: 'term', label: 'Gap Term' },
              { key: 'asin', label: 'ASIN' },
              { key: 'product', label: 'Product' },
              { key: 'set', label: 'Set' },
              { key: 'severity', label: 'Signal', render: (v, row) => <span className={`pill ${SEV_PILL[v]}`} title="Gap severity — indication, not verified">{v} · {row.gaps}</span> },
              { key: 'action', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => verifyInTrends(row.term)}>Open in Trends</button> },
            ]} rows={UNCOVERED} />
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Gap terms come from the cached coverage snapshot — confirm in Trends">
              Gaps are opportunities from the cached snapshot — not failures. Confirm movement in Trends before prioritizing.
            </div>
          </div>
        </div>
      )}

      {view === 'alerts' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Flagged Movement Alerts</h3>
              <span className="pill pill-ochre">{ALERTS.length} active</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'term', label: 'Keyword' },
              { key: 'asin', label: 'ASIN' },
              { key: 'type', label: 'Type' },
              { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${SEV_PILL[v]}`}>{v}</span> },
              { key: 'date', label: 'Date' },
              { key: 'action', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => verifyInTrends(row.term)}>Verify in Trends</button> },
            ]} rows={ALERTS} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Movement by Keyword</h3>
              <span className="pill pill-muted">cached snapshot</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {ALERTS.map(a => (
                <div key={a.id} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{a.term}</div>
                    <div className="text-low" style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{a.asin} · {a.date}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className="pill pill-ochre" style={{ fontSize: 10 }} title="Direction of movement — indication, not verified">↓ Drop</span>
                    <span className={`pill ${SEV_PILL[a.severity]}`} style={{ fontSize: 10 }}>{a.severity}</span>
                    <button className="btn btn-sm btn-ghost" onClick={() => verifyInTrends(a.term)}>Verify in Trends</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
