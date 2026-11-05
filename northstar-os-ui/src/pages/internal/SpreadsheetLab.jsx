import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import ReasoningModelSelector, { useReasoningModel } from '../../components/ReasoningModelSelector.jsx'
import foundationApi from '../../foundation/api.js'
import { useToast } from '../../components/ToastContext.jsx'
import { useState, useMemo } from 'react'

function parseCsv(text) {
  const lines = text.replace(/\r\n/g, '\n').split('\n').filter(l => l.trim())
  if (lines.length === 0) return { columns: [], rows: [] }
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
  const rows = lines.slice(1).map((line, idx) => {
    const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''))
    const row = { _row_index: idx + 2 }
    headers.forEach((h, i) => { row[h] = values[i] !== undefined ? values[i] : '' })
    return row
  })
  return { columns: headers, rows }
}

function downloadCsv(rows, columns, filename) {
  const cols = columns.length ? columns : Object.keys(rows[0] || {}).filter(k => k !== '_row_index')
  const escape = (v) => {
    const s = v == null ? '' : String(v)
    if (s.includes(',') || s.includes('"') || s.includes('\n')) return '"' + s.replace(/"/g, '""') + '"'
    return s
  }
  const csv = [cols.map(escape).join(','), ...rows.map(r => cols.map(c => escape(r[c])).join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function SpreadsheetLab() {
  const { selectedModel, catalog, persist } = useReasoningModel()
  const { toast } = useToast()
  const [raw, setRaw] = useState('sku,name,cost,price\nSKU-001,Water Filter,12.00,29.99\nSKU-002,LED Lamp,8.50,19.99\nSKU-003,,9.00,15.99')
  const [state, setState] = useState({ phase: 'idle' })
  const [analysis, setAnalysis] = useState(null)

  const { columns, rows } = useMemo(() => parseCsv(raw), [raw])

  const analyze = async () => {
    if (!(catalog && catalog.armed)) {
      toast('Hosted reasoning is not armed. Set OPENCODE_GO_ENABLED=1 and supply a key.', 'warn')
      return
    }
    if (rows.length === 0) {
      toast('Paste or upload a non-empty CSV first.', 'warn')
      return
    }
    setState({ phase: 'submitting' })
    try {
      const r = await foundationApi.reasoningSpreadsheetAnalysis({
        rows,
        columns,
        file_name: 'spreadsheet-lab.csv',
        model: selectedModel?.id,
      })
      setAnalysis(r.analysis)
      setState({ phase: 'done' })
    } catch (e) {
      setState({ phase: 'error', message: e.message || 'Analysis failed.' })
    }
  }

  const onFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = (ev) => { setRaw(ev.target.result) }
    reader.readAsText(f)
  }

  return (
    <PageLayout
      title="Spreadsheet Lab"
      subtitle="Ingest, analyze, and prepare spreadsheet exports — deterministic application code with hosted reasoning assistance."
      actions={<>
        <input type="file" accept=".csv,.txt" id="ss-upload" style={{ display: 'none' }} onChange={onFile} />
        <label htmlFor="ss-upload" className="btn btn-sm">Upload CSV</label>
      </>}
    >
      <DataNotice tone="internal" title="Manual workflow only">
        Paste or upload a CSV, run hosted analysis, review the structured report, then export a cleaned CSV for manual use. No automatic publishing, no overwrite of the source file.
      </DataNotice>

      <div className="grid-2" style={{ gap: 16 }}>
        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Input data</h3>
            <span className="pill pill-muted">{rows.length} rows · {columns.length} columns</span>
          </div>
          <ReasoningModelSelector value={selectedModel?.id} onChange={persist} />
          <textarea aria-label="Spreadsheet data"
            className="field"
            rows={12}
            value={raw}
            onChange={e => setRaw(e.target.value)}
            style={{ marginTop: 12, fontFamily: 'var(--font-mono)', fontSize: 12 }}
          />
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-sm" onClick={analyze} disabled={state.phase === 'submitting' || !(catalog && catalog.armed)}>
              {state.phase === 'submitting' ? 'Analyzing…' : 'Analyze with hosted reasoning'}
            </button>
            {!(catalog && catalog.armed) && <span className="text-low" style={{ fontSize: 11, marginLeft: 8 }}>Hosted reasoning not armed.</span>}
          </div>
          {state.phase === 'error' && <div className="pill pill-warn" style={{ marginTop: 10 }}>{state.message}</div>}
        </div>

        <div className="card">
          <div className="card-head">
            <h3 className="card-title">Preview</h3>
            <span className="pill pill-muted">untrusted input</span>
          </div>
          {rows.length > 0 ? (
            <DataTable
              columns={columns.slice(0, 6).map(c => ({ key: c, label: c }))}
              rows={rows.slice(0, 10)}
            />
          ) : <p className="text-low" style={{ fontSize: 13 }}>Paste CSV data to preview rows.</p>}
        </div>
      </div>

      {analysis && (
        <div className="card" data-testid="ss-analysis" style={{ marginTop: 20 }}>
          <div className="card-head">
            <h3 className="card-title">Analysis report</h3>
            <span className={`pill ${analysis.ok ? 'pill-ok' : 'pill-warn'}`}>{analysis.ok ? 'analysis ok' : 'analysis failed'}</span>
          </div>
          {analysis.provenance && <div className="text-low" style={{ fontSize: 11, marginBottom: 10 }}>Model: {analysis.provenance.model}</div>}
          <div style={{ fontSize: 13, marginBottom: 12 }}>{analysis.summary}</div>
          {analysis.warnings && analysis.warnings.length > 0 && (
            <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
              {analysis.warnings.map((w, i) => <span key={i} className="pill pill-warn" style={{ fontSize: 10 }}>{w}</span>)}
            </div>
          )}
          {analysis.anomalies && analysis.anomalies.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Anomalies</div>
              <ul style={{ fontSize: 12, marginTop: 4, paddingLeft: 16 }}>{analysis.anomalies.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </div>
          )}
          {analysis.inferred_formulas && analysis.inferred_formulas.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div className="text-low" style={{ fontSize: 11 }}>Inferred formula patterns</div>
              <DataTable columns={[{ key: 'column', label: 'Column' }, { key: 'formula_pattern', label: 'Pattern' }]} rows={analysis.inferred_formulas} />
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-sm" onClick={() => downloadCsv(rows, columns, 'spreadsheet-lab-cleaned.csv')}>Export cleaned CSV</button>
            <span className="text-low" style={{ fontSize: 11 }}>Export is deterministic; review before manual upload.</span>
          </div>
        </div>
      )}
    </PageLayout>
  )
}
