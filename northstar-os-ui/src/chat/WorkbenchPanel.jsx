// ═══════════════════════════════════════════════════════════════════════════
// WORKBENCH PANEL (V3 S5) — AutothinK premium surface.
//
// A right-hand drawer with three honest views of the current session:
//   • Plan      — the reconstructed tool chain (prompt → step → … → answer)
//   • Artifacts — every build artifact attached to this session
//   • Runs      — the bounded run ledger (chat turns / tool executions)
//
// Honesty contract: nothing is fabricated. An empty plan/artifact list says so;
// a missing asset is marked; a run that cannot be stopped is not pretend-stopped.
// The plan graph is drawn as a LINEAR chain on purpose — that is the true shape
// of the bounded tool loop. (The immersive node-link treatment is the deep-visual
// upgrade, not this functional view.)
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useState } from 'react'
import { chatApi, assetFileUrl } from './api.js'
import ImmersivePlanGraph from './ImmersivePlanGraph.jsx'

const TABS = [
  { id: 'plan', label: 'Plan' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'runs', label: 'Runs' },
]

function kindLabel(kind) {
  return { prompt: 'Prompt', tool: 'Step', answer: 'Answer' }[kind] || kind
}

function StatusBadge({ status }) {
  const s = String(status || 'unknown').toLowerCase()
  return <span className={`wb-badge wb-badge-${s}`}>{s}</span>
}

function relTime(ts) {
  if (!ts) return ''
  try {
    const mins = Math.round((Date.now() - new Date(ts).getTime()) / 60000)
    if (mins < 1) return 'now'
    if (mins < 60) return `${mins}m ago`
    const h = Math.round(mins / 60)
    return h < 24 ? `${h}h ago` : String(ts).slice(0, 10)
  } catch { return '' }
}

function ArtifactsView({ artifacts }) {
  if (!artifacts) return <div className="wb-empty">No artifacts loaded.</div>
  if (!artifacts.length) return <div className="wb-empty">This session has no saved artifacts yet.</div>
  return (
    <div className="wb-artifacts" data-testid="wb-artifacts">
      {artifacts.map((a, i) => {
        const isImage = (a.mime_type || '').startsWith('image/')
        return (
          <div key={`${a.asset_id}-${i}`} className="wb-artifact">
            <div className="wb-artifact-thumb">
              {isImage && a.present && a.asset_id
                ? <img src={assetFileUrl(a.asset_id)} alt={a.name} loading="lazy" />
                : <span className="wb-artifact-glyph">{a.present ? '▤' : '?'}</span>}
            </div>
            <div className="wb-artifact-meta">
              <div className="wb-artifact-name" title={a.name}>{a.name}</div>
              <div className="wb-artifact-sub">
                {a.asset_type || a.kind || 'artifact'}
                {a.state === 'missing_file' && ' · file missing'}
                {a.state === 'missing_metadata' && ' · not stored (no file)'}
                {a.state === 'missing_asset' && ' · record missing'}
              </div>
            </div>
            {a.file_present !== false && a.present !== false && a.asset_id && (
              <a className="wb-artifact-dl" href={assetFileUrl(a.asset_id)} download>Download</a>
            )}
          </div>
        )
      })}
    </div>
  )
}

function RunsView({ runs, sessionId, onCancel }) {
  if (!runs) return <div className="wb-empty">No runs loaded.</div>
  if (!runs.length) return <div className="wb-empty">No runs recorded yet.</div>
  return (
    <div className="wb-runs" data-testid="wb-runs">
      {runs.map((r) => (
        <div key={r.id} className={`wb-run ${r.session_id === sessionId ? 'wb-run-here' : ''}`}>
          <div className="wb-run-head">
            <StatusBadge status={r.status} />
            <span className="wb-run-label" title={r.label}>{r.label || r.kind}</span>
            <span className="wb-run-time">{relTime(r.created_at || r.started_at)}</span>
          </div>
          <div className="wb-run-sub">
            {r.kind}
            {r.session_id === sessionId && ' · this session'}
            {r.progress != null && r.progress > 0 &&
              <span className="wb-run-bar"><span style={{ width: `${Math.round(r.progress * 100)}%` }} /></span>}
          </div>
          {r.status === 'running' && (
            <button type="button" className="btn btn-sm btn-ghost"
              onClick={() => onCancel(r.id)} data-testid="wb-run-cancel">Cancel</button>
          )}
        </div>
      ))}
    </div>
  )
}

export default function WorkbenchPanel({ open, onClose, sessionId, focusId }) {
  const [tab, setTab] = useState('plan')
  const [plan, setPlan] = useState(null)
  const [artifacts, setArtifacts] = useState(null)
  const [runs, setRuns] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!open) return
    setBusy(true)
    setError('')
    try {
      if (tab === 'plan') {
        if (!sessionId) { setPlan({ nodes: [], caveats: [] }); }
        else setPlan(await chatApi.plan(sessionId))
      } else if (tab === 'artifacts') {
        if (!sessionId) { setArtifacts([]); }
        else setArtifacts((await chatApi.artifacts(sessionId)).artifacts || [])
      } else {
        setRuns((await chatApi.runs(50)).runs || [])
      }
    } catch (e) {
      setError(e.message || 'Failed to load')
    } finally {
      setBusy(false)
    }
  }, [open, tab, sessionId])

  useEffect(() => { load() }, [load])

  const cancelRun = useCallback(async (id) => {
    try { await chatApi.cancelRun(id) } catch { /* honest: the row will re-fetch */ }
    load()
  }, [load])

  if (!open) return null

  return (
    <aside className="wb-panel" aria-label="AutothinK workbench" data-testid="chat-workbench">
      <div className="wb-head">
        <div className="wb-rail" role="tablist" aria-label="Workbench views">
          {TABS.map((t) => (
            <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
              className={`wb-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)} data-testid={`wb-tab-${t.id}`}>
              {t.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={load}
          disabled={busy} title="Refresh" aria-label="Refresh workbench">↻</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}
          aria-label="Close workbench" data-testid="wb-close">&rsaquo;</button>
      </div>
      <div className="wb-sub">{focusId === 'autothink' ? 'AutothinK workbench' : 'Session workbench'}</div>
      {error && <div className="wb-error" data-testid="wb-error">{error}</div>}
      <div className="wb-body">
        {tab === 'plan' && <ImmersivePlanGraph plan={plan} />}
        {tab === 'artifacts' && <ArtifactsView artifacts={artifacts} />}
        {tab === 'runs' && <RunsView runs={runs} sessionId={sessionId} onCancel={cancelRun} />}
      </div>
    </aside>
  )
}
