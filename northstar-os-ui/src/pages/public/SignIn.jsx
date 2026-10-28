import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../../foundation/session.jsx'
import foundationApi, { setDevSession } from '../../foundation/api.js'
import { LOCAL_DEV } from '../../foundation/dev.js'

// DEV-BY-PASS (development only, LOCAL_DEV build-time constant):
// In a dev build the sign-in screen is replaced by an automatic route to the
// workspace — no prompt, no username, no password. The dev shim identity
// (X-User-Id/X-Org-Id headers) is still the ONLY backend mechanism and still
// requires ENVIRONMENT=development + a loopback client. The bypass is a UI
// shortcut only; production builds are unchanged and sign in with real
// credentials. The dev constants are empty so they cannot appear in any
// served bundle (check-prod-bundle.cjs asserts their absence).
const LOCAL_DEMO_IDENTIFIER = ''
const LOCAL_DEMO_PASSWORD = ''
const LOCAL_DEMO_SESSION = { userId: 'demo-t2', orgId: 'org-t2', role: 'operator', env: 'development', previewId: '' }

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

  // Dev-only: redirect to /home. GuardedRoutes also redirects /ui/sign-in.
  // No banner here — DevBanner renders on every page via the shell.
  if (LOCAL_DEV) return <Navigate to="/home" replace />

  const submit = async (e) => {
    e.preventDefault()
    // Dev-only skip: no prompt, no credential entry. Route to workspace.
    if (LOCAL_DEV) {
      navigate('/home')
      return
    }
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
      setError('The local dev shim could not authenticate against this backend. This prefilled pair is the local demo identity, not an account: it authenticates only when the connected API runs in development posture on loopback AND the demo identity exists in the local store. Nothing was sent to the credential endpoint - clear this form and type your real local account (identifier and password) instead.')
      return
    }

    // Real credential login (sets the HttpOnly session cookie). Reachable in a
    // dev build only when the operator types a real account, and always in a
    // production build.
    setBusy(true)
    try {
      // Drop any persisted dev-shim identity FIRST. A shim attempt leaves
      // ns-dev-session in localStorage, and foundation/api.js attaches its
      // X-User-Id/X-Org-Id headers to EVERY foundation request - so a real,
      // cookie-authenticated session would keep requesting the demo
      // organization and fail closed with 403 cross_organization_access_denied
      // (foundation/api/deps.py resolves requested_org from X-Org-Id). After a
      // real credential login the cookie is the sole identity.
      setDevSession({ userId: '', orgId: '', role: '', env: 'production', previewId: '' })
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
            <div className="text-low" style={{ fontSize: 11, color: 'var(--ink)' }}>
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