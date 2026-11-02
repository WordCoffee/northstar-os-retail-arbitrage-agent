// Deliverables — the folder a run leaves behind, exactly as written to disk.
//
// Honesty contract: this panel renders only what `GET /api/design-studio/deliverables`
// returns. An empty list says so; it never seeds a sample row, and a field the
// manifest omits is shown as unknown rather than filled in here.

import { useCallback, useEffect, useState } from 'react'

async function fetchDeliverables() {
  const res = await fetch('/api/design-studio/deliverables', { credentials: 'same-origin' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export default function Deliverables() {
  const [state, setState] = useState({ loading: true, error: '', rows: [] })

  const load = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: '' }))
    try {
      const data = await fetchDeliverables()
      setState({ loading: false, error: '', rows: data.deliverables || [] })
    } catch (err) {
      setState({ loading: false, error: String(err.message || err), rows: [] })
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="deliverables-panel">
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 16 }}>Deliverables</h3>
            <div className="text-low" style={{ marginTop: 4 }}>
              Every render that passed the form-adherence gate is written to its own
              folder with the brief, the verdict, the citations and a manifest.
            </div>
          </div>
          <button type="button" className="btn btn-sm" onClick={load} disabled={state.loading}
                  data-testid="deliverables-refresh">
            {state.loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        {state.error && (
          <div className="text-low" role="alert" style={{ marginTop: 12 }} data-testid="deliverables-error">
            Could not read deliverables: {state.error}
          </div>
        )}

        {!state.error && !state.loading && state.rows.length === 0 && (
          <div className="text-low" style={{ marginTop: 12 }} data-testid="deliverables-empty">
            No deliverables yet. A run only creates one when the vision gate accepts the render.
          </div>
        )}

        {state.rows.map(row => (
          <div key={row.run_id} className="card" style={{ padding: 12, marginTop: 12 }}
               data-testid="deliverable-row">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div><strong>{row.run_id}</strong></div>
                <div className="text-low" style={{ fontSize: 12, marginTop: 4 }}>
                  {row.created_at}
                  {' · '}
                  {Array.isArray(row.image_size)
                    ? `${row.image_size[0]}×${row.image_size[1]}`
                    : 'size unknown'}
                  {' · '}
                  {typeof row.bytes === 'number' ? `${Math.round(row.bytes / 1024)} KB` : 'bytes unknown'}
                </div>
                <div className="text-low" style={{ marginTop: 6 }}>{row.brief}</div>
              </div>
              <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                <span className={row.adherence?.ok ? 'pill pill-ok' : 'pill pill-warn'}>
                  {row.adherence?.ok ? 'form matched' : 'form not matched'}
                </span>
                <div className="text-low" style={{ fontSize: 12, marginTop: 6 }}>
                  {row.adherence?.requested || 'form unknown'}
                  {' → '}
                  {row.adherence?.observed || 'unknown'}
                </div>
                <div className="text-low" style={{ fontSize: 12, marginTop: 4 }}>
                  {row.quality?.verdict?.score
                    ? `quality ${row.quality.verdict.score} · ${row.quality.verdict.not_applicable?.length ? 'typography n/a' : 'all axes scored'}`
                    : 'quality not recorded'}
                </div>
              </div>
            </div>
            <div className="text-low" style={{ fontSize: 12, marginTop: 8 }}>
              {Array.isArray(row.files) && row.files.length
                ? row.files.join(' · ')
                : 'file list unknown'}
            </div>
            <img
              src={`/api/design-studio/deliverables/${encodeURIComponent(row.run_id)}/final`}
              alt={`Delivered render for ${row.run_id}`}
              loading="lazy"
              data-testid="deliverable-preview"
              style={{ display: 'block', marginTop: 10, maxWidth: '100%', maxHeight: 220,
                       borderRadius: 8, border: '1px solid var(--divider-mid, rgba(0,0,0,.12))' }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
