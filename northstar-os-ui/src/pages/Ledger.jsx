import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function Ledger({ toast }) {
  const [credits, setCredits] = useState(null)
  const [status, setStatus] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    (async () => {
      try {
        const c = await api.credits()
        setCredits(c.data)
      } catch { /* auth-gated */ }
      try {
        const s = await api.models()
        setStatus(s.data)
      } catch { /* ignore */ }
    })()
  }, [])

  const used = credits ? credits.balance - credits.consumed : 0

  return (
    <div className="page">
      <PageHead
        title="The Ledger"
        sub="Financial tracking — credits, compute spend, and plan posture"
        badges={[{ label: 'live', tone: 'live' }]}
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Compute Credits" icon="ledger">
          {credits ? (
            <div className="metric">
              <Metric k="Balance" v={credits.balance.toLocaleString()} d={`${credits.class} credits`} tone="glow" />
              <Metric k="Consumed" v={credits.consumed.toLocaleString()} d="this period" tone="coral" />
              <Metric k="Available" v={used.toLocaleString()} d={`${credits.period}ly · ${credits.plan} plan`} tone="lime" />
            </div>
          ) : (
            <div className="text-low" style={{ fontSize: 12 }}>Credits endpoint gated or unreachable.</div>
          )}
        </Card>

        <Card title="Engine Posture" icon="gauge">
          {status ? (
            <div className="metric">
              <Metric k="Provider" v="local" d="Ollama default" tone="lime" />
              <Metric k="T2 Model" v={status.local?.defaults?.T2 || 'northstar-qwen3:rev1'} d="reasoning" />
              <Metric k="Cloud Key" v={status.cloud?.key_present ? 'present' : 'none'} d={status.cloud?.live_armed ? 'armed' : 'not armed'} />
            </div>
          ) : (
            <div className="text-low" style={{ fontSize: 12 }}>Engine posture unavailable.</div>
          )}
        </Card>
      </div>
    </div>
  )
}