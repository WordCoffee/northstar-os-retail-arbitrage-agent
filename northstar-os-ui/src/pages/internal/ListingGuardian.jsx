import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'alerts', label: 'Alerts', count: 5 },
  { id: 'diffs', label: 'Diffs', count: 3 },
  { id: 'history', label: 'History' },
  { id: 'escalations', label: 'Escalations' },
]

const SEV_PILL = { High: 'pill-error', Medium: 'pill-warn', Low: 'pill-muted' }
const STATUS_PILL = { Review: 'pill-warn', Monitoring: 'pill-ochre', Resolved: 'pill-muted' }

const ALERTS = [
  { id: 'AL-001', asin: 'B08L5VJQ7T', type: 'Content Change', severity: 'High', date: '2026-09-26', status: 'Review' },
  { id: 'AL-002', asin: 'B09M8KJ4X2', type: 'Rank Drop', severity: 'Medium', date: '2026-09-25', status: 'Monitoring' },
  { id: 'AL-003', asin: 'B08N5WRWNW', type: 'Price Change', severity: 'Low', date: '2026-09-24', status: 'Resolved' },
  { id: 'AL-004', asin: 'B07XJ8C9F3', type: 'New Competitor', severity: 'High', date: '2026-09-23', status: 'Review' },
  { id: 'AL-005', asin: 'B08L5VJQ7T', type: 'Listing Health', severity: 'Medium', date: '2026-09-22', status: 'Monitoring' },
]

const WARNINGS = [
  { id: 'PW-01', kind: 'Policy', asin: 'B08L5VJQ7T', detail: 'Image contains a prohibited claim overlay', severity: 'High' },
  { id: 'PW-02', kind: 'Suppression', asin: 'B07XJ8C9F3', detail: 'Listing suppressed from search — missing required attribute', severity: 'High' },
  { id: 'PW-03', kind: 'Policy', asin: 'B09M8KJ4X2', detail: 'Title exceeds style guidance length', severity: 'Medium' },
]

const DIFFS = [
  { id: 'DF-01', asin: 'B08L5VJQ7T', field: 'Title', before: 'Premium Water Filter — 5 Stage', after: 'Premium Water Filter — Best 5 Stage (Organic)', severity: 'High', date: '2026-09-26' },
  { id: 'DF-02', asin: 'B08N5WRWNW', field: 'Price', before: '$29.99', after: '$24.99', severity: 'Low', date: '2026-09-24' },
  { id: 'DF-03', asin: 'B07XJ8C9F3', field: 'Bullet 2', before: 'Universal fit with 3M adhesive', after: 'Compatible with most phones', severity: 'Medium', date: '2026-09-23' },
]

const HISTORY = [
  { id: 'AL-003', event: 'Price change resolved — within tolerance', date: '2026-09-24', state: 'OBSERVED' },
  { id: 'AL-002', event: 'Rank drop flagged — monitoring window open', date: '2026-09-25', state: 'OBSERVED' },
  { id: 'AL-001', event: 'Content change detected — diff captured', date: '2026-09-26', state: 'CACHED' },
  { id: 'AL-004', event: 'New competitor surfaced historically', date: '2026-09-23', state: 'HISTORICAL' },
]

const ESCALATIONS = [
  { id: 'ES-01', asin: 'B08L5VJQ7T', reason: 'Prohibited claim in title', target: 'ListingForge', state: 'Awaiting Review', age: '4h' },
  { id: 'ES-02', asin: 'B07XJ8C9F3', reason: 'Listing suppressed — needs attribute fix', target: 'Commerce Ops', state: 'Escalated', age: '1d' },
]

const RULES = [
  { rule: 'Alert on rank drop below #20,000', trigger: 'Observed rank shift', state: 'Proposed' },
  { rule: 'Flag content change with no history entry', trigger: 'Content diff', state: 'Proposed' },
  { rule: 'Flag prohibited claim overlays', trigger: 'Policy scan', state: 'Proposed' },
  { rule: 'Escalate listing health below threshold', trigger: 'Health score', state: 'Proposed' },
]

const statePill = (s) => <span className="pill pill-muted" title={s === 'CACHED' ? 'Derived from cached sample data — may be stale' : s === 'HISTORICAL' ? 'Historical record — not current state' : 'Directly observed event (sample data)'}>{s}</span>

