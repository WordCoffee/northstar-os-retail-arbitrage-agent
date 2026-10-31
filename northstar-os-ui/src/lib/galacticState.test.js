import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createEventBus, layoutTopology, topologyLinks, heatmapCells,
  pulseFor, summarizeEvents, toneForRole, formatContext,
} from './galacticState.js'

const NODES = [
  { id: 'master', label: 'Master Brain', role: 'orchestrator' },
  { id: 'ty', label: "Ty's Assistant", role: 'compute' },
  { id: 'bojo', label: 'Bojo', role: 'orchestrator' },
  { id: 'flux', label: 'FLUX 3', role: 'media' },
  { id: 'chrome', label: 'Chrome Connect', role: 'browser' },
]

test('event bus publishes, replays and unsubscribes', () => {
  const bus = createEventBus({ limit: 3, now: () => 1000 })
  const seen = []
  const off = bus.subscribe((e) => seen.push(e.type))
  bus.publish('a')
  bus.publish('b', { n: 2 }, { severity: 'warn', source: 'test' })
  assert.deepEqual(seen, ['a', 'b'])
  assert.equal(bus.replay(1)[0].severity, 'warn')
  assert.equal(bus.replay(1)[0].source, 'test')
  off()
  bus.publish('c')
  assert.deepEqual(seen, ['a', 'b'])
  assert.equal(bus.size, 3)
})

test('event bus ring buffer drops the oldest event', () => {
  const bus = createEventBus({ limit: 2 })
  bus.publish('one')
  bus.publish('two')
  bus.publish('three')
  assert.deepEqual(bus.replay(5).map((e) => e.type), ['two', 'three'])
})

test('a broken subscriber cannot stop the bus', () => {
  const bus = createEventBus()
  bus.subscribe(() => { throw new Error('panel broke') })
  const seen = []
  bus.subscribe((e) => seen.push(e.type))
  assert.doesNotThrow(() => bus.publish('still-alive'))
  assert.deepEqual(seen, ['still-alive'])
})

test('topology is deterministic and puts the orchestrator at the centre', () => {
  const a = layoutTopology(NODES)
  const b = layoutTopology(NODES)
  assert.deepEqual(a, b)
  const master = a.find((n) => n.id === 'master')
  assert.equal(master.centre, true)
  assert.equal(master.x, 500)
  assert.equal(master.y, 300)
  assert.equal(a.length, NODES.length)
  for (const node of a) {
    assert.ok(node.x >= 0 && node.x <= 1000, `${node.id} x`)
    assert.ok(node.y >= 0 && node.y <= 600, `${node.id} y`)
  }
})

test('topology links only connect known nodes', () => {
  const links = topologyLinks(NODES, [['master', 'ty'], ['master', 'missing'], ['ty', 'flux']])
  assert.equal(links.length, 2)
  assert.deepEqual(links.map((l) => [l.from, l.to]), [['master', 'ty'], ['ty', 'flux']])
})

test('heatmap marks known ratios and unknown usage honestly', () => {
  const rows = heatmapCells([
    { id: 'ty', label: 'Ty', context_total: 17408, context_used: 8704, kv_cache: 'q8_0' },
    { id: 'bojo', label: 'Bojo', context_total: 8192, context_used: null },
  ], { columns: 8 })
  assert.equal(rows.length, 2)
  assert.equal(rows[0].known, true)
  assert.equal(rows[0].ratio, 0.5)
  assert.equal(rows[0].cells.filter((c) => c.active).length, 4)
  assert.equal(rows[1].known, false)
  assert.equal(rows[1].ratio, null)
  assert.equal(rows[1].cells.every((c) => c.unknown && !c.active), true)
})

test('heatmap clamps over-budget usage to a full row', () => {
  const [row] = heatmapCells([{ id: 'x', context_total: 100, context_used: 250 }], { columns: 4 })
  assert.equal(row.ratio, 1)
  assert.equal(row.cells.every((c) => c.active), true)
})

test('pulse maps severity to a named class and level', () => {
  assert.equal(pulseFor({ severity: 'error' }).className, 'gx-pulse gx-pulse--error')
  assert.equal(pulseFor({ severity: 'error' }).level, 3)
  assert.equal(pulseFor({}).className, 'gx-pulse gx-pulse--info')
})

test('event summary counts every severity', () => {
  const s = summarizeEvents([
    { severity: 'ok' }, { severity: 'warn' }, { severity: 'warn' }, {},
  ])
  assert.deepEqual(s, { ok: 1, info: 1, warn: 2, error: 0, total: 4 })
})

test('role tones and context formatting', () => {
  assert.equal(toneForRole('compute'), 'cyan')
  assert.equal(toneForRole('unknown'), 'steel')
  assert.equal(formatContext(17408), '17.4k')
  assert.equal(formatContext(null), '—')
})
