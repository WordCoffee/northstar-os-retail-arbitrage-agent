// Keywords & SEO intelligence — 1C-05 UI.
// Consumes REAL foundation keyword APIs. Unknown stays unavailable; page load
// performs zero provider calls and zero writes.
import { useEffect, useState } from 'react'
import { PageHead, Card, Metric } from '../../ui.jsx'
import foundationApi from '../api.js'
import { useSession, hasPerm } from '../session.jsx'
import { StateMessage } from '../components/StatusPrimitives.jsx'

export default function Keywords({ toast }) {
  const session = useSession()
  const canImport = hasPerm(session, 'run_local')
  const [state, setState] = useState({ status: 'loading' })
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [terms, setTerms] = useState([])
  const [sources, setSources] = useState(null)
  const [imports, setImports] = useState([])
  const [selected, setSelected] = useState(null)
  const [selectedRejected, setSelectedRejected] = useState([])
  const [gaps, setGaps] = useState([])

  const load = async () => {
    setState({ status: 'loading' })
    try {
      const [t, s, i, g] = await Promise.all([
        foundationApi.searchTerms(100),
        foundationApi.keywordSources(),
        foundationApi.imports(),
        foundationApi.keywordGaps(),
      ])
      setTerms(t.items || []); setSources(s); setImports(i.items || [])
      setGaps(g.items || [])
      setState({ status: 'ready' })
    } catch (e) { setState({ status: 'error', error: e }) }
  }

  useEffect(() => { load() }, [])

  const search = async () => {
    try { setResults((await foundationApi.keywordSearch(query, 50)).items || []) }
    catch (e) { toast(e.message, 'err') }
  }

  const selectKeyword = async (id) => {
    try { setSelected(await foundationApi.keyword(id)) }
    catch (e) { toast(e.message, 'err') }
  }

  const selectImport = async (id) => {
    try {
      setSelectedRejected((await foundationApi.importRejected(id)).items || [])
    } catch (e) { toast(e.message, 'err') }
  }

  const submitImport = async () => {
    const file = prompt('Source file name (in the local fixtures dir):', 'search_term_report_sample.csv')
    if (!file) return
    try {
      const r = await foundationApi.importSubmit(file, `ui-${Date.now()}`)
      toast(`Import submitted — ${r.job_id.slice(0, 8)}`, 'ok'); load()
    } catch (e) { toast(e.message, 'err') }
  }

  if (state.status === 'loading') return <div className="page" data-testid="keywords-status"><StateMessage state="loading" /></div>
  if (state.status === 'error') return (
    <div className="page" data-testid="keywords-status"><StateMessage state="error" title="Backend unavailable"
      detail={state.error?.message} onRetry={load} /></div>
  )

  const presentTypes = sources ? Object.entries(sources)
    .filter(([, v]) => v.status === 'PRESENT').map(([k]) => k) : []

  return (
    <div className="page" data-testid="keywords-status">
      <PageHead title="Keywords & SEO"
        sub="Shared keyword/search-term/target intelligence — local & imported data only"
        badges={[{ label: session.environment, tone: session.environment === 'sandbox' ? 'demo' : 'live' }]}
        right={<button className="btn" onClick={load}>Refresh</button>} />

      <div className="metric" style={{ marginTop: 14 }}>
        <Metric k="Search terms" v={terms.length} d="imported locally" />
        <Metric k="Keyword gaps" v={gaps.length} d="not yet targeted" />
        <Metric k="Imports" v={imports.length} d="batches" />
        <Metric k="Present sources" v={presentTypes.length} d={presentTypes.join(', ') || 'none'} />
      </div>

      <div className="stack" style={{ marginTop: 18 }}>
        <Card title="Keyword search" icon="prospector">
          <div className="stack">
            <label className="field-label" htmlFor="kw-search">Search phrase</label>
            <input id="kw-search" className="field" placeholder="e.g. dog leash"
                   value={query} onChange={(e) => setQuery(e.target.value)}
                   onKeyDown={(e) => e.key === 'Enter' && search()} />
            <button className="btn btn-primary" onClick={search}>Search</button>
          </div>
          {results.length === 0 && query ? (
            <div className="text-low" style={{ marginTop: 8 }}>No matching keywords (unknown stays unavailable).</div>
          ) : (
            <table className="table" style={{ marginTop: 8 }}>
              <thead><tr><th>Keyword</th><th>Match</th><th>Marketplace</th><th>Confidence</th><th>Targets</th></tr></thead>
              <tbody>
                {results.map((k) => (
                  <tr key={k.id}>
                    <td><button className="link" onClick={() => selectKeyword(k.id)}>{k.normalized_phrase}</button></td>
                    <td>{k.match_type}</td>
                    <td>{k.marketplace}</td>
                    <td>{k.confidence === null ? '—' : k.confidence}</td>
                    <td>{k.target_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {selected && (
          <Card title={`Keyword: ${selected.keyword?.normalized_phrase}`} icon="star">
            <div className="stack">
              <div className="text-low">
                original: {selected.keyword?.original_phrase} · match: {selected.keyword?.match_type} ·
                provenance: imported · freshness: {selected.keyword?.freshness_state}
              </div>
              <div className="text-low">Rank history: {selected.rank_history?.length || 0} observations</div>
              {selected.rank_history?.length ? selected.rank_history.map((r) => (
                <div key={r.id} className="list-row">
                  <span className="mono">{r.placement}</span>
                  <span style={{ flex: 1 }}>rank {r.rank === null ? 'unknown' : r.rank}</span>
                  <span className="mono text-low">{r.observed_at ? r.observed_at.slice(0, 10) : ''}</span>
                </div>
              )) : <div className="text-low" style={{ fontSize: 11 }}>No rank observations — unknown remains unavailable.</div>}
            </div>
          </Card>
        )}

        <Card title="Search-term performance" icon="gauge">
          {terms.length === 0 ? <StateMessage state="empty" title="No search terms imported" /> : (
            <table className="table">
              <thead><tr><th>Search term</th><th>Impr.</th><th>Clicks</th><th>Orders</th><th>Spend</th><th>Revenue</th></tr></thead>
              <tbody>
                {terms.slice(0, 25).map((t) => (
                  <tr key={t.id}>
                    <td>{t.raw_term}</td>
                    <td>{t.impressions ?? '—'}</td>
                    <td>{t.clicks ?? '—'}</td>
                    <td>{t.orders ?? '—'}</td>
                    <td>{t.spend ?? '—'}</td>
                    <td>{t.revenue ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card title="Source files" icon="gauge">
          <div className="stack">
            {sources ? Object.entries(sources).map(([rtype, info]) => (
              <div key={rtype} className="list-row">
                <span className={`status-pill ${info.status === 'PRESENT' ? 'on' : 'off'}`}>{info.status}</span>
                <span style={{ flex: 1 }}>{rtype}</span>
                <span className="mono text-low">{info.files.join(', ')}</span>
              </div>
            )) : <StateMessage state="empty" title="No source registry" />}
          </div>
        </Card>

        <Card title="Import history" icon="jobs">
          {canImport && <button className="btn btn-primary" style={{ marginBottom: 8 }} onClick={submitImport}>Submit import</button>}
          {imports.length === 0 ? <StateMessage state="empty" title="No imports yet" /> : (
            <table className="table">
              <thead><tr><th>Batch</th><th>Status</th><th>Accepted</th><th>Rejected</th><th>Via job</th></tr></thead>
              <tbody>
                {imports.map((b) => (
                  <tr key={b.id}>
                    <td><button className="link" onClick={() => selectImport(b.id)}>{b.id.slice(0, 8)}</button></td>
                    <td><span className={`status-pill ${b.status === 'completed' ? 'on' : ''}`}>{b.status}</span></td>
                    <td>{b.summary?.accepted_rows ?? '—'}</td>
                    <td>{b.summary?.rejected_rows ?? '—'}</td>
                    <td>{b.summary?.via_job ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        {selectedRejected.length > 0 && (
          <Card title="Rejected rows" icon="audit">
            <div className="stack">
              {selectedRejected.map((r) => (
                <div key={r.id} className="list-row">
                  <span className={`status-pill warn`}>row {r.row_index}</span>
                  <span style={{ flex: 1 }}>{r.rejection_reason}</span>
                  <span className="mono text-low">{JSON.stringify(r.row).slice(0, 60)}</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}