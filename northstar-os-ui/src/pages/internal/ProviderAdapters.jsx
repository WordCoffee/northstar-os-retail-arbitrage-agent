import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

const TABS = [
  { id: 'adapters', label: 'Adapters', count: 4 },
  { id: 'health', label: 'Health' },
  { id: 'config', label: 'Configuration' },
]

// ═══ Real provider registry (foundation read; credential NAMES only) ═══
function FoundationProviderRegistry() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.providers()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  return (
    <div className="card" data-testid="pa-registry" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Provider registry</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading provider registry…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in to read the provider registry.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Provider registry unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'name', label: 'Provider', render: (v, row) => v || row.provider_key },
          { key: 'provider_key', label: 'Key', render: (v) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{v}</span> },
          { key: 'category', label: 'Category', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
          { key: 'read_capable', label: 'Access', render: (v, row) => <span className="pill pill-muted">{v ? 'read' : ''}{row.write_capable ? ' + write' : ''}{!v && !row.write_capable ? '—' : ''}</span> },
          { key: 'credential_ref_names', label: 'Credential names', render: (v) => (v && v.length) ? <span className="inline-flex" style={{ gap: 4, flexWrap: 'wrap' }}>{v.map(n => <span key={n} className="pill pill-muted" style={{ fontSize: 10 }}>{n}</span>)}</span> : <span className="pill pill-muted">none</span> },
          { key: 'sandbox_supported', label: 'Sandbox', render: (v) => <span className="pill pill-muted">{v ? 'yes' : 'no'}</span> },
          { key: 'enabled', label: 'Enabled', render: (v) => <span className={`pill ${v ? 'pill-ok' : 'pill-muted'}`} title="Provider arming is an owner decision; disabled by default">{v ? 'enabled' : 'disabled'}</span> },
          { key: 'health', label: 'Health', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
        ]} rows={st.items} />
      ) : (
        <p data-testid="pa-registry-empty" style={{ fontSize: 13 }}>No providers are registered in the foundation yet.</p>
      ))}
      <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>Credential reference <em>names</em> only — values live in the vault and are never exposed. Arming a provider is an owner decision.</div>
    </div>
  )
}

// ═══ Provider key presence + scanner gate (real read; names only) ═══
function ProviderKeyPresence() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.detailedHealth()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const v = st.phase === 'loaded' ? st.value : null
  const providers = v && v.providers ? v.providers : {}
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
      : { l: 'live · backend probe', t: 'muted' }
  const configured = Object.values(providers).filter(s => s === 'configured').length
  return (
    <div className="card" data-testid="pa-key-presence" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Provider credential presence</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Checking provider credential presence…</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Provider presence probe unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <span className={`pill ${v.scanner_mode === 'live_allowed' ? 'pill-warn' : 'pill-muted'}`} title="Live scanner gate — arming is an owner decision">scanner: {v.scanner_mode || 'UNKNOWN'}</span>
            <span className="pill pill-muted" title="Count of provider keys present in the environment (presence only)">{configured} of {Object.keys(providers).length} configured</span>
          </div>
          {Object.keys(providers).length > 0 ? (
            <DataTable columns={[
              { key: 'name', label: 'Provider key (name only)' },
              { key: 'state', label: 'Presence', render: (v) => <span className={`pill ${v === 'configured' ? 'pill-muted' : 'pill-unknown'}`}>{v === 'configured' ? 'configured' : 'not configured'}</span> },
            ]} rows={Object.entries(providers).map(([name, state]) => ({ name, state }))} />
          ) : <p className="text-low" style={{ fontSize: 12 }}>No provider keys reported.</p>}
          <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>
            Presence only — credential <em>values</em> are never read or displayed. Arming a provider for live calls is an owner decision; nothing here enables a call.
          </div>
        </>
      )}
    </div>
  )
}

export default function ProviderAdapters() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'adapters'

  return (
    <PageLayout
      title="Provider Adapters"
      subtitle="Data provider status — adapter health, rate limits, freshness, and controlled provider state."
      actions={<>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Adapter Log — full call history per adapter.', 'info')}>Adapter Log</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Configuration view opened.', 'info')}>Configuration</button>
      </>}
    >
      <DataNotice tone="internal" title="Controlled provider state">
        The “Provider registry” card is a live foundation read (credential names only). The adapter status and configuration views below are sample/observed. Live provider calls are NOT made during normal browsing.
      </DataNotice>

      <FoundationProviderRegistry />
      <ProviderKeyPresence />

      <RoomTabs tabs={TABS} base="/provider-adapters" />

      {view === 'adapters' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Sample adapters (preview)</h3>
              <span className="pill pill-muted">4 adapters · sample</span>
            </div>
            <DataTable columns={[
              { key: 'adapter', label: 'Adapter' },
              { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'Active' ? 'pill-muted' : v === 'Rate Limited' ? 'pill-warn' : 'pill-muted'}`} title="Sample/observed adapter state — not a live probe">{v}</span> },
              { key: 'latency', label: 'Latency' },
              { key: 'data', label: 'Data State' },
              { key: 'calls', label: 'Calls (24h)' },
            ]} rows={[
              { adapter: 'Market Price Feed', status: 'Active', latency: '420ms', data: 'Cached', calls: '1,240' },
              { adapter: 'Rank Tracker', status: 'Active', latency: '180ms', data: 'Observed', calls: '890' },
              { adapter: 'Buy Box Monitor', status: 'Rate Limited', latency: '—', data: 'Stale', calls: '3,200' },
              { adapter: 'Review Aggregator', status: 'Idle', latency: '—', data: 'Unavailable', calls: '0' },
            ]} />
            <div className="text-low" style={{ fontSize: 11, marginTop: 10 }} title="Truth-state rule: green means live-verified only">
              Adapter states here are sample/observed. Green is reserved for genuinely probe-backed, live-verified outcomes; adverse states keep their distinct colour.
            </div>
          </div>
        </div>
      )}

      {view === 'health' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Health &amp; Rate Limits</h3>
            </div>
            <div className="grid-3" style={{ gap: 16 }}>
              {[
                { label: 'Rate Limit Usage', v: '72%', note: 'Of quota used', warn: true },
                { label: 'Data Freshness', v: '2h', note: 'Avg staleness' },
                { label: 'Data Quality', v: 'Good', note: 'Adapters healthy' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: d.warn ? 'var(--ochre)' : 'var(--pine-deep)' }}>{d.v}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{d.note}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Watch Items</h3>
            </div>
            {[
              { item: 'Buy Box Monitor near quota — expect staleness', state: 'Watch', tone: 'pill-warn' },
              { item: 'Review Aggregator idle — no provider key bound', state: 'Idle', tone: 'pill-muted' },
            ].map(w => (
              <div key={w.item} className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 13 }}>{w.item}</div>
                <span className={`pill ${w.tone}`}>{w.state}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {view === 'config' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Adapter Configuration</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Market Price Feed — refresh cadence 2h</div>
                <span className="pill pill-muted">Configured</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Rank Tracker — refresh cadence 1h</div>
                <span className="pill pill-muted">Configured</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Buy Box Monitor — rate limit tripped</div>
                <span className="pill pill-warn">Cooldown</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Review Aggregator — no key bound</div>
                <span className="pill pill-muted">Unbound</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}