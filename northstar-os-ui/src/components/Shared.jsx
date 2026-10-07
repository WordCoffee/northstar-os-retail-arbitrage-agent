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

// ═══ Shared: Empty State ═══
// First-class empty surface (the blueprint's #1 complaint: rooms must not feel
// empty or generic). Uses the existing .empty-title type scale.
export function EmptyState({ title, children, icon }) {
  return (
    <div className="empty-state">
      {icon ? <div className="empty-icon" aria-hidden="true">{icon}</div> : null}
      {title ? <div className="empty-title">{title}</div> : null}
      {children ? <div className="text-low" style={{ fontSize: 13, maxWidth: 460, margin: '0 auto' }}>{children}</div> : null}
    </div>
  )
}

// ═══ Shared: Section Header ═══
export function SectionHeader({ title, sub, right }) {
  return (
    <div className="card-head" style={{ marginBottom: 10 }}>
      <div>
        <h3 className="card-title" style={{ margin: 0 }}>{title}</h3>
        {sub ? <div className="text-low" style={{ fontSize: 12, marginTop: 2 }}>{sub}</div> : null}
      </div>
      {right ? <div>{right}</div> : null}
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