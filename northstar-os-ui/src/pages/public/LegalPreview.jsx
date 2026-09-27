export default function LegalPreview() {
  return (
    <div className="fade-in">
      <div style={{ maxWidth: 700, margin: '32px auto' }}>
        <div className="page-header">
          <h1 className="page-title">Legal &amp; Compliance</h1>
          <p className="page-subtitle">Review the legal framework governing NorthstarOS access.</p>
        </div>
        <div className="stack" style={{ gap: 20 }}>
          {[
            { title: 'Terms of Service', date: '2026-09-01', status: 'active' },
            { title: 'Privacy Policy', date: '2026-09-01', status: 'active' },
            { title: 'Data Processing Agreement', date: '2026-08-15', status: 'active' },
            { title: 'Beta Program Agreement', date: '2026-06-01', status: 'pending' },
          ].map((item, i) => (
            <div key={i} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0 }}>{item.title}</h3>
                <span className={`pill ${item.status === 'active' ? 'pill-ok' : 'pill-ochre'}`}>{item.status}</span>
              </div>
              <p className="text-low" style={{ fontSize: 12, marginTop: 6 }}>Last updated: {item.date}</p>
              <div style={{ marginTop: 12 }}>
                <button className="btn btn-sm">Review Document</button>
                <button className="btn btn-sm btn-ghost" style={{ marginLeft: 8 }}>Download</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}