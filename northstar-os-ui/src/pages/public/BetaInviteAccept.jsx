import { useState } from 'react'

export default function BetaInviteAccept() {
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
              <label htmlFor="agree-terms">I agree to the <a href="/legal">Terms of Service</a> and <a href="/legal">Privacy Policy</a>.</label>
            </div>
            <button className="btn btn-primary btn-block" onClick={() => setStep(2)}>Confirm Acceptance</button>
          </div>
        )}
        {step === 2 && (
          <div className="empty">
            <div className="empty-icon"><svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.5"><polyline points="20 6 9 17 4 12"/></svg></div>
            <div className="empty-title">Access Confirmed</div>
            <p className="text-mid" style={{ marginBottom: 20 }}>Welcome to NorthstarOS. Your workspace is ready.</p>
            <button className="btn btn-primary" onClick={() => window.location.hash = '#/home'}>Enter Workspace</button>
          </div>
        )}
      </div>
    </div>
  )
}