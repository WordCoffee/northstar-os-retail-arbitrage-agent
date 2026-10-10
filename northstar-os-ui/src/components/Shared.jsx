import { useLocation } from 'react-router-dom'
import { readinessForRoute } from '../data/readiness.js'

// ═══ Shared: Evidence Packet Component ═══
export function EvidencePacket({ title, source, freshness, status, children }) {
  return (
    <div className="evidence" style={{ marginBottom: 16 }}>
      <div className="evidence-header">
        <span className="evidence-source">{source}</span>
        <span className="evidence-freshness">{freshness}</span>
        <span className={`pill ${status === 'verified' ? 'pill-ok' : status === 'assumed' ? 'pill-ochre' : status === 'unknown' ? 'pill-unknown' : status === 'contradicted' ? 'pill-error' : 'pill-muted'}`}>
          {status}
        </span>
      </div>
      {title && <h4 style={{ marginBottom: 6 }}>{title}</h4>}
      <div className="evidence-body">{children}</div>
    </div>
  )
}

// ═══ Shared: Data Table Component ═══
export function DataTable({ columns, rows, emptyText = 'No records found' }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={columns.length} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-soft)' }}>{emptyText}</td></tr>
          ) : (
            rows.map((row, i) => (
              <tr key={i}>
                {columns.map(col => (
                  <td key={col.key}>
                    {col.render ? col.render(row[col.key], row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

// ═══ Shared: Metric Tiles Component ═══
// Own grid, no nested grid wrappers at call sites.
export function MetricTiles({ metrics, columns = 4 }) {
  return (
    <div className={`metric-tiles metric-tiles-${columns}`} style={{ marginBottom: 20 }}>
      {metrics.map((m, i) => (
        <div key={i} className="card" style={{ padding: 16 }}>
          <div className="text-low" style={{ fontSize: 11, letterSpacing: 0.04, marginBottom: 4 }}>{m.label}</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: m.tone === 'warn' ? 'var(--ochre)' : m.tone === 'error' ? 'var(--clay)' : 'var(--pine-deep)' }}>{m.value}</div>
          {m.sub && <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>{m.sub}</div>}
        </div>
      ))}
    </div>
  )
}

// ═══ Shared: Empty state with an explicit populate action ═══
// Rule (owner directive 2026-10-09): no seeded/demo/fixture rows anywhere. A
// surface with nothing behind it shows this instead of invented records, and
// the ONLY way to fill it is a deliberate Run action. `action` is the real
// backend the operator triggers; when it is not wired the connect hint is what
// shows, never a fabricated row.
export function EmptyState({ title, what, action, actionLabel, onAction, connect, children }) {
  return (
    <div className="card" data-testid="empty-state" style={{ padding: '28px 20px', textAlign: 'center' }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--pine-deep)', marginBottom: 6 }}>{title}</div>
      <div className="text-low" style={{ fontSize: 12, maxWidth: 520, margin: '0 auto 14px' }}>{what}</div>
      {action && onAction ? (
        <button className="btn btn-sm btn-primary" onClick={onAction} style={{ marginRight: 8 }}>{actionLabel || `Run ${action}`}</button>
      ) : null}
      {connect ? (
        <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>
          Not connected: add key in <strong>Settings › Integrations</strong>
          {children ? <div style={{ marginTop: 6 }}>{children}</div> : null}
        </div>
      ) : children ? <div style={{ marginTop: 10 }}>{children}</div> : null}
    </div>
  )
}

// ═══ Shared: Truth / Sample-Data Notice ═══
// Standardized room-level data truth banner. tone ∈ sample|concept|internal|assumption|unknown
export function DataNotice({ tone = 'sample', title, children }) {
  const meta = {
    sample: { label: 'SAMPLE DATA', className: 'alert-warn', pill: 'pill-warn' },
    cached: { label: 'CACHED SNAPSHOT', className: 'alert', pill: 'pill-forest' },
    concept: { label: 'CONCEPT', className: 'alert', pill: 'pill-muted' },
    internal: { label: 'INTERNAL USE ONLY', className: 'alert', pill: 'pill-muted' },
    assumption: { label: 'ASSUMPTION', className: 'alert-warn', pill: 'pill-ochre' },
    unknown: { label: 'UNKNOWN', className: 'alert', pill: 'pill-unknown' },
  }[tone] || { label: 'SAMPLE DATA', className: 'alert-warn', pill: 'pill-warn' }
  return (
    <div className={meta.className} style={{ marginBottom: 16 }}>
      <div className="alert-title"><span className={`pill ${meta.pill}`}>{meta.label}</span> {title}</div>
      <div className="alert-text">{children}</div>
    </div>
  )
}

// ═══ Shared: Authorization Boundary Note ═══
// Non-activating: explains why a write surface is disabled and what enabling it
// would require (route / permission / audit). Display only — performs no write.
export function AuthorizationNote({ title = 'Authorization boundary', status = 'Disabled — owner approval required', route, permission, audit, children }) {
  return (
    <div className="alert" data-testid="authz-note" style={{ marginBottom: 16 }}>
      <div className="alert-title"><span className="pill pill-ochre">{status}</span> {title}</div>
      <div className="alert-text">
        {children}
        {(route || permission || audit) && (
          <div className="inline-flex" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            {route && <span className="pill pill-muted" title="Backend route that would perform this write">{route}</span>}
            {permission && <span className="pill pill-muted" title="Required permission scope">{permission}</span>}
            {audit && <span className="pill pill-muted" title="Audit event recorded on execution">{audit}</span>}
          </div>
        )}
      </div>
    </div>
  )
}

// ═══ Shared: Section Layout Component ═══
export function PageLayout({ title, subtitle, actions, children }) {
  const { pathname } = useLocation()
  const readiness = readinessForRoute(pathname)
  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-title-row">
          <h1 className="page-title">{title}</h1>
          {readiness && (
            <span className={`pill pill-${readiness.tone}`} title={readiness.title}>
              {readiness.label}
            </span>
          )}
        </div>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
        {actions && <div className="page-meta">{actions}</div>}
      </div>
      {children}
    </div>
  )
}