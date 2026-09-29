import { PageLayout } from '../../components/Shared.jsx'

export default function CustomerLegal() {
  return (
    <PageLayout title="Legal Acceptance" subtitle="Review and accept the legal terms.">
      <div style={{ maxWidth: 600 }}>
        <div className="stack" style={{ gap: 16 }}>
          {[
            { name: 'Terms of Service', accepted: true },
            { name: 'Privacy Policy', accepted: true },
            { name: 'Data Processing Agreement', accepted: false },
          ].map((item, i) => (
            <div key={i} className="card">
              <div className="check-row">
                <input type="checkbox" checked={item.accepted} readOnly />
                <label>{item.name}</label>
              </div>
              <p className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
                {item.accepted ? 'Accepted' : 'Pending acceptance'}
              </p>
            </div>
          ))}
          <button className="btn btn-primary">Accept All</button>
        </div>
      </div>
    </PageLayout>
  )
}