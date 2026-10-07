import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import ListingGuardianLane from '../../components/ListingGuardianLane.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'

const TABS = [
  { id: 'alerts', label: 'Alerts', count: 5 },
  { id: 'diffs', label: 'Diffs', count: 3 },
  { id: 'history', label: 'History' },
  { id: 'lane', label: 'Local Lane' },
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
  { id: 'DF-01', asin: 'B08L5VJQ7T', field: 'Title', before: 'Premium Water Filter — 5 Stage', after: 'Premium Water Filter — Best 5 Stage (Organic)', severity: 'High', date: '2026-09-26', state: 'CACHED' },
  { id: 'DF-02', asin: 'B08N5WRWNW', field: 'Price', before: '$29.99', after: '$24.99', severity: 'Low', date: '2026-09-24', state: 'OBSERVED' },
  { id: 'DF-03', asin: 'B07XJ8C9F3', field: 'Bullet 2', before: 'Universal fit with 3M adhesive', after: 'Compatible with most phones', severity: 'Medium', date: '2026-09-23', state: 'OBSERVED' },
]

const HISTORY = [
  { id: 'AL-001', event: 'Content change detected — diff captured', type: 'Content Change', asin: 'B08L5VJQ7T', severity: 'High', date: '2026-09-26', state: 'CACHED' },
  { id: 'AL-002', event: 'Rank drop flagged — monitoring window open', type: 'Rank Drop', asin: 'B09M8KJ4X2', severity: 'Medium', date: '2026-09-25', state: 'OBSERVED' },
  { id: 'AL-003', event: 'Price change resolved — within tolerance', type: 'Price Change', asin: 'B08N5WRWNW', severity: 'Low', date: '2026-09-24', state: 'OBSERVED' },
  { id: 'AL-004', event: 'New competitor surfaced historically', type: 'New Competitor', asin: 'B07XJ8C9F3', severity: 'High', date: '2026-09-23', state: 'HISTORICAL' },
]

const HISTORY_BY_TYPE = Object.values(HISTORY.reduce((m, h) => {
  (m[h.type] = m[h.type] || { type: h.type, count: 0, severities: [] })
  m[h.type].count += 1
  m[h.type].severities.push(h.severity)
  return m
}, {}))

const HISTORY_BY_STATE = Object.values(HISTORY.reduce((m, h) => {
  (m[h.state] = m[h.state] || { state: h.state, count: 0 })
  m[h.state].count += 1
  return m
}, {}))

const SEV_ORDER = { High: 3, Medium: 2, Low: 1 }
const highestSeverity = (list) => list.reduce((a, b) => (SEV_ORDER[b] > SEV_ORDER[a] ? b : a), 'Low')

// Triage grouping: one row per monitored listing (ASIN) with open/total counts,
// highest severity, and the alert types involved. Operator triage over sample data.
const ALERT_GROUP = Object.values(ALERTS.reduce((m, a) => {
  const g = m[a.asin] = m[a.asin] || { asin: a.asin, count: 0, open: 0, severities: [], types: new Set() }
  g.count += 1
  if (a.status !== 'Resolved') g.open += 1
  g.severities.push(a.severity)
  g.types.add(a.type)
  return m
}, {})).map(g => ({ ...g, severity: highestSeverity(g.severities), types: Array.from(g.types).join(', ') }))

function SourceStatusCard() {
  return (
    <div className="card" data-testid="lg-source-status" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Watchtower source status</h3>
        <span className="pill pill-warn" title="No live listing feed is connected">not connected</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, margin: 0 }}>
        No live listing feed is connected. Alerts, diffs and rank signals below are sample triage records — the triage workflow is real operator work, but the feed itself is not live. Escalations hand a listing to ListingForge or Commerce Ops for manual action; no Guardian rule changes a listing automatically.
      </p>
    </div>
  )
}

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

const SEV_DOT = {
  High: { background: 'var(--status-error-soft)', color: 'var(--status-error)' },
  Medium: { background: 'var(--status-warn-soft)', color: 'var(--status-warn)' },
  Low: { background: 'var(--status-unknown-soft)', color: 'var(--status-unknown)' },
}

