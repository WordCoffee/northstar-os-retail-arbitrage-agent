import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import signals, { settle } from '../../services/signals.js'
import MasterBrainPanel from '../../studio/components/MasterBrainPanel.jsx'

const TABS = [
  { id: 'alerts', label: 'Alerts' },
  { id: 'diffs', label: 'Diffs' },
  { id: 'history', label: 'History' },
  { id: 'escalations', label: 'Escalations' },
]

const SEV_PILL = { High: 'pill-error', Medium: 'pill-warn', Low: 'pill-muted' }
const ts = (x) => (x ? String(x).slice(0, 19).replace('T', ' ') : '—')

// ═══ One real read set: listings + identity enrichment (local) ═══
function useListingHealth() {
  const [st, setSt] = useState({ loaded: false })
  useEffect(() => {
    let alive = true
    settle(signals.ncListingsHealth()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ loaded: true, value: r.value })
      else setSt({ loaded: true, error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.loaded && st.value ? st.value : null
  const listings = v && Array.isArray(v.items) ? v.items : []
  const enrich = v && v.summary && Array.isArray(v.summary.enrichment) ? v.summary.enrichment : []
  const capture = v && v.summary && v.summary.identifier_capture ? v.summary.identifier_capture : {}
  const evidenceRows = v && v.summary ? (v.summary.evidence_rows ?? 0) : 0

  // Derived identity alerts: enrichment records missing identifiers, or non-published listings.
  const alerts = []
  enrich.forEach((e, i) => {
    const cap = String(e.identifier_capture_status || 'unknown')
    if (cap !== 'captured') {
      alerts.push({ id: 'LG-ID-' + i, asin: e.costco_item_number || e.source_product_id || '—', type: 'Identity gap', severity: 'High', date: ts(e.captured_at), status: 'Review' })
    }
  })
  listings.forEach((l, i) => {
    if (String(l.status || '').toLowerCase() !== 'published') {
      alerts.push({ id: 'LG-LS-' + i, asin: l.asin || '—', type: 'Listing status', severity: 'Medium', date: ts(l.updated_at), status: 'Monitoring' })
    }
  })

  // Derived escalations: unresolved identity / unknown split-pack.
  const escalations = enrich
    .filter(e => String(e.identifier_capture_status || '') !== 'captured' || String(e.split_pack_status || '') === 'unknown')
    .slice(0, 40)
    .map((e, i) => ({
      id: 'LG-ES-' + i,
      asin: e.costco_item_number || e.source_product_id || '—',
      reason: `identity ${e.identifier_capture_status || 'unknown'} · split ${e.split_pack_status || 'unknown'}`,
      target: 'Commerce Ops',
      state: 'Awaiting Review',
      age: '—',
    }))

  return { loaded: st.loaded, error: st.error, listings, enrich, capture, evidenceRows, alerts, escalations }
}

export default function ListingGuardian() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const d = useListingHealth()
  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'alerts'

  const escalate = (asin, target) => {
    navigate('/commerce-ops')
    toast(`Escalated ${asin} to ${target} — manual action required there.`, 'info')
  }

  return (
    <PageLayout
      title="Listing Guardian"
      subtitle="Listing &amp; identity watchtower — real local records, triage, and escalations."
      actions={<>
        <button className="btn btn-sm" onClick={() => { navigate('/listings?view=escalations'); toast('Escalation rules live under the Escalations tab.', 'info') }}>New Rule</button>
        <button className="btn btn-sm btn-ghost" onClick={() => { navigate('/listings?view=history'); toast('History shows the change timeline (local).', 'info') }}>History</button>
      </>}
    >
      <DataNotice tone="internal" title="Real local listing &amp; identity records">
        All records here are live local reads (listings, identity enrichment, evidence). No live Amazon feed is connected — this is a local watchtower, not a live listing monitor. Nothing is fabricated.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/listings" />

      {view === 'alerts' && (
        <div className="subview">
          <div className="grid-3" style={{ gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Open alerts</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>{d.alerts.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{d.alerts.filter(a => a.severity === 'High').length} high severity</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Identity enrichment</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--clay)' }}>{d.enrich.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>{d.evidenceRows} evidence rows</div>
            </div>
            <div className="card" style={{ padding: 14 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Escalations</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ochre)' }}>{d.escalations.length}</div>
              <div className="text-low" style={{ fontSize: 11 }}>to Commerce Ops</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Identity &amp; listing alerts</h3>
              <span className={`pill ${d.alerts.length ? 'pill-clay' : 'pill-muted'}`}>{d.alerts.length} derived · local</span>
            </div>
            {d.alerts.length > 0 ? (
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'asin', label: 'Item' },
                { key: 'type', label: 'Alert Type' },
                { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${SEV_PILL[v] || 'pill-muted'}`}>{v}</span> },
                { key: 'date', label: 'Date' },
                { key: 'escalate', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => escalate(row.asin, 'Commerce Ops')}>Escalate</button> },
              ]} rows={d.alerts} />
            ) : <p data-testid="lg-alerts-empty" style={{ fontSize: 13 }}>No identity or listing alerts derived from local data. Honest empty state.</p>}
          </div>

          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Listing &amp; identity records</h3>
              <span className="pill pill-muted">{d.listings.length} listings · local</span>
            </div>
            {d.listings.length > 0 ? (
              <DataTable columns={[
                { key: 'asin', label: 'ASIN' },
                { key: 'title', label: 'Title', render: (x) => <span title={x}>{x && x.length > 46 ? x.slice(0, 45) + '…' : x}</span> },
                { key: 'status', label: 'Status', render: (x) => <span className="pill pill-muted">{x || 'UNKNOWN'}</span> },
                { key: 'overall_score', label: 'Score', render: (x) => x == null ? <span className="pill pill-unknown">UNKNOWN</span> : <span className="pill pill-muted">{x}</span> },
                { key: 'updated_at', label: 'Updated', render: (x) => ts(x) },
              ]} rows={d.listings} />
            ) : <p style={{ fontSize: 13 }}>No listing records yet. Honest empty state.</p>}
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
              {Object.entries(d.capture).map(([k, n]) => <span key={k} className="pill pill-ochre" style={{ fontSize: 10 }}>{k}: {n}</span>)}
            </div>
          </div>
        </div>
      )}

      {view === 'diffs' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Detected Changes</h3>
              <span className="pill pill-muted">not connected</span>
            </div>
            <p style={{ fontSize: 13 }}>No listing before/after change feed is connected, so no diffs are shown. Honest empty state — no fabricated diffs.</p>
          </div>
        </div>
      )}

      {view === 'history' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Change Timeline</h3>
              <span className="pill pill-muted">{d.listings.length} events · local</span>
            </div>
            {d.listings.length > 0 ? (
              <div className="timeline">
                {[...d.listings].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))).map((l, i) => (
                  <div key={i} className="timeline-item">
                    <div className="timeline-dot timeline-dot-info">i</div>
                    <div className="timeline-content">
                      <div className="timeline-text">{l.asin} — {l.status || 'UNKNOWN'}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                        <span className="timeline-date">{ts(l.updated_at)}</span>
                        {l.overall_score != null && <span className="pill pill-muted" style={{ fontSize: 10 }}>score {l.overall_score}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <p style={{ fontSize: 13 }}>No listing history. Honest empty state.</p>}
          </div>
        </div>
      )}

      {view === 'escalations' && (
        <div className="subview">
          <DataNotice tone="internal" title="Escalations are manual">
            Escalating hands a listing to Commerce Ops for operator action. No Guardian rule changes a listing automatically.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Escalation Queue</h3>
              <span className={`pill ${d.escalations.length ? 'pill-ochre' : 'pill-muted'}`}>{d.escalations.length} items · local</span>
            </div>
            {d.escalations.length > 0 ? (
              <DataTable columns={[
                { key: 'id', label: 'ID' },
                { key: 'asin', label: 'Item' },
                { key: 'reason', label: 'Reason' },
                { key: 'target', label: 'Target Room' },
                { key: 'state', label: 'State', render: (v) => <span className="pill pill-warn">{v}</span> },
                { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm" onClick={() => escalate(row.asin, row.target)}>Open in room</button> },
              ]} rows={d.escalations} />
            ) : <p data-testid="lg-escalations-empty" style={{ fontSize: 13 }}>No escalations derived from local data. Honest empty state.</p>}
          </div>
        </div>
      )}
    <MasterBrainPanel title="Studio evidence for listing health (read-only)" />
    </PageLayout>
  )
}
