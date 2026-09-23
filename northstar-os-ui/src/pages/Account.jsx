import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function Account({ toast }) {
  const [credits, setCredits] = useState(null)
  const [status, setStatus] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const c = await api.credits()
        setCredits(c.data)
      } catch { /* gated */ }
      try {
        const s = await api.models()
        setStatus(s.data)
      } catch { /* ignore */ }
    })()
  }, [])

  return (
    <div className="page">
      <PageHead
        title="Account"
        sub="Profile, plan, and authorization posture"
        badges={[{ label: 'live', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Profile" icon="account">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <input className="field" style={{ flex: 1 }} defaultValue="T2 Holdings" aria-label="Account name" />
            <input className="field" style={{ flex: 1 }} defaultValue="tyrone@t2holdings.com" aria-label="Email" />
            <button className="btn btn-primary" onClick={() => toast('Profile saved', 'ok')}>Save</button>
          </div>
        </Card>

        <Card title="Plan & Credits" icon="star">
          {credits ? (
            <div className="metric">
              <Metric k="Plan" v={credits.plan} d={`${credits.class} class`} tone="glow" />
              <Metric k="Allotment" v={credits.allotment.toLocaleString()} d={`${credits.period}ly credits`} />
              <Metric k="Consumed" v={credits.consumed.toLocaleString()} d="this period" tone="coral" />
              <Metric k="Balance" v={(credits.balance - credits.consumed).toLocaleString()} d="remaining" tone="lime" />
            </div>
          ) : (
            <div className="text-low" style={{ fontSize: 12 }}>Credits endpoint gated or unreachable.</div>
          )}
        </Card>

        <Card title="Authorization Posture" icon="alert">
          <div className="stack">
            <div className="gate-row">
              <div>
                <div className="gate-name">Live cost data</div>
                <div className="gate-desc">Costco / Unwrangle / Amazon lookups</div>
              </div>
              <button className="status-pill off" onClick={() => toast('Live data gate closed — requires named operator approval', 'err')}>Authorization required</button>
            </div>
            <div className="gate-row">
              <div>
                <div className="gate-name">Local engine runs</div>
                <div className="gate-desc">generation / analysis via Ollama</div>
              </div>
              <button className="status-pill on" onClick={() => toast('Local engine gate open — generation live', 'ok')}>Open</button>
            </div>
            <div className="gate-row">
              <div>
                <div className="gate-name">Cloud provider</div>
                <div className="gate-desc">OpenRouter routed calls</div>
              </div>
              <button className={`status-pill ${status?.cloud?.key_present ? 'warn' : 'off'}`} onClick={() => toast(status?.cloud?.key_present ? 'Cloud key present but not armed' : 'No cloud key configured', status?.cloud?.key_present ? 'ok' : 'err')}>
                {status?.cloud?.key_present ? 'key present' : 'not configured'}
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}