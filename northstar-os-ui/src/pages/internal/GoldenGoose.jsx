import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useNavigate, useParams, useLocation } from 'react-router-dom'

const TABS = [
  { id: 'queue', label: 'Queue', count: 2 },
  { id: 'detail', label: 'Opportunity Detail' },
  { id: 'log', label: 'Decision Log' },
]

const OPPS = [
  { id: 'GG-001', name: 'Water Filter Pro', why: 'High margin + low competition', source: 'Algorithmic signal analysis', confidence: 'Moderate', supporting: ['Verified supplier pricing', 'Low competitive density', 'Consistent demand trend'], contradicting: ['Seasonal Q4 demand dip', 'Shipping costs not verified'], sourcing: 'Direct manufacturer — needs invoice verification', portfolio: 'Set B (12 ASINs, 8% exposure)', relatedScout: 'B08L5VJQ7T' },
  { id: 'GG-002', name: 'LED Garden Light', why: 'Seasonal demand spike + untapped supply', source: 'Market trend monitoring', confidence: 'Low', supporting: ['Growing search volume', 'Few dedicated listings'], contradicting: ['High seasonal variance', 'Return rate data unavailable'], sourcing: 'Unknown — no sourcing path established', portfolio: 'Not in portfolio', relatedScout: 'B09M8KJ4X2' },
]

const DECISIONS = [
  { id: 'GG-001', decision: 'Under review — verification pending', confidence: 'Moderate', date: '2026-09-24', status: 'Review', tone: 'pill-warn' },
  { id: 'GG-002', decision: 'Hold — seasonal variance risk', confidence: 'Low', date: '2026-09-25', status: 'Hold', tone: 'pill-ochre' },
  { id: 'GG-003', decision: 'Dismissed — sourcing path absent', confidence: '—', date: '2026-09-22', status: 'Dismissed', tone: 'pill-muted' },
]

function oppCard(opp, navigate) {
  return (
    <div key={opp.id} className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title" style={{ fontSize: 18 }}>{opp.name}</h3>
        <span className={`pill ${opp.confidence === 'High' ? 'pill-ok' : opp.confidence === 'Moderate' ? 'pill-ochre' : 'pill-warn'}`}>{opp.confidence} confidence</span>
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

      <div className="evidence" style={{ marginBottom: 16 }}>
        <div className="evidence-header">
          <span className="evidence-source">Sourcing Route</span>
          <span className="evidence-freshness">Needs Verification</span>
        </div>
        <div className="evidence-body">{opp.sourcing}</div>
      </div>

      <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <span className="pill pill-muted">Portfolio: {opp.portfolio}</span>
        <span className="pill pill-forest">Related SourceScout: {opp.relatedScout}</span>
      </div>

      <div className="inline-flex" style={{ gap: 8 }}>
        <button className="btn btn-sm" onClick={() => navigate(`/product-finder/${opp.relatedScout}`)}>Open SourceScout</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/commerce-ops')}>Send to Commerce Ops</button>
        <button className="btn btn-sm btn-ghost">Add to Watch</button>
      </div>
    </div>
  )
}

export default function GoldenGooseDesk() {
  const navigate = useNavigate()
  const { id } = useParams()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : (id ? 'detail' : 'queue')
  const selected = OPPS.find(o => o.id === (id || 'GG-001')) || OPPS[0]

  return (
    <PageLayout
      title="Golden Goose Finder"
      subtitle="Review desk for surfaced opportunities — judgment, not recommendations."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/golden-goose?view=queue')}>New Analysis</button>
        <button className="btn btn-sm btn-ghost">Settings</button>
      </>}
    >
      <DataNotice tone="sample" title="Evidence-based surfacing — fictional sample data">
        Opportunities are surfaced based on algorithmic analysis of market signals. Confidence levels reflect data quality, not purchase recommendations. All data is fictional sample data.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/golden-goose" />

      {view === 'queue' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Opportunity Queue</h3>
              <span className="pill pill-warn">2 under review</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'name', label: 'Opportunity' },
              { key: 'confidence', label: 'Confidence' },
              { key: 'why', label: 'Why Surfaced' },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => navigate(`/golden-goose/${row.id}`)}>Open</button> },
            ]} rows={OPPS} />
          </div>
        </div>
      )}

      {view === 'detail' && oppCard(selected, navigate)}

      {view === 'log' && (
        <div className="subview">
          <DataNotice tone="internal" title="Decision log is internal review history">
            Log entries reflect operator review state and are not recommendations to purchase.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Decision Log</h3>
              <span className="pill pill-muted">3 entries</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'decision', label: 'Decision' },
              { key: 'confidence', label: 'Confidence' },
              { key: 'date', label: 'Date' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
            ]} rows={DECISIONS} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}