const fieldGlyph = (field) => {
  if (/title/i.test(field)) return 'T'
  if (/price/i.test(field)) return '$'
  if (/bullet/i.test(field)) return 'B'
  return '•'
}

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

      <SourceStatusCard />

      <RoomTabs tabs={TABS} base="/listings" />

      {view === 'lane' && <ListingGuardianLane />}

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
              <h3 className="card-title">Triage by listing</h3>
              <span className="pill pill-muted">{ALERT_GROUP.length} listings · sample</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              {ALERT_GROUP.map(g => (
                <div key={g.asin} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--divider)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-mono)' }}>{g.asin}</div>
                    <div className="text-low" style={{ fontSize: 11 }}>{g.types} · {g.open} open / {g.count} total</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`pill ${SEV_PILL[g.severity]}`} title="Highest severity across this listing's alerts">{g.severity}</span>
                    <button className="btn btn-sm" onClick={() => escalate(g.asin, 'Commerce Ops')}>Escalate</button>
                  </div>
                </div>
              ))}
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
          <div className="split-aside-l">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Detected Changes</h3>
                <span className="pill pill-muted">{DIFFS.length}</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {DIFFS.map(d => {
                  const active = selectedDiff.id === d.id
                  return (
                    <button key={d.id} onClick={() => setSelectedDiff(d)} style={{
                      display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                      padding: '10px 12px', borderRadius: 6, fontFamily: 'var(--font-ui)',
                      border: `1px solid ${active ? 'rgba(29,90,29,0.35)' : 'var(--divider)'}`,
                      background: active ? 'var(--forest-glow)' : 'var(--surface)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{ width: 22, height: 22, flexShrink: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--divider-mid)', borderRadius: 4, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--pine)' }}>{fieldGlyph(d.field)}</span>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{d.field} changed</span>
                        <span className={`pill ${SEV_PILL[d.severity]}`} style={{ marginLeft: 'auto', fontSize: 10 }}>{d.severity}</span>
                      </div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--ink-mid)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {d.before} <span className="text-low">→</span> {d.after}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                        <span className="text-low" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{d.date}</span>
                        <span className="text-low" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{d.asin}</span>
                        {statePill(d.state)}
                      </div>
                    </button>
                  )
                })}
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
              <div className="text-low" style={{ fontSize: 11, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span>Provenance: {statePill(selectedDiff.state)}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>diff {selectedDiff.id}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>ASIN {selectedDiff.asin}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>{selectedDiff.date}</span>
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
          <div className="split-aside-r">
            <div className="card">
              <div className="card-head">
                <h3 className="card-title">Change Timeline</h3>
                <span className="pill pill-muted">{HISTORY.length} events · sample</span>
              </div>
              <div className="timeline">
                {HISTORY.map((h, i) => (
                  <div key={i} className="timeline-item">
                    <div className="timeline-dot" style={SEV_DOT[h.severity]} title={`Severity: ${h.severity}`}>·</div>
                    <div className="timeline-content">
                      <div className="timeline-text">{h.event}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                        <span className="timeline-date">{h.date}</span>
                        <span className="pill pill-muted" style={{ fontSize: 10 }}>{h.id}</span>
                        <span className="text-low" style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{h.asin}</span>
                        <span className="pill pill-ochre" style={{ fontSize: 10 }} title="Event type">{h.type}</span>
                        {statePill(h.state)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3 className="card-title" style={{ fontSize: 15 }}>Watch Summary</h3>
                <span className="pill pill-muted">last 7 days · sample</span>
              </div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Events by type</div>
              <div className="stack" style={{ gap: 6, marginBottom: 16 }}>
                {HISTORY_BY_TYPE.map(g => (
                  <div key={g.type} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--divider)' }}>
                    <span style={{ fontSize: 12 }}>{g.type}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className={`pill ${SEV_PILL[highestSeverity(g.severities)]}`} style={{ fontSize: 10 }}>{highestSeverity(g.severities)}</span>
                      <span className="pill pill-muted" style={{ fontSize: 10 }}>{g.count}</span>
                    </span>
                  </div>
                ))}
              </div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 8 }}>Events by provenance</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                {HISTORY_BY_STATE.map(s => <span key={s.state} className="pill pill-muted" style={{ fontSize: 10 }}>{s.state} · {s.count}</span>)}
              </div>
              <div className="text-low" style={{ fontSize: 11 }} title="Watchtower summary only — source detail lives in Alerts and Diffs">
                Indications from the sample watch feed — not verified fact.
              </div>
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
