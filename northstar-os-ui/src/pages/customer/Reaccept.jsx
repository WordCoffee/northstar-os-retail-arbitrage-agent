import { PageLayout } from '../../components/Shared.jsx'
import { useNavigate } from 'react-router-dom'

// Re-acceptance surface. Recording acceptance is a real write that is not
// activated in this beta; this page points to the live legal status instead.
export default function CustomerReaccept() {
  const navigate = useNavigate()
  return (
    <PageLayout title="Re-accept Terms" subtitle="Your legal terms have been updated.">
      <div className="card" style={{ maxWidth: 500 }}>
        <h2 style={{ marginBottom: 8 }}>Terms Updated</h2>
        <p className="text-mid" style={{ marginBottom: 20 }}>Your organization has new terms that require re-acceptance.</p>
        <div className="alert-warn" style={{ marginBottom: 20 }}>
          <div className="alert-title">Action Required</div>
          <div className="alert-text">Failure to re-accept within 30 days may result in access restrictions.</div>
        </div>
        <div className="check-row" style={{ marginBottom: 16 }}>
          <input type="checkbox" id="reaccept" disabled />
          <label htmlFor="reaccept">I accept the updated terms</label>
        </div>
        <button className="btn btn-primary btn-block" disabled title="Acceptance recording is not activated in this beta">Confirm Re-acceptance</button>
        <div className="inline-flex" style={{ gap: 10, marginTop: 12, justifyContent: 'center' }}>
          <button className="btn btn-sm btn-ghost" onClick={() => navigate('/legal')}>View live legal status</button>
        </div>
        <p className="text-low" style={{ fontSize: 12, marginTop: 8 }}>Re-acceptance recording is not activated in this beta; your operator records acceptance during onboarding.</p>
      </div>
    </PageLayout>
  )
}