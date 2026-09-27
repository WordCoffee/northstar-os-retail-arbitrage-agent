import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'topics', label: 'Topics', count: 14 },
  { id: 'entries', label: 'Recent Entries' },
  { id: 'unlearn', label: 'Revision & Unlearn' },
]

export default function MemoryBank() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'topics'

  return (
    <PageLayout
      title="Memory Bank"
      subtitle="Per-account knowledge store — facts, preferences, experiences, and AI-derived learnings. All local, no live calls."
      actions={<>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Knowledge is indexed by topic and freshness.', 'info')}>View Knowledge</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Unlearn opens revision control — reversible.', 'info')}>Unlearn</button>
      </>}
    >
      <DataNotice tone="internal" title="Internal use only — all data is local">
        Memory Bank stores facts and AI-derived learnings. Nothing here is shared externally, and no external provider call is made from this surface.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/memory-bank" />

      {view === 'topics' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Knowledge Topics</h3>
              <span className="pill pill-forest">1,247 stored facts</span>
            </div>
            <DataTable columns={[
              { key: 'label', label: 'Topic' },
              { key: 'entries', label: 'Entries' },
              { key: 'freshness', label: 'Freshness' },
              { key: 'source', label: 'Source' },
            ]} rows={[
              { label: 'Amazon FBA Policies', entries: '142', freshness: '1 day ago', source: 'Ingested doc' },
              { label: 'Product Categories', entries: '387', freshness: '3 days ago', source: 'AI-derived' },
              { label: 'Sourcing Patterns', entries: '219', freshness: '1 week ago', source: 'Experience log' },
              { label: 'Operator Preferences', entries: '499', freshness: 'Real-time', source: 'Interaction' },
            ]} />
          </div>
        </div>
      )}

      {view === 'entries' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Recent Entries</h3>
              <span className="pill pill-muted">Latest activity</span>
            </div>
            {[
              { entry: 'Operator prefers Set B stock levels kept below 30 units', kind: 'Preference', time: '2h ago', tone: 'pill-forest' },
              { entry: 'Listing Guardian alert pattern for B08L5VJQ7T', kind: 'Learning', time: '1d ago', tone: 'pill-ochre' },
              { entry: 'Sourcing pattern: invoice-before-verification is a risk signal', kind: 'Experience', time: '3d ago', tone: 'pill-ochre' },
              { entry: 'Q3 2026 margin observations across Set A', kind: 'Fact', time: '5d ago', tone: 'pill-muted' },
            ].map(e => (
              <div key={e.entry} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{e.entry}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{e.time}</div>
                </div>
                <span className={`pill ${e.tone}`}>{e.kind}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'unlearn' && (
        <div className="subview">
          <DataNotice tone="unknown" title="Unlearn is reversible but reviewed">
            Revisions and unlearn requests apply to local knowledge only. Nothing is permanently destroyed without confirmation.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Revision &amp; Unlearn</h3>
            </div>
            <div className="stack" style={{ gap: 12 }}>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Topic or entry to revise</label>
                <input className="input" placeholder="e.g., Sourcing Patterns" />
              </div>
              <div className="field-row" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: 'var(--ink-mid)' }}>Reason</label>
                <input className="input" placeholder="What changed or why it should be unlearned" />
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => toast('Revision queued for local knowledge (sample).', 'info')}>Submit Revision</button>
                <button className="btn btn-sm btn-ghost" onClick={() => toast('Unlearn requires explicit reason — surfaced for review.', 'info')}>Unlearn Entry</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}