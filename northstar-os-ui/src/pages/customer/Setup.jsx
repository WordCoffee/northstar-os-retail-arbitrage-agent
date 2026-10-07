import { PageLayout, DataNotice } from '../../components/Shared.jsx'
import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'
import { useSession } from '../../foundation/session.jsx'

// ═══ Real onboarding checklist (organization-scoped foundation read) ═══
function FoundationOnboarding() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.onboardingStatus()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', value: r.value })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [])
  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }
  const v = st.phase === 'loaded' ? st.value : null
  const steps = v && Array.isArray(v.steps) ? v.steps : []
  const checklist = v && v.checklist ? v.checklist : {}
  return (
    <div className="card" data-testid="setup-onboarding" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Onboarding status</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading onboarding status…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in to view onboarding status.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Onboarding status unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {v && (
        <>
          <div className="inline-flex" style={{ gap: 8, marginBottom: 12 }}>
            <span className={`pill ${v.completed ? 'pill-ok' : 'pill-ochre'}`}>{v.completed ? 'onboarding complete' : 'in progress'}</span>
            {v.completed_at && <span className="pill pill-muted">completed {v.completed_at}</span>}
          </div>
          {steps.length > 0 ? (
            <div className="stack" style={{ gap: 8 }}>
              {steps.map(s => (
                <div key={s} className="check-row">
                  <input type="checkbox" checked={!!checklist[s]} readOnly />
                  <label>{s.replace(/_/g, ' ')}</label>
                  <span className={`pill ${checklist[s] ? 'pill-muted' : 'pill-ochre'}`} style={{ marginLeft: 'auto', fontSize: 10 }}>{checklist[s] ? 'done' : 'pending'}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-low" style={{ fontSize: 12 }}>No onboarding steps have been initialized for this organization yet.</p>}
        </>
      )}
    </div>
  )
}

export default function CustomerSetup() {
  const navigate = useNavigate()
  const session = useSession()
  const orgName = session.activeOrganizationId
    || (session.organizations && session.organizations[0] && session.organizations[0].name) || ''
  return (
    <PageLayout title="Setup & Onboarding" subtitle="Complete your workspace configuration.">
      <DataNotice tone="internal" title="Live onboarding + session identity">
        “Onboarding status” is a live, organization-scoped read. The organization identity below is the current session; legal acceptance lives on the Legal page. No fabricated profile data.
      </DataNotice>

      <FoundationOnboarding />

      <div style={{ maxWidth: 600 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Organization</h3>
            <span className="pill pill-muted">live · session</span>
          </div>
          <div className="inline-flex" style={{ gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <span className="pill pill-muted">{orgName || 'no active organization'}</span>
            <span className="pill pill-muted">role: {session.role || 'UNKNOWN'}</span>
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Legal acceptance</h3>
            <span className="pill pill-muted">see Legal page</span>
          </div>
          <p style={{ fontSize: 13 }}>Legal documents and your acceptance status are shown live on the Legal page.</p>
          <button className="btn btn-sm btn-ghost" onClick={() => navigate('/legal')}>Open Legal</button>
        </div>
      </div>
    </PageLayout>
  )
}
