import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import signals, { settle } from '../../services/signals.js'

const TABS = [
  { id: 'sets', label: 'Sets' },
  { id: 'trends', label: 'Trends' },
  { id: 'coverage', label: 'Coverage' },
  { id: 'alerts', label: 'Alerts' },
]

// ═══ One real read set: local keyword data + foundation keyword service ═══
function useKeywordData() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [local, fSearch, fGaps] = await Promise.all([
        settle(signals.ncKeywords()),
        settle(foundationApi.keywordSearch('')),
        settle(foundationApi.keywordGaps()),
      ])
      if (alive) setSt({ loaded: true, local, fSearch, fGaps })
    })()
    return () => { alive = false }
  }, [])
  const local = st.local && st.local.ok ? st.local.value : null
  const keywords = local && Array.isArray(local.items) ? local.items : []
  const perf = local && local.summary && Array.isArray(local.summary.performance) ? local.summary.performance : []
  const fKw = st.fSearch && st.fSearch.ok ? (st.fSearch.value.items || []) : []
  const fGaps = st.fGaps && st.fGaps.ok ? (st.fGaps.value.items || []) : []
  const anyOk = (st.local && st.local.ok) || (st.fSearch && st.fSearch.ok) || (st.fGaps && st.fGaps.ok)
  return { loaded: st.loaded, anyOk, keywords, perf, fKw, fGaps }
}

const DIR_PILL = (m) => /promot|up|ris/i.test(m || '') ? 'pill-ok' : /demot|down|fall/i.test(m || '') ? 'pill-ochre' : 'pill-muted'

export default function KeywordTracker() {
  const { toast } = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const d = useKeywordData()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'sets'

  const verified = (term) => toast(`Opened “${term}” — verify against the live source before acting.`, 'info')

  return (
    <PageLayout
      title="Keyword Tracker"
      subtitle="Search-visibility lab — keyword sets, rank trends, coverage health, and flagged movement, from real local + foundation data."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Track New — adding terms is not connected in this beta (sample).', 'info')}>Track New</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Reports export uses local keyword data.', 'info')}>Reports</button>
      </>}
    >
      <DataNotice tone="internal" title="Real keyword data — local + foundation">
        Keyword sets and rank movement come from the local keyword store; tracked keywords and coverage gaps come from the foundation keyword service. Empty is shown honestly — nothing is fabricated. Position figures are observed snapshots, not guaranteed live ranks.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/keyword-tracker" />

      {view === 'sets' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Keyword Sets</h3>
              <span className={`pill pill-${d.loaded && !d.anyOk ? 'unknown' : 'muted'}`}>{d.loaded ? `${d.keywords.length} local · ${d.fKw.length} foundation` : 'Loading…'}</span>
            </div>
            {d.keywords.length > 0 ? (
              <DataTable columns={[
                { key: 'keyword', label: 'Keyword' },
                { key: 'search_volume', label: 'Volume', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : Number(v).toLocaleString() },
                { key: 'trend_direction', label: 'Trend', render: (v) => <span className={`pill ${DIR_PILL(v)}`}>{v || 'UNKNOWN'}</span> },
                { key: 'competition_level', label: 'Competition', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'relevance_score', label: 'Relevance', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{v}</span> },
                { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => verified(row.keyword)}>Verify</button> },
              ]} rows={d.keywords} />
            ) : <p data-testid="kw-sets-empty" style={{ fontSize: 13 }}>No local keyword sets. Honest empty state.</p>}
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Foundation tracked keywords</h3>
              <span className="pill pill-muted">{d.fKw.length}</span>
            </div>
            {d.fKw.length > 0 ? (
              <DataTable columns={[
                { key: 'normalized_phrase', label: 'Keyword' },
                { key: 'match_type', label: 'Match', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'confidence', label: 'Confidence', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{v}</span> },
                { key: 'link_count', label: 'Coverage', render: (v) => v ? <span className="pill pill-muted">{v} linked</span> : <span className="pill pill-unknown">No listing</span> },
              ]} rows={d.fKw} />
            ) : <p style={{ fontSize: 13 }}>No foundation keyword data ingested yet. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'trends' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Rank Trend Summary</h3>
              <span className="pill pill-muted">{d.perf.length} performance rows · local</span>
            </div>
            {d.perf.length > 0 ? (
              <DataTable columns={[
                { key: 'asin', label: 'ASIN' },
                { key: 'organic_rank', label: 'Organic', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">#{v}</span> },
                { key: 'sponsored_rank', label: 'Sponsored', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">#{v}</span> },
                { key: 'movement', label: 'Movement', render: (v) => <span className={`pill ${DIR_PILL(v)}`}>{v || 'UNKNOWN'}</span> },
                { key: 'tier', label: 'Tier', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'recorded_at', label: 'Recorded', render: (v) => v ? String(v).slice(0, 19).replace('T', ' ') : '—' },
              ]} rows={d.perf} />
            ) : <p data-testid="kw-trends-empty" style={{ fontSize: 13 }}>No rank-trend observations recorded. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'coverage' && (
        <div className="subview">
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Coverage Gaps</h3>
              <span className="pill pill-ochre">{d.fGaps.length} untargeted · foundation</span>
            </div>
            {d.fGaps.length > 0 ? (
              <DataTable columns={[
                { key: 'normalized_phrase', label: 'Gap Keyword' },
                { key: 'match_type', label: 'Match', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'confidence', label: 'Confidence', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{v}</span> },
                { key: 'action', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => verified(row.normalized_phrase)}>Verify</button> },
              ]} rows={d.fGaps} />
            ) : <p data-testid="kw-gaps-empty" style={{ fontSize: 13 }}>No coverage gaps recorded. Honest empty state — no untargeted keywords in the foundation data.</p>}
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Gaps are untargeted keywords from the foundation service — opportunities, not failures.</div>
          </div>
        </div>
      )}

      {view === 'alerts' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Flagged Movement Alerts</h3>
              <span className={`pill ${d.perf.filter(p => p.movement).length ? 'pill-ochre' : 'pill-muted'}`}>{d.perf.filter(p => p.movement).length} with movement · local</span>
            </div>
            {d.perf.filter(p => p.movement).length > 0 ? (
              <DataTable columns={[
                { key: 'asin', label: 'ASIN' },
                { key: 'movement', label: 'Movement', render: (v) => <span className={`pill ${DIR_PILL(v)}`}>{v || 'UNKNOWN'}</span> },
                { key: 'tier', label: 'Tier', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
                { key: 'days_in_tier', label: 'Days in tier', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'action', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate('/keyword-tracker?view=trends')}>Verify in Trends</button> },
              ]} rows={d.perf.filter(p => p.movement)} />
            ) : <p data-testid="kw-alerts-empty" style={{ fontSize: 13 }}>No flagged movement. Honest empty state — no rank movement recorded.</p>}
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Movement is an observed indication, not verified live rank. Confirm in Trends before acting.</div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
