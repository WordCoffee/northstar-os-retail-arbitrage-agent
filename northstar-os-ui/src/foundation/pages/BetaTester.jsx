// Private Beta — tester / organization owner experience.
// Onboarding, plan & usage, seat usage, legal acceptance, account status, and
// support. Wire-only to the Phase 1C API; never duplicates backend logic.
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../../ui.jsx'
import foundationApi from '../api.js'
import { useSession, hasPerm } from '../session.jsx'
import { StateMessage } from '../components/StatusPrimitives.jsx'

const LIFECYCLE_PLAIN = {
  invited: 'Your organization is invited but not yet active.',
  onboarding: 'Your organization is being onboarded — complete the checklist to continue.',
  active: 'Your organization is active.',
  paused: 'Your organization is paused. Contact support to resume.',
  suspended: 'Your organization is suspended. Feature use is blocked. Contact support to resolve this.',
  downgraded: 'Your plan was downgraded. Gated features are limited until a plan is assigned.',
  cancelled: 'Your access has been cancelled. Contact support if this is unexpected.',
  archived: 'Your organization has been archived.',
}

export default function BetaTester({ toast }) {
  const session = useSession()
  const [state, setState] = useState({ status: 'loading' })
  const [onboarding, setOnboarding] = useState(null)
  const [plan, setPlan] = useState(null)
  const [accept, setAccept] = useState(null)
  const [tickets, setTickets] = useState([])
  const [ticketForm, setTicketForm] = useState({ category: 'other', severity: 'low', subject: '', description: '' })
  const [accepting, setAccepting] = useState(false)
  const [selected, setSelected] = useState(null)

  const load = async () => {
    setState({ status: 'loading' })
    try {
      const [o, p, a, t] = await Promise.all([
        foundationApi.onboardingStatus().catch(() => null),
        foundationApi.planUsage().catch(() => null),
        foundationApi.legalAcceptanceStatus().catch(() => null),
        foundationApi.supportTickets().catch(() => null),
      ])
      setOnboarding(o); setPlan(p); setAccept(a); setTickets(t?.items || [])
      setState({ status: 'ready' })
    } catch (e) {
      setState({ status: 'error', error: e })
    }
  }
  useEffect(() => { load() }, [])

  const acceptDocs = async () => {
    setAccepting(true)
    try {
      await foundationApi.legalAccept({ business_use: true, age_18_plus: true })
      toast('Legal documents accepted', 'ok'); load()
    } catch (e) { toast(e.message, 'err') }
    finally { setAccepting(false) }
  }

  const completeStep = async (step) => {
    try { await foundationApi.onboardingComplete(step); toast('Step completed', 'ok'); load() }
    catch (e) { toast(e.message, 'err') }
  }

  const submitTicket = async () => {
    try {
      const r = await foundationApi.supportSubmit(ticketForm)
      toast(`Ticket ${r.reference_id} submitted`, 'ok')
      setTicketForm({ category: 'other', severity: 'low', subject: '', description: '' })
      load()
    } catch (e) { toast(e.message, 'err') }
  }

  const openTicket = async (id) => {
    try { setSelected(await foundationApi.supportTicket(id)) }
    catch (e) { toast(e.message, 'err') }
  }

  if (state.status === 'loading') return <div className="page"><StateMessage state="loading" /></div>
  if (state.status === 'error') return (
    <div className="page"><StateMessage state="error" title="Beta unavailable"
      detail={state.error?.message} onRetry={load} /></div>
  )

  const lifecycle = plan?.lifecycle_state || 'unknown'
  const usage = plan?.usage
  const used = usage?.monthly_jobs_used || 0
  const max = usage?.max_jobs_per_month || 0
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0
  const seatsUsed = plan?.seats?.used || 0
  const seatLimit = plan?.seats?.limit || 0

  return (
    <div className="page">
      <PageHead title="Private Beta"
        sub="Invite-only beta — onboarding, plan, usage, and support"
        badges={[{ label: lifecycle, tone: lifecycle === 'active' ? 'on' : 'warn' }]}
        right={<button className="btn" onClick={load}>Refresh</button>} />

      {lifecycle !== 'active' && lifecycle !== 'onboarding' && (
        <div className="stack" style={{ marginTop: 14 }}>
          <Card title="Account status" icon="lock">
            <div className="list-row">
              <span className={`status-pill ${lifecycle === 'active' ? 'on' : 'warn'}`}>{lifecycle}</span>
              <span style={{ flex: 1 }}>{LIFECYCLE_PLAIN[lifecycle] || 'Status unavailable.'}</span>
            </div>
            {(lifecycle === 'suspended' || lifecycle === 'paused') && (
              <div className="text-low" style={{ fontSize: 12 }}>
                To resolve this, submit a support ticket below or contact the beta operator.
              </div>
            )}
          </Card>
        </div>
      )}

      <div className="stack" style={{ marginTop: 14 }}>
        {accept && !accept.accepted && (
          <Card title="Required documents" icon="audit">
            <div className="stack">
              <div className="text-low">
                You must accept the current beta documents before using product features.
                Your business-use and 18+ attestations are required.
              </div>
              <button className="btn btn-primary" disabled={accepting} onClick={acceptDocs}>
                {accepting ? 'Accepting…' : 'Accept documents & attestations'}
              </button>
            </div>
          </Card>
        )}

        {onboarding && !onboarding.completed && (
          <Card title="Onboarding checklist" icon="check">
            <div className="stack">
              {Object.entries(onboarding.checklist || {}).map(([step, done]) => (
                <div key={step} className="list-row">
                  <span className={`status-pill ${done ? 'on' : 'off'}`}>{done ? 'done' : 'todo'}</span>
                  <span style={{ flex: 1 }}>{step.replace(/_/g, ' ')}</span>
                  {!done && <button className="btn btn-ghost" onClick={() => completeStep(step)}>Mark done</button>}
                </div>
              ))}
              {Object.values(onboarding.checklist || {}).every(Boolean) &&
                <button className="btn btn-primary" onClick={() => completeStep()}>Complete onboarding</button>}
            </div>
          </Card>
        )}

        <Card title="Plan & usage" icon="ledger">
          <div className="metric">
            <Metric k="Plan / cohort" v={plan?.plan?.tier || '—'} d={`support: ${plan?.plan?.support_level || 'none'}`} />
            <Metric k="Jobs used" v={`${used} / ${max}`} d={`${pct}% of monthly allowance`} tone={pct >= 80 ? 'warn' : 'ok'} />
            <Metric k="Seats" v={`${seatsUsed} / ${seatLimit}`} d="members in use" />
            <Metric k="Reset" v={plan?.reset_rule || '—'} d="period boundary" />
          </div>
          <div className="meter" style={{ marginTop: 8 }}>
            <div style={{ width: `${pct}%` }} className="meter-fill" />
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
            Entitlements: export {plan?.entitlements?.export_enabled ? 'enabled' : 'disabled'} ·
            advanced reports {plan?.entitlements?.advanced_reports ? 'enabled' : 'disabled'} ·
            override {plan?.plan?.override_allowed ? 'allowed' : 'not allowed'}
          </div>
        </Card>

        <Card title="Support" icon="help">
          <div className="stack">
            <div className="field-row">
              <select className="field" style={{ flex: 1 }} value={ticketForm.category}
                      onChange={(e) => setTicketForm({ ...ticketForm, category: e.target.value })}>
                <option value="bug">Bug</option><option value="onboarding">Onboarding</option>
                <option value="usability">Usability</option><option value="data_quality">Data quality</option>
                <option value="billing_test_mode">Billing / test mode</option>
                <option value="feature_request">Feature request</option><option value="other">Other</option>
              </select>
              <select className="field" value={ticketForm.severity}
                      onChange={(e) => setTicketForm({ ...ticketForm, severity: e.target.value })}>
                <option value="blocker">Blocker</option><option value="high">High</option>
                <option value="medium">Medium</option><option value="low">Low</option>
              </select>
            </div>
            <input className="field" placeholder="Subject" value={ticketForm.subject}
                   onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })} />
            <textarea className="field" rows={3} placeholder="Description"
                      value={ticketForm.description}
                      onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })} />
            <div className="text-low" style={{ fontSize: 11 }}>
              Do NOT submit passwords, card data, API keys, marketplace credentials, invoices, or confidential supplier documents. Attachments are not accepted.
            </div>
            <button className="btn btn-primary" onClick={submitTicket}>Submit ticket</button>
          </div>
          {tickets.length > 0 && (
            <table className="table" style={{ marginTop: 10 }}>
              <thead><tr><th>Ref</th><th>Category</th><th>Severity</th><th>Status</th><th>Reply</th></tr></thead>
              <tbody>
                {tickets.map((t) => (
                  <tr key={t.id} onClick={() => openTicket(t.id)} style={{ cursor: 'pointer' }}>
                    <td>{t.reference_id}</td>
                    <td>{t.category}</td>
                    <td>{t.severity}</td>
                    <td><span className={`status-pill`}>{t.status}</span></td>
                    <td>{t.tester_visible_note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {selected && (
          <Card title={`Ticket ${selected.reference_id}`} icon="help">
            <div className="stack">
              <div className="text-low">{selected.description}</div>
              <div className="list-row">
                <span className="k">Status</span><span style={{ flex: 1 }}>{selected.status}</span>
              </div>
              <div className="list-row">
                <span className="k">Reply</span>
                <span style={{ flex: 1 }}>{selected.tester_visible_note || 'No reply yet.'}</span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}