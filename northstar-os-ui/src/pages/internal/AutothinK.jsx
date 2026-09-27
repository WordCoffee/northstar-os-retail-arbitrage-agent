import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation, useNavigate } from 'react-router-dom'

const TABS = [
  { id: 'runs', label: 'Runs', count: 4 },
  { id: 'composer', label: 'Composer' },
  { id: 'output', label: 'Output Detail' },
]

const RUNS = [
  { id: 'R-01', topic: 'Competitor Pricing Shift', engine: 'Ling 3.0 Flash', status: 'Complete', started: '2026-09-22', output: '3 insights', tone: 'pill-forest' },
  { id: 'R-02', topic: 'Buy Box Risk Assessment', engine: 'Ling 3.0 Flash', status: 'Running', started: '2026-09-25', output: '—', tone: 'pill-ochre' },
  { id: 'R-03', topic: 'Margin Hypothesis Scan', engine: 'Northstar Inline', status: 'Queued', started: '—', output: '—', tone: 'pill-muted' },
  { id: 'R-04', topic: 'Listing Copy Quality', engine: 'Ling 3.0 Flash', status: 'Complete', started: '2026-09-20', output: '2 insights', tone: 'pill-forest' },
]

export default function AutothinK() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'runs'

  const newRun = () => navigate('/autothink?view=composer')

  return (
    <PageLayout
      title="AutothinK"
      subtitle="Research run workspace — compose research tasks, review outputs, and track the knowledge plane in action."
      actions={<>
        <button className="btn btn-sm" onClick={newRun}>New Research Run</button>
      </>}
    >
      <DataNotice tone="sample" title="Runs are demonstration records">
        Topics, engines, and outputs are sample data. A research run never fabricates claims — every output cites its data source or says UNKNOWN.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/autothink" />

      {view === 'runs' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Research Runs</h3>
              <span className="pill pill-forest">4 runs</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'topic', label: 'Topic' },
              { key: 'engine', label: 'Engine' },
              { key: 'status', label: 'Status', render: (v, row) => <span className={`pill ${row.tone}`}>{v}</span> },
              { key: 'started', label: 'Started' },
              { key: 'output', label: 'Output' },
            ]} rows={RUNS} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">How Outputs Are Grounded</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Every insight cites its data source or states UNKNOWN</div>
                <span className="pill pill-forest">Enforced</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Engine choice is explicit per run — no silent delegation</div>
                <span className="pill pill-muted">Explicit</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Outputs feed Memory Bank and shared data layer only after review</div>
                <span className="pill pill-ochre">Review Gate</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'composer' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Research Run Composer</h3>
            </div>
            <div className="stack" style={{ gap: 12 }}>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Research Topic</label>
                <input className="input" placeholder="e.g., Buy Box risk on Set A ASINs" defaultValue="Competitor Pricing Shift" />
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Engine</label>
                <select className="select">
                  <option>Ling 3.0 Flash</option>
                  <option>Northstar Inline</option>
                </select>
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Data Sources Allowed</label>
                <input className="input" placeholder="e.g., Listing Guardian, Keyword Tracker, Monitoring" />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => toast('Run queued (sample) — engine will cite sources in every output.', 'info')}>Queue Research Run</button>
                <button className="btn btn-sm btn-ghost">Save Draft</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'output' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">R-02 — Buy Box Risk Assessment</h3>
              <span className="pill pill-ochre">Running</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>Buy box position may shift on Set A — engine gathering seller-side data</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Sources: Monitoring · Status: IN PROGRESS</div>
                </div>
                <span className="pill pill-muted">Streaming</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13 }}>Seller count on B08L5VJQ7T</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Status: UNKNOWN — provider data not connected</div>
                </div>
                <span className="pill pill-unknown">UNKNOWN</span>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => toast('Saved to Memory Bank (sample).', 'info')}>Send to Memory Bank</button>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}