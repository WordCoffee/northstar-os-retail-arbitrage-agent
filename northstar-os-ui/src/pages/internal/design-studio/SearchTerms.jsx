// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — SECTION: ADS › SEARCH TERMS (Phase 6 items 4-6)
//
// Imported marketplace evidence, not live data:
//   • Sponsored Products search-term reports (CSV/JSON) and Brand Analytics
//     Search Query Performance files are imported into the TENANT's store,
//     archived with the observed date and the source label.
//   • Missing columns display UNKNOWN, never 0.
//   • The report caveats (65-day lookback, 31-day API range, click-only bias)
//     are shown with the data, not buried in a doc.
//   • Brand Analytics reads UNAVAILABLE until a file is imported.
//   • Briefs are COMPOSED from imported evidence + the brand profile. No image
//     or video is generated anywhere on this surface.
//   • Variant metrics are user- or file-entered only; the comparison view makes
//     no causation claim.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import { useToast } from '../../../components/ToastContext.jsx'
import { readRoom } from '../../../studio/engine/store.js'
import {
  importReport, fetchImports, fetchTerms, termsExportHref, makeBrief,
  fetchVariants, createVariant, addVariantMetric, importVariantMetrics, fetchCompare,
} from '../../../studio/engine/imports.js'

const KINDS = [
  { id: 'sp_search_terms', label: 'Sponsored Products search terms (CSV/JSON)' },
  { id: 'brand_analytics_sqp', label: 'Brand Analytics Search Query Performance (CSV/JSON)' },
]

// Shown BEFORE an import so the limits are known up front, and attached to
// every import afterwards by the server.
const KNOWN_NOTES = {
  sp_search_terms: [
    '65-day lookback ceiling in the console export.',
    'The reporting API returns at most 31 days per request; a longer file is a union of pulls and may miss days inside it.',
    'Click-only bias: a term appears only after at least one click. Impressions without a click are absent.',
  ],
  brand_analytics_sqp: [
    '65-day lookback ceiling in the console export.',
    'No clicks or spend columns: those figures stay UNKNOWN with this file.',
  ],
}

// A NULL from the server is UNKNOWN on screen. Never 0.
function fmt(v) {
  if (v === null || v === undefined || v === '') return 'UNKNOWN'
  return typeof v === 'number' ? String(v) : String(v)
}

function readBrandProfile() {
  // The one brand profile every creative room reads (Projects › Brand).
  const p = readRoom('ds-brand-profile', null)
  return p || null
}

function kindLabel(id) {
  return (KINDS.find(k => k.id === id) || {}).label || id
}

