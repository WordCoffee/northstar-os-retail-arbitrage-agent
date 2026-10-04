import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import foundationApi from '../../foundation/api.js'
import { settle } from '../../services/signals.js'

const CATEGORIES = ['bug', 'onboarding', 'usability', 'data_quality', 'billing_test_mode', 'feature_request', 'other']
const SEVERITIES = ['blocker', 'high', 'medium', 'low']

// ═══ Real ticket queue (organization-scoped, tester view) ═══
export function TicketQueue() {
  const navigate = useNavigate()
  const [st, setSt] = useState({ phase: 'loading' })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let alive = true
    settle(foundationApi.supportTickets()).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', items: r.value.items || [] })
      else setSt({ phase: (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [reload])

  const badge = st.phase === 'loading' ? { l: 'Loading…', t: 'muted' }
    : st.phase === 'auth' ? { l: 'sign-in required', t: 'unknown' }
      : st.phase === 'error' ? { l: 'unavailable', t: 'unknown' }
        : { l: 'live · foundation', t: 'muted' }

  return (
    <div className="card" data-testid="support-queue" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Your tickets</h3>
        <span className={`pill pill-${badge.t}`}>{badge.l}</span>
      </div>
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading tickets…</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in to view your support tickets.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Ticket queue unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {st.phase === 'loaded' && (st.items.length > 0 ? (
        <DataTable columns={[
          { key: 'reference_id', label: 'Reference', render: (v, row) => v || row.id },
          { key: 'subject', label: 'Subject' },
          { key: 'category', label: 'Category', render: (v) => <span className="pill pill-muted">{v || 'UNKNOWN'}</span> },
          { key: 'severity', label: 'Severity', render: (v) => <span className={`pill ${v === 'blocker' || v === 'high' ? 'pill-error' : v === 'low' ? 'pill-muted' : 'pill-warn'}`}>{v || 'UNKNOWN'}</span> },
          { key: 'status', label: 'Status', render: (v) => <span className={`pill ${v === 'resolved' || v === 'closed' ? 'pill-muted' : 'pill-warn'}`}>{v || 'UNKNOWN'}</span> },
          { key: 'created_at', label: 'Created' },
          { key: 'open', label: '', render: (v, row) => <button className="btn btn-sm btn-ghost" onClick={() => navigate(`/support/${row.id}`)}>Open</button> },
        ]} rows={st.items} />
      ) : (
        <p data-testid="support-empty" style={{ fontSize: 13 }}>You have no support tickets yet.</p>
      ))}
      <div style={{ marginTop: 10 }}>
        <button className="btn btn-sm btn-ghost" onClick={() => setReload(n => n + 1)}>Refresh</button>
      </div>
    </div>
  )
}

// ═══ New ticket (real submit; no secrets, no attachments) ═══
function NewTicket() {
  const [form, setForm] = useState({ category: 'usability', severity: 'medium', subject: '', description: '' })
  const [state, setState] = useState({ phase: 'idle' })
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.subject.trim()) { setState({ phase: 'error', message: 'A subject is required.' }); return }
    setState({ phase: 'sending' })
    const r = await settle(foundationApi.supportSubmit(form))
    if (r.ok) setState({ phase: 'done', ref: r.value.reference_id || r.value.ticket_id })
    else setState({ phase: 'error', message: (r.error && r.error.status === 401) ? 'Sign in to submit a ticket.' : `Submit failed${r.error && r.error.code ? ` (${r.error.code})` : ''}.` })
  }

  return (
    <div className="card" data-testid="support-new" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Report an issue</h3>
        <span className="pill pill-muted">no secrets · no attachments</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 10 }}>
        Do NOT include passwords, card data, API keys, marketplace credentials, invoices, or confidential supplier documents. Attachments are not accepted in this beta.
      </p>
      <form className="stack" style={{ gap: 12 }} onSubmit={submit}>
        <div className="grid-2" style={{ gap: 12 }}>
          <label className="stack" style={{ gap: 4 }}>
            <span className="text-low" style={{ fontSize: 11 }}>Category</span>
            <select className="field" value={form.category} onChange={set('category')}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="text-low" style={{ fontSize: 11 }}>Severity</span>
            <select className="field" value={form.severity} onChange={set('severity')}>
              {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Subject</span>
          <input className="field" value={form.subject} onChange={set('subject')} placeholder="Short summary" />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Description</span>
          <textarea className="field" value={form.description} onChange={set('description')} placeholder="What happened, what you expected." rows={3} />
        </label>
        <div className="inline-flex" style={{ gap: 10, alignItems: 'center' }}>
          <button className="btn btn-primary" type="submit" disabled={state.phase === 'sending'}>{state.phase === 'sending' ? 'Submitting…' : 'Submit ticket'}</button>
          {state.phase === 'done' && <span className="pill pill-ok" data-testid="support-submitted">Submitted — reference {state.ref}</span>}
          {state.phase === 'error' && <span className="pill pill-warn">{state.message}</span>}
        </div>
      </form>
    </div>
  )
}

