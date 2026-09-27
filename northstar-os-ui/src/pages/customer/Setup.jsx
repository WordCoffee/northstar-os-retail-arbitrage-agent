import { PageLayout } from '../../components/Shared.jsx'

export default function CustomerSetup() {
  return (
    <PageLayout title="Setup & Onboarding" subtitle="Complete your workspace configuration.">
      <div style={{ maxWidth: 600 }}>
        <div className="card">
          <h3 className="card-title">Organization Profile</h3>
          <div className="field-group" style={{ marginTop: 16 }}>
            <label className="label">Organization Name</label>
            <input className="field" defaultValue="T2 Holdings LLC" />
          </div>
          <div className="field-group">
            <label className="label">Primary Contact</label>
            <input className="field" defaultValue="T2 Holdings — Operations" />
          </div>
        </div>
        <div className="card">
          <h3 className="card-title">Legal Acceptance</h3>
          <div className="stack" style={{ gap: 10, marginTop: 12 }}>
            {[
              { name: 'Terms of Service', accepted: true },
              { name: 'Privacy Policy', accepted: true },
              { name: 'Data Processing Agreement', accepted: false },
            ].map((item, i) => (
              <div key={i} className="check-row">
                <input type="checkbox" checked={item.accepted} readOnly />
                <label>{item.name}</label>
                <span className={`pill ${item.accepted ? 'pill-ok' : 'pill-ochre'}`} style={{ marginLeft: 'auto' }}>{item.accepted ? 'Accepted' : 'Pending'}</span>
              </div>
            ))}
          </div>
          <button className="btn btn-primary" style={{ marginTop: 16 }}>Complete Setup</button>
        </div>
      </div>
    </PageLayout>
  )
}