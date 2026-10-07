import { useState } from 'react'
import { DataNotice } from './Shared.jsx'

// AdPilot — local lane. Calls the real /api/ad-pilot/* backend (ad_pilot.py).
// PLANNING ONLY: this lane returns recommendations with rationale and a basis.
// It never applies a live ad change and never spends money.

const API = '/api/ad-pilot'

function KV({ obj }) {
  if (!obj || typeof obj !== 'object') return null
  return (
    <div className="text-low" style={{ fontSize: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 12px' }}>
      {Object.entries(obj).map(([k, v]) => (
        <div key={k}><strong>{k}</strong>: {typeof v === 'object' ? JSON.stringify(v) : String(v)}</div>
      ))}
    </div>
  )
}

export default function AdPilotLane() {
  const [bid, setBid] = useState({ keyword: 'turmeric powder', current_bid: '0.75', acos: '42', target_acos: '30', clicks: '25', orders: '1', impressions: '900' })
  const [acos, setAcos] = useState({ product_cost: '8.00', amazon_price: '24.99' })
  const [rec, setRec] = useState(null)
  const [target, setTarget] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const setB = (k) => (e) => setBid({ ...bid, [k]: e.target.value })
  const setA = (k) => (e) => setAcos({ ...acos, [k]: e.target.value })

  async function post(path, body, setter) {
    setBusy(true); setErr('')
    try {
      const r = await fetch(`${API}${path}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setter(j)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="subview ns-lane">
      <DataNotice tone="internal" title="Local lane — recommendations only, no live spend">
        This lane calls the local AdPilot engine and returns bid/target recommendations
        with rationale. It does not connect to any ad account, does not change bids, and
        does not spend money. Applying changes is a separate, operator-approved action.
      </DataNotice>

      <div className="split-aside" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head"><h3 className="card-title">Bid recommendation</h3></div>
          <div className="ms-grid">
            <div><label htmlFor="ap-kw">Keyword</label><input id="ap-kw" type="text" value={bid.keyword} onChange={setB('keyword')} /></div>
            <div><label htmlFor="ap-cb">Current bid</label><input id="ap-cb" type="text" value={bid.current_bid} onChange={setB('current_bid')} /></div>
          </div>
          <div className="ms-grid-3">
            <div><label htmlFor="ap-acos">ACoS %</label><input id="ap-acos" type="text" value={bid.acos} onChange={setB('acos')} /></div>
            <div><label htmlFor="ap-ta">Target ACoS %</label><input id="ap-ta" type="text" value={bid.target_acos} onChange={setB('target_acos')} /></div>
            <div><label htmlFor="ap-ck">Clicks</label><input id="ap-ck" type="text" value={bid.clicks} onChange={setB('clicks')} /></div>
          </div>
          <div className="ms-grid-3">
            <div><label htmlFor="ap-or">Orders</label><input id="ap-or" type="text" value={bid.orders} onChange={setB('orders')} /></div>
            <div><label htmlFor="ap-im">Impressions</label><input id="ap-im" type="text" value={bid.impressions} onChange={setB('impressions')} /></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={() => post('/bid-recommendation', {
              keyword: bid.keyword, current_bid: Number(bid.current_bid) || 0,
              acos: Number(bid.acos) || 0, target_acos: Number(bid.target_acos) || 30,
              clicks: Number(bid.clicks) || 0, orders: Number(bid.orders) || 0,
              impressions: Number(bid.impressions) || 0,
            }, setRec)}>Recommend Bid</button>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3 className="card-title">Target ACoS</h3></div>
          <div className="ms-grid">
            <div><label htmlFor="ap-pc">Product cost</label><input id="ap-pc" type="text" value={acos.product_cost} onChange={setA('product_cost')} /></div>
            <div><label htmlFor="ap-pr">Amazon price</label><input id="ap-pr" type="text" value={acos.amazon_price} onChange={setA('amazon_price')} /></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={() => post('/target-acos', {
              product_cost: Number(acos.product_cost) || 0, amazon_price: Number(acos.amazon_price) || 0,
            }, setTarget)}>Compute Target ACoS</button>
          </div>
          <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>
            Break-even-aware target from real unit economics (cost, fees, desired margin).
          </div>
        </div>
      </div>

      {err && <div className="alert alert-error" style={{ marginBottom: 16 }}><div className="alert-text">{err}</div></div>}

      <div className="split-aside">
        <div className="card">
          <div className="card-head"><h3 className="card-title">Bid decision</h3></div>
          {!rec && <div className="ms-empty">Run a bid recommendation.</div>}
          {rec && (
            <>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                <span className="pill pill-muted">current {rec.current_bid}</span>
                <span className={`pill pill-${rec.action === 'increase' ? 'ok' : rec.action === 'decrease' ? 'warn' : 'muted'}`}>
                  {rec.action} → {rec.recommended_bid}
                </span>
                <span className="pill pill-muted">{rec.adjustment_pct}%</span>
                <span className="pill pill-muted">confidence {rec.confidence}</span>
                {rec.needs_approval && <span className="pill pill-ochre">needs approval</span>}
              </div>
              <label>Reasoning</label>
              <div className="card" style={{ margin: 0, padding: 10 }}>{rec.reasoning}</div>
              <label>Metrics basis</label>
              <KV obj={rec.metrics} />
              <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>{rec.notice}</div>
            </>
          )}
        </div>

        <div className="card">
          <div className="card-head"><h3 className="card-title">Target ACoS result</h3></div>
          {!target && <div className="ms-empty">Compute a target ACoS.</div>}
          {target && <KV obj={target} />}
        </div>
      </div>
    </div>
  )
}
