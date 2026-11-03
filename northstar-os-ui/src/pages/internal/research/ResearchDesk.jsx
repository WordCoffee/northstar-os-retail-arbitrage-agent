// ═══════════════════════════════════════════════════════════════════════════
// AUTOTHINK — RESEARCH DESK (U10)
//
// Query the local curated corpus, read the sources it returns, and choose how
// deep to look. It is a deterministic keyword search over an index the operator
// owns — not a web crawler, not a semantic model, and not a claim about quality.
//
// HONESTY CONTRACT
//   • The caveats the API returns are shown verbatim, next to the results.
//   • A depth mode changes the number of records asked for; it never claims a
//     better answer, and the panel says so.
//   • An empty index or an unreachable API is stated, never filled with samples.
// ═══════════════════════════════════════════════════════════════════════════

import { useState } from 'react'

import Icon from '../../../components/Icon.jsx'
import { DataTable } from '../../../components/Shared.jsx'
import { useToast } from '../../../components/ToastContext.jsx'

const API = '/api/corpus'
// Anonymous callers sit in a 30/min bucket; the dev identity shim keeps this lane
// out of it. Production has a real session and sends no shim.
const DEV_HEADERS = import.meta.env.DEV ? { 'X-User-Id': 'demo-t2' } : {}

export const DEPTH_MODES = [
  { id: 'quick', label: 'Quick', limit: 10, note: 'The first 10 records. Fast, shallow.' },
  { id: 'standard', label: 'Standard', limit: 20, note: 'The first 20 records. The default.' },
  { id: 'deep', label: 'Deep', limit: 50, note: 'Up to 50 records. Slower, wider, same index.' },
]

async function getJson(path, params) {
  const url = new URL(`${API}${path}`, window.location.origin)
  for (const [k, v] of Object.entries(params || {})) url.searchParams.set(k, String(v))
  const send = () => fetch(url.toString(), { credentials: 'include', headers: DEV_HEADERS })
  let res = await send()
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

function recordTitle(r) {
  return r.title || r.name || r.source_id || r.id || 'untitled record'
}

export default function ResearchDesk() {
  const { toast } = useToast()
  const [query, setQuery] = useState('')
  const [depth, setDepth] = useState('standard')
  const [state, setState] = useState({ phase: 'idle' })

  const mode = DEPTH_MODES.find((d) => d.id === depth) || DEPTH_MODES[1]

  const run = async (e) => {
    if (e) e.preventDefault()
    const q = query.trim()
    if (!q) return
    setState({ phase: 'loading', query: q, depth: mode.id })
    try {
      const out = await getJson('/search', { q, limit: mode.limit })
      setState({ phase: 'done', query: q, depth: mode.id, out })
      if (!out.count) toast(`No corpus record matches "${q}". The index is not filled in for this.`, 'info')
    } catch (err) {
      setState({ phase: 'error', query: q, depth: mode.id, error: err.message || 'the search call failed' })
    }
  }

  const out = state.phase === 'done' ? state.out : null
  const matches = (out && out.matches) || []

  return (
    <div className="subview stack" style={{ gap: 14 }} data-testid="research-desk">
      <div className="card">
        <div className="card-head">
          <h3 className="card-title">Research desk</h3>
          <span className="pill pill-forest">local corpus · no web crawl</span>
        </div>
        <form onSubmit={run} className="stack" style={{ gap: 10 }}>
          <label className="stack" style={{ gap: 4 }}>
            <span className="text-low" style={{ fontSize: 11 }}>What are you researching?</span>
            <input className="field" data-testid="rd-query" value={query}
                   onChange={(e) => setQuery(e.target.value)}
                   placeholder="e.g. lion's mane extract sourcing" />
          </label>
          <div className="inline-flex" style={{ gap: 6, flexWrap: 'wrap' }}>
            {DEPTH_MODES.map((d) => (
              <button key={d.id} type="button" title={d.note}
                      className={`btn btn-sm ${depth === d.id ? 'btn-primary' : ''}`}
                      data-testid={`rd-depth-${d.id}`} onClick={() => setDepth(d.id)}>
                {d.label} · {d.limit}
              </button>
            ))}
          </div>
          <div className="text-low" style={{ fontSize: 11 }} data-testid="rd-depth-note">{mode.note}</div>
          <div>
            <button className="btn btn-sm btn-primary" type="submit" data-testid="rd-run"
                    disabled={state.phase === 'loading' || !query.trim()}>
              <Icon name="search" size={13} /> {state.phase === 'loading' ? 'Searching...' : 'Search the corpus'}
            </button>
          </div>
        </form>
      </div>

      {state.phase === 'error' && (
        <div className="alert" data-testid="rd-error">
          <div className="alert-title">The corpus could not be searched</div>
          <div className="alert-text">{state.error} — nothing is shown rather than sample rows.</div>
        </div>
      )}

      {out && (
        <div className="card" data-testid="rd-results">
          <div className="card-head">
            <h3 className="card-title">Sources</h3>
            <span className="pill pill-muted" data-testid="rd-count">
              {out.count} record(s) · {state.depth} depth
            </span>
          </div>
          {out.count === 0 ? (
            <p style={{ fontSize: 13 }}>
              No record in the local index matches “{state.query}”. The index only holds what has been
              ingested — an empty result is not evidence that nothing exists.
            </p>
          ) : (
            <DataTable
              columns={[
                { key: 'title', label: 'Record', render: (v, row) => recordTitle(row) },
                { key: 'source', label: 'Source', render: (v) => v || 'UNKNOWN' },
                { key: 'license', label: 'Licence', render: (v) => v || 'UNKNOWN' },
                {
                  key: 'url',
                  label: 'Link',
                  render: (v) => (v
                    ? <a href={v} target="_blank" rel="noreferrer noopener">open</a>
                    : <span className="text-low">none</span>),
                },
              ]}
              rows={matches}
            />
          )}
          {(out.caveats || []).length > 0 && (
            <ul className="text-low" style={{ fontSize: 11, marginTop: 10, paddingLeft: 18 }} data-testid="rd-caveats">
              {out.caveats.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
