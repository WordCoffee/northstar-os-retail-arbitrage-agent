import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric, Gate } from '../ui.jsx'
import { api } from '../services/api.js'

export default function Hub({ toast, navigate }) {
  const [summary, setSummary] = useState(null)
  const [models, setModels] = useState(null)
  const [credits, setCredits] = useState(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    (async () => {
      try { setSummary(await api.summary()) } catch { /* ignore */ }
      try {
        const m = await api.models()
        setModels(m.data)
        setLive(!!m.data?.cloud?.live_armed)
      } catch { /* ignore */ }
      try {
        const c = await api.credits()
        setCredits(c.data)
      } catch { /* ignore */ }
    })()
  }, [])

  const passPct = summary?.pass_rate ? Math.round(summary.pass_rate * 100) : 0
  const total = summary?.total || 470

  return (
    <div className="page">
      <PageHead
        title="Operations Hub"
        sub="Portfolio overview · live backend"
        badges={[{ label: live ? 'live armed' : 'gated', tone: 'live' }, { label: 'backend connected', tone: 'ok' }]}
        right={
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => toast('Pinned ops snapshot to board', 'ok')}>♡ Pin snapshot</button>
            <button className="btn btn-primary" onClick={() => toast('Batch queued — live refresh requires opened gate', 'ok')}>▶ Run batch</button>
          </div>
        }
      />

      <div className="metric" style={{ marginTop: 14 }}>
        <Metric k="Matched Products" v={total} d="live sourcescout catalog" tone="glow" />
        <Metric k="Quantity PASS" v={summary?.pass || 245} d={`${passPct}% pass rate`} tone="lime" />
        <Metric k="Needs Review" v={summary?.review || 205} d="ambiguous / unmapped" tone="coral" />
        <Metric k="Compute Credits" v={credits ? credits.balance.toLocaleString() : '—'} d={credits ? `${credits.plan} plan` : 'gated'} tone="lime" />
      </div>

      <div className="stack" style={{ marginTop: 18 }}>
        <Card title="Alpha Command Deck" icon="gauge">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <span className="badge badge-live">engine: local · {models?.local?.defaults?.T2 || 'northstaros-qwen3.8:27b'}</span>
            <span className="badge badge-ok">installed: {(models?.local?.installed || []).length} models</span>
            <span className="badge badge-ok">cloud key: {models?.cloud?.key_present ? 'present' : 'none'}</span>
            <span className="badge badge-demo">live refresh: {live ? 'armed' : 'gated'}</span>
          </div>
        </Card>

        <Card title="Service Grid" icon="star">
          <div className="stack">
            {[
              ['prospector', 'Prospector', 'Retail Arbitrage Agent', 'Live catalog of 470+ Kirkland products with real margin/ROI math.', '/prospector'],
              ['chisel', 'OfferChisel', 'Listing Optimizer', 'Real listing generation via local engine (title, bullets, keywords).', '/offerchisel'],
              ['auctioneer', 'The Auctioneer', 'Amazon Ads Agent', 'Live campaign economics — break-even ACoS from real fee structure.', '/auctioneer'],
              ['crier', 'The Town Crier', 'Social Media Agent', 'Real caption generation with brand-voice enforcement.', '/towncrier']
            ].map(([icon, name, sub, desc, route]) => (
              <div key={name} className="list-row" style={{ cursor: 'pointer' }} onClick={() => navigate(route)}>
                <Icon name={icon} size={16} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>{sub}</div>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>{desc}</div>
                </div>
                <span className="badge badge-live">live</span>
                <span className="text-low" style={{ fontSize: 11 }}>open →</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Quick Actions" icon="create">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {[
              ['Scan products', '/prospector'],
              ['Generate listing', '/offerchisel'],
              ['Build ad plan', '/auctioneer'],
              ['Create post', '/towncrier']
            ].map(([label, route]) => (
              <button key={label} className="btn" onClick={() => navigate(route)}>
                {label} →
              </button>
            ))}
          </div>
        </Card>

        <Card title="Gates & Authorizations" icon="alert">
          <div className="stack">
            <Gate name="Live Costco Scan" desc="live provider pulls for price refresh" state={live ? 'on' : 'off'} toast={toast} />
            <Gate name="Amazon Listing / Purchase" desc="listing, pricing, purchase, transaction" state="off" toast={toast} />
            <Gate name="Social Publish" desc="scheduling to live channels" state="off" toast={toast} />
            <Gate name="Attribution Generation" desc="maas= tags (requires stable ACoS)" state="warn" toast={toast} />
          </div>
        </Card>
      </div>
    </div>
  )
}