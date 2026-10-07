import { useState } from 'react'
import { DataNotice } from './Shared.jsx'

// SocialPulse — local lane. Calls the real /api/social/* backend (social_pulse.py):
// platform captions/hashtags and the brand-voice upload path (the same path a
// customer uses to upload their own voice). Drafts only — nothing is published.

const API = '/api/social'
const PLATFORMS = ['instagram', 'facebook', 'tiktok', 'twitter']
const ANGLES = ['quality', 'value', 'lifestyle', 'seasonal', 'gift']

export default function SocialPulseLane() {
  const [f, setF] = useState({
    title: 'Mogra Organics Organic Turmeric Powder',
    brand: 'Mogra Organics',
    platform: 'instagram',
    angle: 'quality',
    useLlm: false,
  })
  const [voice, setVoice] = useState({ tone: 'warm', style: 'friendly', emoji_usage: 'light', hashtags_per_post: '10' })
  const [cap, setCap] = useState(null)
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [notice, setNotice] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const setV = (k) => (e) => setVoice({ ...voice, [k]: e.target.value })

  async function genCaption() {
    setBusy(true); setErr(''); setCap(null)
    try {
      const r = await fetch(`${API}/caption`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product: { title: f.title, brand: f.brand },
          platform: f.platform, brand: f.brand, angle: f.angle,
          use_llm: f.useLlm,
        }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setCap(j)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  async function saveVoice() {
    setBusy(true); setErr(''); setNotice(''); setSaved(null)
    try {
      const r = await fetch(`${API}/brand-voice`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand: f.brand,
          profile: {
            tone: voice.tone, style: voice.style,
            emoji_usage: voice.emoji_usage,
            hashtags_per_post: Number(voice.hashtags_per_post) || 10,
          },
        }),
      })
      const j = await r.json()
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `HTTP ${r.status}`)
      setSaved(j.saved)
      setNotice(`Brand voice saved for ${f.brand} (entry ${j.entry_id}). Every caption below now uses it.`)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="subview ns-lane">
      <DataNotice tone="internal" title="Local lane — drafts only, nothing is published">
        This lane calls the local SocialPulse engine (offline template fallback; local LLM
        when available). Captions are drafts awaiting review. Publishing is a separate,
        operator-approved action and is not enabled here.
      </DataNotice>

      <div className="split-aside" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-head"><h3 className="card-title">Capture / caption inputs</h3></div>
          <label htmlFor="sp-title">Product</label>
          <input id="sp-title" type="text" value={f.title} onChange={set('title')} />
          <label htmlFor="sp-brand">Brand</label>
          <input id="sp-brand" type="text" value={f.brand} onChange={set('brand')} />
          <div className="ms-grid">
            <div>
              <label htmlFor="sp-plat">Platform</label>
              <select id="sp-plat" value={f.platform} onChange={set('platform')}>
                {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="sp-angle">Angle</label>
              <select id="sp-angle" value={f.angle} onChange={set('angle')}>
                {ANGLES.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>
          <div className="ms-check">
            <input id="sp-llm" type="checkbox" checked={f.useLlm} onChange={(e) => setF({ ...f, useLlm: e.target.checked })} />
            <label htmlFor="sp-llm" style={{ margin: 0 }}>use local LLM (slower; off = instant template caption)</label>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={genCaption}>
              {busy ? 'Working…' : 'Generate Caption'}
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h3 className="card-title">Brand voice (upload path)</h3></div>
          <div className="ms-grid">
            <div><label htmlFor="sp-tone">Tone</label><input id="sp-tone" type="text" value={voice.tone} onChange={setV('tone')} /></div>
            <div><label htmlFor="sp-style">Style</label><input id="sp-style" type="text" value={voice.style} onChange={setV('style')} /></div>
          </div>
          <div className="ms-grid">
            <div><label htmlFor="sp-emoji">Emoji usage</label><input id="sp-emoji" type="text" value={voice.emoji_usage} onChange={setV('emoji_usage')} /></div>
            <div><label htmlFor="sp-tags">Hashtags per post</label><input id="sp-tags" type="text" value={voice.hashtags_per_post} onChange={setV('hashtags_per_post')} /></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-primary" disabled={busy} onClick={saveVoice}>Save Brand Voice</button>
          </div>
          {notice && <div className="alert" style={{ marginTop: 12 }}><div className="alert-text">{notice}</div></div>}
          {saved && (
            <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
              stored voice: {JSON.stringify(saved)}
            </div>
          )}
        </div>
      </div>

      {err && <div className="alert alert-error" style={{ marginBottom: 16 }}><div className="alert-text">{err}</div></div>}

      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Caption preview</h3>
          {cap && <span className="pill pill-muted">score {cap.score}</span>}
        </div>
        {!cap && <div className="ms-empty">Generate a caption to preview it here.</div>}
        {cap && (
          <>
            <label>Caption</label>
            <div className="card" style={{ margin: 0, padding: 12 }}>{cap.caption}</div>
            <div className="ms-grid" style={{ marginTop: 10 }}>
              <div>
                <label>Hashtags</label>
                <div className="text-low" style={{ fontSize: 12 }}>{(cap.hashtags || []).join(' ')}</div>
              </div>
              <div>
                <label>Call to action</label>
                <div className="text-low" style={{ fontSize: 12 }}>{cap.cta || '—'}</div>
              </div>
            </div>
            {cap.review_required && <div className="pill pill-ochre" style={{ marginTop: 10 }}>review required</div>}
          </>
        )}
      </div>
    </div>
  )
}
