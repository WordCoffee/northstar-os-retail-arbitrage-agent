// Organization selector + role/environment dev context (foundation, dev-only).
import { useSession } from '../session.jsx'

const ROLES = ['organization_owner', 'organization_admin', 'operator', 'analyst', 'viewer']

export default function OrgSelector() {
  const { organizations, activeOrganizationId, dev, updateDev } = useSession()
  const orgs = organizations || []
  return (
    <div className="fs-org-selector">
      {orgs.length > 1 ? (
        <select aria-label="Active organization"
                value={activeOrganizationId || ''}
                onChange={(e) => updateDev({ orgId: e.target.value })}>
          {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      ) : (
        <span className="fs-muted">{orgs[0]?.name || 'no organization'}</span>
      )}
      <select aria-label="Dev role" value={dev.role || ''}
              onChange={(e) => updateDev({ role: e.target.value })}>
        <option value="">role…</option>
        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <select aria-label="Dev environment" value={dev.env || 'production'}
              onChange={(e) => updateDev({ env: e.target.value })}>
        <option value="production">production</option>
        <option value="sandbox">sandbox</option>
      </select>
    </div>
  )
}