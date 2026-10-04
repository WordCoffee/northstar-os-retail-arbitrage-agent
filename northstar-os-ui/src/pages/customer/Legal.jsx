import { PageLayout, DataTable, DataNotice, AuthorizationNote } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real legal documents + acceptance status (foundation read) ═══
function LegalLive() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      const [docs, status] = await Promise.all([
        settle(foundationApi.legalDocuments()),
        settle(foundationApi.legalAcceptanceStatus()),
      ])
      if (alive) setSt({ phase: 'loaded', docs, status })
    })()
    return () => { alive = false }
  }, [])
  const docs = st.docs && st.docs.ok ? (st.docs.value.items || []) : []
  const status = st.status && st.status.ok ? st.status.value : null
  const anyAuth = st.phase === 'loaded' && st.status && !st.status.ok && st.status.error && st.status.error.status === 401
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : anyAuth ? { l: 'sign-in required', t: 'unknown' }
      : (docs.length || status) ? { l: 'live · foundation', t: 'muted' }
        : { l: 'unavailable', t: 'unknown' }
  return (
    <div className="card" data-testid="legal-live" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Legal documents &amp; acceptance</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading legal documents…</p>}
      {anyAuth && <p style={{ fontSize: 13 }}>Sign in to view your legal acceptance status.</p>}
      {st.phase === 'loaded' && !anyAuth && (
        <>
          {docs.length > 0 ? (
            <DataTable columns={[
              { key: 'title', label: 'Document', render: (v, row) => v || row.doc_type },
              { key: 'doc_type', label: 'Type' },
              { key: 'version', label: 'Version', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
            ]} rows={docs} />
          ) : <p className="text-low" style={{ fontSize: 12 }}>No published legal documents for this environment yet — honest empty state.</p>}
          {status && (
            <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
              <span className={`pill ${status.accepted ? 'pill-ok' : 'pill-ochre'}`}>{status.accepted ? 'accepted' : 'action required'}</span>
              <span className="pill pill-muted">business use attested: {status.business_use_attested ? 'yes' : 'no'}</span>
              <span className="pill pill-muted">18+ attested: {status.age_18_attested ? 'yes' : 'no'}</span>
              {Array.isArray(status.missing_documents) && status.missing_documents.length > 0 && (
                <span className="inline-flex" style={{ gap: 4, flexWrap: 'wrap' }}>
                  {status.missing_documents.map(m => <span key={m} className="pill pill-ochre" style={{ fontSize: 10 }}>missing: {m}</span>)}
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function CustomerLegal() {
  return (
    <PageLayout title="Legal Acceptance" subtitle="Review and accept the legal terms.">
      <DataNotice tone="internal" title="Live documents + acceptance status">
        The “Legal documents &amp; acceptance” card is a live foundation read. Recording acceptance is a real, audited write that is not activated in this beta yet — it stays disabled below.
      </DataNotice>

      <LegalLive />

      <AuthorizationNote
        title="Record legal acceptance"
        status="Disabled — write not activated"
        route="POST /api/v1/foundation/legal/acceptance"
        permission="PERM_VIEW"
        audit="legal acceptance (account_acceptance)"
      >
        Recording acceptance attests business use and 18+ status against the current document versions. This write is not activated in this beta; acceptance is recorded by the operator during onboarding. Live status is shown above.
      </AuthorizationNote>
      <div style={{ maxWidth: 600 }}>
        <button className="btn btn-primary" disabled title="Acceptance recording is not activated in this beta">Accept All</button>
      </div>
    </PageLayout>
  )
}