import { useEffect, useState, useCallback } from 'react'
import TysOpsPanel from './TysOpsPanel.jsx'

// Improvement room — the operator's view of the continuous improvement engine.
// Read-mostly: the only actions are "dry run", "run one cycle", and the stop
// switch. A real cycle rewrites knowledge packs, so it is deliberately explicit.

const BASE = '/api/v1/improvement'

async function call(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const j = await res.json(); if (j.detail) detail = j.detail } catch { /* ignore */ }
    throw new Error(String(detail))
  }
  return res.json()
}

const card = {
  background: 'var(--surface, #fbf8f1)',
  border: '1px solid var(--line, #ddd5c7)',
  borderRadius: 14,
  padding: 18,
  marginBottom: 16,
}
const row = { display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }
const btn = {
  padding: '8px 14px',
  borderRadius: 10,
  border: '1px solid var(--line, #ddd5c7)',
  background: 'transparent',
  cursor: 'pointer',
  font: 'inherit',
}
const btnDanger = { ...btn, borderColor: '#b4543f', color: '#b4543f' }
const tile = {
  flex: '1 1 150px',
  background: 'var(--paper, #f5f0e6)',
  borderRadius: 12,
  padding: '14px 16px',
}
const mono = { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 12 }

function Tile({ label, value, hint }) {
  return (
    <div style={tile}>
      <div style={{ fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', opacity: 0.65 }}>{label}</div>
      <div style={{ fontSize: 26, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {hint && <div style={{ fontSize: 12, opacity: 0.6, marginTop: 2 }}>{hint}</div>}
    </div>
  )
}

function Table({ head, rows, empty }) {
  if (!rows.length) return <p style={{ fontSize: 13, opacity: 0.6 }}>{empty}</p>
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
      <thead>
        <tr>{head.map((h) => (
          <th key={h} style={{ textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid var(--line, #ddd5c7)', fontWeight: 600 }}>{h}</th>
        ))}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((cell, j) => (
              <td key={j} style={{ padding: '7px 8px', borderBottom: '1px solid var(--line-soft, #eee7da)', verticalAlign: 'top' }}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Improvement() {
  const [status, setStatus] = useState(null)
  const [queue, setQueue] = useState({ gaps: [] })
  const [cycles, setCycles] = useState([])
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    try {
      const [s, q, c] = await Promise.all([call('/status'), call('/queue'), call('/cycles?limit=8')])
      setStatus(s); setQueue(q); setCycles(c.cycles || []); setError('')
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const act = async (label, path, body) => {
    setBusy(label); setNote(''); setError('')
    try {
      const out = await call(path, body ? { method: 'POST', body: JSON.stringify(body) } : { method: 'POST' })
      setNote(label === 'cycle'
        ? `Cycle ${out.cycle_id}: ${out.gaps} gaps, ${out.promoted?.length || 0} promoted, coverage ${Math.round((out.coverage?.before || 0) * 100)}% → ${Math.round((out.coverage?.after || 0) * 100)}%`
        : `${label} ok`)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const stopped = status?.stopped
  const packs = status?.packs?.domains || {}
  const packRows = Object.entries(packs).map(([id, v]) => [
    id, v.atoms, <span style={mono}>{v.version}</span>, v.invalid ? `${v.invalid} invalid` : 'clean',
  ])
  const gapRows = (queue.gaps || []).map((g) => [
    g.gap_id, g.domain, (g.question || '').slice(0, 90), g.score,
  ])
  const cycleRows = cycles.map((c) => [
    <span style={mono}>{c.cycle_id}</span>,
    c.status,
    `${c.gaps || 0} / ${c.promoted || 0}`,
    (c.finished_at || '').replace('T', ' '),
    c.rollback_cmd || '',
  ])

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: '28px 20px 60px' }}>
      <div style={{ ...row, justifyContent: 'space-between', marginBottom: 6 }}>
        <h1 style={{ fontSize: 28, margin: 0 }}>Improvement</h1>
        <span style={{
          fontSize: 12, padding: '4px 10px', borderRadius: 999,
          background: stopped ? '#f3ded8' : '#e2eee4',
          color: stopped ? '#8e3b28' : '#2f5d3a',
        }}>{stopped ? 'stopped' : 'running'}</span>
      </div>
      <p style={{ fontSize: 14, opacity: 0.7, marginTop: 0 }}>
        What Bojo learned, what it is missing, and the exact rollback for every change.
      </p>

      <TysOpsPanel />

      <div style={{ ...card, ...row }}>
        <button style={stopped ? btn : btnDanger} disabled={!!busy}
                onClick={() => act(stopped ? 'resume' : 'stop', stopped ? '/resume' : '/stop')}>
          {stopped ? 'Resume the loop' : 'Stop the loop'}
        </button>
        <button style={btn} disabled={!!busy || stopped}
                onClick={() => act('cycle', '/cycle', { dry_run: true })}>
          Dry run
        </button>
        <button style={btn} disabled={!!busy || stopped}
                onClick={() => act('cycle', '/cycle', { dry_run: false })}>
          Run one cycle
        </button>
        <button style={btn} disabled={!!busy} onClick={load}>Refresh</button>
        {busy && <span style={{ fontSize: 13, opacity: 0.7 }}>{busy}…</span>}
      </div>

      {error && <div style={{ ...card, borderColor: '#b4543f', color: '#8e3b28' }}>{error}</div>}
      {note && <div style={{ ...card, borderColor: '#2f5d3a' }}>{note}</div>}

      <div style={{ ...row, marginBottom: 16 }}>
        <Tile label="Golden coverage" value={status ? `${Math.round((status.coverage || 0) * 100)}%` : '—'}
              hint={status ? `${status.golden_items} questions` : ''} />
        <Tile label="Open gaps" value={status ? status.open_gaps : '—'} hint="knowledge misses + feedback" />
        <Tile label="Atoms" value={status ? status.packs.total : '—'} hint="do / don't rules" />
        <Tile label="Cycles" value={status ? status.cycle_count : '—'} hint={status?.last_cycle?.status || 'none yet'} />
        <Tile label="Live grading"
              value={status ? (status.live_ready ? 'ready' : 'GPU busy') : '—'}
              hint={status ? (status.live_ready
                ? `${Math.round((status.gpu?.free_mb || 0) / 1024)} GB free`
                : 'knowledge cycles still run') : ''} />
      </div>

      <div style={card}>
        <h2 style={{ fontSize: 17, margin: '0 0 10px' }}>Knowledge packs</h2>
        <Table head={['Domain', 'Atoms', 'Version', 'Integrity']} rows={packRows} empty="No packs yet." />
      </div>

      <div style={card}>
        <h2 style={{ fontSize: 17, margin: '0 0 10px' }}>Gap queue</h2>
        <Table head={['Gap', 'Domain', 'Question', 'Score']} rows={gapRows}
               empty="Nothing open — every golden question is covered." />
      </div>

      <div style={card}>
        <h2 style={{ fontSize: 17, margin: '0 0 10px' }}>Recent cycles</h2>
        <Table head={['Cycle', 'Status', 'Gaps / promoted', 'Finished', 'Rollback']}
               rows={cycleRows} empty="No cycle has run yet." />
      </div>

      <p style={{ fontSize: 12, opacity: 0.55 }}>
        A cycle snapshots the base commit, researches gaps from the curated corpus, promotes only
        atoms that close a gap, and records the rollback command. Nothing here spends money or
        publishes to a marketplace.
      </p>
    </div>
  )
}
