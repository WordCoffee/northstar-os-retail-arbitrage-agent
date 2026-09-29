import { PageLayout } from '../../components/Shared.jsx'

export default function SuspendedAccount() {
  return (
    <PageLayout title="Account Suspended" subtitle="Feature access is currently blocked.">
      <div className="suspended-page">
        <div className="suspended-card card">
          <div className="suspended-icon"><svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></div>
          <div className="suspended-title">Account Suspended</div>
          <p className="suspended-text">Your organization cannot use product features right now. To resolve this, contact the beta operator through the support channel provided during onboarding.</p>
          <div className="alert-error" style={{ marginBottom: 20 }}>
            <div className="alert-title">Suspension State: org_lifecycle_blocked</div>
            <div className="alert-text">This is an administrative action. No automated reversal is available.</div>
          </div>
          <button className="btn btn-primary btn-block">Contact Support</button>
        </div>
      </div>
    </PageLayout>
  )
}