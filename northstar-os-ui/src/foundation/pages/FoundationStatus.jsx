// Internal Foundation status page — consumes REAL foundation APIs.
// Shows only foundation data or honest empty/error states. No invented business data.
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../../ui.jsx'
import foundationApi from '../api.js'
import { useSession } from '../session.jsx'
import { ProvenanceBadge, StateMessage } from '../components/StatusPrimitives.jsx'

export default function FoundationStatus({ toast }) {
  const session = useSession()
  const [state, setState] = useState({ status: 'loading', error: null })
  const [providers, setProviders] = useState([])
  const [marketplaces, setMarketplaces] = useState([])
  const [productsTotal, setProductsTotal] = useState(null)
  const [usage, setUsage] = useState(null)
  const [approvals, setApprovals] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [candidates, setCandidates] = useState([])
  const [posture, setPosture] = useState(null)
  const [schedulePosture, setSchedulePosture] = useState(null)
  const [imports, setImports] = useState([])
  const [audit, setAudit] = useState([])
  const [envPosture, setEnvPosture] = useState(null)
  const [balance, setBalance] = useState(null)
  const [exceptions, setExceptions] = useState([])

  const load = async () => {
    setState({ status: 'loading', error: null })
    try {
      const [p, m, prod, u, a, c, cand, qp, sp, imp, au, ep, bal] = await Promise.all([
        foundationApi.providers(),
        foundationApi.marketplaces(),
        foundationApi.products(1, 0),
        foundationApi.usageSummary(),
        foundationApi.approvals(),
        foundationApi.identityConflicts(),
        foundationApi.identityCandidates(),
        foundationApi.queuePosture().catch(() => null),
        foundationApi.schedulePosture().catch(() => null),
        foundationApi.imports().catch(() => null),
        foundationApi.audit(50).catch(() => null),
        foundationApi.environment(),
        foundationApi.usageSummary(),
      ])
      setProviders(p.items || [])
      setMarketplaces(m.items || [])
      setProductsTotal(prod.total ?? 0)
      setUsage(u)
      setApprovals(a.items || [])
      setConflicts(c.items || [])
      setCandidates(cand.items || [])
      setPosture(qp)
      setSchedulePosture(sp)
      setImports(imp ? (imp.items || []) : [])
      setAudit(au ? (au.items || []) : [])
      setEnvPosture(ep)
      setBalance(bal)
      setExceptions([
        ...(Array.isArray(c) ? c : []).slice(0, 5).map((x) => ({ kind: 'identity_conflict', text: `${x.conflict_type} — ${x.detail}`, id: x.id })),
        ...(Array.isArray(cand) ? cand : []).slice(0, 5).map((x) => ({ kind: 'unresolved_candidate', text: `candidate ${x.raw_asin || x.raw_title || x.id} — ${x.reason}`, id: x.id })),
        ...(Array.isArray(a?.items) ? a.items.filter((x) => x.state === 'requested').slice(0, 5).map((x) => ({ kind: 'pending_approval', text: `${x.capability} pending approval`, id: x.id })) : []),
      ])
      setState({ status: 'ready', error: null })
    } catch (e) {
      setState({ status: 'error', error: e })
    }
  }

  useEffect(() => { load() }, [])

  if (state.status === 'loading') return <div className="page"><StateMessage state="loading" /></div>
  if (state.status === 'error') {
    return <div className="page"><StateMessage state="error"
      title="Foundation API unavailable"
      detail={`${state.error?.message || 'error'} — the foundation router may not be mounted on this backend.`}
      onRetry={load} /></div>
  }

  return (
    <div className="page">
      <PageHead
        title="Foundation"
        sub="P0 shared foundation — organizations, identity, provenance, providers, jobs, usage (shadow), audit, approvals"
        badges={[
          { label: session.environment, tone: session.environment === 'sandbox' ? 'demo' : 'live' },
          { label: `role: ${session.role || 'none'}`, tone: 'ok' },
        ]}
        right={<button className="btn" onClick={load}>Refresh</button>}
      />

      <div className="metric" style={{ marginTop: 14 }}>
        <Metric k="Providers" v={providers.length} d={`${providers.filter((p) => p.enabled).length} enabled`} />
        <Metric k="Marketplaces" v={marketplaces.length} d={marketplaces[0]?.code || '—'} tone="glow" />
        <Metric k="Canonical products" v={productsTotal === null ? '—' : productsTotal} d="in foundation DB (local)" />
        <Metric k="Shadow balance" v={usage ? usage.balance_shadow : '—'} d={usage?.label || 'shadow'} tone="lime" />
      </div>

      <div className="metric" style={{ marginTop: 8 }}>
        <Metric k="Auth posture" v={envPosture?.auth_posture || '—'} d={envPosture?.real_authentication_active ? 'JWT active' : 'local dev only'} />
        <Metric k="Environment" v={envPosture?.environment || '—'} d={`view: ${envPosture?.view_context || 'normal'}`} />
        <Metric k="Queue" v={posture ? `${posture.queued} queued` : '—'} d={posture ? `${posture.leased} leased · ${posture.running} running` : 'worker posture unavailable'} />
        <Metric k="Dead letter" v={posture?.dead_letter || '—'} d="requires review" />
        <Metric k="Schedules" v={schedulePosture ? `${schedulePosture.enabled_count}/${schedulePosture.schedule_count}` : '—'} d="enabled/total" />
        <Metric k="Imports" v={imports.length} d={imports.filter((i) => i.status === 'completed').length + ' completed'} />
      </div>

      <div className="stack" style={{ marginTop: 18 }}>
        <Card title="Operations posture" icon="gauge">
          <div className="stack">
            <div className="list-row">
              <span className="status-pill on">auth</span>
              <span style={{ flex: 1 }}>JWT-first; issuer/audience/signature/expiry validated; revoked sessions rejected; dev headers ignored outside local development</span>
            </div>
            <div className="list-row">
              <span className="status-pill on">org isolation</span>
              <span style={{ flex: 1 }}>membership + roles resolved server-side; cross-org requests denied</span>
            </div>
            <div className="list-row">
              <span className="status-pill on">execution</span>
              <span style={{ flex: 1 }}>durable worker + persisted scheduler; local/fake handlers only; no remote calls</span>
            </div>
            <div className="list-row">
              <span className="status-pill on">usage</span>
              <span style={{ flex: 1 }}>Decimal reservations + settlement; shadow ledger; no billing processors</span>
            </div>
          </div>
        </Card>

        <Card title="Exceptions & next steps" icon="audit">
          {exceptions.length === 0 ? (
            <StateMessage state="empty" title="No open exceptions" />
          ) : exceptions.map((x) => (
            <div key={`${x.kind}-${x.id}`} className="list-row">
              <span className="status-pill warn">{x.kind}</span>
              <span style={{ flex: 1 }}>{x.text}</span>
            </div>
          ))}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
            Actionable: approve pending approvals, resolve identity conflicts, review dead-letter jobs, import missing source reports.
          </div>
        </Card>

        <Card title="Recent audit activity" icon="audit">
          {audit.length === 0 ? <StateMessage state="empty" title="No audit events" /> : (
            <div className="stack">
              {audit.slice(0, 12).map((e) => (
                <div key={e.id} className="list-row">
                  <span className={`status-pill ${e.result === 'success' ? 'on' : 'warn'}`}>{e.result}</span>
                  <span style={{ flex: 1 }}>{e.action}</span>
                  <span className="mono text-low">{e.occurred_at ? e.occurred_at.slice(11, 19) : ''}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Providers" icon="gauge">
          {providers.length === 0 ? (
            <StateMessage state="empty" title="No providers registered" />
          ) : (
            <table className="table">
              <thead><tr><th>Provider</th><th>Category</th><th>Read</th><th>Write</th><th>Health</th><th>Enabled</th></tr></thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name} <span className="mono text-low" style={{ fontSize: 10.5 }}>{p.provider_key}</span></td>
                    <td>{p.category}</td>
                    <td>{p.read_capable ? 'yes' : 'no'}</td>
                    <td>{p.write_capable ? 'yes' : 'no'}</td>
                    <td><span className={`status-pill ${p.health === 'ok' ? 'on' : 'warn'}`}>{p.health}</span></td>
                    <td><span className={`status-pill ${p.enabled ? 'on' : 'off'}`}>{p.enabled ? 'enabled' : 'disabled'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Identity resolution queue" icon="prospector">
          <div className="metric">
            <Metric k="Unresolved candidates" v={candidates.length} d="pack/variation/no-ASIN" tone="coral" />
            <Metric k="Identity conflicts" v={conflicts.length} d="not silently merged" tone="coral" />
            <Metric k="Approvals pending" v={approvals.filter((a) => a.state === 'requested').length} d="require authorized approver" />
          </div>
          {(candidates.length > 0 || conflicts.length > 0) && (
            <div className="stack" style={{ marginTop: 10 }}>
              {conflicts.slice(0, 5).map((c) => (
                <div key={c.id} className="list-row">
                  <ProvenanceBadge kind="imported" />
                  <span style={{ flex: 1 }}>{c.conflict_type} — {c.detail}</span>
                </div>
              ))}
              {candidates.slice(0, 5).map((c) => (
                <div key={c.id} className="list-row">
                  <ProvenanceBadge kind="unavailable" />
                  <span style={{ flex: 1 }}>candidate {c.raw_asin || c.raw_title || c.id} — {c.reason}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Usage (shadow mode)" icon="ledger">
          {usage ? (
            <div className="metric">
              <Metric k="Consumed (shadow)" v={usage.consumed_shadow} d="no debits applied" />
              <Metric k="Adjustments (shadow)" v={usage.adjustments_shadow} d="reversals" />
              <Metric k="Balance (shadow)" v={usage.balance_shadow} d={usage.label} tone="glow" />
            </div>
          ) : <StateMessage state="empty" title="No usage recorded" />}
          <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
            Shadow mode records hypothetical credits but never debits a spendable balance (owner decision 6).
          </div>
        </Card>

        <Card title="Marketplaces" icon="star">
          <div className="stack">
            {marketplaces.map((m) => (
              <div key={m.id} className="list-row">
                <span style={{ flex: 1 }}>{m.code} · {m.country} · {m.currency}</span>
                <span className={`status-pill ${m.active ? 'on' : 'off'}`}>{m.active ? 'active' : 'inactive'}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}