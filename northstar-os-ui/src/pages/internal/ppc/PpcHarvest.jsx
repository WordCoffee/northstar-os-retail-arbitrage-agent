// ═══════════════════════════════════════════════════════════════════════════
// ADPILOT — PPC HARVEST LANE (U9)
//
// Report in, change log out, bulk file out. The operator uploads a search-term
// report they already have; the page parses it in the browser, the Python
// specialist decides what is worth harvesting or negating, and the operator
// downloads a validated sheet.
//
// HONESTY CONTRACT
//   • No Amazon API exists in this lane and none is contacted. Nothing is
//     uploaded to an ad platform, nothing is applied to an account.
//   • The file is parsed to rows in the browser; the file itself is not stored.
//   • A report with the wrong columns is REJECTED with the missing names.
//   • The bulk sheet's column layout is Northstar's own, not a verified Amazon
//     template, and the panel says so next to the download.
// ═══════════════════════════════════════════════════════════════════════════

import { useState } from 'react'

import Icon from '../../../components/Icon.jsx'
import { DataTable } from '../../../components/Shared.jsx'
import { useToast } from '../../../components/ToastContext.jsx'
import { readReport } from '../../../lib/ppcCsv.js'

const API = '/api/adpilot'
// The backend files anonymous callers in a 30/min bucket; the dev identity shim
// keeps this lane out of it. Production has a real session and sends no shim.
const DEV_HEADERS = import.meta.env.DEV ? { 'X-User-Id': 'demo-t2' } : {}

