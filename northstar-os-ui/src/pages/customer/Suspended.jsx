import { PageLayout } from '../../components/Shared.jsx'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../../foundation/session.jsx'

// Account-blocked surface. Renders the real session suspension state/message
// (set by the backend when the org lifecycle is blocking) rather than a
// hardcoded placeholder.
export default function SuspendedAccount() {
  const navigate = useNavigate()
  const session = useSession()
  const stateLabel = session.suspensionState || 'org_lifecycle_blocked'
  const message = session.suspensionMessage
    || 'Your organization cannot use product features right now.'
  return (
    <PageLayout title="Account Suspended" subtitle="Feature access is currently blocked.">
      <div className="suspended-page">
        <div className="suspended-card card">
          <div className="suspended-icon"><svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
          <div className="suspended-title">Account Suspended</div>
          <p className="suspended-text">{message} To resolve this, contact the beta operator through the support channel.</p>
          <div className="alert-error" style={{ marginBottom: 20 }}>
            <div className="alert-title">Suspension State: {stateLabel}</div>
            <div className="alert-text">This is an administrative action. No automated reversal is available — a platform admin must resume the organization.</div>
          </div>
          <button className="btn btn-primary btn-block" onClick={() => navigate('/support')}>Contact Support</button>
        </div>
      </div>
    </PageLayout>
  )
}