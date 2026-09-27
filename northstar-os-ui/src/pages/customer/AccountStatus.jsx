import { PageLayout } from '../../components/Shared.jsx'

export default function AccountStatus() {
  return (
    <PageLayout title="Account Status" subtitle="Your current account condition and entitlements.">
      <div className="stack" style={{ gap: 20 }}>
        <MetricTiles metrics={[
          { label: 'Status', value: 'Active', sub: 'All services' },
          { label: 'Plan', value: 'AutothinK', sub: 'Annual' },
          { label: 'Expires', value: '2027-09-01', sub: 'Auto-renewal' },
          { label: 'Seats', value: '2', sub: 'of 5' },
        ]} />
        <div className="card">
          <h3 className="card-title">Account Details</h3>
          <DataTable columns={[
            { key: 'field', label: 'Field' },
            { key: 'value', label: 'Value' },
          ]} rows={[
            { field: 'Organization', value: 'T2 Holdings LLC' },
            { field: 'Role', value: 'Operator' },
            { field: 'Created', value: '2026-06-01' },
            { field: 'Last Login', value: '2026-09-26 09:14' },
            { field: 'UI Mode', value: 'Full' },
            { field: 'Environment', value: 'Production' },
          ]} />
        </div>
      </div>
    </PageLayout>
  )
}