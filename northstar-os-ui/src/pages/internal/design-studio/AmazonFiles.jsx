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
    try {
      const j = await api(`/amazon-files/${uid}`)
      setSelectedUpload(j.upload)
      const rj = await api(`/amazon-files/${uid}/rows?limit=200`)
      setRows(rj.rows || [])
      const pj = await api(`/amazon-files/${uid}/proposals`)
      setProposals(pj.proposals || [])
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

  const downloadHref = (cid) => `${API}/amazon-files/change/${cid}/download`

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="amazon-files-workspace">
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
        </div>
      )}
    </div>
  )
}
