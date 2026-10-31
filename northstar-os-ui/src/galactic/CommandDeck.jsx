import { useEffect, useMemo, useRef, useState } from 'react'
import { createEventBus, pulseFor } from '../lib/galacticState.js'
import NodeTopology from './NodeTopology.jsx'
import KVCacheHeatmap from './KVCacheHeatmap.jsx'
import EventStream from './EventStream.jsx'
import './galactic.css'

// Fallback is deliberately labelled: the deck still renders offline, but it
// never presents these values as live telemetry.
const FALLBACK = {
  telemetry: 'fallback',
  nodes: [
    { id: 'master', label: 'Master Brain', role: 'orchestrator', status: 'ready', model: 'orchestrator' },
    { id: 'ty', label: "Ty's Assistant", role: 'compute', status: 'ready', model: 'northstaros-27b-coder' },
    { id: 'bojo', label: 'Bojo', role: 'worker', status: 'resident', model: 'bojo' },
    { id: 'flux', label: 'FLUX 3 Klein', role: 'media', status: 'ready', model: 'flux3' },
    { id: 'chrome', label: 'Chrome Connect', role: 'browser', status: 'gated', model: 'controller' },
    { id: 'memory', label: 'Memory Bank', role: 'memory', status: 'ready', model: 'context' },
    { id: 'ast', label: 'AST Engine', role: 'worker', status: 'ready', model: 'symbol edit' },
  ],
  links: [
    ['master', 'ty'], ['master', 'bojo'], ['master', 'flux'], ['master', 'chrome'],
    ['master', 'memory'], ['master', 'ast'], ['ty', 'ast'],
  ],
  kv: [
    { id: 'ty', label: 'Ty 27B', context_total: 17408, context_used: null, kv_cache: 'q8_0', role: 'compute' },
    { id: 'bojo', label: 'Bojo 1.9B', context_total: 8192, context_used: null, kv_cache: 'q8_0', role: 'worker' },
  ],
  lanes: { installed: [], missing: [] },
  hardware: {},
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (value.includes('ready') || value.includes('ok')) return 'ok'
  if (value.includes('gated') || value.includes('wait')) return 'warn'
  if (value.includes('error') || value.includes('down')) return 'error'
  return 'info'
}

