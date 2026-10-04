import { PageLayout } from '../../components/Shared.jsx'
import { useNavigate } from 'react-router-dom'

export default function DowngradedAccount() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Account Downgraded" subtitle="Your plan has been changed.">
      <div className="suspended-page">
        <div className="suspended-card card">
          <div className="suspended-icon"><svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--ochre)" strokeWidth="1.5"><path d="M12 2v10M8 6l4-4 4 4M4 12h16"/></svg></div>
          <div className="suspended-title">Plan Downgraded</div>
          <p className="suspended-text">Your plan has been changed. Some services may have reduced access or different entitlements.</p>
          <div className="alert-warn" style={{ marginBottom: 20 }}>
            <div className="alert-title">Plan changed by an operator</div>
            <div className="alert-text">Review your current entitlements and usage. Contact your organization operator for questions.</div>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <button className="btn btn-primary" onClick={() => navigate('/plan')}>Review Entitlements</button>
            <button className="btn btn-ghost" onClick={() => navigate('/support')}>Contact Support</button>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}