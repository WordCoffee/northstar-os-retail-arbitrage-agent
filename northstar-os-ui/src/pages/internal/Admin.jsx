import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function InternalAdmin() {
  return (
    <PageLayout title="Internal Administration" subtitle="System configuration and operational controls.">
      <div className="stack" style={{ gap: 24 }}>
        <div className="card">
          <h3 className="card-title">System Status</h3>
          <div className="stack" style={{ gap: 8, marginTop: 12 }}>
            {[
              { label: 'Catalog Index', status: 'Healthy', color: 'pill-ok' },
              { label: 'Enrichment Pipeline', status: 'Active', color: 'pill-ok' },
              { label: 'Auth Service', status: 'Active', color: 'pill-ok' },
              { label: 'Data Warehouse', status: 'Active', color: 'pill-ok' },
              { label: 'Legacy Sync', status: 'Deprecated', color: 'pill-muted' },
            ].map((item, i) => (
              <div key={i} className="list-row">
                <span style={{ flex: 1, fontSize: 13 }}>{item.label}</span>
                <span className={item.color}>{item.status}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3 className="card-title">Configuration</h3>
          <DataTable columns={[
            { key: 'setting', label: 'Setting' },
            { key: 'value', label: 'Value' },
          ]} rows={[
            { setting: 'UI Mode', value: 'Full' },
            { setting: 'Environment', value: 'Production' },
            { setting: 'Data Provider', value: 'Local (sample)' },
            { setting: 'Live Calls', value: 'Disabled' },
          ]} />
        </div>
      </div>
    </PageLayout>
  )
}