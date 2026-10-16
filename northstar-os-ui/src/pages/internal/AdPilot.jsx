import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import MasterBrainPanel from '../../studio/components/MasterBrainPanel.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import Icon from '../../components/Icon.jsx'
import ReasoningModelSelector, { useReasoningModel } from '../../components/ReasoningModelSelector.jsx'
import foundationApi from '../../foundation/api.js'
import { useToast } from '../../components/ToastContext.jsx'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { AssetThumb, ThumbPlaceholder, ModeToggle } from '../../studio/components/Chrome.jsx'
import { renderDoc } from '../../studio/engine/doc.js'
import { buildAdDoc, adFormat, AD_PLACEMENTS } from '../../studio/engine/adDoc.js'
import { useAssetStore, useDecodedAssets } from '../../studio/engine/assets.js'
import { useRoom } from '../../studio/engine/store.js'
import { DEFAULT_BRAND_KITS } from '../../studio/engine/presets.js'

const TABS = [
  { id: 'campaigns', label: 'Campaigns', count: 8 },
  { id: 'detail', label: 'Campaign Detail' },
  { id: 'terms', label: 'Search Terms' },
  { id: 'planner', label: 'Planner' },
  { id: 'creatives', label: 'Creatives' },
  { id: 'placements', label: 'Placements' },
  { id: 'rules', label: 'Rules' },
]

// ── Imported ad evidence (2026-10-16) ─────────────────────────────────────
// Campaigns and terms come from the seller's OWN imported files (file-only
// architecture: no Amazon API exists). A metric the file does not carry is
// UNKNOWN, never 0. With no import the room shows an honest empty state.
const EVIDENCE_API = '/api/design-studio'

async function evidenceGet(path) {
  const res = await fetch(`${EVIDENCE_API}${path}`, { credentials: 'include' })
  if (!res.ok) throw new Error(`http-${res.status}`)
  return res.json()
}

const asNum = (v) => {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function deriveCampaigns(rows) {
  const by = new Map()
  for (const r of rows) {
    const key = r.campaign_id || r.campaign_name || '(unidentified)'
    if (!by.has(key)) by.set(key, { id: key, name: r.campaign_name || r.campaign_id || 'UNKNOWN', spend: null, sales: null, clicks: null, impressions: null, rows: 0 })
    const c = by.get(key)
    c.rows += 1
    for (const f of ['spend', 'sales', 'clicks', 'impressions']) {
      const v = asNum(r[f])
      if (v !== null) c[f] = (c[f] ?? 0) + v
    }
  }
  const out = [...by.values()].map(c => ({
    ...c,
    spend: c.spend === null ? 'UNKNOWN' : c.spend,
    acos: (c.spend !== null && c.sales) ? `${Math.round((c.spend / c.sales) * 1000) / 10}%` : 'UNKNOWN',
  }))
  out.sort((a, b) => (typeof b.spend === 'number' ? b.spend : -1) - (typeof a.spend === 'number' ? a.spend : -1))
  return out
}

function useImportedAdEvidence() {
  const [st, setSt] = useState({ phase: 'loading' })
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const list = await evidenceGet('/amazon-files')
        const bulks = (list.uploads || [])
          .filter(u => u.kind === 'ads_bulksheet' || u.kind === 'ads_search_terms')
          .sort((a, b) => String(b.uploaded_at || '').localeCompare(String(a.uploaded_at || '')))
        if (!bulks.length) { if (alive) setSt({ phase: 'empty' }); return }
        const newest = bulks[0]
        const rows = await evidenceGet(`/amazon-files/${newest.id}/rows?limit=800`)
        let terms = []
        try {
          const t = await evidenceGet('/terms?limit=200')
          terms = t.rows || []
        } catch { /* terms are optional evidence */ }
        if (alive) setSt({ phase: 'ready', source: newest, rows: rows.rows || [], campaigns: deriveCampaigns(rows.rows || []), terms })
      } catch (e) {
        if (alive) setSt({ phase: 'error', message: e.message })
      }
    })()
    return () => { alive = false }
  }, [])
  return st
}

