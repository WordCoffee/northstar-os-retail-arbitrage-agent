// Pure state helpers for the Galactic command deck. No React, no DOM, no
// network: the deck's structure, heatmap and event bus are deterministic so the
// node test runner can pin them.

export const EVENT_LIMIT = 240

export const ROLE_TONES = {
  orchestrator: 'violet',
  compute: 'cyan',
  memory: 'gold',
  media: 'rose',
  browser: 'steel',
  worker: 'green',
  default: 'steel',
}

let _eventSeq = 0

export function createEventBus({ limit = EVENT_LIMIT, now = () => Date.now() } = {}) {
  const events = []
  const subscribers = new Set()
  return {
    publish(type, payload = {}, { severity = 'info', source = 'ui' } = {}) {
      _eventSeq += 1
      const event = {
        id: `evt_${String(_eventSeq).padStart(5, '0')}`,
        type: String(type || 'event'),
        payload: payload || {},
        severity: ['ok', 'info', 'warn', 'error'].includes(severity) ? severity : 'info',
        source: String(source || 'ui'),
        ts: now(),
      }
      events.push(event)
      if (events.length > limit) events.splice(0, events.length - limit)
      for (const fn of subscribers) {
        try { fn(event) } catch { /* a broken panel must not stop the bus */ }
      }
      return event
    },
    subscribe(fn) {
      if (typeof fn !== 'function') return () => {}
      subscribers.add(fn)
      return () => subscribers.delete(fn)
    },
    replay(n = 40) {
      return events.slice(-Math.max(0, Number(n) || 0))
    },
    get size() { return events.length },
  }
}

export function toneForRole(role) {
  return ROLE_TONES[String(role || '').toLowerCase()] || ROLE_TONES.default
}

// The orchestrator sits at the centre; every other node is placed on a stable
// ring in input order. Coordinates are in a 0..1000 x 0..600 viewBox.
export function layoutTopology(nodes, { width = 1000, height = 600 } = {}) {
  const list = Array.isArray(nodes) ? nodes.filter((n) => n && n.id) : []
  if (!list.length) return []
  const centre = list.find((n) => n.role === 'orchestrator') || list[0]
  const ring = list.filter((n) => n.id !== centre.id)
  const cx = width / 2
  const cy = height / 2
  const rx = Math.min(width * 0.38, 330)
  const ry = Math.min(height * 0.34, 190)
  const out = [{
    ...centre, x: cx, y: cy, r: 42, tone: toneForRole(centre.role), centre: true,
  }]
  ring.forEach((node, i) => {
    const angle = (-Math.PI / 2) + (i / Math.max(1, ring.length)) * Math.PI * 2
    out.push({
      ...node,
      x: Math.round(cx + Math.cos(angle) * rx),
      y: Math.round(cy + Math.sin(angle) * ry),
      r: 28,
      tone: toneForRole(node.role),
      centre: false,
    })
  })
  return out
}

export function topologyLinks(nodes, links) {
  const byId = new Map(layoutTopology(nodes).map((n) => [n.id, n]))
  const pairs = Array.isArray(links) ? links : []
  const out = []
  for (const pair of pairs) {
    const [from, to] = Array.isArray(pair) ? pair : [pair?.from, pair?.to]
    const a = byId.get(from)
    const b = byId.get(to)
    if (a && b) out.push({ from, to, x1: a.x, y1: a.y, x2: b.x, y2: b.y })
  }
  return out
}

// One row per configured KV lane. Usage is only claimed when the backend
// supplies context_used; otherwise the row is explicitly `unknown`.
export function heatmapCells(kv, { columns = 16 } = {}) {
  const cols = Math.max(4, Math.min(48, Number(columns) || 16))
  const lanes = Array.isArray(kv) ? kv : []
  return lanes.map((lane) => {
    const total = lane.context_total == null ? NaN : Number(lane.context_total)
    const hasUsed = lane.context_used !== null && lane.context_used !== undefined
      && lane.context_used !== ''
    const used = hasUsed ? Number(lane.context_used) : NaN
    const known = Number.isFinite(total) && total > 0 && Number.isFinite(used) && used >= 0
    const ratio = known ? Math.max(0, Math.min(1, used / total)) : null
    const filled = known ? Math.round(ratio * cols) : 0
    return {
      id: String(lane.id || lane.label || 'lane'),
      label: String(lane.label || lane.id || 'lane'),
      kv_cache: lane.kv_cache || null,
      context_total: Number.isFinite(total) ? total : null,
      context_used: known ? used : null,
      ratio: ratio == null ? null : Number(ratio.toFixed(4)),
      known,
      cells: Array.from({ length: cols }, (_, i) => ({
        i,
        active: known && i < filled,
        unknown: !known,
        // The last active cell carries the fractional remainder so a 0.63
        // ratio does not look like a whole cell.
        partial: known && i === filled && ratio > 0 && ratio < 1,
      })),
      tone: toneForRole(lane.role),
    }
  })
}

export function pulseFor(event) {
  const severity = ['ok', 'info', 'warn', 'error'].includes(event?.severity)
    ? event.severity
    : 'info'
  return {
    className: `gx-pulse gx-pulse--${severity}`,
    level: { ok: 1, info: 1, warn: 2, error: 3 }[severity],
  }
}

export function summarizeEvents(events) {
  const counts = { ok: 0, info: 0, warn: 0, error: 0 }
  for (const event of Array.isArray(events) ? events : []) {
    const key = counts[event?.severity] != null ? event.severity : 'info'
    counts[key] += 1
  }
  return { ...counts, total: Object.values(counts).reduce((a, b) => a + b, 0) }
}

export function formatContext(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}
