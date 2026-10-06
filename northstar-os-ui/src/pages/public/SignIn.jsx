import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../../foundation/session.jsx'
import foundationApi from '../../foundation/api.js'
import { LOCAL_DEV } from '../../foundation/dev.js'

// Local private-beta demo identity.
// The SPA authenticates locally through the loopback development identity shim
// (SessionProvider "dev session" -> X-User-Id/X-Org-Id/X-Role). Hosted
// environments ignore those headers, so this grants no production access and
// cannot bypass a real auth posture. Role is deliberately "operator" so
// internal-only surfaces (/beta-ops, /admin) remain guarded.
//
// orgId is intentionally EMPTY. The foundation DB is a fresh temp SQLite per
// server start and seeds no users or orgs, so this shim user has no memberships:
// requesting an org would 403 (cross_organization_access_denied) and strand the
// operator on /sign-in. With the user only, /me resolves and
// active_organization_id is null.
const LOCAL_DEMO_IDENTIFIER = 'T2'
const LOCAL_DEMO_PASSWORD = '123abc'
const LOCAL_DEMO_SESSION = { userId: 'demo-t2', orgId: '', role: 'operator', env: 'production' }

export default function SignIn() {
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()
  const invitedOrg = new URLSearchParams(location.search).get('org') || ''
  const [form, setForm] = useState(LOCAL_DEV
    ? { identifier: LOCAL_DEMO_IDENTIFIER, password: LOCAL_DEMO_PASSWORD }
    : { identifier: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Already signed in (incl. after a page refresh) -> straight to the workspace.
  if (session.authenticated) return <Navigate to="/home" replace />

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    const identifier = (form.identifier || '').trim()

    if (LOCAL_DEV) {
      // Explicit local-development identity shim (never a hosted fallback).
      if (identifier.toLowerCase() !== LOCAL_DEMO_IDENTIFIER.toLowerCase() || form.password !== LOCAL_DEMO_PASSWORD) {
        setError('Those credentials did not match the local private-beta account.')
        return
      }
      session.updateDev(LOCAL_DEMO_SESSION)
      navigate('/home')
      return
    }

    // Hosted: real credential login (sets the HttpOnly session cookie).
    setBusy(true)
    try {
      await foundationApi.login(identifier.toLowerCase(), form.password)
      await session.refresh()
      navigate('/home')
    } catch {
      setError('Invalid email or password.')
    } finally {
      setBusy(false)
    }
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
              <Link to="/recovery">Forgot password?</Link> &nbsp;·&nbsp; <Link to="/beta">Need help?</Link> &nbsp;·&nbsp; <Link to="/legal">Legal</Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
