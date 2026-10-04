import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import signals, { settle } from '../../services/signals.js'

// ═══ Real invite lookup (used only when a ?code= is present) ═══
// Public, no-secrets validation via /api/v1/invites/{code}. Never fabricates an
// invite. Redemption itself requires a signed-in account and is not performed here.
function RealInvite({ code }) {
  const navigate = useNavigate()
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(signals.inviteLookup(code)).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', invite: (r.value && r.value.invite) || null })
      else setSt({ phase: (r.error && r.error.status === 404) ? 'not_found' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [code])

  const inv = st.phase === 'loaded' ? st.invite : null
  const expired = inv && inv.expires_at ? (new Date(inv.expires_at).getTime() < Date.now()) : false
  const statusLabel = !inv ? '' : inv.redeemed ? 'Redeemed' : expired ? 'Expired' : 'Active'
  const statusTone = !inv ? '' : inv.redeemed || expired ? 'pill-warn' : 'pill-forest'

  return (
    <div className="fade-in" style={{ maxWidth: 520, margin: '40px auto' }}>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>Accept Invitation</h2>
        <p className="text-mid" style={{ marginBottom: 24 }}>Review and confirm your access to NorthstarOS.</p>

        {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Validating invitation…</p>}
        {st.phase === 'not_found' && <p data-testid="invite-not-found" style={{ fontSize: 13 }}>This invitation code is not recognized. Nothing is fabricated — ask your operator to reissue it.</p>}
        {st.phase === 'error' && <p style={{ fontSize: 13 }}>Invitation validation is unavailable right now. Try again shortly.</p>}

        {inv && (
          <div className="stack" style={{ gap: 16 }}>
            <div className="evidence">
              <div className="evidence-header">
                <span className={`pill ${statusTone}`}>{statusLabel}</span>
                <span className="evidence-source">{inv.code}</span>
              </div>
              <p className="evidence-body">
                Cohort <strong>{inv.cohort || 'UNKNOWN'}</strong>{inv.plan ? <> · plan <strong>{inv.plan}</strong></> : null}
                {inv.email ? <> · invited email {inv.email}</> : null}.
                {inv.expires_at ? <> Expires {inv.expires_at}.</> : null}
              </p>
            </div>
            <div className="text-low" style={{ fontSize: 12 }}>
              Invitations are single-use. Redemption completes after you sign in; this page only validates the code.
            </div>
            <button
              className="btn btn-primary btn-block"
              disabled={!inv || inv.redeemed || expired}
              title={inv.redeemed ? 'This invitation has already been redeemed' : expired ? 'This invitation has expired' : ''}
              onClick={() => navigate('/sign-in?invite=' + encodeURIComponent(inv.code))}
            >
              Continue to Sign In
            </button>
            <div style={{ textAlign: 'center' }}><Link to="/beta" className="text-low" style={{ fontSize: 12 }}>Back</Link></div>
          </div>
        )}
      </div>
    </div>
  )
}

// ═══ Demo invite flow (no ?code= present) — harness-pinned, unchanged ═══
function DemoInvite() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  return (
    <div className="fade-in" style={{ maxWidth: 520, margin: '40px auto' }}>
      <div className="card">
        <h2 style={{ marginBottom: 4 }}>Accept Invitation</h2>
        <p className="text-mid" style={{ marginBottom: 24 }}>Review and confirm your access to NorthstarOS.</p>
        {step === 1 && (
          <div className="stack" style={{ gap: 16 }}>
            <div className="evidence">
              <div className="evidence-header">
                <span className="pill pill-forest">Invitation</span>
                <span className="evidence-source">INV-2026-09-26-0042</span>
              </div>
              <p className="evidence-body">You have been invited by <strong>T2 Holdings LLC</strong> to join NorthstarOS as an Operator.</p>
            </div>
            <div className="field-group">
              <label className="label">Organization Name</label>
              <input className="field" defaultValue="T2 Holdings LLC" readOnly />
            </div>
            <div className="field-group">
              <label className="label">Role</label>
              <input className="field" defaultValue="Operator" readOnly />
            </div>
            <div className="check-row" style={{ marginBottom: 8 }}>
              <input type="checkbox" id="agree-terms" />
              <label htmlFor="agree-terms">I agree to the <Link to="/legal">Terms of Service</Link> and <Link to="/legal">Privacy Policy</Link>.</label>
            </div>
            <button className="btn btn-primary btn-block" onClick={() => setStep(2)}>Confirm Acceptance</button>
          </div>
        )}
        {step === 2 && (
          <div className="empty">
            <div className="empty-icon"><svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.5"><polyline points="20 6 9 17 4 12"/></svg></div>
            <div className="empty-title">Access Confirmed</div>
            <p className="text-mid" style={{ marginBottom: 20 }}>Your invitation is accepted. Sign in to open your NorthstarOS workspace.</p>
            <button className="btn btn-primary" onClick={() => navigate('/sign-in?org=' + encodeURIComponent('T2 Holdings LLC'))}>Continue to Sign In</button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function BetaInviteAccept() {
  const location = useLocation()
  const code = new URLSearchParams(location.search).get('code') || ''
  return code ? <RealInvite code={code} /> : <DemoInvite />
}