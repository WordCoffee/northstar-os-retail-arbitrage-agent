// Private Beta invite entry — sign up with an invite code (closed by default).
// Non-revealing denial on invalid/revoked/expired invites.
import { useState } from 'react'
import { PageHead, Card } from '../../ui.jsx'
import foundationApi from '../api.js'

export default function BetaSignup({ toast }) {
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)

  const submit = async () => {
    setBusy(true)
    try {
      const r = await foundationApi.signup({ email, invite_code: code })
      setDone(r)
      toast('Invite accepted — sign in to continue', 'ok')
    } catch (e) {
      toast(e.message || 'Signup is not available at this time', 'err')
    } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <PageHead title="Private Beta Invite"
        sub="Invite-only access — signup is closed unless you have a valid invite" />
      <div className="stack" style={{ marginTop: 16 }}>
        <Card title="Enter your invite" icon="lock">
          <div className="stack">
            <label className="field-label" htmlFor="signup-email">Email</label>
            <input id="signup-email" className="field" placeholder="you@example.com"
                   value={email} onChange={(e) => setEmail(e.target.value)} />
            <label className="field-label" htmlFor="signup-code">Invite code</label>
            <input id="signup-code" className="field" placeholder="XXXX-XXXX"
                   value={code} onChange={(e) => setCode(e.target.value)} />
            <button className="btn btn-primary" disabled={busy || !email || !code} onClick={submit}>
              {busy ? 'Accepting…' : 'Accept invite'}
            </button>
            <div className="text-low" style={{ fontSize: 11 }}>
              If your invite is invalid, revoked, or expired, signup is not available. After accepting, sign in and accept the beta documents.
            </div>
          </div>
        </Card>
        {done && (
          <Card title="Invite accepted" icon="check">
            <div className="text-low">
              Your account is ready. Sign in to complete onboarding and legal acceptance.
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}