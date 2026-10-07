import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import signals, { settle } from '../../services/signals.js'

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
  return (
    <PageLayout
      title="Provider Adapters"
      subtitle="Data provider registry, credential presence, and the live scanner gate — read-only."
    >
      <DataNotice tone="internal" title="Read-only provider state">
        The registry and credential presence are live reads (names only). No live provider calls are made during normal browsing; arming is an owner decision.
      </DataNotice>
      <FoundationProviderRegistry />
      <ProviderKeyPresence />
    </PageLayout>
  )
}
