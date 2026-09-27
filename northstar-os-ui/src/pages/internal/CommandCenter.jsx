import { PageLayout, MetricTiles, DataTable } from '../../components/Shared.jsx'
import { useState } from 'react'

export default function CommandCenter() {
  const [tasks] = useState([
    { id: 'T-01', title: 'Review SourceScout B08L5VJQ7T', type: 'decision', urgency: 'high' },
    { id: 'T-02', title: 'Approve Commerce Ops handoff #4471', type: 'approval', urgency: 'high' },
    { id: 'T-03', title: 'Investigate GG-001 opportunity', type: 'research', urgency: 'medium' },
    { id: 'T-04', title: 'Verify invoice for Lot #8823', type: 'sourcing', urgency: 'medium' },
    { id: 'T-05', title: 'Review Q3 profitability report', type: 'report', urgency: 'low' },
  ])

  const exceptions = [
    { id: 'EX-01', title: 'Org #0838 lifecycle blocked', severity: 'error' },
    { id: 'EX-02', title: 'Invite INV-2026-09-25-0192 expired', severity: 'warn' },
  ]

  const portfolio = [
    { set: 'Set A', asins: 12, margin: '~18%', status: 'Active' },
    { set: 'Set B', asins: 8, margin: 'UNKNOWN', status: 'Research' },
    { set: 'Set C', asins: 15, margin: '~22%', status: 'Approved' },
  ]

  return (
    <PageLayout
      title="Command Center"
      subtitle="Operator briefing — urgent decisions, research queue, exceptions, and cross-suite activity."
      actions={<><button className="btn btn-sm">New Scan</button><button className="btn btn-sm btn-ghost">Briefing Settings</button></>}
    >
      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div className="card" style={{ padding: 14 }}>
          <div className="text-low" style={{ fontSize: 11 }}>Urgent Decisions</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>2</div>
          <div className="text-low" style={{ fontSize: 11 }}>Require review</div>
          <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample task list, not live data">Basis: sample task list</div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <div className="text-low" style={{ fontSize: 11 }}>Research Queue</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>5</div>
          <div className="text-low" style={{ fontSize: 11 }}>Active tasks</div>
          <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample queue, not live data">Basis: sample queue</div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <div className="text-low" style={{ fontSize: 11 }}>Exceptions</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--clay)' }}>2</div>
          <div className="text-low" style={{ fontSize: 11 }}>Require attention</div>
          <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample exception feed, not live monitoring">Basis: sample exception feed</div>
        </div>
        <div className="card" style={{ padding: 14 }}>
          <div className="text-low" style={{ fontSize: 11 }}>Portfolio Exposure</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--pine-deep)' }}>3</div>
          <div className="text-low" style={{ fontSize: 11 }}>Active sets</div>
          <div className="text-low" style={{ fontSize: 10, marginTop: 2 }} title="Count derived from the sample portfolio, not live records">Basis: sample portfolio</div>
        </div>
      </div>

      <div className="alert alert-error" style={{ marginBottom: 24 }}>
        <div className="alert-title">2 Exceptions Require Immediate Attention</div>
        <div className="alert-text">Organization #0838 lifecycle blocked (suspended). Invite INV-2026-09-25-0192 expired.</div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Urgent Decisions</h3>
            <span className="pill pill-clay">2 items</span>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            {tasks.filter(t => t.urgency === 'high').map(t => (
              <div className="list-row" key={t.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.title}</div>
                  <span className={`pill ${t.type === 'decision' ? 'pill-warn' : 'pill-forest'}`}>{t.type}</span>
                </div>
                <span className="pill pill-error">Urgent</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Research Queue</h3>
            <span className="pill pill-forest">{tasks.length} tasks</span>
          </div>
          <DataTable columns={[
            { key: 'id', label: 'ID' },
            { key: 'title', label: 'Task' },
            { key: 'type', label: 'Type' },
            { key: 'urgency', label: 'Priority' },
          ]} rows={tasks} />
        </div>
      </div>

      <div className="stack" style={{ gap: 20, marginTop: 20 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Portfolio Exposure</h3>
            <span className="pill pill-forest">3 sets</span>
          </div>
          <DataTable columns={[
            { key: 'set', label: 'Set' },
            { key: 'asins', label: 'ASINs' },
            { key: 'margin', label: 'Margin', render: (v) => v === 'UNKNOWN'
              ? <span className="pill pill-unknown">UNKNOWN</span>
              : <span className="pill pill-muted" title="Estimated value — not a verified calculation">{v}</span> },
            { key: 'status', label: 'Status', render: (v) => v === 'Research'
              ? <span className="pill pill-warn">{v}</span>
              : v === 'Approved'
                ? <span className="pill pill-muted" title="Internal review state — not an authorization to purchase">{v}</span>
                : <span className="pill pill-forest">{v}</span> },
          ]} rows={portfolio} />
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">What Changed</h3>
          </div>
          <div className="timeline" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {[
              { date: '2026-09-26', text: 'Set #47: 2 new ASINs added to research queue', status: 'ok', basis: 'cached' },
              { date: '2026-09-25', text: 'Organization #0838 lifecycle blocked — review required', status: 'error', basis: 'observed' },
              { date: '2026-09-25', text: 'Invite INV-2026-09-25-0192 expired', status: 'warn', basis: 'observed' },
              { date: '2026-09-24', text: 'Golden Goose opportunity GG-001 surfaced', status: 'info', basis: 'cached' },
            ].map((item, i) => (
              <div key={i} className="timeline-item" style={{ display: 'flex', gap: 12, padding: '8px 0', position: 'relative' }}>
                <div style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, background: item.status === 'error' ? 'rgba(160,64,32,0.12)' : item.status === 'warn' ? 'rgba(184,134,11,0.12)' : item.status === 'info' ? 'rgba(29,90,29,0.12)' : 'rgba(45,106,45,0.12)', color: item.status === 'error' ? '#a04020' : item.status === 'warn' ? '#b8860b' : item.status === 'info' ? '#1d5a1d' : '#2d6a2d' }}>
                  {item.status === 'error' ? '!' : item.status === 'warn' ? '!' : '·'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--ink)' }}>{item.text}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: 'var(--ink-soft)', fontFamily: 'var(--font-mono)' }}>{item.date}</span>
                    <span className="pill pill-muted" style={{ fontSize: 10 }} title={item.basis === 'cached' ? 'Derived from cached sample data' : 'Directly observed lifecycle event (sample data)'}>{item.basis}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}