const STATUS_PILL = { Healthy: 'pill-forest', Review: 'pill-warn', Critical: 'pill-ochre' }

// ═══ Hosted ad-copy proposal (OpenCode Go) — proposal only, never published ═══
function AdCopyProposalPanel() {
  const { selectedModel, catalog, persist } = useReasoningModel()
  const { toast } = useToast()
  const [form, setForm] = useState({
    product_name: 'Premium Water Filter',
    facts: '3-stage filtration; 10-cup capacity; BPA-free; easy-change filters; fits standard cabinets.',
    brand_tone: 'professional',
    format_hint: 'Amazon Sponsored Products',
  })
  const [state, setState] = useState({ phase: 'idle' })

  const submit = async () => {
    if (!(catalog && catalog.armed)) {
      toast('Hosted reasoning is not armed. Set OPENCODE_GO_ENABLED=1 and supply a key.', 'warn')
      return
    }
    setState({ phase: 'submitting' })
    try {
      const r = await foundationApi.reasoningAdCopyProposal({
        product_facts: {
          name: form.product_name,
          facts: form.facts.split('\n').map(s => s.trim()).filter(Boolean),
        },
        brand_tone: form.brand_tone,
        format_hint: form.format_hint,
        model: selectedModel?.id,
      })
      setState({ phase: 'done', value: r.proposal })
    } catch (e) {
      setState({ phase: 'error', message: e.message || 'Proposal failed.' })
    }
  }

  const prop = state.phase === 'done' ? state.value : null

  return (
    <div className="card" data-testid="ap-proposal" style={{ marginTop: 20 }}>
      <div className="card-head">
        <h3 className="card-title">Hosted ad-copy proposal</h3>
        <span className="pill pill-ochre">proposal only · not published</span>
      </div>
      <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
        Generates proposed ad copy from supplied facts and brand tone. The output is for owner review — it is never pushed to an advertising platform.
      </p>
      <ReasoningModelSelector value={selectedModel?.id} onChange={persist} />
      <label className="stack" style={{ gap: 4, marginTop: 12 }}>
        <span className="text-low" style={{ fontSize: 11 }}>Product name</span>
        <input className="field" value={form.product_name} onChange={e => setForm(f => ({ ...f, product_name: e.target.value }))} />
      </label>
      <label className="stack" style={{ gap: 4, marginTop: 10 }}>
        <span className="text-low" style={{ fontSize: 11 }}>Approved facts (one per line)</span>
        <textarea className="field" rows={4} value={form.facts} onChange={e => setForm(f => ({ ...f, facts: e.target.value }))} />
      </label>
      <div className="grid-2" style={{ gap: 12, marginTop: 10 }}>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Brand tone</span>
          <input className="field" value={form.brand_tone} onChange={e => setForm(f => ({ ...f, brand_tone: e.target.value }))} />
        </label>
        <label className="stack" style={{ gap: 4 }}>
          <span className="text-low" style={{ fontSize: 11 }}>Format hint</span>
          <input className="field" value={form.format_hint} onChange={e => setForm(f => ({ ...f, format_hint: e.target.value }))} />
        </label>
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="btn btn-sm" onClick={submit} disabled={state.phase === 'submitting' || !(catalog && catalog.armed)}>
          {state.phase === 'submitting' ? 'Generating…' : 'Generate ad copy'}
        </button>
        {!(catalog && catalog.armed) && <span className="text-low" style={{ fontSize: 11, marginLeft: 8 }}>Hosted reasoning not armed.</span>}
      </div>
      {state.phase === 'error' && <div className="pill pill-warn" style={{ marginTop: 10 }}>{state.message}</div>}
      {prop && (
        <div style={{ marginTop: 16 }}>
          <div className="inline-flex" style={{ gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <span className={`pill ${prop.ok ? 'pill-ok' : 'pill-warn'}`}>{prop.ok ? 'proposal ok' : 'proposal failed'}</span>
            {prop.provenance && <span className="pill pill-muted">{prop.provenance.model}</span>}
          </div>
          {prop.warnings && prop.warnings.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              {prop.warnings.map((w, i) => <span key={i} className="pill pill-warn" style={{ fontSize: 10 }}>{w}</span>)}
            </div>
          )}
          {prop.unsupported_claims && prop.unsupported_claims.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Unsupported:</span>
              {prop.unsupported_claims.map((c, i) => <span key={i} className="pill pill-unknown" style={{ fontSize: 10 }}>{c}</span>)}
            </div>
          )}
          <div className="card" style={{ background: 'var(--pine-bleached)' }}>
            <div className="card-head"><h4 className="card-title" style={{ fontSize: 13 }}>Proposed copy</h4></div>
            <div style={{ fontSize: 12 }}>
              <div style={{ fontWeight: 600 }}>{(prop.headlines || []).join(' / ')}</div>
              <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{prop.body}</div>
              <div style={{ marginTop: 6, fontWeight: 600 }}>{prop.cta}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ═══ Real ad-creative renderer ══════════════════════════════════════════════
// Renders the operator's own ad copy and attached artwork at each paid
// placement's true pixel size, using the shared studio renderer. Selecting a
// placement drives the master creative in the Design Studio.
const AdCreativePreview = ({ doc }) => {
  const canvasRef = useRef(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const maxW = 300
    const scale = Math.min(1, maxW / doc.w)
    const W = Math.max(1, Math.round(doc.w * scale))
    const H = Math.max(1, Math.round(doc.h * scale))
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H }
    renderDoc(canvas.getContext('2d'), doc, { W, H })
    return undefined
  }, [doc])
  return (
    <canvas ref={canvasRef} data-testid="ad-preview-canvas"
      style={{ width: '100%', maxWidth: 280, height: 'auto', display: 'block' }} />
  )
}

function AdCreatives({ copy, setCopy, attachedAssetId, setAttachedAssetId, store, kit }) {
  const [placement, setPlacement] = useState('meta-feed')
  const { images } = useDecodedAssets(store.assets)
  const doc = useMemo(
    () => buildAdDoc({ ...copy, placement, assetId: attachedAssetId, kit }),
    [copy.headline, copy.body, copy.cta, placement, attachedAssetId, kit],
  )
  return (
    <div className="subview stack" style={{ gap: 14 }}>
      <div className="card">
        <div className="card-head">
          <h3 className="card-title" style={{ fontSize: 15 }}>Ad creative</h3>
          <span className="pill pill-forest">local render</span>
        </div>
        <p className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
          The copy below and your attached artwork are rendered at each placement&rsquo;s own pixel size. Geometry is
          normalised, so one creative renders correctly at every placement. No ad is served and no platform is contacted.
        </p>
        <div className="grid-2" style={{ gap: 16, alignItems: 'start' }}>
          <div className="stack" style={{ gap: 12 }}>
            <label className="stack" style={{ gap: 4 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Headline</span>
              <input className="field" value={copy.headline} onChange={e => setCopy(c => ({ ...c, headline: e.target.value }))} />
            </label>
            <label className="stack" style={{ gap: 4 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Body copy</span>
              <textarea className="field" rows={3} value={copy.body} onChange={e => setCopy(c => ({ ...c, body: e.target.value }))} />
            </label>
            <label className="stack" style={{ gap: 4 }}>
              <span className="text-low" style={{ fontSize: 11 }}>Call to action</span>
              <input className="field" value={copy.cta} onChange={e => setCopy(c => ({ ...c, cta: e.target.value }))} />
            </label>
            <div>
              <div className="text-low" style={{ fontSize: 11, marginBottom: 6 }}>Attached artwork</div>
              <div className="sp-asset-grid">
                {store.assets.filter(a => a.role === 'reference').slice(0, 6).map(a => (
                  <AssetThumb key={a.id} asset={a} height={48} selected={attachedAssetId === a.id}
                    onClick={() => setAttachedAssetId(attachedAssetId === a.id ? '' : a.id)} />
                ))}
              </div>
              {!store.assets.filter(a => a.role === 'reference').length && <ThumbPlaceholder height={48} label="no artwork uploaded" />}
              <label className="sp-dropzone" style={{ marginTop: 10 }}>
                <Icon name="upload" size={14} /> Upload creative artwork
                <input type="file" accept="image/*" multiple style={{ display: 'none' }}
                  onChange={async (e) => {
                    const added = await store.add(e.target.files, { role: 'reference', tags: ['ad'] })
                    if (added.length) { setAttachedAssetId(added[0].id); setCopy(c => ({ ...c })) }
                    e.target.value = ''
                  }} />
              </label>
            </div>
          </div>

          <div className="stack" style={{ gap: 12 }}>
            <div className="stage" style={{ padding: 14, background: 'linear-gradient(180deg,#1b2a1c,#131f14)' }}>
              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <AdCreativePreview doc={doc} />
              </div>
            </div>
            <div className="text-low" style={{ fontSize: 11 }}>
              {adFormat(placement).label} · {doc.w}×{doc.h} · {kit.name}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3 className="card-title" style={{ fontSize: 15 }}>All placements</h3>
          <span className="pill pill-muted">{AD_PLACEMENTS.length} rendered from one master</span>
        </div>
        <div className="sp-formats">
          <div className="sp-format-list">
            {AD_PLACEMENTS.map(p => (
              <button key={p.id} className={`sp-format ${placement === p.id ? 'active' : ''}`}
                onClick={() => setPlacement(p.id)} title={p.note}>
                <span className="sp-format-box ar-wide" style={{ aspectRatio: `${adFormat(p.id).w} / ${adFormat(p.id).h}` }} />
                <span className="sp-format-label">{p.label}</span>
                <span className="text-mono sp-format-dims">{adFormat(p.id).w}×{adFormat(p.id).h}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="inline-flex" style={{ gap: 8, marginTop: 14 }}>
          <button className="btn btn-sm btn-primary" onClick={() => window.open('/ui/#/creative-studio?view=ads', '_blank', 'noopener')}>
            <Icon name="brush" size={13} /> Open full creative set in Design Studio
          </button>
          <span className="pill pill-muted">opens the master canvas with this copy</span>
        </div>
      </div>
    </div>
  )
}

function healthRollup(campaigns) {
  if (!campaigns || !campaigns.length) return 'no imported campaigns yet'
  const withSpend = campaigns.filter(c => typeof c.spend === 'number').length
  return `${campaigns.length} campaign(s) from the imported file · ${withSpend} with spend data`
}

export default function AdPilot() {
  const navigate = useNavigate()
  const location = useLocation()
  const { toast } = useToast()

  const [mode, setMode] = useRoom('ap-mode', 'simple')
  const [kits] = useRoom('ap-kits', DEFAULT_BRAND_KITS)
  const [activeKitId] = useRoom('ap-active-kit', 'kit-pine')
  const [adCopy, setAdCopy] = useRoom('ap-creative-copy', {
    headline: 'Water that tastes like it should.',
    body: 'Three-stage filtration removes sediment, chlorine and taste — in one countertop unit, with no tools to install.',
    cta: 'Shop now',
  })
  const [attachedAssetId, setAttachedAssetId] = useState('')
  const store = useAssetStore()
  const kit = kits.find(k => k.id === activeKitId) || kits[0] || DEFAULT_BRAND_KITS[0]
  const evidence = useImportedAdEvidence()
  const [selectedCampaign, setSelectedCampaign] = useState(null)

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'campaigns'
  const campaigns = evidence.phase === 'ready' ? evidence.campaigns : []

  return (
    <PageLayout
      title="AdPilot"
      subtitle="Advertising operations workbench — campaign health, budget, placements, performance, and a real creative renderer."
      actions={<>
        <ModeToggle mode={mode} onChange={setMode} />
        <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=planner')}>Create Campaign</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Bulk actions operate on the local campaign records below — nothing is sent to an ad platform.', 'info')}>Bulk Actions</button>
      </>}
    >
      {evidence.phase === 'empty' && (
        <DataNotice tone="cached" title="No ad files imported yet">
          Import an Ads bulksheet (or search-term report) in <strong>Design Studio → Ads → Amazon files</strong> and this
          room reads it: campaigns, spend and terms come from your own files. Nothing here is live tracking and nothing
          is sent to an ad platform.
        </DataNotice>
      )}
      {evidence.phase === 'ready' && (
        <DataNotice tone="cached" title={`Reading ${evidence.source.filename} (observed ${evidence.source.observed_from || 'UNKNOWN'} → ${evidence.source.observed_to || 'UNKNOWN'})`}>
          Observed file data, not live tracking. A metric your file does not carry reads UNKNOWN, never 0.
          Nothing is sent to an ad platform.
        </DataNotice>
      )}
      {evidence.phase === 'error' && (
        <DataNotice tone="sample" title="Could not read the imported files">
          {evidence.message} — the room will not substitute sample numbers. Try again after the stack is healthy.
        </DataNotice>
      )}

      <RoomTabs tabs={TABS} base="/adpilot" />

      <MasterBrainPanel title="Studio evidence for ads (read-only)" />

      {view === 'campaigns' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Campaign Health</h3>
              <span className="pill pill-muted">{healthRollup(campaigns)}</span>
            </div>
            {evidence.phase === 'loading' && <p style={{ fontSize: 13 }}>Reading your imported files…</p>}
            {evidence.phase === 'empty' && (
              <div style={{ padding: '10px 0' }} data-testid="ap-campaigns-empty">
                <p style={{ fontSize: 13, marginBottom: 10 }}>
                  No campaigns yet — campaigns appear here after you import a bulksheet in Ads → Amazon files.
                </p>
                <button className="btn btn-sm btn-primary" onClick={() => navigate('/design-studio?section=ads&view=amazon-files')}>
                  Import a bulksheet
                </button>
              </div>
            )}
            {evidence.phase === 'ready' && campaigns.length > 0 && (
              <DataTable columns={[
                { key: 'name', label: 'Campaign' },
                { key: 'spend', label: 'Spend (observed)', render: (v) => typeof v === 'number' ? v.toFixed(2) : <span className="pill pill-unknown">UNKNOWN</span> },
                { key: 'sales', label: 'Sales (observed)', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v.toFixed(2) },
                { key: 'acos', label: 'ACoS (derived)', render: (v) => v === 'UNKNOWN' ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'clicks', label: 'Clicks', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'open', label: '', render: (v, row) => (
                  <button className="btn btn-sm" onClick={() => { setSelectedCampaign(row); navigate('/adpilot?view=detail') }}>Open</button>
                ) },
              ]} rows={campaigns} />
            )}
            {evidence.phase === 'ready' && campaigns.length === 0 && (
              <p style={{ fontSize: 13 }}>The imported file carries no campaign-level rows. Honest empty state.</p>
            )}
          </div>

          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-head">
              <h3 className="card-title">Observed range &amp; source</h3>
              <span className="pill pill-muted">{evidence.phase === 'ready' ? 'file evidence' : 'no file'}</span>
            </div>
            {evidence.phase === 'ready' ? (
              <div className="grid-3" style={{ gap: 16 }}>
                <div>
                  <div className="text-low" style={{ fontSize: 11 }}>Source file</div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{evidence.source.filename}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>checksum {(evidence.source.checksum || '').slice(0, 10)}…</div>
                </div>
                <div>
                  <div className="text-low" style={{ fontSize: 11 }}>Observed window</div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>
                    {evidence.source.observed_from || 'UNKNOWN'} → {evidence.source.observed_to || 'UNKNOWN'}
                  </div>
                  <div className="text-low" style={{ fontSize: 11 }}>as the file states it</div>
                </div>
                <div>
                  <div className="text-low" style={{ fontSize: 11 }}>Rows read</div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{evidence.rows.length}</div>
                  <div className="text-low" style={{ fontSize: 11 }}>never modified — the archive is read-only</div>
                </div>
              </div>
            ) : (
              <p style={{ fontSize: 13 }}>No imported file yet — this panel fills from your first Ads import.</p>
            )}
          </div>
        </div>
      )}

      {view === 'detail' && (
        <div className="subview">
          {!selectedCampaign && (
            <div className="card">
              <p style={{ fontSize: 13, marginBottom: 10 }}>Open a campaign from the Campaigns tab to see its observed detail here.</p>
              <button className="btn btn-sm" onClick={() => navigate('/adpilot?view=campaigns')}>Back to campaigns</button>
            </div>
          )}
          {selectedCampaign && (
            <>
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-head">
                  <h3 className="card-title">{selectedCampaign.name}</h3>
                  <span className="pill pill-muted">observed file data</span>
                </div>
                <div className="grid-4" style={{ gap: 12 }}>
                  {[
                    { label: 'Spend (observed)', v: typeof selectedCampaign.spend === 'number' ? selectedCampaign.spend.toFixed(2) : 'UNKNOWN' },
                    { label: 'Sales (observed)', v: selectedCampaign.sales == null ? 'UNKNOWN' : selectedCampaign.sales.toFixed(2) },
                    { label: 'ACoS (derived)', v: selectedCampaign.acos },
                    { label: 'Clicks', v: selectedCampaign.clicks == null ? 'UNKNOWN' : selectedCampaign.clicks },
                  ].map(d => (
                    <div key={d.label}>
                      <div className="text-low" style={{ fontSize: 11, marginBottom: 4 }}>{d.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--pine-deep)' }}>{d.v}</div>
                      <div className="text-low" style={{ fontSize: 10, marginTop: 2 }}>from {evidence.phase === 'ready' ? evidence.source.filename : 'no file'}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h3 className="card-title">Search Term Performance</h3>
                  <span className="pill pill-muted">from your imported term evidence</span>
                </div>
                {evidence.phase === 'ready' && evidence.terms.length > 0 ? (
                  <DataTable columns={[
                    { key: 'term', label: 'Search Term' },
                    { key: 'impressions', label: 'Impressions', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                    { key: 'clicks', label: 'Clicks', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                    { key: 'spend', label: 'Spend', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                  ]} rows={[...evidence.terms].sort((a, b) => (b.clicks ?? -1) - (a.clicks ?? -1)).slice(0, 10)} />
                ) : (
                  <p style={{ fontSize: 13 }}>No search-term evidence imported yet — import a search-term report in Design Studio → Ads → Amazon files. Honest empty state.</p>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {view === 'planner' && (
        <div className="subview">
          <DataNotice tone="assumption" title="Planning aid — nothing is applied automatically">
            This planner works from your imported file evidence. It never generates fake recommendations and never
            authorizes spend; every change is made by you in Amazon's console.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Planning basis</h3>
              <span className="pill pill-muted">{evidence.phase === 'ready' ? 'file evidence' : 'no file'}</span>
            </div>
            {evidence.phase === 'ready' && campaigns.length > 0 ? (
              <DataTable columns={[
                { key: 'name', label: 'Campaign' },
                { key: 'spend', label: 'Observed spend', render: (v) => typeof v === 'number' ? v.toFixed(2) : <span className="pill pill-unknown">UNKNOWN</span> },
                { key: 'acos', label: 'Observed ACoS (derived)', render: (v) => v === 'UNKNOWN' ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'proposed', label: 'Proposed change', render: () => <span className="pill pill-muted">you decide</span> },
              ]} rows={campaigns} />
            ) : (
              <p style={{ fontSize: 13 }}>Import a bulksheet to plan against your own observed numbers. Honest empty state — no invented recommendations.</p>
            )}
          </div>

          <AdCopyProposalPanel />
        </div>
      )}

      {view === 'terms' && (
        <div className="subview">
          <DataNotice tone="cached" title="Search-term evidence from your imported files">
            Harvest and negative suggestions are yours to make; the studio shows the evidence and never changes a campaign.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Term Analysis</h3>
              <span className="pill pill-muted">{evidence.phase === 'ready' ? `${evidence.terms.length} imported term(s)` : 'no terms imported'}</span>
            </div>
            {evidence.phase === 'ready' && evidence.terms.length > 0 ? (
              <DataTable columns={[
                { key: 'term', label: 'Search Term' },
                { key: 'impressions', label: 'Impr.', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'clicks', label: 'Clicks', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
                { key: 'spend', label: 'Spend', render: (v) => v == null ? <span className="pill pill-unknown">UNKNOWN</span> : v },
              ]} rows={[...evidence.terms].sort((a, b) => (b.clicks ?? -1) - (a.clicks ?? -1)).slice(0, 25)} />
            ) : (
              <p style={{ fontSize: 13 }}>No search-term evidence yet — import a search-term report in Design Studio → Ads → Amazon files. Honest empty state.</p>
            )}
          </div>
        </div>
      )}

      {view === 'creatives' && (
        <AdCreatives copy={adCopy} setCopy={setAdCopy} attachedAssetId={attachedAssetId}
          setAttachedAssetId={setAttachedAssetId} store={store} kit={kit} />
      )}

      {view === 'placements' && (
        <div className="subview stack" style={{ gap: 14 }}>
          <DataNotice tone="cached" title="Placement creative sizes">
            The creative sizes below are the real pixel dimensions each placement expects (from the spec registry).
            No live ad-platform reporting is connected; nothing here claims placement performance.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Placement creative sizes</h3>
              <span className="pill pill-muted">rendered by the studio engine</span>
            </div>
            <div className="sp-format-list">
              {AD_PLACEMENTS.map(p => {
                const f = adFormat(p.id)
                return (
                  <button key={p.id} className="sp-format" onClick={() => navigate('/adpilot?view=creatives')} title={`${p.note} Renders the current creative at ${f.w}×${f.h}.`}>
                    <span className="sp-format-box ar-wide" style={{ aspectRatio: `${f.w} / ${f.h}` }} />
                    <span className="sp-format-label">{p.label}</span>
                    <span className="text-mono sp-format-dims">{f.w}×{f.h}</span>
                  </button>
                )
              })}
            </div>
          </div>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Placement Insights — Product Launch</h3>
              <span className="pill pill-muted" title="Cached snapshot — not live data">Cached snapshot</span>
            </div>
            <DataTable columns={[
              { key: 'placement', label: 'Placement' },
              { key: 'share', label: 'Impression Share' },
              { key: 'ctr', label: 'CTR' },
              { key: 'acos', label: 'ACoS' },
              { key: 'basis', label: 'Basis', render: (v) => <span className="pill pill-muted" title="Stored sample window — not live reporting">{v}</span> },
            ]} rows={[
              { placement: 'Top of Search', share: '62%', ctr: '8.9%', acos: '18.2%', basis: 'CACHED' },
              { placement: 'Rest of Search', share: '21%', ctr: '4.1%', acos: '26.7%', basis: 'CACHED' },
              { placement: 'Product Pages', share: '17%', ctr: '3.2%', acos: '31.4%', basis: 'CACHED' },
            ]} />
          </div>
        </div>
      )}

      {view === 'rules' && (
        <div className="subview">
          <DataNotice tone="internal" title="Rule definitions are templates — none fire">
            These are example rule TEMPLATES to plan with. No rule evaluates automatically and nothing is ever applied;
            a rule is a note for you, not an automation.
          </DataNotice>
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Rule Templates</h3>
              <span className="pill pill-muted">templates only</span>
            </div>
            <DataTable columns={[
              { key: 'rule', label: 'Rule' },
              { key: 'scope', label: 'Scope' },
              { key: 'condition', label: 'Condition' },
              { key: 'evaluated', label: 'Last Evaluated' },
              { key: 'state', label: 'State', render: (v) => <span className={`pill ${v === 'Armed' ? 'pill-warn' : 'pill-muted'}`}>{v}</span> },
            ]} rows={[
              { rule: 'Pause term if ACoS > 30%', scope: 'Any campaign', condition: 'ACoS > 30% over 7d', evaluated: 'never — templates do not evaluate', state: 'Draft' },
              { rule: 'Raise budget if pacing < 80%', scope: 'Any campaign', condition: 'Pacing < 80% at day 14', evaluated: 'never — templates do not evaluate', state: 'Draft' },
              { rule: 'Flag placement ACoS drift', scope: 'Any campaign', condition: 'ACoS delta > +8pp week/week', evaluated: 'never — templates do not evaluate', state: 'Draft' },
            ]} />
          </div>
        </div>
      )}
    </PageLayout>
  )
}