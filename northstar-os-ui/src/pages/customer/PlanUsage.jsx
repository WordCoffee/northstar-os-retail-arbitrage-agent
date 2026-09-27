import { PageLayout, MetricTiles, DataTable } from '../../components/Shared.jsx'

export default function PlanUsage() {
  return (
    <PageLayout title="Plan & Usage" subtitle="Track your usage against your entitlement.">
      <MetricTiles metrics={[
        { label: 'Plan', value: 'AutothinK', sub: 'Annual' },
        { label: 'Usage', value: '68%', sub: 'of monthly quota' },
        { label: 'Products Scanned', value: '1,247', sub: 'This period' },
        { label: 'Seats', value: '2 / 5', sub: 'Active users' },
      ]} />
      <div className="card">
        <h3 className="card-title">Usage Meter</h3>
        <div className="meter" style={{ marginTop: 12, marginBottom: 8 }}>
          <div className="meter-fill meter-fill-forest" style={{ width: '68%' }}></div>
        </div>
        <div className="text-low" style={{ fontSize: 12 }}>68% of 5,000 scan credits used. ~1,600 remaining.</div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="card-title">Billing History</h3>
        <DataTable columns={[
          { key: 'period', label: 'Period' },
          { key: 'amount', label: 'Amount' },
          { key: 'status', label: 'Status' },
        ]} rows={[
          { period: 'Sep 2026', amount: '$299.00', status: 'Paid' },
          { period: 'Aug 2026', amount: '$299.00', status: 'Paid' },
          { period: 'Jul 2026', amount: '$299.00', status: 'Paid' },
        ]} />
      </div>
    </PageLayout>
  )
}