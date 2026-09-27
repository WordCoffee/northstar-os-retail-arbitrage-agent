import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../../foundation/session.jsx'

// Local private-beta demo identity.
// The SPA authenticates locally through the loopback development identity shim
// (SessionProvider "dev session" -> X-User-Id/X-Org-Id/X-Role). Hosted
// environments ignore those headers, so this grants no production access and
// cannot bypass a real auth posture. Role is deliberately "operator" so
// internal-only surfaces (/beta-ops, /admin) remain guarded.
const LOCAL_DEMO_IDENTIFIER = 'T2'
const LOCAL_DEMO_PASSWORD = '123abc'
const LOCAL_DEMO_SESSION = { userId: 'demo-t2', orgId: 'org-t2', role: 'operator', env: 'production' }

export default function SignIn() {
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()
  const invitedOrg = new URLSearchParams(location.search).get('org') || ''
  const [form, setForm] = useState({ identifier: LOCAL_DEMO_IDENTIFIER, password: LOCAL_DEMO_PASSWORD })
  const [error, setError] = useState('')

  // Already signed in (incl. after a page refresh) -> straight to the workspace.
  if (session.authenticated) return <Navigate to="/home" replace />

  const submit = (e) => {
    e.preventDefault()
    setError('')
    const identifier = (form.identifier || '').trim().toLowerCase()
    if (identifier !== LOCAL_DEMO_IDENTIFIER.toLowerCase() || form.password !== LOCAL_DEMO_PASSWORD) {
      setError('Those credentials did not match the local private-beta account.')
      return
    }
    // Establish the local session (persisted in localStorage -> survives refresh).
    session.updateDev(LOCAL_DEMO_SESSION)
    navigate('/home')
  }

  return (
    <div className="fade-in">
      <div style={{ maxWidth: 420, margin: '60px auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.5" style={{ margin: '0 auto 12px' }}><path d="M12 2L3 7 12 12 21 7 21 17 12 22 3 17"/></svg>
          <h2>Sign In</h2>
          <p className="text-mid" style={{ fontSize: 13 }}>Enter your credentials to access NorthstarOS.</p>
        </div>

        {invitedOrg && (
          <div className="alert alert-warn" style={{ marginBottom: 16 }}>
            <div className="alert-title">Invitation accepted</div>
            <div className="alert-text">You accepted an invitation for <strong>{invitedOrg}</strong>. Sign in to open your workspace.</div>
          </div>
        )}

        <div className="card">
          <form className="stack" style={{ gap: 16 }} onSubmit={submit}>
            <div className="field-group">
              <label className="label" htmlFor="signin-id">Email or Organization ID</label>
              <input id="signin-id" className="field" type="text" placeholder="you@org.com" value={form.identifier} onChange={e => setForm({ ...form, identifier: e.target.value })} />
            </div>
            <div className="field-group">
              <label className="label" htmlFor="signin-pw">Password</label>
              <input id="signin-pw" className="field" type="password" placeholder="Enter password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </div>
            {error && <div className="text-low" style={{ fontSize: 12, color: 'var(--status-error, #b4432f)' }} role="alert">{error}</div>}
            <button className="btn btn-primary btn-block" type="submit">Sign In</button>
            <div className="text-low" style={{ fontSize: 11 }}>
              Local private-beta sign-in. In hosted environments, use your organization’s credentials.
            </div>
            <div style={{ textAlign: 'center', fontSize: 13 }}>
              <a href="#/recovery">Forgot password?</a> &nbsp;·&nbsp; <a href="#/beta">Need help?</a>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
