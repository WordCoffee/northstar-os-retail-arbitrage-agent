import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real decision-control evaluate (backend gate policy) ═══
// A numeric score never sets PURCHASE_READY; mandatory gates + explicit approval do.
const GG_GATES = ['product_identity', 'variation_identity', 'pack_identity', 'economics_complete',
  'cost_known', 'fees_known', 'eligibility', 'sourcing_route', 'documentation', 'brand_permission']
const GATE_OPTS = ['PASS', 'FAIL', 'UNKNOWN', 'NOT_APPLICABLE']
const READINESS_OPTS = ['COMPLETE_VERIFIED', 'COMPLETE_ESTIMATED', 'SOURCE_UNVERIFIED', 'UNKNOWN']

function EvaluatePanel() {
  const [form, setForm] = useState({ item_id: '', economics_readiness: 'COMPLETE_VERIFIED', sample: false, approved: false })
  const [gates, setGates] = useState(() => Object.fromEntries(GG_GATES.map(g => [g, 'PASS'])))
  const [state, setState] = useState({ phase: 'idle' })

  const run = async () => {
    setState({ phase: 'submitting' })
    const body = {
      item_id: form.item_id || undefined,
      gate_inputs: gates,
      economics_readiness: form.economics_readiness,
      approval: form.approved ? { state: 'GRANTED' } : { state: 'none' },
      sample: form.sample,
    }
    const r = await settle(foundationApi.goldenGooseEvaluate(body))
    if (r.ok) setState({ phase: 'done', value: r.value })
    else setState({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', message: (r.error && r.error.message) || 'Evaluate failed.' })
  }

  const dec = state.phase === 'done' && state.value ? state.value.decision : null

  return (
    <div className="card" data-testid="gg-evaluate" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Evaluate opportunity (decision control)</h3>
        <span className="pill pill-muted">backend gate policy</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Set the mandatory gates and economics readiness; the backend decides the review/purchase state. A score alone never yields PURCHASE_READY — mandatory gates and explicit approval control readiness.
      </p>
      <div className="grid-3" style={{ gap: 12, marginBottom: 12 }}>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Item id (optional)</span>
          <input className="field" value={form.item_id} onChange={e => setForm(f => ({ ...f, item_id: e.target.value }))} placeholder="e.g. GG-001" />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Economics readiness</span>
          <select className="field" value={form.economics_readiness} onChange={e => setForm(f => ({ ...f, economics_readiness: e.target.value }))}>
            {READINESS_OPTS.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <div className="stack" style={{ gap: 8, justifyContent: 'center' }}>
          <div className="check-row"><input type="checkbox" id="gg-sample" checked={form.sample} onChange={e => setForm(f => ({ ...f, sample: e.target.checked }))} /><label htmlFor="gg-sample">Sample row (never purchase-ready)</label></div>
          <div className="check-row"><input type="checkbox" id="gg-approve" checked={form.approved} onChange={e => setForm(f => ({ ...f, approved: e.target.checked }))} /><label htmlFor="gg-approve">Approval granted (explicit)</label></div>
        </div>
      </div>
      <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Mandatory gates</div>
      <div className="grid-5" style={{ gap: 10, marginBottom: 12 }}>
        {GG_GATES.map(g => (
          <label key={g} className="stack" style={{ gap: 3 }}>
            <span className="text-low" style={{ fontSize: 10 }}>{g}</span>
            <select className="field" value={gates[g]} onChange={e => setGates(s => ({ ...s, [g]: e.target.value }))}>
              {GATE_OPTS.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn btn-sm" onClick={run} disabled={state.phase === 'submitting'}>{state.phase === 'submitting' ? 'Evaluating…' : 'Evaluate'}</button>
        {state.phase === 'auth' && <span className="pill pill-unknown">Sign in required.</span>}
        {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
      </div>
      {dec && (
        <div data-testid="gg-evaluate-result" style={{ marginTop: 14 }}>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <span className={`pill ${dec.decision_state === 'PURCHASE_READY' ? 'pill-ok' : dec.decision_state === 'APPROVAL_REQUIRED' ? 'pill-ochre' : 'pill-muted'}`}>{dec.decision_state}</span>
            <span className={`pill ${dec.purchase_ready ? 'pill-ok' : 'pill-muted'}`} title="Purchase authorization is never granted by a score">{dec.purchase_ready ? 'purchase-ready' : 'purchase NOT authorized'}</span>
            {dec.overall_score != null && <span className="pill pill-muted">score {dec.overall_score}</span>}
            {state.value.resale_score != null && <span className="pill pill-muted">resale {state.value.resale_score}</span>}
            <span className="pill pill-muted">approval: {dec.approval_state}</span>
          </div>
          {dec.missing_information && dec.missing_information.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Missing:</span>
              {dec.missing_information.map(m => <span key={m} className="pill pill-unknown" style={{ fontSize: 10 }}>{m}</span>)}
            </div>
          )}
          {dec.warnings && dec.warnings.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
              {dec.warnings.map((w, i) => <span key={i} className="pill pill-warn" style={{ fontSize: 10 }}>{w}</span>)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const TABS = [
  { id: 'queue', label: 'Queue', count: 2 },
  { id: 'review', label: 'Review' },
  { id: 'decisions', label: 'Decisions' },
  { id: 'history', label: 'History' },
]

const OPPS = [
  {
    id: 'GG-001', name: 'Water Filter Pro', rank: 1, score: 82, contradictions: 2,
    why: 'High margin + low competition', source: 'Algorithmic signal analysis', confidence: 'Moderate',
    freshness: 'surfaced 2d ago · cached snapshot',
    supporting: ['Verified supplier pricing', 'Low competitive density', 'Consistent demand trend'],
    contradicting: ['Seasonal Q4 demand dip', 'Shipping costs not verified'],
    unknowns: ['Supplier invoice / authenticity not verified', 'Shipping cost basis unavailable', 'Return rate observed data missing'],
    failReasons: ['Seasonal Q4 demand dip', 'Shipping costs not verified', 'Margins depend on assumed fee basis'],
    sourcing: 'Direct manufacturer — needs invoice verification',
    portfolio: 'Set B (12 ASINs, 8% exposure)', relatedScout: 'B08L5VJQ7T',
    note: 'Operator note (sample): verify supplier invoice and shipping basis before any sourcing decision.',
  },
  {
    id: 'GG-002', name: 'LED Garden Light', rank: 2, score: 64, contradictions: 2,
    why: 'Seasonal demand spike + untapped supply', source: 'Market trend monitoring', confidence: 'Low',
    freshness: 'surfaced 1d ago · cached snapshot',
    supporting: ['Growing search volume', 'Few dedicated listings'],
    contradicting: ['High seasonal variance', 'Return rate data unavailable'],
    unknowns: ['No sourcing path established', 'Return rate data unavailable', 'Brand authorization unclear'],
    failReasons: ['High seasonal variance', 'Untracked demand history', 'No established supplier'],
    sourcing: 'Unknown — no sourcing path established',
    portfolio: 'Not in portfolio', relatedScout: 'B09M8KJ4X2',
    note: 'Operator note (sample): seasonal — treat research confidence as low until demand history exists.',
  },
]

const CONF_PILL = { High: 'pill-forest', Moderate: 'pill-ochre', Low: 'pill-warn' }
const CONF_TITLE = 'Data-quality signal — not a purchase recommendation'

const DECISIONS = [
  { id: 'GG-001', decision: 'Under review — verification pending', confidence: 'Moderate', date: '2026-09-24', status: 'Review', tone: 'pill-warn' },
  { id: 'GG-002', decision: 'Hold — seasonal variance risk', confidence: 'Low', date: '2026-09-25', status: 'Hold', tone: 'pill-ochre' },
  { id: 'GG-003', decision: 'Dismissed — sourcing path absent', confidence: '—', date: '2026-09-22', status: 'Dismissed', tone: 'pill-muted' },
]

const HISTORY = [
  { id: 'GG-001', event: 'Surfaced by algorithm', detail: 'High margin + low competition', date: '2026-09-24', state: 'CACHED' },
  { id: 'GG-002', event: 'Surfaced by market trend monitoring', detail: 'Seasonal demand spike', date: '2026-09-25', state: 'OBSERVED' },
  { id: 'GG-001', event: 'Review opened — verification pending', detail: 'Assigned Operator A', date: '2026-09-24', state: 'OBSERVED' },
  { id: 'GG-003', event: 'Dismissed — sourcing path absent', detail: 'No supplier path established', date: '2026-09-22', state: 'HISTORICAL' },
]

const statePill = (s) => <span className="pill pill-muted" title={s === 'CACHED' ? 'Derived from cached sample data — may be stale' : s === 'HISTORICAL' ? 'Historical record — not current state' : 'Directly observed event (sample data)'}>{s}</span>

function oppCard(opp, navigate, toast) {
  return (
    <div key={opp.id} className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title" style={{ fontSize: 18 }}>{opp.name}</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="pill pill-muted" title="Surfaced rank — ordering only, not a purchase recommendation">Rank #{opp.rank}</span>
          <span className="pill pill-muted" title="Algorithmic surfaced score — not a purchase recommendation">{opp.score}</span>
          <span className={`pill ${CONF_PILL[opp.confidence] || 'pill-muted'}`} title={CONF_TITLE}>{opp.confidence} research confidence</span>
        </div>
      </div>

      <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
        <div>
          <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Why Surfaced</div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{opp.why}</div>
        </div>
        <div>
          <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>Source</div>
          <div style={{ fontSize: 14 }}>{opp.source}</div>
        </div>
      </div>

      <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
        <div>
          <h4 style={{ fontSize: 13, color: 'var(--pine)', marginBottom: 8 }}>Supporting Signals</h4>
          <div className="stack" style={{ gap: 6 }}>
            {opp.supporting.map((s, i) => (
              <div key={i} className="check-row" style={{ fontSize: 13 }}><input type="checkbox" checked readOnly /> <label>{s}</label></div>
            ))}
          </div>
        </div>
        <div>
          <h4 style={{ fontSize: 13, color: 'var(--clay)', marginBottom: 8 }}>Contradicting Signals</h4>
          <div className="stack" style={{ gap: 6 }}>
            {opp.contradicting.map((s, i) => (
              <div key={i} className="check-row" style={{ fontSize: 13 }}><input type="checkbox" readOnly /> <label>{s}</label></div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
        <div className="card" style={{ padding: 14, background: 'var(--surface-2, rgba(138,138,122,0.06))' }}>
          <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>What Remains Unknown</div>
          <div className="stack" style={{ gap: 6 }}>
            {opp.unknowns.map((u, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <span className="pill pill-unknown" style={{ fontSize: 10 }}>UNKNOWN</span>
                <span style={{ fontSize: 13 }}>{u}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card" style={{ padding: 14, background: 'var(--surface-2, rgba(138,138,122,0.06))' }}>
          <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Why It May Fail</div>
          <div className="stack" style={{ gap: 6 }}>
            {opp.failReasons.map((u, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <span className="pill pill-warn" style={{ fontSize: 10 }}>RISK</span>
                <span style={{ fontSize: 13 }}>{u}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="evidence" style={{ marginBottom: 16 }}>
        <div className="evidence-header">
          <span className="evidence-source">Sourcing Route</span>
          <span className="evidence-freshness">Needs Verification</span>
        </div>
        <div className="evidence-body">{opp.sourcing}</div>
      </div>

      <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <span className="pill pill-muted">Portfolio: {opp.portfolio}</span>
        <span className="pill pill-muted" title="Related research entity — no authorization implied">Related SourceScout: {opp.relatedScout}</span>
      </div>

      <div style={{ borderTop: '1px solid var(--divider)', paddingTop: 12, marginBottom: 12 }}>
        <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Review Notes</div>
        <div style={{ fontSize: 13, color: 'var(--ink-mid)' }}>{opp.note}</div>
      </div>

      <div className="inline-flex" style={{ gap: 8 }}>
        <button className="btn btn-sm" onClick={() => navigate(`/product-finder/${opp.relatedScout}`)}>Open SourceScout</button>
        <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/commerce-ops'); toast('Escalated to Commerce Ops — operator decision required there.', 'info') }}>Escalate to Commerce Ops</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Held for review — no change to sourcing or purchase state.', 'info')}>Hold</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Rejected — opportunity moved out of the active review queue.', 'info')}>Reject</button>
      </div>
    </div>
  )
}

function PersistedQueue() {
  const [st, setSt] = useState({ loaded: false, items: [], basis: 'UNKNOWN' })
  useEffect(() => {
    let alive = true
    foundationApi.goldenGooseQueue()
      .then((r) => { if (alive) setSt({ loaded: true, items: r.items || [], basis: r.basis || 'UNKNOWN' }) })
      .catch(() => { if (alive) setSt({ loaded: true, items: [], basis: 'UNKNOWN' }) })
    return () => { alive = false }
  }, [])
  return (
    <div className="card" data-testid="gg-persisted-queue">
      <div className="card-head">
        <h3 className="card-title">Persisted Queue</h3>
        <span className="pill pill-muted" data-testid="gg-persisted-basis">{st.basis}</span>
      </div>
      {st.items.length > 0 ? (
        <ul data-testid="gg-persisted-items">
          {st.items.map((i) => <li key={i.item_id}>{i.item_id}{i.resale_score != null ? ' - score ' + i.resale_score : ''}</li>)}
        </ul>
      ) : (
        <p data-testid="gg-persisted-empty">No persisted opportunities yet. Basis: UNKNOWN.</p>
      )}
    </div>
  )
}

function PersistedReview({ id }) {
  const [st, setSt] = useState({ state: 'loading' })
  useEffect(() => {
    let alive = true
    setSt({ state: 'loading' })
    foundationApi.goldenGooseItem(id)
      .then((item) => { if (alive) setSt({ state: 'loaded', item }) })
      .catch((e) => {
        if (!alive) return
        const state = (e && e.status === 404) ? 'not_found'
          : (e && e.status === 403) ? 'denied'
            : 'error'
        setSt({ state, detail: (e && e.code) || null })
      })
    return () => { alive = false }
  }, [id])

  if (st.state === 'loading') {
    return <div className="card" data-testid="gg-persisted-review"><p data-testid="gg-review-loading">Loading persisted opportunity {id}…</p></div>
  }
  if (st.state === 'not_found') {
    return <div className="card" data-testid="gg-persisted-review"><p data-testid="gg-review-not-found">No persisted opportunity {id} for your organization. Nothing is fabricated.</p></div>
  }
  if (st.state === 'denied') {
    return <div className="card" data-testid="gg-persisted-review"><p data-testid="gg-review-denied">Not available for your organization.</p></div>
  }
  if (st.state === 'error') {
    return <div className="card" data-testid="gg-persisted-review"><p data-testid="gg-review-error">Persisted opportunity unavailable{st.detail ? ' (' + st.detail + ')' : ''}.</p></div>
  }

  const item = st.item || {}
  const dec = item.latest_decision || null
  return (
    <div className="card" data-testid="gg-persisted-review" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Persisted Opportunity <span data-testid="gg-review-id">{item.item_id}</span></h3>
        <span className="pill pill-muted" title="Persisted record — organization-scoped, read-only">OBSERVED</span>
      </div>
      <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <span className="pill pill-muted" title="Stored match state — a status never authorizes a purchase">{item.match_state || 'UNKNOWN'}</span>
        {item.resale_score == null
          ? <span className="pill pill-unknown" data-testid="gg-review-score">UNKNOWN</span>
          : <span className="pill pill-muted" data-testid="gg-review-score" title="Stored resale score — informational, not a purchase authorization">Resale Score {item.resale_score}</span>}
        {item.net_per_unit != null && <span className="pill pill-muted">Net/unit {item.net_per_unit}</span>}
        <span className="pill pill-muted" title="Stored policy exclusion flag">{Number(item.policy_exclusion_flag) ? 'Policy excluded' : 'Not policy-excluded'}</span>
      </div>
      <div className="card" style={{ padding: 14, background: 'var(--surface-2, rgba(138,138,122,0.06))' }}>
        <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Latest Recorded Decision</div>
        {dec
          ? <div data-testid="gg-review-decision" style={{ fontSize: 13 }}>
              <span className="pill pill-muted">{dec.decision_state || 'UNKNOWN'}</span>
              <span style={{ marginLeft: 8 }}>recorded {dec.created_at || 'UNKNOWN'} · review log only, not a purchase authorization</span>
            </div>
          : <div data-testid="gg-review-decision" style={{ fontSize: 13 }}><span className="pill pill-unknown">UNKNOWN</span> <span style={{ marginLeft: 8 }}>no decision recorded</span></div>}
      </div>
    </div>
  )
}

function PersistedDecisions() {
  const [st, setSt] = useState({ loaded: false, rows: [], error: null })
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const q = await foundationApi.goldenGooseQueue()
        const items = q.items || []
        const rows = await Promise.all(items.map(async (i) => {
          try {
            const full = await foundationApi.goldenGooseItem(i.item_id)
            return { item_id: i.item_id, decision: full.latest_decision || null, unavailable: false }
          } catch (e) {
            return { item_id: i.item_id, decision: null, unavailable: true, denied: !!(e && e.status === 403) }
          }
        }))
        if (alive) setSt({ loaded: true, rows, error: null })
      } catch (e) {
        if (alive) setSt({ loaded: true, rows: [], error: (e && e.code) || 'error' })
      }
    })()
    return () => { alive = false }
  }, [])

  const rows = st.rows.map((r) => ({
    item_id: r.item_id,
    state: r.decision ? (r.decision.decision_state || 'UNKNOWN') : (r.unavailable ? (r.denied ? 'DENIED' : 'UNAVAILABLE') : 'UNKNOWN'),
    when: r.decision ? (r.decision.created_at || 'UNKNOWN') : '—',
    tone: r.decision ? 'pill-muted' : 'pill-unknown',
  }))

  return (
    <div data-testid="gg-persisted-decisions" style={{ marginTop: 20 }}>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Persisted Decisions</h3>
          <span className="pill pill-muted">latest per item · organization-scoped</span>
        </div>
        {rows.length > 0 ? (
          <DataTable columns={[
            { key: 'item_id', label: 'Item' },
            { key: 'state', label: 'Latest Decision', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
            { key: 'when', label: 'Recorded' },
          ]} rows={rows} />
        ) : (
          <p data-testid="gg-decisions-empty">{st.error ? 'Decisions unavailable for your organization.' : 'No persisted decisions yet. Basis: UNKNOWN.'}</p>
        )}
      </div>
    </div>
  )
}

export default function GoldenGooseDesk() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'review' : 'queue')
  const selected = OPPS.find(o => o.id === (id || 'GG-001')) || OPPS[0]
  const isDemoId = OPPS.some(o => o.id === id)

  return (
    <PageLayout
      title="Golden Goose Finder"
      subtitle="Review desk for surfaced opportunities — judgment, not recommendations."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/golden-goose?view=queue')}>New Analysis</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Opportunity desk settings are not connected yet.', 'info')}>Settings</button>
      </>}
    >
      <DataNotice tone="sample" title="Evidence-based surfacing — fictional sample data">
        Opportunities are surfaced based on algorithmic analysis of market signals. Confidence levels reflect data quality, not purchase recommendations. The evaluate panel is a real backend decision-control; the opportunity queue below is fictional sample data.
      </DataNotice>

      <EvaluatePanel />

      <RoomTabs tabs={TABS} base="/golden-goose" />

      {view === 'queue' && (
        <div className="subview">
          <PersistedQueue />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Opportunity Queue</h3>
              <span className="pill pill-warn">{OPPS.length} under review</span>
            </div>
            <DataTable columns={[
              { key: 'rank', label: 'Rank', render: (v) => <span className="pill pill-muted" title="Surfaced rank — ordering only">{v}</span> },
              { key: 'id', label: 'ID' },
              { key: 'name', label: 'Opportunity' },
              { key: 'score', label: 'Score', render: (v) => <span className="pill pill-muted" title="Algorithmic surfaced score — not a purchase recommendation">{v}</span> },
              { key: 'confidence', label: 'Research Confidence', render: (v) => <span className={`pill ${CONF_PILL[v] || 'pill-muted'}`} title={CONF_TITLE}>{v}</span> },
              { key: 'contradictions', label: 'Contradictions', render: (v) => <span className={`pill ${v > 0 ? 'pill-warn' : 'pill-muted'}`} title="Contradicting signals count — reason to scrutinize, not dismiss">{v}</span> },
              { key: 'why', label: 'Why Surfaced' },
              { key: 'freshness', label: 'Freshness', render: (v) => <span className="pill pill-muted" title="Provenance stamp — cached snapshot, not live market data">{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/golden-goose/${row.id}`)}>Open</button> },
            ]} rows={OPPS} />
          </div>
        </div>
      )}

      {view === 'review' && ((id && !isDemoId) ? <PersistedReview id={id} /> : oppCard(selected, navigate, toast))}

      {view === 'decisions' && (
        <div className="subview">
          <DataNotice tone="internal" title="Decision log is internal review history">
            Log entries reflect operator review state and are not recommendations to purchase.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Decisions</h3>
              <span className="pill pill-muted">{DECISIONS.length} entries</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'decision', label: 'Decision' },
              { key: 'confidence', label: 'Research Confidence', render: (v) => v === '—' ? <span>—</span> : <span className={`pill ${CONF_PILL[v] || 'pill-muted'}`} title={CONF_TITLE}>{v}</span> },
              { key: 'date', label: 'Date' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
            ]} rows={DECISIONS} />
          </div>
          <PersistedDecisions />
        </div>
      )}

      {view === 'history' && (
        <div className="subview">
          <DataNotice tone="sample" title="Historical log — demonstration data">
            Records shown are samples; OBSERVED/CACHED/HISTORICAL tags describe provenance, not current state.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">History</h3>
              <span className="pill pill-muted">{HISTORY.length} entries · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'event', label: 'Event' },
              { key: 'detail', label: 'Detail' },
              { key: 'date', label: 'Date' },
              { key: 'state', label: 'Provenance', render: (v) => statePill(v) },
            ]} rows={HISTORY} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}