export default function ListingGuardian() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedDiff, setSelectedDiff] = useState(DIFFS[0])

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'

  const escalate = (asin, target) => {
    navigate(target === 'ListingForge' ? '/listingforge' : '/commerce-ops')
    toast(`Escalated to ${target} — uncertainty preserved on handoff.`, 'info')
  }

  return (
    <PageLayout
      title="Listing Guardian"
      subtitle="Watchtower — content changes, policy/suppression warnings, diffs, and escalations for monitored listings."
      actions={<>
        <button className="btn btn-sm" onClick={() => { navigate('/listings?view=escalations'); toast('Escalation rules live under the Escalations tab.', 'info') }}>New Rule</button>
        <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/listings?view=history'); toast('History shows the change timeline (sample).', 'info') }}>History</button>
      </>}
    >
      <DataNotice tone="sample" title="Guardian records are sample data">
        Alerts, diffs, ranks, and warnings are demonstration records until a connected Listing Guardian backend exists. Rank movement is an indication, not verified fact. Escalation is manual — no rule takes automated action.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/listings" />

      {view === 'alerts' && (
        <div className="subview">
          <div className="grid-3" style={{ gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Open Alerts</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{ALERTS.filter(a => a.status !== 'Resolved').length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{ALERTS.filter(a => a.severity === 'High').length} high severity</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count from the sample alert feed">Basis: sample feed</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Policy / Suppression</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--clay)' }}>{WARNINGS.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>Require attention</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count from the sample warnings list">Basis: sample warnings</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Pending Escalations</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ochre)' }}>{ESCALATIONS.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>To ListingForge / Commerce Ops</div>
              <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count from the sample escalation queue">Basis: sample escalations</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Policy &amp; Suppression Warnings</h3>
              <span className="pill pill-clay">{WARNINGS.length} active</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {WARNINGS.map(w => (
                <div key={w.id} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{w.detail}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>{w.kind} · {w.asin}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`pill ${SEV_PILL[w.severity]}`} title="Severity — must be reviewed by an operator">{w.severity}</span>
                    <button className="btn btn-sm" onClick={() => escalate(w.asin, 'ListingForge')}>Escalate to ListingForge</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Alert Feed</h3>
              <span className="pill pill-clay">{ALERTS.length} active · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'asin', label: 'ASIN' },
              { key: 'type', label: 'Alert Type' },
              { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${SEV_PILL[v]}`}>{v}</span> },
              { key: 'date', label: 'Date' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${STATUS_PILL[v] || 'pill-muted'}`}>{v}</span> },
              { key: 'escalate', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => escalate(row.asin, 'Commerce Ops')}>Escalate</button> },
            ]} rows={ALERTS} />
          </div>
        </div>
      )}

      {view === 'diffs' && (
        <div className="subview">
          <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20, alignItems: 'start' }}>
            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Detected Changes</h3>
                <span className="pill pill-muted">{DIFFS.length}</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {DIFFS.map(d => (
                  <button key={d.id} className={`filter-pill ${selectedDiff.id === d.id ? 'active' : ''}`} style={{ textAlign: 'left', justifyContent: 'flex-start', whiteSpace: 'normal' }} onClick={() => setSelectedDiff(d)}>
                    {d.asin} · {d.field}
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title">{selectedDiff.asin} — {selectedDiff.field}</h3>
                <span className={`pill ${SEV_PILL[selectedDiff.severity]}`}>{selectedDiff.severity}</span>
              </div>
              <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
                <div className="card" style={{ padding: 14, background: 'var(--surface-2, rgba(138,138,122,0.06))' }}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Before · {selectedDiff.date}</div>
                  <div style={{ fontSize: 13 }}>{selectedDiff.before}</div>
                </div>
                <div className="card" style={{ padding: 14, background: 'rgba(196,148,26,0.06)' }}>
                  <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>After</div>
                  <div style={{ fontSize: 13 }}>{selectedDiff.after}</div>
                </div>
              </div>
              <div className="inline-flex" style={{ gap: 8 }}>
                <button className="btn btn-sm" onClick={() => escalate(selectedDiff.asin, 'ListingForge')}>Escalate to ListingForge</button>
                <button className="btn btn-sm btn-ghost" onClick={() => toast('Marked as reviewed — no listing change is made from here.', 'info')}>Mark Reviewed</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'history' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Change Timeline</h3>
              <span className="pill pill-muted">{HISTORY.length} events · sample</span>
            </div>
            <div className="timeline" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {HISTORY.map((h, i) => (
                <div key={i} className="timeline-item" style={{ display: 'flex', gap: 12, padding: '8px 0' }}>
                  <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, background: 'rgba(138,138,122,0.12)', color: '#8a8a7a' }}>·</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13 }}>{h.event}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, color: 'var(--ink-soft)', fontFamily: 'var(--font-mono)' }}>{h.date}</span>
                      <span className="pill pill-muted" style={{ fontSize: 10 }}>{h.id}</span>
                      {statePill(h.state)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {view === 'escalations' && (
        <div className="subview">
          <DataNotice tone="internal" title="Escalations are manual">
            Escalating hands a listing to ListingForge or Commerce Ops for operator action. No Guardian rule changes a listing automatically.
          </DataNotice>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Escalation Queue</h3>
              <span className="pill pill-ochre">{ESCALATIONS.length} items · sample</span>
            </div>
            <DataTable columns={[
              { key: 'id', label: 'ID' },
              { key: 'asin', label: 'ASIN' },
              { key: 'reason', label: 'Reason' },
              { key: 'target', label: 'Target Room' },
              { key: 'state', label: 'State', render: (v, row) => <span className={`pill ${row.state === 'Awaiting Review' ? 'pill-warn' : 'pill-ochre'}`}>{v}</span> },
              { key: 'age', label: 'Age', render: (v) => <span className="pill pill-muted" title="Time open — aging signals urgency, not auto-escalation">{v}</span> },
              { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => escalate(row.asin, row.target)}>Open in room</button> },
            ]} rows={ESCALATIONS} />
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Escalation Rules</h3>
              <span className="pill pill-muted">Proposed — not enforced</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {RULES.map(r => (
                <div key={r.rule} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{r.rule}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>{r.trigger}</div>
                  </div>
                  <span className="pill pill-muted">{r.state}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
