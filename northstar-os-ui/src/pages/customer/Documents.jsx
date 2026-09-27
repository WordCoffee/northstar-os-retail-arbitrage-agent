import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function DocumentsLib() {
  return (
    <PageLayout title="Documents" subtitle="Your contract, legal, and operational records.">
      <DataTable columns={[
        { key: 'name', label: 'Document' },
        { key: 'type', label: 'Type' },
        { key: 'date', label: 'Date' },
        { key: 'status', label: 'Status' },
      ]} rows={[
        { name: 'Service Agreement', type: 'Contract', date: '2026-09-01', status: 'Active' },
        { name: 'Privacy Policy', type: 'Legal', date: '2026-09-01', status: 'Active' },
        { name: 'DPA v2.1', type: 'Compliance', date: '2026-08-15', status: 'Active' },
        { name: 'Beta Addendum', type: 'Agreement', date: '2026-06-01', status: 'Pending' },
      ]} />
    </PageLayout>
  )
}