// Account recovery. No recovery backend is wired in this beta — the surface is
// honest about that and does not present a working control.
export default function Recovery() {
  return (
    <div className="fade-in">
      <div style={{ maxWidth: 420, margin: '60px auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h2>Recovery</h2>
          <p className="text-mid" style={{ fontSize: 13 }}>Reset your credentials or verify your identity.</p>
        </div>
        <div className="card">
          <div className="alert-warn" style={{ marginBottom: 16 }}>
            <div className="alert-title">Recovery is not connected in this beta</div>
            <div className="alert-text">Self-service recovery is not wired yet. Contact your organization operator or the beta support channel to restore access.</div>
          </div>
          <div className="stack" style={{ gap: 16 }}>
            <div className="field-group">
              <label className="label">Organization ID</label>
              <input className="field" placeholder="Enter your organization identifier" disabled />
            </div>
            <div className="field-group">
              <label className="label">Verification Method</label>
              <select className="field" disabled>
                <option>Email verification</option>
                <option>Organization admin recovery</option>
                <option>Hardware key</option>
              </select>
            </div>
            <button className="btn btn-primary btn-block" disabled title="Recovery is not wired in this beta">Send Recovery Link</button>
            <p className="text-low" style={{ fontSize: 12, textAlign: 'center' }}>No recovery link is sent. Access restoration is an operator action during the beta.</p>
          </div>
        </div>
      </div>
    </div>
  )
}