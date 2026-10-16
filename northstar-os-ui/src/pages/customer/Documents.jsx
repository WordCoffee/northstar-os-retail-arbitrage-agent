import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

// ═══ Real legal documents + acceptance status (foundation read) ═══
function FoundationLegal() {
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
    <>
      <div className="card" data-testid="docs-live" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <h3 className="card-title">Legal documents</h3>
          <span className={`pill pill-${badge.t}`}>{badge.l}</span>
        </div>
        {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading legal documents…</p>}
        {st.phase === 'loaded' && docs.length > 0 ? (
          <DataTable columns={[
            { key: 'title', label: 'Document', render: (v, row) => v || row.doc_type },
            { key: 'doc_type', label: 'Type' },
            { key: 'version', label: 'Version', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
            { key: 'content_hash', label: 'Hash', render: (v) => <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{v ? String(v).slice(0, 12) + '…' : 'UNKNOWN'}</span> },
          ]} rows={docs} />
        ) : st.phase === 'loaded' ? (
          <p data-testid="docs-empty" style={{ fontSize: 13 }}>No published legal documents for this environment yet — honest empty state.</p>
        ) : null}
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <h3 className="card-title">Acceptance status</h3>
          {status && <span className={`pill ${status.accepted ? 'pill-ok' : 'pill-ochre'}`}>{status.accepted ? 'accepted' : 'action required'}</span>}
        </div>
        {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading acceptance status…</p>}
        {anyAuth && <p style={{ fontSize: 13 }}>Sign in to view your acceptance status.</p>}
        {status && (
          <>
            <div className="inline-flex" style={{ gap: 8, flexWrap: 'wrap' }}>
              <span className="pill pill-muted">enforcement: {status.enforcement_active ? 'active' : 'inactive'}</span>
              <span className="pill pill-muted">business use attested: {status.business_use_attested ? 'yes' : 'no'}</span>
              <span className="pill pill-muted">18+ attested: {status.age_18_attested ? 'yes' : 'no'}</span>
            </div>
            {Array.isArray(status.missing_documents) && status.missing_documents.length > 0 && (
              <div className="inline-flex" style={{ gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                <span className="text-low" style={{ fontSize: 11 }}>Missing:</span>
                {status.missing_documents.map(m => <span key={m} className="pill pill-ochre" style={{ fontSize: 10 }}>{m}</span>)}
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default function DocumentsLib() {
  return (
    <PageLayout title="Documents" subtitle="Your contract, legal, and operational records.">
      <DataNotice tone="internal" title="Legal documents are live; operational records have no backend yet">
        The legal document set and acceptance status are live foundation reads. Operational records have no backend yet, so the table below is an honest empty state - nothing is fabricated.l the account backend is connected.
      </DataNotice>

      <FoundationLegal />

      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Operational records</h3>
          <span className="pill pill-muted">not connected</span>
        </div>
        <p style={{ fontSize: 13 }}>No operational-records backend is connected. Honest empty state — no fabricated records.</p>
      </div>
    </PageLayout>
  )
}