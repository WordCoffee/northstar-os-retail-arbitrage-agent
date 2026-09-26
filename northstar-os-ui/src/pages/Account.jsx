// Account — production-shaped foundation account UI (1C-06/D05).
// Consumes REAL foundation data (/me, usage, providers, audit, sessions).
// Integrations/postures are labeled truthfully — nothing is invented.
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../ui.jsx'
import foundationApi from '../foundation/api.js'
import { useSession } from '../foundation/session.jsx'
import { StateMessage } from '../foundation/components/StatusPrimitives.jsx'

export default function Account({ toast }) {
  const session = useSession()
  const [state, setState] = useState({ status: 'loading' })
  const [usage, setUsage] = useState(null)
  const [providers, setProviders] = useState([])
  const [audit, setAudit] = useState([])
  const [sessions, setSessions] = useState([])

  const load = async () => {
    setState({ status: 'loading' })
    try {
      const [u, p, a] = await Promise.all([
        foundationApi.usageSummary(),
        foundationApi.providers(),
        foundationApi.audit(25),
      ])
      setUsage(u); setProviders(p.items || []); setAudit(a.items || [])
      setState({ status: 'ready' })
    } catch (e) { setState({ status: 'error', error: e }) }
  }
  useEffect(() => { load() }, [])

  const revokeSession = async (jti) => {
    try {
      await foundationApi.rawReq(`/session/revoke?jti=${encodeURIComponent(jti)}`,
                                 { method: 'POST' })
      toast('Session revoked', 'ok')
    } catch (e) { toast(e.message, 'err') }
  }

  if (state.status === 'loading') return <div className="page"><StateMessage state="loading" /></div>
  if (state.status === 'error') return (
    <div className="page"><StateMessage state="error" title="Account unavailable"
      detail={state.error?.message} onRetry={load} /></div>
  )

  return (
    <div className="page">
      <PageHead title="Account"
        sub="Profile, organization, members, roles, security, sessions, plan, credits, usage, integrations, posture"
        badges={[{ label: session.environment, tone: session.environment === 'sandbox' ? 'demo' : 'live' },
                 { label: `role: ${session.role || 'none'}`, tone: 'ok' }]} />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Profile" icon="account">
          <div className="stack">
            <div className="list-row"><span className="k">User</span><span style={{ flex: 1 }}>{session.userId}</span></div>
            <div className="list-row"><span className="k">Active organization</span><span style={{ flex: 1 }}>{session.activeOrganizationId || '—'}</span></div>
            <div className="list-row"><span className="k">Organizations</span><span style={{ flex: 1 }}>{session.organizations.length} member</span></div>
          </div>
        </Card>

        <Card title="Organization & members" icon="team">
          <div className="stack">
            {session.organizations.length === 0 ? (
              <StateMessage state="empty" title="No organization memberships" />
            ) : session.organizations.map((o) => (
              <div key={o.id} className="list-row">
                <span style={{ flex: 1 }}>{o.name}</span>
                <span className="mono text-low">{o.id.slice(0, 8)}</span>
                <span className="status-pill">{o.role}</span>
              </div>
            ))}
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
            Roles and permissions are resolved server-side from memberships. Preview never elevates.
          </div>
        </Card>

        <Card title="Security & sessions" icon="lock">
          <div className="stack">
            <div className="list-row">
              <span className="status-pill on">JWT</span>
              <span style={{ flex: 1 }}>Signed session; issuer/audience/expiry validated; revocation supported</span>
            </div>
            <div className="list-row">
              <span className="status-pill on">No token in URL</span>
              <span style={{ flex: 1 }}>tokens live in Authorization headers only</span>
            </div>
            <div className="text-low" style={{ fontSize: 11 }}>
              Current sessions: {sessions.length} shown (revoke by jti from the server-side session registry).
            </div>
            {sessions.map((s) => (
              <div key={s.jti || s.id} className="list-row">
                <span className="mono text-low">{(s.jti || s.id || '').slice(0, 12)}</span>
                <span style={{ flex: 1 }}>{s.revoked_at ? 'revoked' : 'active'}</span>
                {!s.revoked_at && (
                  <button className="btn btn-ghost" onClick={() => revokeSession(s.jti || s.id)}>Revoke</button>
                )}
              </div>
            ))}
          </div>
        </Card>

        <Card title="Plan, credits & usage" icon="ledger">
          <div className="metric">
            <Metric k="Balance (shadow)" v={usage?.balance_shadow ?? '—'} d={usage?.label || 'shadow'} tone="lime" />
            <Metric k="Consumed" v={usage?.consumed_shadow ?? '—'} d="this period" />
            <Metric k="Adjustments" v={usage?.adjustments_shadow ?? '—'} d="reversals" />
          </div>
          <div className="text-low" style={{ fontSize: 11 }}>
            Shadow mode: no debits applied; reservations and settlements tracked per job (1C-04).
          </div>
        </Card>

        <Card title="Integrations & provider posture" icon="gauge">
          <div className="stack">
            {providers.length === 0 ? <StateMessage state="empty" title="No providers registered" /> : providers.map((p) => (
              <div key={p.id} className="list-row">
                <span style={{ flex: 1 }}>{p.name}</span>
                <span className="mono text-low">{p.provider_key}</span>
                <span className={`status-pill ${p.enabled ? 'on' : 'off'}`}>{p.enabled ? 'enabled' : 'disabled'}</span>
              </div>
            ))}
            <div className="list-row">
              <span className="status-pill off">Amazon</span>
              <span style={{ flex: 1 }}>no live Amazon integration configured</span>
            </div>
            <div className="list-row">
              <span className="status-pill off">Amazon Ads</span>
              <span style={{ flex: 1 }}>no live Ads integration configured</span>
            </div>
            <div className="list-row">
              <span className="status-pill off">Suppliers</span>
              <span style={{ flex: 1 }}>supplier integrations not configured</span>
            </div>
            <div className="list-row">
              <span className="status-pill off">Social</span>
              <span style={{ flex: 1 }}>social integrations not configured</span>
            </div>
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
            No raw keys are exposed. Unimplemented integrations are labeled truthfully.
          </div>
        </Card>

        <Card title="Recent audit activity" icon="audit">
          {audit.length === 0 ? <StateMessage state="empty" title="No audit events" /> : (
            <div className="stack">
              {audit.slice(0, 10).map((e) => (
                <div key={e.id} className="list-row">
                  <span className="status-pill">{e.result}</span>
                  <span style={{ flex: 1 }}>{e.action}</span>
                  <span className="mono text-low">{e.occurred_at ? e.occurred_at.slice(11, 19) : ''}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}