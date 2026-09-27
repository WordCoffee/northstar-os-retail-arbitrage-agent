export default function BetaDenied() {
  return (
    <div className="fade-in">
      <div style={{ maxWidth: 500, margin: '60px auto', textAlign: 'center' }}>
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" strokeWidth="1.5" style={{ margin: '0 auto 20px' }}><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        <h1 style={{ fontSize: 22, marginBottom: 10 }}>Access Not Available</h1>
        <p className="text-mid" style={{ marginBottom: 20 }}>Your invitation could not be verified. The invitation may have expired, been revoked, or the code is invalid.</p>
        <div className="stack" style={{ gap: 10 }}>
          <button className="btn btn-primary btn-block" onClick={() => window.location.href = '/beta'}>Request New Invitation</button>
          <button className="btn btn-ghost btn-block" onClick={() => window.location.href = '/sign-in'}>Sign In</button>
        </div>
      </div>
    </div>
  )
}