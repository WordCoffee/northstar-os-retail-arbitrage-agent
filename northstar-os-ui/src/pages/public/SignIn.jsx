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
// LOCAL_DEV is a build-time constant (see foundation/dev.js): in a built bundle
// these fold to empty values and the whole branch is eliminated. The shim
// identity and its credentials must not survive into ANY served bundle - a
// served bundle signs in through the real credential path only.
const LOCAL_DEMO_IDENTIFIER = LOCAL_DEV ? 'T2' : ''
const LOCAL_DEMO_PASSWORD = LOCAL_DEV ? '123abc' : ''
const LOCAL_DEMO_SESSION = LOCAL_DEV
  ? { userId: 'demo-t2', orgId: 'org-t2', role: 'operator', env: 'production' }
  : null

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

    // The shim identity (LOCAL_DEV only) NEVER touches the credential endpoint.
    // It either authenticates through the loopback shim or fails closed with an
    // explanation - no /auth/login request is made and nothing is logged. Only
    // the EXACT demo pair takes this path; any other typed pair (including the
    // demo identifier with a real password) is an explicit real login.
    const isShimPair = LOCAL_DEV
      && identifier.toLowerCase() === LOCAL_DEMO_IDENTIFIER.toLowerCase()
      && form.password === LOCAL_DEMO_PASSWORD

    if (isShimPair) {
      setBusy(true)
      session.updateDev(LOCAL_DEMO_SESSION)
      const shim = await session.refresh()
      setBusy(false)
      if (shim && shim.authenticated) {
        navigate('/home')
        return
      }
      setError('The local dev shim could not authenticate against this backend. The shim works only when the connected API runs in development posture on loopback; a containerized API never sees a loopback client. Nothing was sent to the credential endpoint.')
      return
    }

    // Real credential login (sets the HttpOnly session cookie). Reachable in a
    // dev build only when the operator types a real account, and always in a
    // production build.
    setBusy(true)
    try {
      await foundationApi.login(identifier.toLowerCase(), form.password)
      await session.refresh()
      navigate('/home')
    } catch {
      setError(LOCAL_DEV
        ? 'Invalid credentials. Sign in with a real local account, or run the local backend in development posture for the shim.'
        : 'Invalid email or password.')
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
            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign In'}</button>
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
