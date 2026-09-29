import { PageLayout } from '../../components/Shared.jsx'

export default function CustomerReaccept() {
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
          <input type="checkbox" id="reaccept" />
          <label htmlFor="reaccept">I accept the updated terms</label>
        </div>
        <button className="btn btn-primary btn-block">Confirm Re-acceptance</button>
      </div>
    </PageLayout>
  )
}