export default function CommandDeck() {
  const busRef = useRef(null)
  if (!busRef.current) busRef.current = createEventBus()
  const bus = busRef.current
  const pageRef = useRef(null)
  const lastErrorRef = useRef('')

  const [snapshot, setSnapshot] = useState(FALLBACK)
  const [events, setEvents] = useState(() => bus.replay(40))
  const [selected, setSelected] = useState('master')
  const [pulse, setPulse] = useState(0)
  const [stream, setStream] = useState('connecting')

  useEffect(() => bus.subscribe((event) => {
    setEvents((previous) => [...previous.slice(-79), event])
    setPulse((value) => value + 1)
  }), [bus])

  // Preferred transport: one SSE snapshot every 8 s. The poll below remains a
  // fallback for browsers without EventSource or when the stream errors; the
  // SSE snapshot is merged into the same bus as UI events.
  useEffect(() => {
    if (typeof EventSource === 'undefined') {
      setStream('unsupported')
      return undefined
    }
    let closed = false
    const source = new EventSource('/api/v1/galactic/events')
    const onSnapshot = (event) => {
      if (closed) return
      try {
        const payload = JSON.parse(event.data)
        if (!payload || !Array.isArray(payload.nodes)) return
        setSnapshot({ ...FALLBACK, ...payload, telemetry: 'live' })
        setStream('open')
        bus.publish('telemetry.snapshot', {
          nodes: payload.nodes.length,
          kv: Array.isArray(payload.kv) ? payload.kv.length : 0,
          transport: 'sse',
        }, { severity: 'ok', source: 'telemetry' })
      } catch (error) {
        if (!closed) {
          bus.publish('telemetry.stream.bad_frame', { error: String(error?.message || error) }, {
            severity: 'warn', source: 'telemetry',
          })
        }
      }
    }
    source.addEventListener('snapshot', onSnapshot)
    source.onopen = () => {
      if (!closed) {
        setStream('open')
        bus.publish('telemetry.stream.open', {}, { severity: 'ok', source: 'telemetry' })
      }
    }
    source.onerror = () => {
      if (!closed) {
        setStream('error')
        bus.publish('telemetry.stream.error', {}, { severity: 'warn', source: 'telemetry' })
      }
    }
    return () => {
      closed = true
      source.removeEventListener('snapshot', onSnapshot)
      source.close()
    }
  }, [bus])

  useEffect(() => {
    if (stream === 'open') return undefined
    let alive = true
    let timer = null
    async function load() {
      try {
        const response = await fetch('/api/v1/galactic/state', {
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const body = await response.json()
        const payload = body?.data || body
        if (!alive || !payload || !Array.isArray(payload.nodes)) return
        setSnapshot({ ...FALLBACK, ...payload, telemetry: 'live' })
        if (lastErrorRef.current) {
          lastErrorRef.current = ''
          bus.publish('telemetry.recovered', {}, { severity: 'ok', source: 'telemetry' })
        }
        bus.publish('telemetry.snapshot', {
          nodes: payload.nodes.length,
          kv: Array.isArray(payload.kv) ? payload.kv.length : 0,
        }, { severity: 'ok', source: 'telemetry' })
      } catch (error) {
        if (!alive) return
        const message = String(error?.message || error)
        if (message !== lastErrorRef.current) {
          lastErrorRef.current = message
          bus.publish('telemetry.unavailable', { error: message }, {
            severity: 'warn', source: 'telemetry',
          })
        }
      } finally {
        if (alive) timer = setTimeout(load, 8000)
      }
    }
    load()
    return () => {
      alive = false
      if (timer) clearTimeout(timer)
    }
  }, [bus, stream])

  const nodes = snapshot.nodes || []
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selected) || nodes[0] || null,
    [nodes, selected],
  )
  const lastEvent = events[events.length - 1]
  const pulseInfo = pulseFor(lastEvent)

  const onPointerMove = (event) => {
    const page = pageRef.current
    if (!page) return
    const rect = page.getBoundingClientRect()
    page.style.setProperty('--gx-x', `${((event.clientX - rect.left) / Math.max(1, rect.width)) * 100}%`)
    page.style.setProperty('--gx-y', `${((event.clientY - rect.top) / Math.max(1, rect.height)) * 100}%`)
  }

  return (
    <section className="gx-deck" ref={pageRef} onPointerMove={onPointerMove}>
      <div key={pulse} className={`gx-scan ${pulseInfo.className}`} aria-hidden="true" />
      <header className="gx-header">
        <div>
          <span className="gx-eyebrow">Northstar OS · Tactile Command Deck</span>
          <h2>Galactic Control Surface</h2>
          <p>
            Live agent topology, KV-cache pressure and the unified event stream.
            {snapshot.telemetry === 'fallback' ? ' Telemetry is offline; showing the last known shape.' : ' Telemetry is live.'}
          </p>
        </div>
        <div className="gx-status-row" role="status" aria-live="polite">
          {nodes.slice(0, 5).map((node) => (
            <span key={node.id} className={`gx-status gx-status--${statusTone(node.status)}`}>
              <i className="gx-lamp" /> {node.label}
            </span>
          ))}
        </div>
      </header>

      <div className="gx-grid">
        <section className="gx-panel gx-panel--topology" aria-labelledby="gx-topology-title">
          <div className="gx-panel-head">
            <div>
              <span className="gx-eyebrow">Stellar node topology</span>
              <h3 id="gx-topology-title">Agent cluster</h3>
            </div>
            <span className={`gx-telemetry gx-telemetry--${snapshot.telemetry}`}>
              {snapshot.telemetry}{stream === 'open' ? ' · sse' : stream === 'error' ? ' · poll' : ''}
            </span>
          </div>
          <NodeTopology
            nodes={nodes}
            links={snapshot.links || []}
            selected={selected}
            onSelect={setSelected}
            pulse={pulse}
          />
        </section>

        <aside className="gx-panel gx-panel--detail" aria-labelledby="gx-detail-title">
          <div className="gx-panel-head">
            <div>
              <span className="gx-eyebrow">Selected node</span>
              <h3 id="gx-detail-title">{selectedNode?.label || 'No node'}</h3>
            </div>
            <span className={`gx-status gx-status--${statusTone(selectedNode?.status)}`}>
              <i className="gx-lamp" /> {selectedNode?.status || 'unknown'}
            </span>
          </div>
          <dl className="gx-facts">
            <div><dt>Role</dt><dd>{selectedNode?.role || '—'}</dd></div>
            <div><dt>Model</dt><dd>{selectedNode?.model || '—'}</dd></div>
            <div><dt>Context</dt><dd>{selectedNode?.context_tokens ? `${selectedNode.context_tokens} tokens` : 'not reported'}</dd></div>
            <div><dt>KV cache</dt><dd>{selectedNode?.kv_cache || 'not reported'}</dd></div>
          </dl>
          <div className="gx-actions">
            <button type="button" className="gx-btn" onClick={() => {
              bus.publish('deck.focus', { node: selected }, { severity: 'info', source: 'ui' })
              setPulse((value) => value + 1)
            }}>
              Focus node
            </button>
            <button type="button" className="gx-btn gx-btn--ghost" onClick={() => {
              bus.publish('deck.pulse', { node: selected }, { severity: 'ok', source: 'ui' })
              setPulse((value) => value + 1)
            }}>
              Pulse deck
            </button>
            <button type="button" className="gx-btn gx-btn--ghost" onClick={() => setEvents(bus.replay(60))}>
              Replay stream
            </button>
          </div>
        </aside>

        <section className="gx-panel gx-panel--heat" aria-labelledby="gx-heat-title">
          <div className="gx-panel-head">
            <div>
              <span className="gx-eyebrow">Memory pressure</span>
              <h3 id="gx-heat-title">KV-cache heatmap</h3>
            </div>
          </div>
          <KVCacheHeatmap kv={snapshot.kv || []} />
        </section>

        <section className="gx-panel gx-panel--events" aria-labelledby="gx-events-title">
          <div className="gx-panel-head">
            <div>
              <span className="gx-eyebrow">System stream</span>
              <h3 id="gx-events-title">Event bus</h3>
            </div>
          </div>
          <EventStream events={events} onReplay={() => setEvents(bus.replay(60))} />
        </section>
      </div>
    </section>
  )
}
