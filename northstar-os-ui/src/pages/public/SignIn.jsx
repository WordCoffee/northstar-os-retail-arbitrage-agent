import { useState } from 'react'

export default function SignIn() {
  const [form, setForm] = useState({ identifier: '', password: '' })
  return (
    <div className="fade-in">
      <div style={{ maxWidth: 420, margin: '60px auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.5" style={{ margin: '0 auto 12px' }}><path d="M12 2L3 7 12 12 21 7 21 17 12 22 3 17"/></svg>
          <h2>Sign In</h2>
          <p className="text-mid" style={{ fontSize: 13 }}>Enter your credentials to access NorthstarOS.</p>
        </div>
        <div className="card">
          <div className="stack" style={{ gap: 16 }}>
            <div className="field-group">
              <label className="label">Email or Organization ID</label>
              <input className="field" type="email" placeholder="you@org.com" value={form.identifier} onChange={e => setForm({...form, identifier: e.target.value})} />
            </div>
            <div className="field-group">
              <label className="label">Password</label>
              <input className="field" type="password" placeholder="Enter password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} />
            </div>
            <button className="btn btn-primary btn-block">Sign In</button>
            <div style={{ textAlign: 'center', fontSize: 13 }}>
              <a href="/recovery">Forgot password?</a> &nbsp;·&nbsp; <a href="/legal">Need help?</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}