import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'rankings', label: 'Rankings', count: 20 },
  { id: 'terms', label: 'Tracked Terms', count: 148 },
  { id: 'reports', label: 'Reports' },
]

const RANKINGS = [
  { term: 'water filter', volume: '12.4K', rank: '#14', change: '↑ 3', asin: 'B08L5VJQ7T', tone: 'pill-forest' },
  { term: 'water purifier', volume: '8.7K', rank: '#32', change: '↓ 5', asin: 'B08L5VJQ7T', tone: 'pill-clay' },
  { term: 'countertop filter', volume: '6.2K', rank: '#8', change: '↑ 1', asin: 'B08L5VJQ7T', tone: 'pill-forest' },
  { term: 'BPA free water filter', volume: '4.5K', rank: '#45', change: '↓ 12', asin: 'B08L5VJQ7T', tone: 'pill-clay' },
  { term: 'family water filter', volume: '3.8K', rank: '#21', change: '↑ 2', asin: 'B08L5VJQ7T', tone: 'pill-forest' },
]

export default function KeywordTracker() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'rankings'

  return (
    <PageLayout
      title="Keyword Tracker"
      subtitle="Search visibility — ranking positions, search volume, and term-level opportunity."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Track New — add a term to the tracked set.', 'info')}>Track New</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Reports export is sample data.', 'info')}>Reports</button>
      </>}
    >
      <DataNotice tone="cached" title="Rankings are a cached snapshot">
        Position data is a cached snapshot from 2h ago. Search volume is estimated and must not be treated as verified traffic.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/keyword-tracker" />

      {view === 'rankings' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Ranking Positions</h3>
              <span className="pill pill-muted">Top 20 tracked</span>
            </div>
            <DataTable columns={[
              { key: 'term', label: 'Keyword' },
              { key: 'volume', label: 'Search Vol' },
              { key: 'rank', label: 'Position' },
              { key: 'change', label: 'Change', render: (v) => <span style={{ color: v.startsWith('↑') ? 'var(--pine-deep)' : 'var(--clay)' }}>{v}</span> },
              { key: 'asin', label: 'ASIN' },
            ]} rows={RANKINGS} />
          </div>
        </div>
      )}

      {view === 'terms' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Tracked Terms by ASIN</h3>
              <span className="pill pill-forest">148 terms · 6 ASINs</span>
            </div>
            {[
              { asin: 'B08L5VJQ7T', count: 34, focus: 'water filter, purifier, countertop filter' },
              { asin: 'B09M8KJ4X2', count: 28, focus: 'desk lamp, LED, adjustable lamp' },
              { asin: 'B07XJ8C9F3', count: 22, focus: 'phone mount, car mount, magnetic' },
              { asin: 'B08N5WRWNW', count: 41, focus: 'bluetooth speaker, portable, waterproof' },
            ].map(g => (
              <div key={g.asin} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{g.asin}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{g.focus}</div>
                </div>
                <span className="pill pill-muted">{g.count} terms</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'reports' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Report Queue</h3>
            </div>
            {[
              { report: 'Weekly position snapshot', schedule: 'Mondays 06:00', state: 'Scheduled' },
              { report: 'Opportunity gap scan', schedule: 'Bi-weekly', state: 'Draft' },
              { report: 'Volume trend report', schedule: 'Monthly', state: 'Not generated' },
            ].map(r => (
              <div key={r.report} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{r.report}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{r.schedule}</div>
                </div>
                <span className="pill pill-muted">{r.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PageLayout>
  )
}