export default function SupportCenter() {
  return (
    <PageLayout title="Support Center" subtitle="Open tickets and help resources.">
      <DataNotice tone="internal" title="Support is organization-scoped">
        Tickets shown are your organization&apos;s own, read live from the foundation service. Support is best-effort for the beta — no guaranteed response time.
      </DataNotice>
      <TicketQueue />
      <NewTicket />
    </PageLayout>
  )
}

export function TicketDetail() {
  const { id } = useParams()
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    settle(foundationApi.supportTicket(id)).then(r => {
      if (!alive) return
      if (r.ok) setSt({ phase: 'loaded', ticket: r.value })
      else setSt({ phase: (r.error && r.error.status === 404) ? 'not_found' : (r.error && r.error.status === 401) ? 'auth' : 'error', error: r.error })
    })
    return () => { alive = false }
  }, [id])
  const t = st.phase === 'loaded' ? st.ticket : null
  return (
    <PageLayout title={`Ticket ${t && (t.reference_id || t.id) ? (t.reference_id || t.id) : '#' + (id || '')}`} subtitle="Your support ticket detail.">
      {st.phase === 'loading' && <p style={{ fontSize: 13 }}>Loading ticket…</p>}
      {st.phase === 'not_found' && <p style={{ fontSize: 13 }}>No ticket with this id for your organization — nothing is fabricated.</p>}
      {st.phase === 'auth' && <p style={{ fontSize: 13 }}>Sign in to view this ticket.</p>}
      {st.phase === 'error' && <p style={{ fontSize: 13 }}>Ticket unavailable{st.error && st.error.code ? ` (${st.error.code})` : ''}.</p>}
      {t && (
        <div className="stack" style={{ gap: 16 }}>
          <div className="evidence">
            <div className="evidence-header">
              <span className={`pill ${t.status === 'resolved' || t.status === 'closed' ? 'pill-muted' : 'pill-warn'}`}>{t.status || 'UNKNOWN'}</span>
              <span className="evidence-source">{t.reference_id || t.id}</span>
              <span className="evidence-freshness">{t.created_at || ''}</span>
            </div>
            <p className="evidence-body"><strong>{t.subject || 'UNKNOWN'}</strong>{t.category ? ` · ${t.category}` : ''}{t.severity ? ` · ${t.severity}` : ''}</p>
          </div>
          <div className="card">
            <div className="card-head"><h3 className="card-title">Description</h3></div>
            <div style={{ fontSize: 13 }}>{t.description || 'UNKNOWN'}</div>
          </div>
          {t.tester_visible_note && (
            <div className="card">
              <div className="card-head"><h3 className="card-title">Support response</h3></div>
              <div style={{ fontSize: 13 }}>{t.tester_visible_note}</div>
            </div>
          )}
        </div>
      )}
    </PageLayout>
  )
}