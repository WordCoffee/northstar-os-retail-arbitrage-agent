import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { PageHead, Card, Metric } from '../ui.jsx'
import { api } from '../services/api.js'

export default function Autothink({ toast }) {
  const [models, setModels] = useState(null)
  const [history, setHistory] = useState([])
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    (async () => {
      try {
        const m = await api.models()
        setModels(m.data)
      } catch { /* engine may be offline */ }
      try {
        const h = await api.autothinkHistory(8)
        setHistory(Array.isArray(h) ? h : h.items || [])
      } catch { /* ignore */ }
    })()
  }, [])

  const run = async () => {
    const q = query.trim() || 'Give a concise status of the retail arbitrage portfolio posture and 3 recommended next actions.'
    setRunning(true)
    setResult('')
    try {
      const res = await api.autothinkRun({ query: q, provider: 'local', tier: 'T2' })
      setResult(res.content || '(no output)')
      toast(`AutothinK ran in ${(res.elapsed_ms / 1000).toFixed(1)}s (${res.tokens.completion} tokens)`, 'ok')
    } catch (e) {
      setResult('')
      toast(`AutothinK failed: ${e.message}`, 'err')
    } finally {
      setRunning(false)
    }
  }

  const local = models?.local || {}
  const installed = local.installed || []

  return (
    <div className="page">
      <PageHead
        title="AutothinK"
        sub="AI decision engine — live local models and real runs"
        badges={[{ label: 'live · local engine', tone: 'live' }]}
        right={
          <button className="btn btn-primary" onClick={run} disabled={running}>
            <Icon name="brain" size={15} /> {running ? 'Running…' : 'Run'}
          </button>
        }
      />

      <div className="stack" style={{ marginTop: 14 }}>
        <Card title="Engine Status" icon="brain">
          <div className="metric">
            <Metric k="Engine" v="local" d="Ollama" tone="glow" />
            <Metric k="T2 Model" v={local.defaults?.T2 || 'northstaros-qwen3.8:27b'} d="default reasoning" tone="lime" />
            <Metric k="Installed Models" v={installed.length} d={installed.join(' · ') || 'none detected'} />
          </div>
          <div className="divider" />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {installed.map((m) => <span key={m} className="badge badge-live">{m}</span>)}
            {models?.cloud?.key_present ? <span className="badge badge-ok">cloud key present</span> : null}
          </div>
        </Card>

        <Card title="Decision Run" icon="create">
          <textarea className="field" placeholder="Ask AutothinK anything about your operation, or leave blank for a portfolio posture summary…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Autothink query" />
          {result && (
            <div className="list-row" style={{ marginTop: 10, whiteSpace: 'pre-wrap' }}>
              <div style={{ flex: 1, fontSize: 13 }}>{result}</div>
            </div>
          )}
        </Card>

        <Card title="Recent Runs" icon="gauge">
          {history.length === 0 ? (
            <div className="text-low" style={{ fontSize: 12 }}>No recent runs yet — hit Run above.</div>
          ) : (
            <div className="stack">
              {history.slice(0, 6).map((h, i) => (
                <div key={i} className="list-row">
                  <Icon name="brain" size={16} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12.5 }}>{h.query || h.prompt || '(run)'}</div>
                    <div className="text-low mono" style={{ fontSize: 10.5 }}>{h.model || h.provider || ''} · {(h.elapsed_ms ? (h.elapsed_ms / 1000).toFixed(1) + 's' : h.created_at || h.timestamp || '')}</div>
                  </div>
                  <span className="badge badge-live">{h.tier || 'T2'}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}