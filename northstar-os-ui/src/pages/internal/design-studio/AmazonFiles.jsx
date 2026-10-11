// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — SECTION: ADS › AMAZON FILES (file-only workflow)
//
// NorthstarOS never signs in to Amazon. The seller downloads files from Amazon,
// uploads them here, approves proposed changes row by row, and receives a NEW
// change file to upload to Amazon manually. This surface:
//   • archives each upload read-only (checksum, observed range, validation);
//   • proposes row-level changes with before/after, evidence and blocks;
//   • refuses blocked rows and spend-limit rows without a second confirmation;
//   • writes the delta file and shows the round-trip proof;
//   • builds the A+ asset pack (NOT an uploadable module file).
// No provider call exists anywhere on this surface.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import { useToast } from '../../../components/ToastContext.jsx'

const API = '/api/design-studio'

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = null
    try { detail = (await res.json()).detail } catch { /* non-JSON */ }
    const err = new Error((detail && detail.message) || `http-${res.status}`)
    err.status = res.status
    err.code = detail && detail.code
    throw err
  }
  return res.json()
}

const fmt = (v) => (v === null || v === undefined || v === '' ? 'UNKNOWN' : String(v))

export default function AmazonFiles() {
  const { toast } = useToast()
  const [uploads, setUploads] = useState([])
  const [selectedUpload, setSelectedUpload] = useState(null)
  const [rows, setRows] = useState([])
  const [rowEdits, setRowEdits] = useState({}) // row_index -> {op, fields}
  const [proposals, setProposals] = useState([])
  const [spendLimit, setSpendLimit] = useState('')
  const [downloadedAt, setDownloadedAt] = useState('')
  const [fileName, setFileName] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastWrite, setLastWrite] = useState(null)
  const [aplusPack, setAplusPack] = useState(null)
  const [changeFiles, setChangeFiles] = useState([])
  const [reportChangeId, setReportChangeId] = useState('')
  const [reportMatch, setReportMatch] = useState(null)
  const [corrections, setCorrections] = useState({}) // report row index -> {drop, fields:{...}}
  const [correctResult, setCorrectResult] = useState(null)
  const [compareTarget, setCompareTarget] = useState('')
  const [compareResult, setCompareResult] = useState(null)
  const [showOnboarding, setShowOnboarding] = useState(false)

  const reloadUploads = useCallback(async () => {
    try {
      const j = await api('/amazon-files')
      setUploads(j.uploads || [])
    } catch { setUploads([]) }
  }, [])

  useEffect(() => { reloadUploads() }, [reloadUploads])

  const openUpload = useCallback(async (uid) => {
    setLastWrite(null)
    setAplusPack(null)
    setRowEdits({})
    setReportMatch(null)
    setCorrectResult(null)
    setCompareResult(null)
    setReportChangeId('')
    setCompareTarget('')
    try {
      const j = await api(`/amazon-files/${uid}`)
      setSelectedUpload(j.upload)
      const rj = await api(`/amazon-files/${uid}/rows?limit=200`)
      setRows(rj.rows || [])
      const pj = await api(`/amazon-files/${uid}/proposals`)
      setProposals(pj.proposals || [])
      const cj = await api(`/amazon-files/${uid}/changes`)
      setChangeFiles(cj.change_files || [])
    } catch (e) {
      toast(`Could not open the upload: ${e.message}`, 'error')
    }
  }, [toast])

  const onFile = async (e) => {
    const f = e.target.files && e.target.files[0]
    if (!f) return
    setBusy(true)
    try {
      const buf = await f.arrayBuffer()
      let binary = ''
      const bytes = new Uint8Array(buf)
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
      const j = await api('/amazon-files/upload', {
        method: 'POST',
        body: JSON.stringify({
          filename: f.name,
          content_b64: btoa(binary),
          downloaded_at: downloadedAt || null,
        }),
      })
      setFileName(f.name)
      toast(`Uploaded ${f.name}: detected ${j.upload.kind} (${j.upload.row_count} row(s)). Read-only archive.`, 'info')
      await reloadUploads()
      await openUpload(j.upload.id)
    } catch (err) {
      toast(`Upload refused: ${err.message}. Nothing was stored.`, 'error')
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  const editableFields = useMemo(() => {
    const kind = selectedUpload && selectedUpload.kind
    if (kind === 'ads_bulksheet' || kind === 'ads_search_terms') return ['bid', 'budget', 'state', 'match_type', 'keyword_text']
    if (kind === 'listing_template') return ['title', 'price', 'quantity']
    return []
  }, [selectedUpload])

  const patchEdit = (rowIndex, patch) => setRowEdits(prev => {
    const cur = prev[rowIndex] || { op: 'Update', fields: {} }
    return { ...prev, [rowIndex]: { ...cur, ...patch, fields: { ...cur.fields, ...(patch.fields || {}) } } }
  })

  const propose = async () => {
    const changes = Object.entries(rowEdits).map(([idx, e]) => ({
      sheet: (rows[Number(idx)] || {}).sheet || (selectedUpload.sheets[0] || {}).name,
      row_index: Number(idx),
      op: e.op,
      fields: Object.fromEntries(Object.entries(e.fields || {}).filter(([, v]) => v !== '')),
      reason: 'operator-proposed change',
    }))
    if (!changes.length) { toast('Select a row and set an operation first.', 'error'); return }
    setBusy(true)
    try {
      const j = await api(`/amazon-files/${selectedUpload.id}/proposals`, {
        method: 'POST',
        body: JSON.stringify({
          changes,
          spend_limit_cents: spendLimit ? Math.round(Number(spendLimit) * 100) : null,
        }),
      })
      setProposals(j.proposals || [])
      toast(`${j.proposals.length} proposal(s) built. Blocked rows cannot be approved; spend-limit rows need a second confirmation.`, 'info')
    } catch (e) {
      toast(`Proposals failed: ${e.message}`, 'error')
    } finally { setBusy(false) }
  }

  const decide = async (pid, action, second = false) => {
    try {
      await api(`/amazon-files/proposals/${pid}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ second_confirmation: second }),
      })
      const pj = await api(`/amazon-files/${selectedUpload.id}/proposals`)
      setProposals(pj.proposals || [])
    } catch (e) {
      toast(`${action} refused: ${e.message}`, 'error')
    }
  }

  const write = async () => {
    setBusy(true)
    try {
      const j = await api(`/amazon-files/${selectedUpload.id}/write`, { method: 'POST', body: JSON.stringify({}) })
      setLastWrite(j)
      toast(`Change file written: ${j.change_file.filename}. Round-trip: ${j.roundtrip.ok ? 'only the approved changes differ' : 'FAILED - do not upload'}.`, j.roundtrip.ok ? 'info' : 'error')
      const cj = await api(`/amazon-files/${selectedUpload.id}/changes`)
      setChangeFiles(cj.change_files || [])
    } catch (e) {
      toast(`Write refused: ${e.message}`, 'error')
    } finally { setBusy(false) }
  }

  const buildPack = async () => {
    try {
      const j = await api(`/amazon-files/${selectedUpload.id}/aplus-pack`, {
        method: 'POST',
        body: JSON.stringify({ assets: [{ name: 'hero.png', placement: 'Premium full-width image' }] }),
      })
      setAplusPack(j.pack)
      toast('A+ asset pack built. It is NOT an uploadable module file - assemble the module yourself.', 'info')
    } catch (e) {
      toast(`A+ pack failed: ${e.message}`, 'error')
    }
  }

  const fileToB64 = async (f) => {
    const buf = await f.arrayBuffer()
    let binary = ''
    const bytes = new Uint8Array(buf)
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return btoa(binary)
  }

  const matchReport = async (e) => {
    const f = e.target.files && e.target.files[0]
    if (!f) return
    if (!reportChangeId) { toast('Choose which change file the report belongs to first.', 'error'); e.target.value = ''; return }
    setBusy(true)
    try {
      const content_b64 = await fileToB64(f)
      const j = await api('/amazon-files/reports/match', {
        method: 'POST',
        body: JSON.stringify({ filename: f.name, content_b64, change_file_id: reportChangeId, downloaded_at: downloadedAt || null }),
      })
      setReportMatch(j)
      setCorrections({})
      setCorrectResult(null)
      toast(`Report matched: ${j.match.matched_count} row(s) linked, ${j.match.unmatched_count} unmatched (reported, never guessed).`, 'info')
      await reloadUploads()
    } catch (err) {
      toast(`Report refused: ${err.message}`, 'error')
    } finally {
      setBusy(false)
      e.target.value = ''
    }
  }

  const patchCorrection = (rowIndex, patch) => setCorrections(prev => {
    const cur = prev[rowIndex] || { drop: false, fields: {} }
    return { ...prev, [rowIndex]: { ...cur, ...patch, fields: { ...cur.fields, ...(patch.fields || {}) } } }
  })

  const writeCorrected = async () => {
    if (!reportMatch) return
    setBusy(true)
    try {
      const payload = Object.entries(corrections).map(([idx, c]) => ({
        row_index: (reportMatch.match.matches[Number(idx)] || {}).change ? reportMatch.match.matches[Number(idx)].change.row : Number(idx),
        drop: !!c.drop,
        fields: Object.fromEntries(Object.entries(c.fields || {}).filter(([, v]) => v !== '')),
      })).filter(c => c.drop || Object.keys(c.fields).length > 0)
      const j = await api(`/amazon-files/change/${reportMatch.change_file.id}/correct`, {
        method: 'POST',
        body: JSON.stringify({ corrections: payload }),
      })
      setCorrectResult(j)
      toast(`Corrected file written: ${j.change_file.filename}. Round-trip: ${j.roundtrip.ok ? 'only the corrections differ' : 'FAILED - do not upload'}.`, j.roundtrip.ok ? 'info' : 'error')
      if (selectedUpload) {
        const cj = await api(`/amazon-files/${selectedUpload.id}/changes`)
        setChangeFiles(cj.change_files || [])
      }
    } catch (e) {
      toast(`Corrected file refused: ${e.message}`, 'error')
    } finally { setBusy(false) }
  }

  const runCompare = async () => {
    if (!compareTarget) { toast('Choose the later file to compare against.', 'error'); return }
    setBusy(true)
    try {
      const j = await api(`/amazon-files/${selectedUpload.id}/compare`, {
        method: 'POST',
        body: JSON.stringify({ after_upload_id: compareTarget }),
      })
      setCompareResult(j)
      toast(`Compared ${j.comparison.count} entit(y/ies). A missing metric is UNKNOWN, never 0.`, 'info')
    } catch (e) {
      toast(`Comparison refused: ${e.message}`, 'error')
    } finally { setBusy(false) }
  }

  const downloadHref = (cid) => `${API}/amazon-files/change/${cid}/download`
  const SAMPLE_BASE = `${import.meta.env.BASE_URL}samples/amazon-files/`

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="amazon-files-workspace">
      {/* ── Seller onboarding: first-run guide + sample pack (item 11) ──── */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Icon name="compass" size={16} />
          <strong style={{ fontSize: 14 }}>New here? Start with the guide and the sample files</strong>
          <button className="btn btn-sm" onClick={() => setShowOnboarding(v => !v)} data-testid="af-onboarding-toggle">
            {showOnboarding ? 'Hide' : 'Show'} guide
          </button>
        </div>
        {showOnboarding && (
          <div style={{ marginTop: 10, fontSize: 12 }} data-testid="af-onboarding">
            <div style={{ fontWeight: 600 }}>Which files to download, and where</div>
            <ol style={{ margin: '6px 0 0 16px', padding: 0, lineHeight: 1.6 }}>
              <li><strong>Ads bulksheets</strong> — Amazon Ads console → Bulk operations → download the Sponsored Products / Brands / Display bulksheet for the entities you want to change.</li>
              <li><strong>Listing / inventory templates</strong> — Seller Central → Catalog → Add products via upload (or the category template) → download the CURRENT template; the tab-delimited .txt and .xlsx both work. An old template is flagged, and a legacy .xls is refused with its fix.</li>
              <li><strong>Search-term and Brand Analytics reports</strong> — Ads → Reports, and Brand Analytics → Search Query Performance.</li>
              <li><strong>A+ ASIN list</strong> — a simple two-column file (asin, contentReferenceKey) of the ASINs you want modules for.</li>
              <li><strong>Processing / error reports</strong> — after you upload a change file to Amazon yourself, download the report Amazon gives you and upload it here: rows are matched back to your change and its proposal, with the cause shown and a corrected resubmittable file offered.</li>
            </ol>
            <div style={{ fontWeight: 600, marginTop: 10 }}>What Northstar returns</div>
            <ul style={{ margin: '6px 0 0 16px', padding: 0, lineHeight: 1.6 }}>
              <li>A <strong>change file</strong> (a NEW version; changed rows only; the original is untouched) that you upload to Amazon yourself. Northstar never submits anything.</li>
              <li>An <strong>A+ asset pack</strong> — assets, copy slots, alt text and placement instructions. Never an uploadable module file.</li>
              <li>A <strong>corrected resubmittable file</strong> when a processing report shows errors.</li>
            </ul>
            <div style={{ fontWeight: 600, marginTop: 10 }}>Sample pack (synthetic, redacted)</div>
            <div className="text-low" style={{ marginTop: 4 }}>Try the whole round-trip with fake IDs before touching a real account file:</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }} data-testid="af-samples">
              {['sp_bulksheet.xlsx', 'sb_bulksheet.xlsx', 'sp_search_terms.xlsx', 'listing_template.txt',
                'listing_detail_template.txt', 'aplus_list.csv', 'ads_error_report.xlsx',
                'listing_processing_report.txt', 'metrics_before.xlsx', 'metrics_after.xlsx', 'README.txt'].map(n => (
                <a key={n} className="btn btn-sm" href={`${SAMPLE_BASE}${n}`} download>{n}</a>
              ))}
            </div>
            <div className="text-low" style={{ marginTop: 8 }}>
              No Amazon sign-in, no API, no credentials: every file here travels by your own download/upload. Nothing on this page contacts Amazon.
            </div>
          </div>
        )}
      </div>

      {/* ── Upload ──────────────────────────────────────────────────────── */}
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Icon name="upload" size={16} />
          <strong style={{ fontSize: 14 }}>Upload an Amazon file</strong>
          <span className="pill pill-muted">file-only — no Amazon sign-in, no API</span>
        </div>
        <div className="text-low" style={{ fontSize: 12, margin: 0, marginTop: 6 }}>
          Download the file from Amazon, upload it here, approve the changes, then upload the change file back to Amazon yourself.
          Supported: Ads bulksheets (.xlsx/.csv), listing/inventory templates (.txt/.xlsx), Brand Analytics, A+ ASIN lists. A legacy
          .xls is refused with the stated fix. Nothing on this page contacts Amazon.
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 10 }}>
          <div className="field-group" style={{ minWidth: 220 }}>
            <label className="label">File</label>
            <input className="field" type="file" accept=".xlsx,.xls,.csv,.tsv,.txt" onChange={onFile} data-testid="af-file" disabled={busy} />
          </div>
          <div className="field-group">
            <label className="label">Downloaded from Amazon on</label>
            <input className="field" type="date" value={downloadedAt} onChange={e => setDownloadedAt(e.target.value)} data-testid="af-downloaded" />
          </div>
          <div className="field-group" style={{ minWidth: 160 }}>
            <label className="label">Spend limit (currency)</label>
            <input className="field" type="number" step="0.01" value={spendLimit} onChange={e => setSpendLimit(e.target.value)} placeholder="e.g. 1.00" data-testid="af-spend-limit" />
          </div>
        </div>
        {fileName && <div className="text-low" style={{ fontSize: 11, marginTop: 6 }}>Last upload: {fileName}</div>}
      </div>

      {/* ── Archive ─────────────────────────────────────────────────────── */}
      <div className="card" style={{ padding: 16 }}>
        <strong style={{ fontSize: 13 }}>Upload archive</strong>
        {uploads.length === 0 ? (
          <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>No files uploaded yet. The archive is empty — not a zero.</div>
        ) : (
          <table className="table" style={{ marginTop: 8, fontSize: 12 }} data-testid="af-archive">
            <thead><tr><th>File</th><th>Kind</th><th>Rows</th><th>Observed</th><th>Uploaded</th><th>Checksum</th><th /></tr></thead>
            <tbody>
              {uploads.map(u => (
                <tr key={u.id}>
                  <td>{u.filename}</td>
                  <td>{u.kind}</td>
                  <td>{u.row_count}</td>
                  <td>{u.observed_from ? `${u.observed_from} → ${u.observed_to || '?'}` : 'UNKNOWN'}</td>
                  <td>{(u.uploaded_at || '').slice(0, 10)}</td>
                  <td className="text-mono" style={{ fontSize: 10 }}>{(u.checksum || '').slice(0, 10)}…</td>
                  <td><button className="btn btn-sm" onClick={() => openUpload(u.id)}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Rows + proposals ───────────────────────────────────────────── */}
      {selectedUpload && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: 13 }}>{selectedUpload.filename}</strong>
            <span className="pill pill-muted">{selectedUpload.kind}</span>
            {selectedUpload.missing_columns.length > 0 && (
              <span className="pill pill-warn">missing: {selectedUpload.missing_columns.join(', ')} (UNKNOWN)</span>
            )}
          </div>
          {(selectedUpload.notes || []).map((n, i) => <div key={i} className="text-low" style={{ fontSize: 11, marginTop: 2 }}>• {n}</div>)}

          {selectedUpload.kind === 'aplus_asin_list' ? (
            <div style={{ marginTop: 10 }}>
              <button className="btn btn-sm btn-primary" onClick={buildPack} data-testid="af-aplus-pack">Build A+ asset pack</button>
              <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>
                A+ output is an asset pack plus instructions — never an uploadable module file. The ASIN bulk-upload limit is UNKNOWN (sources conflict).
              </div>
              {aplusPack && (
                <div className="alert" style={{ marginTop: 8 }} data-testid="af-aplus-result">
                  <div className="alert-title">A+ asset pack ({aplusPack.asins.length} ASIN(s)) — not an uploadable module file</div>
                  <div className="alert-text" style={{ fontSize: 12 }}>
                    {aplusPack.instructions.map((x, i) => <div key={i}>• {x}</div>)}
                    <div style={{ marginTop: 4 }}>ASIN bulk-upload limit: <strong>UNKNOWN</strong>. {aplusPack.asin_bulk_upload_limit_note}</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              <div style={{ overflowX: 'auto', marginTop: 8 }}>
                <table className="table" style={{ fontSize: 12 }} data-testid="af-rows">
                  <thead>
                    <tr>
                      <th>#</th><th>Entity / SKU</th><th>ID</th><th>Current</th><th>Operation</th><th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 50).map((r, i) => {
                      const edit = rowEdits[i] || { op: 'Update', fields: {} }
                      return (
                        <tr key={i}>
                          <td>{i}</td>
                          <td>{r.entity || r.sku || '—'}</td>
                          <td>{r.keyword_id || r.campaign_id || r.sku || '—'}</td>
                          <td className="text-low" style={{ fontSize: 11 }}>
                            {editableFields.map(f => r[f] ? `${f}=${r[f]} ` : '').join('') || '—'}
                          </td>
                          <td>
                            <select className="field" style={{ minWidth: 100 }} value={edit.op} data-testid={`af-op-${i}`}
                              onChange={e => patchEdit(i, { op: e.target.value })}>
                              {(selectedUpload.kind === 'listing_template'
                                ? ['Create', 'Update', 'Archive']
                                : ['Create', 'Update', 'Archive']).map(o => <option key={o} value={o}>{o}</option>)}
                            </select>
                          </td>
                          <td>
                            {editableFields.slice(0, 2).map(f => (
                              <input key={f} className="field" style={{ width: 120, marginRight: 4 }} placeholder={f}
                                value={(edit.fields && edit.fields[f]) || ''}
                                onChange={e => patchEdit(i, { fields: { [f]: e.target.value } })} />
                            ))}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-sm btn-primary" onClick={propose} disabled={busy} data-testid="af-propose">Propose selected changes</button>
                <button className="btn btn-sm" onClick={write} disabled={busy || !proposals.some(p => p.status === 'approved')} data-testid="af-write">Write change file</button>
              </div>
            </>
          )}

          {proposals.length > 0 && (
            <div style={{ marginTop: 12 }} data-testid="af-proposals">
              <strong style={{ fontSize: 12 }}>Proposals</strong>
              {proposals.map(p => (
                <div key={p.id} className="alert" style={{ marginTop: 8 }}>
                  <div className="alert-title">
                    [{p.status}] {p.entity || p.sheet} · {p.id_field || 'id'}={fmt(p.id_value)} · {p.op || '—'}
                  </div>
                  <div className="alert-text" style={{ fontSize: 12 }}>
                    <div>Before → after: {Object.keys(p.after || {}).map(k => `${k}: ${fmt(p.before && p.before[k])} → ${fmt(p.after[k])}`).join('; ') || '(operation only)'}</div>
                    <div>Reason: {p.reason}</div>
                    <div>Evidence: {p.evidence.filename} (downloaded {p.evidence.downloaded_at || 'UNKNOWN'}), checksum {(p.evidence.checksum || '').slice(0, 10)}…</div>
                    {p.stale && <div style={{ color: 'var(--status-warn, #a05a00)' }}>⚠ {p.stale_note}</div>}
                    {(p.title_flags || []).map((f, i) => (
                      <div key={i} style={{ color: 'var(--status-warn, #a05a00)' }}>⚑ {f.review} ({f.rule}): {f.detail}</div>
                    ))}
                    {(p.spend_notes || []).map((n, i) => <div key={i}>💰 {n}</div>)}
                    {(p.blocks || []).map((b, i) => <div key={i} style={{ color: 'var(--status-error, #b4432f)' }}>⛔ {b}</div>)}
                  </div>
                  <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                    {p.status === 'proposed' && (
                      <>
                        <button className="btn btn-sm" onClick={() => decide(p.id, 'approve', false)} data-testid={`af-approve-${p.id}`}>Approve</button>
                        {p.requires_second_confirmation && (
                          <button className="btn btn-sm btn-primary" onClick={() => decide(p.id, 'approve', true)} data-testid={`af-approve2-${p.id}`}>Approve with second confirmation</button>
                        )}
                        <button className="btn btn-sm btn-ghost" onClick={() => decide(p.id, 'reject')}>Reject</button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {lastWrite && (
            <div className="alert" style={{ marginTop: 12 }} data-testid="af-write-result">
              <div className="alert-title">Change file: {lastWrite.change_file.filename}</div>
              <div className="alert-text" style={{ fontSize: 12 }}>
                <div>Round-trip: {lastWrite.roundtrip.ok ? 'PASS — only the approved change(s) differ' : `FAILED — ${lastWrite.roundtrip.violations.join('; ')}`}</div>
                <div>Rows written: {lastWrite.roundtrip.written_count} · source checksum {(lastWrite.roundtrip.source_checksum || '').slice(0, 10)}… · written checksum {(lastWrite.roundtrip.written_checksum || '').slice(0, 10)}…</div>
                <div>The original upload was not modified. Upload this file to Amazon yourself.</div>
                <a className="btn btn-sm" style={{ marginTop: 6 }} href={downloadHref(lastWrite.change_file.id)} data-testid="af-download">Download change file</a>
              </div>
            </div>
          )}

          {/* ── Change files + processing report + corrected file (item 2) ── */}
          {changeFiles.length > 0 && (
            <div style={{ marginTop: 14 }} data-testid="af-changes">
              <strong style={{ fontSize: 12 }}>Change files written from this upload</strong>
              <table className="table" style={{ fontSize: 12, marginTop: 6 }}>
                <thead><tr><th>File</th><th>v</th><th>Rows</th><th>Written</th><th /></tr></thead>
                <tbody>
                  {changeFiles.map(c => (
                    <tr key={c.id}>
                      <td>{c.filename}</td>
                      <td>{c.version}</td>
                      <td>{c.row_count}</td>
                      <td>{(c.written_at || '').slice(0, 16).replace('T', ' ')}</td>
                      <td><a className="btn btn-sm" href={downloadHref(c.id)}>Download</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: 10, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div className="field-group" style={{ minWidth: 240 }}>
                  <label className="label">Processing report belongs to</label>
                  <select className="field" value={reportChangeId} onChange={e => setReportChangeId(e.target.value)} data-testid="af-report-change">
                    <option value="">— choose a change file —</option>
                    {changeFiles.map(c => <option key={c.id} value={c.id}>{c.filename}</option>)}
                  </select>
                </div>
                <div className="field-group">
                  <label className="label">Amazon processing / error report</label>
                  <input className="field" type="file" accept=".xlsx,.csv,.tsv,.txt" onChange={matchReport} disabled={busy} data-testid="af-report-file" />
                </div>
              </div>
              <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>
                Upload the report Amazon gave you after submitting a change file. Error rows are matched to your change rows and the proposals
                that produced them; a row whose ID is not in the change file is reported as unmatched, never guessed at.
              </div>
              {reportMatch && (
                <div className="alert" style={{ marginTop: 8 }} data-testid="af-report-match">
                  <div className="alert-title">
                    Matched {reportMatch.match.matched_count} row(s) · unmatched {reportMatch.match.unmatched_count}
                  </div>
                  <div className="alert-text" style={{ fontSize: 12 }}>
                    {reportMatch.match.matches.map((m2, i) => (
                      <div key={i} style={{ marginTop: 4 }}>
                        <div>Row {i}: {m2.id_field}={fmt(m2.id_value)} → change row {m2.change ? m2.change.row : '?'} · proposal {m2.proposal_id || 'UNKNOWN'}</div>
                        <div>Cause (quoted): {fmt(m2.cause)}</div>
                        {m2.fix_hint && <div>Hint: {m2.fix_hint}</div>}
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 4 }}>
                          <label style={{ fontSize: 11 }}>
                            <input type="checkbox" checked={!!(corrections[i] || {}).drop}
                              onChange={e => patchCorrection(i, { drop: e.target.checked })} /> drop this row
                          </label>
                          <input className="field" style={{ width: 200 }} placeholder="fix value (field=value? use the field name)"
                            data-testid={`af-correct-${i}`}
                            onChange={e => {
                              const v = e.target.value
                              const eq = v.indexOf('=')
                              if (eq > 0) patchCorrection(i, { fields: { [v.slice(0, eq).trim()]: v.slice(eq + 1).trim() } })
                            }} />
                        </div>
                      </div>
                    ))}
                    {reportMatch.match.unmatched.map((u2, i) => (
                      <div key={`u${i}`} style={{ marginTop: 4, color: 'var(--status-warn, #a05a00)' }}>
                        Unmatched: {u2.id_field}={fmt(u2.id_value)} — {u2.cause}
                      </div>
                    ))}
                    <div style={{ marginTop: 6 }}>{reportMatch.match.note}</div>
                    <button className="btn btn-sm btn-primary" style={{ marginTop: 6 }} onClick={writeCorrected} disabled={busy} data-testid="af-write-corrected">
                      Write corrected resubmittable file
                    </button>
                  </div>
                </div>
              )}
              {correctResult && (
                <div className="alert" style={{ marginTop: 8 }} data-testid="af-correct-result">
                  <div className="alert-title">Corrected file: {correctResult.change_file.filename}</div>
                  <div className="alert-text" style={{ fontSize: 12 }}>
                    <div>Round-trip: {correctResult.roundtrip.ok ? 'PASS — only the corrections differ' : `FAILED — ${correctResult.roundtrip.violations.join('; ')}`}</div>
                    <div>Dropped rows: {correctResult.dropped} · rows kept: {correctResult.roundtrip.written_count}</div>
                    <div>The original upload and the previous change file are untouched. Upload the corrected file to Amazon yourself.</div>
                    <a className="btn btn-sm" style={{ marginTop: 6 }} href={downloadHref(correctResult.change_file.id)} data-testid="af-download-corrected">Download corrected file</a>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Before/after performance comparison (item 5) ─────────────── */}
          {(selectedUpload.kind === 'ads_bulksheet' || selectedUpload.kind === 'ads_search_terms') && uploads.length > 1 && (
            <div style={{ marginTop: 14 }} data-testid="af-compare">
              <strong style={{ fontSize: 12 }}>Before / after comparison</strong>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 6 }}>
                <div className="field-group" style={{ minWidth: 260 }}>
                  <label className="label">Compare against (the LATER file)</label>
                  <select className="field" value={compareTarget} onChange={e => setCompareTarget(e.target.value)} data-testid="af-compare-target">
                    <option value="">— choose a later upload —</option>
                    {uploads.filter(u => u.id !== selectedUpload.id).map(u => (
                      <option key={u.id} value={u.id}>{u.filename} ({u.kind})</option>
                    ))}
                  </select>
                </div>
                <button className="btn btn-sm" onClick={runCompare} disabled={busy} data-testid="af-compare-run">Compare</button>
              </div>
              {compareResult && (
                <div style={{ marginTop: 8 }} data-testid="af-compare-result">
                  <div className="alert-text" style={{ fontSize: 12 }}>
                    <div><strong>No causation:</strong> {compareResult.comparison.causation}</div>
                    <div>{compareResult.comparison.stale_window_note}</div>
                  </div>
                  <table className="table" style={{ fontSize: 12, marginTop: 6 }}>
                    <thead><tr><th>Entity</th><th>In</th><th>Impr (b→a)</th><th>Clicks (b→a)</th><th>Spend (b→a)</th><th>Δ clicks</th><th>Sample</th></tr></thead>
                    <tbody>
                      {compareResult.comparison.rows.slice(0, 40).map(r => (
                        <tr key={r.key}>
                          <td className="text-mono" style={{ fontSize: 11 }}>{r.key}</td>
                          <td>{r.present_in}</td>
                          <td>{fmt(r.metrics.impressions.before)} → {fmt(r.metrics.impressions.after)}</td>
                          <td>{fmt(r.metrics.clicks.before)} → {fmt(r.metrics.clicks.after)}</td>
                          <td>{fmt(r.metrics.spend.before)} → {fmt(r.metrics.spend.after)}</td>
                          <td>{fmt(r.delta_clicks)}</td>
                          <td>{r.sample && r.sample.sample ? `${r.sample.sample} (${fmt(r.sample.clicks)} clicks)` : 'UNKNOWN'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="text-low" style={{ fontSize: 11, marginTop: 4 }}>{compareResult.comparison.note}</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