export default function SearchTerms() {
  const { toast } = useToast()
  const [kind, setKind] = useState('sp_search_terms')
  const [sourceLabel, setSourceLabel] = useState('')
  const [observedFrom, setObservedFrom] = useState('')
  const [observedTo, setObservedTo] = useState('')
  const [fileContent, setFileContent] = useState(null)
  const [fileName, setFileName] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastImport, setLastImport] = useState(null) // {state, data} | {state:'error'}

  const [importsState, setImportsState] = useState({ state: 'loading', imports: [], kinds: {} })
  const [termsState, setTermsState] = useState({ state: 'loading', terms: [], counts: null })
  const [termQuery, setTermQuery] = useState('')
  const [kindFilter, setKindFilter] = useState('')

  const [briefState, setBriefState] = useState(null) // {state, brief} | {state:'error'}
  const [briefBusy, setBriefBusy] = useState(false)

  const [variantsState, setVariantsState] = useState({ state: 'loading', variants: [], metrics: [] })
  const [variantName, setVariantName] = useState('')
  const [variantAssetId, setVariantAssetId] = useState('')
  const [metricTarget, setMetricTarget] = useState('')
  const [metricForm, setMetricForm] = useState({ impressions: '', clicks: '', orders: '', spend: '', sales: '' })
  const [metricsFileMsg, setMetricsFileMsg] = useState(null)
  const [compareState, setCompareState] = useState(null)

  const reloadImports = useCallback(async () => {
    const r = await fetchImports()
    setImportsState(r)
    return r
  }, [])

  const reloadTerms = useCallback(async (q, k) => {
    const r = await fetchTerms({ q: q ?? termQuery, kind: k ?? kindFilter, limit: 200 })
    setTermsState(r)
    return r
  }, [termQuery, kindFilter])

  const reloadVariants = useCallback(async () => {
    const r = await fetchVariants()
    setVariantsState(r)
    return r
  }, [])

  useEffect(() => {
    reloadImports()
    reloadTerms('', '')
    reloadVariants()
  }, [reloadImports, reloadTerms, reloadVariants])

  const onFile = async (e) => {
    const f = e.target.files && e.target.files[0]
    if (!f) { setFileContent(null); setFileName(''); return }
    try {
      const text = await f.text()
      setFileContent(text)
      setFileName(f.name)
    } catch (err) {
      setFileContent(null)
      setFileName('')
      toast(`Could not read the file: ${String(err.message || err)}`, 'error')
    }
  }

  const runImport = async () => {
    if (!fileContent) { toast('Choose a report file first. Nothing was imported.', 'error'); return }
    if (!sourceLabel.trim()) { toast('Add a source label (e.g. "SP console export, US").', 'error'); return }
    setBusy(true)
    setLastImport(null)
    const res = await importReport({
      kind, sourceLabel: sourceLabel.trim(), filename: fileName,
      content: fileContent, observedFrom: observedFrom || null, observedTo: observedTo || null,
    })
    setBusy(false)
    setLastImport(res)
    if (res.state === 'imported') {
      toast(`Imported ${res.data.rows_added} row(s) from the file.`, 'info')
      await reloadImports()
      await reloadTerms(termQuery, kindFilter)
      await reloadVariants()
    } else if (res.state === 'duplicate') {
      toast('That exact file was already imported for this account. Nothing was duplicated.', 'info')
      await reloadImports()
    } else {
      toast(`Import failed: ${res.reason || 'unknown reason'}. Nothing was stored.`, 'error')
    }
  }

  const runBrief = async () => {
    setBriefBusy(true)
    const profile = readBrandProfile()
    // Keywords come from the brand profile's promise + audience words; when the
    // profile is empty they stay empty and the brief says UNKNOWN instead.
    const words = `${(profile && profile.promise) || ''} ${(profile && profile.audience) || ''}`
      .toLowerCase().split(/[^a-z0-9']+/).filter(w => w.length >= 4)
    const brand = profile ? {
      objective: `Move "${profile.name || 'the brand'}" search terms into the creative.`,
      audience: profile.audience || null,
      voice: profile.voice || null,
      promise: profile.promise || null,
    } : null
    const res = await makeBrief({
      q: termQuery, limit: 25, brand, keywords: words.slice(0, 12),
    })
    setBriefBusy(false)
    setBriefState(res)
    if (res.state === 'ready') toast('Brief composed from the imported terms. Nothing was generated.', 'info')
    else toast(`Brief failed: ${res.reason}. Nothing was composed.`, 'error')
  }

  const addVariant = async () => {
    if (!variantName.trim()) { toast('Give the variant a name first.', 'error'); return }
    const r = await createVariant({ name: variantName.trim(), asset_id: variantAssetId.trim() || null, format: null })
    if (r.state === 'ready') {
      setVariantName('')
      setVariantAssetId('')
      toast('Variant created.', 'info')
      await reloadVariants()
    } else toast(`Could not create the variant: ${r.reason}`, 'error')
  }

  const submitMetric = async () => {
    if (!metricTarget) { toast('Pick a variant first.', 'error'); return }
    const num = (v) => (v === '' ? null : Number(v))
    const r = await addVariantMetric(metricTarget, {
      impressions: num(metricForm.impressions), clicks: num(metricForm.clicks),
      orders: num(metricForm.orders), spend: num(metricForm.spend), sales: num(metricForm.sales),
    })
    if (r.state === 'ready') {
      setMetricForm({ impressions: '', clicks: '', orders: '', spend: '', sales: '' })
      toast('Metric entry stored for the selected variant.', 'info')
      await reloadVariants()
    } else toast(`Metric not stored: ${r.reason}`, 'error')
  }

  const onMetricsFile = async (e) => {
    const f = e.target.files && e.target.files[0]
    if (!f) return
    try {
      const content = await f.text()
      const r = await importVariantMetrics({ content, filename: f.name })
      setMetricsFileMsg(r)
      if (r.state === 'ready') {
        toast(`Metrics file: ${r.rows_added} row(s) attached${r.unmatched.length ? `, ${r.unmatched.length} unmatched` : ''}.`, 'info')
        await reloadVariants()
      } else toast(`Metrics file failed: ${r.reason}`, 'error')
    } catch (err) {
      setMetricsFileMsg({ state: 'error', reason: String(err.message || err) })
    } finally {
      e.target.value = ''
    }
  }

  const runCompare = async () => {
    const r = await fetchCompare()
    setCompareState(r)
  }

  const ba = (importsState.kinds || {}).brand_analytics_sqp || null
  const sp = (importsState.kinds || {}).sp_search_terms || null

  const shownTerms = termsState.terms || []

  return (
    <div data-testid="search-terms-workspace" className="stack" style={{ gap: 16 }}>
      {/* ── Import ─────────────────────────────────────────────────────── */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Icon name="download" size={16} />
          <strong style={{ fontSize: 14 }}>Import a marketplace report</strong>
          <span className="pill pill-muted">file data — never live</span>
        </div>
        <div className="text-low" style={{ fontSize: 12, marginBottom: 12 }}>
          Files are archived for this account with the observed date and your source label. A missing
          column is stored as UNKNOWN — never as 0. The report does not become a live feed.
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="field-group" style={{ minWidth: 260 }}>
            <label className="label">Report kind</label>
            <select className="field" value={kind} onChange={e => setKind(e.target.value)}>
              {KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
            </select>
          </div>
          <div className="field-group" style={{ minWidth: 200 }}>
            <label className="label">Source label</label>
            <input className="field" value={sourceLabel} placeholder="e.g. SP console export, US" onChange={e => setSourceLabel(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="label">Observed from</label>
            <input className="field" type="date" value={observedFrom} onChange={e => setObservedFrom(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="label">Observed to</label>
            <input className="field" type="date" value={observedTo} onChange={e => setObservedTo(e.target.value)} />
          </div>
          <div className="field-group" style={{ minWidth: 220 }}>
            <label className="label">File (CSV or JSON)</label>
            <input className="field" type="file" accept=".csv,.tsv,.json,text/csv,application/json" onChange={onFile} data-testid="import-file" />
          </div>
          <button className="btn btn-primary" disabled={busy || !fileContent} onClick={runImport} data-testid="import-run">
            {busy ? 'Importing…' : 'Import file'}
          </button>
        </div>
        {!fileContent && <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>No file selected yet. Import is disabled until you pick one.</div>}

        <div style={{ marginTop: 12 }} data-testid="import-notes">
          {(KNOWN_NOTES[kind] || []).map((n, i) => (
            <div key={i} className="text-low" style={{ fontSize: 11 }}>• {n}</div>
          ))}
        </div>

        {lastImport && (
          <div
            className="alert"
            data-testid="import-result"
            style={{ marginTop: 12, background: lastImport.state === 'imported' ? 'var(--surface-2, #f4f1ea)' : 'var(--surface-2, #f4f1ea)' }}
          >
            {lastImport.state === 'imported' || lastImport.state === 'duplicate' ? (
              <>
                <div className="alert-title" data-testid="import-banner">{lastImport.data.banner.text}</div>
                <div className="alert-text" style={{ fontSize: 12 }}>
                  {lastImport.state === 'duplicate'
                    ? 'Already archived for this account — nothing was duplicated.'
                    : `${lastImport.data.rows_added} row(s) archived under the source label "${lastImport.data.import.source_label}".`}
                  {lastImport.data.import.missing_columns && lastImport.data.import.missing_columns.length > 0 && (
                    <> Columns absent from the file (values UNKNOWN): {lastImport.data.import.missing_columns.join(', ')}.</>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="alert-title">Import refused — nothing was stored</div>
                <div className="alert-text" style={{ fontSize: 12 }}>{lastImport.reason}</div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Archive + Brand Analytics status ───────────────────────────── */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: 16, flex: '2 1 480px' }}>
          <strong style={{ fontSize: 13 }}>Import archive</strong>
          {importsState.state === 'error' ? (
            <div className="alert alert-warn" style={{ marginTop: 8 }}>
              <div className="alert-title">Imports could not be read</div>
              <div className="alert-text" style={{ fontSize: 12 }}>Reason: {importsState.reason}. This is not an empty archive.</div>
            </div>
          ) : importsState.imports.length === 0 ? (
            <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>No files imported yet. The first import appears here with its date and source label.</div>
          ) : (
            <table className="table" style={{ marginTop: 8, fontSize: 12 }}>
              <thead><tr><th>Imported</th><th>Observed</th><th>Source label</th><th>Kind</th><th>Rows</th><th>Missing cols</th></tr></thead>
              <tbody>
                {importsState.imports.map(imp => (
                  <tr key={imp.id}>
                    <td>{(imp.imported_at || '').slice(0, 10)}</td>
                    <td>{imp.observed_from || imp.observed_to ? `${imp.observed_from || '?'} → ${imp.observed_to || '?'}` : 'UNKNOWN'}</td>
                    <td>{imp.source_label}</td>
                    <td>{kindLabel(imp.kind)}</td>
                    <td>{imp.row_count}{imp.skipped_rows ? ` (+${imp.skipped_rows} term-less skipped)` : ''}</td>
                    <td>{(imp.missing_columns || []).length ? imp.missing_columns.join(', ') : 'none'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card" style={{ padding: 16, flex: '1 1 240px' }} data-testid="ba-status">
          <strong style={{ fontSize: 13 }}>Brand Analytics (Search Query Performance)</strong>
          {ba && ba.available ? (
            <div style={{ marginTop: 8, fontSize: 12 }}>
              <span className="pill pill-ok">IMPORTED</span>
              <div className="text-low" style={{ marginTop: 6 }}>
                Latest: {(ba.latest.imported_at || '').slice(0, 10)} · {ba.latest.source_label} · {ba.latest.row_count} row(s)
              </div>
              <div className="text-low" style={{ marginTop: 4 }}>{ba.banner.text}</div>
            </div>
          ) : (
            <div style={{ marginTop: 8, fontSize: 12 }}>
              <span className="pill pill-muted" data-testid="ba-unavailable">UNAVAILABLE</span>
              <div className="text-low" style={{ marginTop: 6 }}>
                No Brand Analytics file has been imported for this account. The studio will not stand in for it.
                {importsState.state === 'error' && ' (Backend unreachable — availability is UNKNOWN.)'}
              </div>
            </div>
          )}
          {sp && sp.available && (
            <div className="text-low" style={{ marginTop: 10, fontSize: 11 }}>
              Sponsored Products terms: latest import {(sp.latest.imported_at || '').slice(0, 10)}, {sp.row_count} row(s).
            </div>
          )}
        </div>
      </div>

      {/* ── Terms table ────────────────────────────────────────────────── */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 13 }}>Imported terms</strong>
          <input className="field" style={{ maxWidth: 220 }} placeholder="Search terms…" value={termQuery} onChange={e => setTermQuery(e.target.value)} />
          <select className="field" style={{ maxWidth: 220 }} value={kindFilter} onChange={e => setKindFilter(e.target.value)}>
            <option value="">Both report kinds</option>
            {KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
          <button className="btn btn-sm" onClick={() => reloadTerms(termQuery, kindFilter)}>Apply</button>
          <a className="btn btn-sm" href={termsExportHref({ q: termQuery, kind: kindFilter })} data-testid="terms-export">Export CSV</a>
          <button className="btn btn-sm btn-primary" disabled={briefBusy || shownTerms.length === 0} onClick={runBrief} data-testid="brief-run">
            {briefBusy ? 'Composing…' : 'Create brief from the shown terms'}
          </button>
        </div>
        <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
          Ranked by clicks, highest first — with the click-only bias attached to every ranking. An empty
          cell in the export or an UNKNOWN here means the column was absent from the file.
        </div>

        {termsState.state === 'error' ? (
          <div className="alert alert-warn" style={{ marginTop: 10 }}>
            <div className="alert-title">Terms could not be read</div>
            <div className="alert-text" style={{ fontSize: 12 }}>Reason: {termsState.reason}. This is not an empty dataset.</div>
          </div>
        ) : shownTerms.length === 0 ? (
          <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>No terms to show. Import a report above, or widen the filter.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ marginTop: 8, fontSize: 12 }} data-testid="terms-table">
              <thead>
                <tr>
                  <th>Term</th><th>Campaign</th><th>Match</th>
                  <th>Impressions</th><th>Clicks</th><th>Orders</th><th>Spend</th><th>Sales</th>
                  <th>Observed</th><th>Kind</th>
                </tr>
              </thead>
              <tbody>
                {shownTerms.map(t => (
                  <tr key={t.id}>
                    <td>{t.term}</td>
                    <td>{t.campaign || 'UNKNOWN'}</td>
                    <td>{t.match_type || 'UNKNOWN'}</td>
                    <td>{fmt(t.impressions)}</td>
                    <td>{fmt(t.clicks)}</td>
                    <td>{fmt(t.orders)}</td>
                    <td>{fmt(t.spend)}</td>
                    <td>{fmt(t.sales)}</td>
                    <td>{t.row_from || t.row_to ? `${t.row_from || '?'} → ${t.row_to || '?'}` : 'UNKNOWN'}</td>
                    <td>{t.kind === 'brand_analytics_sqp' ? 'BA SQP' : 'SP terms'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {termsState.counts && termsState.state === 'ready' && (
          <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
            {termsState.counts.total} term row(s) shown · {termsState.counts.without_clicks_column} without a clicks column (UNKNOWN, not zero)
          </div>
        )}
      </div>

      {/* ── Brief output ───────────────────────────────────────────────── */}
      {briefState && (
        <div className="card" style={{ padding: 16 }} data-testid="brief-panel">
          {briefState.state === 'ready' ? (
            <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <strong style={{ fontSize: 13 }}>Creative brief</strong>
                <span className="pill pill-muted">composed — nothing generated</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginTop: 10, fontSize: 12 }}>
                <div><div className="label">Objective</div>{briefState.brief.objective}</div>
                <div><div className="label">Audience</div>{briefState.brief.audience}</div>
                <div><div className="label">Voice</div>{briefState.brief.voice}</div>
                <div><div className="label">Promise</div>{briefState.brief.promise}</div>
              </div>
              <table className="table" style={{ marginTop: 12, fontSize: 12 }}>
                <thead>
                  <tr>
                    <th>Term</th><th>Impressions</th><th>Clicks</th><th>Orders</th><th>Spend</th><th>Sales</th>
                    <th>Observed</th><th>Sample</th><th>Confidence note</th>
                  </tr>
                </thead>
                <tbody>
                  {briefState.brief.ranked_terms.map((r, i) => (
                    <tr key={i}>
                      <td>{r.evidence.term}{r.matched_keyword ? <> <span className="pill pill-muted">brand term</span></> : null}</td>
                      <td>{fmt(r.evidence.impressions)}</td>
                      <td>{fmt(r.evidence.clicks)}</td>
                      <td>{fmt(r.evidence.orders)}</td>
                      <td>{fmt(r.evidence.spend)}</td>
                      <td>{fmt(r.evidence.sales)}</td>
                      <td>{r.evidence.observed_from === 'UNKNOWN' ? 'UNKNOWN' : `${r.evidence.observed_from} → ${r.evidence.observed_to}`}</td>
                      <td><span className={`pill ${r.confidence.sample === 'large' ? 'pill-ok' : 'pill-muted'}`}>{r.confidence.sample}</span></td>
                      <td className="text-low" style={{ fontSize: 11 }}>
                        {r.confidence.note}
                        {r.bias && <div style={{ marginTop: 4 }}>{r.bias}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
                {briefState.brief.notes.map((n, i) => <div key={i}>• {n}</div>)}
              </div>
            </>
          ) : (
            <div className="alert alert-warn">
              <div className="alert-title">Brief not composed</div>
              <div className="alert-text" style={{ fontSize: 12 }}>{briefState.reason}</div>
            </div>
          )}
        </div>
      )}

      {/* ── Variants + performance comparison (item 6) ─────────────────── */}
      <div className="card" style={{ padding: 16 }} data-testid="variants-panel">
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <strong style={{ fontSize: 13 }}>Creative variants & performance</strong>
          <span className="pill pill-muted">user- or file-entered metrics only</span>
        </div>
        <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>
          Metrics here are entered by you or imported from a file you supply. This view never infers a
          number, and it makes no causation claim: Amazon's reports carry no creative identifier, so a
          difference cannot be attributed to a creative from this data.
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 10 }}>
          <div className="field-group" style={{ minWidth: 180 }}>
            <label className="label">New variant name</label>
            <input className="field" value={variantName} onChange={e => setVariantName(e.target.value)} placeholder="e.g. Hero v2 — warmer light" />
          </div>
          <div className="field-group" style={{ minWidth: 180 }}>
            <label className="label">Uploaded asset id (optional)</label>
            <input className="field" value={variantAssetId} onChange={e => setVariantAssetId(e.target.value)} placeholder="asset id from Assets" />
          </div>
          <button className="btn btn-sm" onClick={addVariant}>Add variant</button>
          <div className="field-group">
            <label className="label">Metrics file (CSV/JSON)</label>
            <input className="field" type="file" accept=".csv,.tsv,.json" onChange={onMetricsFile} data-testid="variant-metrics-file" />
          </div>
          <button className="btn btn-sm" onClick={runCompare} data-testid="compare-run">Refresh comparison</button>
        </div>
        {metricsFileMsg && (
          <div className="text-low" style={{ fontSize: 11, marginTop: 6 }} data-testid="metrics-import-result">
            {metricsFileMsg.state === 'ready'
              ? <>Metrics file: {metricsFileMsg.rows_added} row(s) attached; {metricsFileMsg.unmatched.length} unmatched (never turned into variants).</>
              : <>Metrics file failed: {metricsFileMsg.reason}. Nothing was stored.</>}
          </div>
        )}

        {variantsState.state === 'error' && (
          <div className="alert alert-warn" style={{ marginTop: 10 }}>
            <div className="alert-title">Variants could not be read</div>
            <div className="alert-text" style={{ fontSize: 12 }}>Reason: {variantsState.reason}.</div>
          </div>
        )}

        {variantsState.state === 'ready' && variantsState.variants.length === 0 ? (
          <div className="text-low" style={{ fontSize: 12, marginTop: 10 }}>No variants yet. Add one above to start a comparison.</div>
        ) : (
          <table className="table" style={{ marginTop: 10, fontSize: 12 }}>
            <thead><tr><th>Variant</th><th>Asset</th><th>Status</th><th>Metric rows</th><th>Add metric (user-entered)</th></tr></thead>
            <tbody>
              {(variantsState.variants || []).map(v => {
                const count = (variantsState.metrics || []).filter(m => m.variant_id === v.id).length
                const active = metricTarget === v.id
                return (
                  <tr key={v.id}>
                    <td>{v.name}</td>
                    <td>{v.asset_id || 'UNKNOWN'}</td>
                    <td>{v.status}</td>
                    <td>{count || 'none'}</td>
                    <td>
                      <button className="btn btn-sm" onClick={() => setMetricTarget(active ? '' : v.id)}>{active ? 'Cancel' : 'Add'}</button>
                      {active && (
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                          {['impressions', 'clicks', 'orders', 'spend', 'sales'].map(f => (
                            <input key={f} className="field" style={{ width: 90 }} placeholder={f} value={metricForm[f]}
                              onChange={e => setMetricForm({ ...metricForm, [f]: e.target.value })} />
                          ))}
                          <button className="btn btn-sm btn-primary" onClick={submitMetric}>Store</button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {compareState && compareState.state === 'ready' && (
          <div style={{ marginTop: 12 }} data-testid="variant-compare">
            <table className="table" style={{ fontSize: 12 }}>
              <thead><tr><th>Variant</th><th>Impressions</th><th>Clicks</th><th>Orders</th><th>Spend</th><th>Sales</th><th>Sources</th><th>Warnings</th></tr></thead>
              <tbody>
                {compareState.comparison.map(row => (
                  <tr key={row.variant.id}>
                    <td>{row.variant.name}</td>
                    <td>{fmt(row.totals.impressions)}</td>
                    <td>{fmt(row.totals.clicks)}</td>
                    <td>{fmt(row.totals.orders)}</td>
                    <td>{fmt(row.totals.spend)}</td>
                    <td>{fmt(row.totals.sales)}</td>
                    <td>{row.sources.length ? row.sources.join(', ') : 'none'}</td>
                    <td className="text-low" style={{ fontSize: 11 }}>{row.warnings.map((w, i) => <div key={i}>• {w}</div>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>
              {compareState.note}
              {compareState.attributionGap && <div style={{ marginTop: 4 }}>{compareState.attributionGap}</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
