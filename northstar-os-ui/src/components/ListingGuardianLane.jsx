import { useState } from 'react'
import { DataNotice, EmptyState } from './Shared.jsx'

// Listing Guardian — local listing-health audit. Audits operator-supplied listing
// text against Amazon-style best practices + compliance using the local engine.
// No live Amazon observation: it never claims to see live listing state.

const API = '/api/listing-guardian'

export default function ListingGuardianLane() {
  const [f, setF] = useState({
    title: 'Mogra Organics Organic Turmeric Powder 5 lb | Golden & Earthy',
    brand: 'Mogra Organics',
    bullets: 'Premium organic turmeric powder from single-origin farms\nEarthy golden flavor for curries, soups and smoothies\nResealable 5 lb pouch keeps it fresh\nNo fillers or additives',
    description: 'Mogra Organics Organic Turmeric Powder is a golden, earthy spice for daily cooking.',
    keywords: 'organic turmeric powder, golden spice',
  })
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function run() {
    setBusy(true); setErr(''); setRes(null)
    try {
      const body = {
        listing: {
          product: { brand: f.brand },
          title: f.title,
          bullets: f.bullets.split('\n').map((s) => s.trim()).filter(Boolean),
          description: f.description,
          keywords: f.keywords.split(',').map((s) => s.trim()).filter(Boolean),
        },
      }
      const r = await fetch(`${API}/audit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setRes(j)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const tone = res?.status === 'healthy' ? 'ok' : res?.status === 'attention' ? 'ochre' : 'error'

  return (
    <div className="subview ns-lane fade-in">
      <DataNotice tone="internal" title="Local audit — no live Amazon observation">
        This audits the listing text you paste against Amazon-style best practices and
        compliance rules using the local engine. It does not read live Amazon state;
        treat results as a pre-flight check, not a live listing-health measurement.
      </DataNotice>

      <div className="split-aside-l">
        <div className="card">
          <div className="card-head"><h3 className="card-title">Listing text</h3></div>
          <label htmlFor="lg-title">Title</label>
          <input id="lg-title" type="text" value={f.title} onChange={set('title')} />
          <label htmlFor="lg-brand">Brand</label>
          <input id="lg-brand" type="text" value={f.brand} onChange={set('brand')} />
          <label htmlFor="lg-bullets">Bullets (one per line)</label>
          <textarea id="lg-bullets" value={f.bullets} onChange={set('bullets')} style={{ minHeight: 110 }} />
          <label htmlFor="lg-desc">Description</label>
          <textarea id="lg-desc" value={f.description} onChange={set('description')} />
          <label htmlFor="lg-kw">Keywords (comma separated)</label>
          <input id="lg-kw" type="text" value={f.keywords} onChange={set('keywords')} />
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={run}>
              {busy ? 'Auditing…' : 'Audit Listing'}
            </button>
          </div>
          {err && <div className="alert alert-error" style={{ marginTop: 12 }}><div className="alert-text">{err}</div></div>}
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Audit result</h3>
            {res && <span className={`pill pill-${tone}`}>{res.status} · {res.passed}/{res.total}</span>}
          </div>
          {!res && <EmptyState icon="🛡" title="No audit yet">Paste a listing and run the audit.</EmptyState>}
          {res && (
            <>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                <span className="pill pill-muted">score {res.score?.composite}</span>
                <span className="pill pill-muted">weighted {res.weighted_ratio}</span>
                <span className={`pill ${res.compliance?.ok ? 'pill-ok' : 'pill-error'}`}>
                  compliance {res.compliance?.ok ? 'clear' : `${res.compliance?.violations?.length} issue(s)`}
                </span>
              </div>
              <table className="table">
                <thead><tr><th>Check</th><th>Result</th><th>Detail</th></tr></thead>
                <tbody>
                  {res.checks.map((c) => (
                    <tr key={c.check}>
                      <td className="mono-cell">{c.check}</td>
                      <td><span className={`pill ${c.ok ? 'pill-ok' : 'pill-error'}`}>{c.ok ? 'pass' : 'fail'}</span></td>
                      <td className="text-low" style={{ fontSize: 12 }}>{c.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {res.compliance && !res.compliance.ok && (
                <div className="alert alert-warn" style={{ marginTop: 12 }}>
                  <div className="alert-title">Compliance findings</div>
                  <div className="alert-text">
                    {(res.compliance.violations || []).map((v, i) => <div key={i}>{v.rule || v.message || JSON.stringify(v)}</div>)}
                  </div>
                </div>
              )}
              <div className="text-low" style={{ fontSize: 11, marginTop: 10 }}>{res.basis}</div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
