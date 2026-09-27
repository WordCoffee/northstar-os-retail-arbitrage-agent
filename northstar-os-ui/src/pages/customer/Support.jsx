import { useState } from 'react'
import { PageLayout, DataTable } from '../../components/Shared.jsx'

export default function SupportCenter() {
  const [tickets] = useState([
    { id: 'SUP-001', subject: 'Product set sync delay', status: 'open', priority: 'high', date: '2026-09-26' },
    { id: 'SUP-002', subject: 'Invoice format question', status: 'resolved', priority: 'low', date: '2026-09-24' },
    { id: 'SUP-003', subject: 'Onboarding guidance needed', status: 'pending', priority: 'medium', date: '2026-09-22' },
  ])
  return (
    <PageLayout title="Support Center" subtitle="Open tickets and help resources.">
      <DataTable columns={[
        { key: 'id', label: 'ID' },
        { key: 'subject', label: 'Subject' },
        { key: 'status', label: 'Status' },
        { key: 'priority', label: 'Priority' },
        { key: 'date', label: 'Date' },
      ]} rows={tickets} />
    </PageLayout>
  )
}

export function TicketDetail() {
  return (
    <PageLayout title="Ticket SUP-001" subtitle="Product set sync delay">
      <div className="stack" style={{ gap: 16 }}>
        <div className="evidence">
          <div className="evidence-header">
            <span className="pill pill-warn">Open</span>
            <span className="evidence-source">Created: 2026-09-26</span>
          </div>
          <p className="evidence-body">Product set synchronization is delayed by approximately 4 hours. This is consistent with known latency in the enrichment pipeline.</p>
        </div>
        <div className="card">
          <h4 style={{ marginBottom: 8 }}>Timeline</h4>
          <div className="timeline">
            <div className="timeline-item">
              <div className="timeline-dot timeline-dot-info">i</div>
              <div className="timeline-content"><div className="timeline-text">Ticket created</div><div className="timeline-date">2026-09-26 09:14</div></div>
            </div>
            <div className="timeline-item">
              <div className="timeline-dot timeline-dot-warn">!</div>
              <div className="timeline-content"><div className="timeline-text">Escalated to support</div><div className="timeline-date">2026-09-26 10:30</div></div>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}