async function post(path, body) {
  const send = () => fetch(`${API}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...DEV_HEADERS },
    body: JSON.stringify(body),
  })
  let res = await send()
  // The API files anonymous callers in a 30/min bucket, and a room that loads
  // several panels can trip it. Honour Retry-After once, then say so plainly.
  if (res.status === 429) {
    const wait = Math.min(2000, Math.max(400, (Number(res.headers.get('Retry-After')) || 1) * 1000))
    await new Promise((resolve) => setTimeout(resolve, wait))
    res = await send()
  }
  if (!res.ok) {
    throw new Error(res.status === 429
      ? 'the API is rate-limiting this browser (30 calls a minute); wait a moment and try again'
      : `HTTP ${res.status}`)
  }
  return res.json()
}

function base64ToBlob(b64, mime) {
  const bin = atob(String(b64 || ''))
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
  return new Blob([bytes], { type: mime })
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

function ChangeTable({ title, rows, columns, empty, testId }) {
  return (
    <div className="card" style={{ marginTop: 16 }} data-testid={testId}>
      <div className="card-head">
        <h3 className="card-title" style={{ fontSize: 14 }}>{title}</h3>
        <span className="pill pill-muted">{rows.length} row(s)</span>
      </div>
      {rows.length === 0
        ? <p className="text-low" style={{ fontSize: 12 }}>{empty}</p>
        : <DataTable columns={columns} rows={rows} />}
    </div>
  )
}

export default function PpcHarvest() {
  const { toast } = useToast()
  const [state, setState] = useState({ phase: 'idle' })
  const [bulk, setBulk] = useState(null)
  const [building, setBuilding] = useState(false)

  const onFile = async (file) => {
    setBulk(null)
    setState({ phase: 'reading', name: file?.name || '' })
    const parsed = await readReport(file)
    if (!parsed.ok) {
      setState({ phase: 'error', error: parsed.error, name: file?.name || '' })
      toast(`Could not read that report: ${parsed.error}.`, 'warn')
      return
    }
    try {
      const analysis = await post('/analyze', { rows: parsed.rows, target_acos: 0.35 })
      setState({ phase: 'done', analysis, name: file?.name || '', rows: parsed.rows, read: parsed.rows.length })
      if (!analysis.ok) toast(`The report was rejected: ${analysis.error}`, 'warn')
    } catch (e) {
      setState({ phase: 'error', error: e.message || 'the analysis call failed', name: file?.name || '' })
    }
  }

  const buildBulk = async () => {
    if (state.phase !== 'done' || !state.analysis?.ok) return
    setBuilding(true)
    try {
      const out = await post('/bulk', { rows: state.rows, target_acos: 0.35 })
      setBulk(out)
      if (out.ok) {
        download(base64ToBlob(out.bytes_b64, out.mime), out.filename)
        toast(`Wrote ${out.filename} - ${out.rows} validated row(s), ${out.bytes.toLocaleString()} bytes.`, 'info')
      } else {
        toast(`The bulk file was refused: ${out.error || 'validation failed'}.`, 'warn')
      }
    } catch (e) {
      setBulk({ ok: false, error: e.message || 'the bulk call failed' })
    } finally {
      setBuilding(false)
    }
  }

  const analysis = state.phase === 'done' ? state.analysis : null

  return (
    <div className="subview stack" style={{ gap: 14 }} data-testid="ppc-harvest">
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Search-term report</h3>
          <span className="pill pill-forest">file only · no Amazon API</span>
        </div>
        <p className="text-low" style={{ fontSize: 12, marginBottom: 10 }}>
          Upload the search-term report you downloaded from your ads console. The page parses it here,
          sends the rows to the local analyst, and nothing is uploaded to any ad platform. A report with
          the wrong columns is rejected with the missing names rather than repaired.
        </p>
        <label className="btn btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <Icon name="upload" size={13} /> {state.phase === 'reading' ? 'Reading...' : 'Choose a CSV report'}
          <input type="file" accept=".csv,text/csv,text/plain" style={{ display: 'none' }}
                 data-testid="ppc-report-input"
                 onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }} />
        </label>
        {state.name && (
          <span className="text-low" style={{ fontSize: 11, marginLeft: 10 }} data-testid="ppc-report-name">
            {state.name}
          </span>
        )}
        <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
          Expected columns: campaign, ad group, customer search term, impressions, clicks, spend, sales, orders.
        </div>
      </div>

      {state.phase === 'error' && (
        <div className="alert" data-testid="ppc-error">
          <div className="alert-title">The report could not be analysed</div>
          <div className="alert-text">{state.error}</div>
        </div>
      )}

      {analysis && !analysis.ok && (
        <div className="alert" data-testid="ppc-rejected">
          <div className="alert-title">
            <span className="pill pill-warn">REJECTED</span> {analysis.status}
          </div>
          <div className="alert-text">
            {analysis.error}
            {analysis.expected && (
              <> Expected one of: <span className="text-mono">{analysis.expected.join(', ')}</span>.</>
            )}
          </div>
        </div>
      )}

      {analysis && analysis.ok && (
        <div data-testid="ppc-analysis">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Change log</h3>
              <span className="pill pill-muted">{state.read} row(s) read</span>
            </div>
            <p style={{ fontSize: 13 }} data-testid="ppc-summary">{analysis.summary}</p>
            <div className="text-low" style={{ fontSize: 11 }}>
              Target ACoS {(analysis.thresholds?.target_acos * 100).toFixed(0)}% ·
              {' '}negatives need {analysis.thresholds?.min_clicks_negative}+ clicks with no order ·
              every proposal carries the source row it came from
            </div>
          </div>

          <ChangeTable
            title="Harvest as exact-match keywords"
            testId="ppc-harvest-rows"
            rows={analysis.harvest || []}
            empty="No term converted inside the target ACoS. Nothing is invented to fill this table."
            columns={[
              { key: 'term', label: 'Search term', render: (v, row) => row.source_row?.['customer search term'] },
              { key: 'campaign', label: 'Campaign', render: (v, row) => row.source_row?.campaign },
              { key: 'orders', label: 'Orders' },
              { key: 'acos', label: 'ACoS', render: (v) => (v == null ? 'UNKNOWN' : `${(v * 100).toFixed(1)}%`) },
              { key: 'action', label: 'Proposed change' },
            ]}
          />

          <ChangeTable
            title="Negate (clicks, no orders)"
            testId="ppc-negative-rows"
            rows={analysis.negatives || []}
            empty="No term reached the click threshold with zero orders."
            columns={[
              { key: 'term', label: 'Search term', render: (v, row) => row.source_row?.['customer search term'] },
              { key: 'campaign', label: 'Campaign', render: (v, row) => row.source_row?.campaign },
              { key: 'clicks', label: 'Clicks' },
              { key: 'spend', label: 'Spend' },
              { key: 'action', label: 'Proposed change' },
            ]}
          />

          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-head">
              <h3 className="card-title">Bulk file</h3>
              <span className="pill pill-muted">validated before it is written</span>
            </div>
            <button className="btn btn-sm btn-primary" data-testid="ppc-build-bulk"
                    onClick={buildBulk} disabled={building}>
              <Icon name="download" size={13} /> {building ? 'Building...' : 'Build and download the bulk file'}
            </button>
            <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
              The column layout is Northstar&rsquo;s own, not a verified Amazon bulk template — map it to
              the current template before uploading. Nothing is uploaded from here.
            </div>
            {bulk && (
              <div className="text-low" style={{ fontSize: 12, marginTop: 8 }} data-testid="ppc-bulk-status">
                {bulk.ok
                  ? `${bulk.filename} - ${bulk.rows} row(s), ${bulk.bytes.toLocaleString()} bytes. ${bulk.note}`
                  : `Refused: ${bulk.error || 'validation failed'}`}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
