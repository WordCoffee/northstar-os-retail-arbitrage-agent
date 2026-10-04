import { PageLayout, DataTable, MetricTiles, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real organization entitlements (foundation read) ═══
function WorkspaceEntitlements() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.entitlements()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="ws-entitlements" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Your entitlements</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading entitlements…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in to view your entitlements.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Entitlements unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
            <span className="pill pill-muted" title="Plan tier from the entitlement service">tier: {v.tier || 'UNKNOWN'}</span>
            <span className="pill pill-muted">jobs/mo: {v.max_jobs_per_month ?? 'UNKNOWN'}</span>
            <span className="pill pill-muted">seats: {v.seat_limit ?? 'UNKNOWN'}</span>
            <span className="pill pill-muted">export: {v.export_enabled ? 'enabled' : 'disabled'}</span>
            <span className="pill pill-muted">advanced reports: {v.advanced_reports ? 'yes' : 'no'}</span>
            <span className="pill pill-muted">support: {v.support_level || 'none'}</span>
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>These flags are the authoritative entitlements for your organization. Service availability below is a capability map, not an entitlement list.</div>
        </>
      )}
    </div>
  )
}

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'services', label: 'Entitled Services', count: 8 },
  { id: 'plan', label: 'Plan & Usage' },
  { id: 'activity', label: 'What Changed' },
]

const SERVICES = [
  { name: 'SourceScout', route: '/product-finder', status: 'Available', tone: 'forest' },
  { name: 'Golden Goose Finder', route: '/golden-goose', status: 'Available', tone: 'forest' },
  { name: 'ListingForge', route: '/listingforge', status: 'Available', tone: 'forest' },
  { name: 'AdPilot', route: '/adpilot', status: 'Available', tone: 'forest' },
  { name: 'Profitability Dashboard', route: '/profitability', status: 'Available', tone: 'forest' },
  { name: 'Commerce Ops', route: '/commerce-ops', status: 'Limited', tone: 'ochre' },
  { name: 'SocialPulse', route: '/socialpulse', status: 'Concept', tone: 'unknown' },
  { name: 'Creative Studio', route: '/creative-studio', status: 'Concept', tone: 'unknown' },
]

export default function CustomerWorkspace() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'overview'

  return (
    <PageLayout
      title="Customer Workspace"
      subtitle="Your NorthstarOS briefing — entitlements, actions, service access, and account state."
      actions={<>
        <button className="btn btn-sm" onClick={() => navigate('/plan')}>View Plan Details</button>
        <button className="btn btn-sm btn-ghost" onClick={() => navigate('/support')}>Contact Support</button>
      </>}
    >
      <DataNotice tone="sample" title="Live entitlements + sample workspace figures">
        “Your entitlements” is a live foundation read. The plan/usage figures and open tasks below are demonstration data.
      </DataNotice>

      <WorkspaceEntitlements />

      <RoomTabs tabs={TABS} base="/customer-workspace" />

      {view === 'overview' && (
        <div className="subview">
          <div className="alert alert-warn" style={{ marginBottom: 20 }}>
            <div className="alert-title">2 Actions Required</div>
            <div className="alert-text">Review Product Set #47 (2 items flagged). Accept updated Terms (updated 2026-09-25).</div>
          </div>
          <MetricTiles metrics={[
            { label: 'Plan', value: 'Business', sub: 'Renewal Sep 2026' },
            { label: 'Usage', value: '68%', sub: 'Monthly quota', tone: 'warn' },
            { label: 'Entitled Services', value: '5', sub: 'Access level: Full' },
            { label: 'Actions Required', value: '2', sub: 'Review needed', tone: 'warn' },
          ]} columns={4} />
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Open Tasks</h3>
              <span className="pill pill-clay">2 pending</span>
            </div>
            {[
              { task: 'Review Product Set #47', note: '2 items flagged for confirmation', state: 'Review', tone: 'pill-warn' },
              { task: 'Accept updated Terms', note: 'Terms updated 2026-09-25', state: 'Pending', tone: 'pill-ochre' },
            ].map(t => (
              <div key={t.task} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.task}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{t.note}</div>
                </div>
                <span className={`pill ${t.tone}`}>{t.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'services' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Entitled Services</h3>
              <span className="pill pill-muted">sample · capability map</span>
            </div>
            {SERVICES.map(s => (
              <div key={s.name} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>Launch the {s.name} room</div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className={`pill pill-${s.tone}`}>{s.status}</span>
                  <button className="btn btn-sm btn-ghost" onClick={() => navigate(s.route)}>Open</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'plan' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Plan &amp; Usage</h3>
              <span className="pill pill-forest">Business</span>
            </div>
            <DataTable columns={[
              { key: 'label', label: 'Item' },
              { key: 'value', label: 'Value' },
            ]} rows={[
              { label: 'Monthly Quota', value: '68% used' },
              { label: 'API Calls', value: '4,200 / 6,000' },
              { label: 'Data Retention', value: '90 days' },
              { label: 'Renewal Date', value: 'Sep 2026' },
            ]} />
          </div>
        </div>
      )}

      {view === 'activity' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">What Changed</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>2026-09-25 — Terms updated</div>
                <span className="pill pill-ochre">Action</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>2026-09-24 — Product Set #47 updated</div>
                <span className="pill pill-ochre">Action</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>2026-09-20 — Plan upgraded to Business</div>
                <span className="pill pill-forest">Change</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}