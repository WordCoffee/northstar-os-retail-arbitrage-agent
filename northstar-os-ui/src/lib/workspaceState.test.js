import test from 'node:test'
import assert from 'node:assert/strict'
import {
  serialize, parse, pick, withDefaults, clampScroll, WORKSPACE_VERSION,
} from './workspaceState.js'

const KEYS = ['tab', 'collapsed', 'scrollY']

test('round-trip restores an allowlisted state', () => {
  const now = 1_700_000_000_000
  const raw = serialize({ tab: 'create', collapsed: { rail: true }, scrollY: 420, junk: 1 }, { keys: KEYS, now })
  assert.deepEqual(parse(raw, { keys: KEYS, now }), { tab: 'create', collapsed: { rail: true }, scrollY: 420 })
})

test('unknown keys are dropped, never merged', () => {
  const now = Date.now()
  const raw = JSON.stringify({ v: WORKSPACE_VERSION, savedAt: now, state: { tab: 'x', injected: 'evil' } })
  assert.deepEqual(parse(raw, { keys: KEYS, now }), { tab: 'x' })
})

test('version mismatch returns null', () => {
  const raw = JSON.stringify({ v: 0, savedAt: Date.now(), state: { tab: 'x' } })
  assert.equal(parse(raw, { keys: KEYS }), null)
})

test('corrupt JSON returns null instead of throwing', () => {
  assert.equal(parse('{not json', { keys: KEYS }), null)
  assert.equal(parse('', { keys: KEYS }), null)
  assert.equal(parse(null, { keys: KEYS }), null)
})

test('expired state is refused', () => {
  const now = 1_700_000_000_000
  const raw = serialize({ tab: 'x' }, { keys: KEYS, now: now - 1000 * 60 * 60 * 24 * 30 })
  assert.equal(parse(raw, { keys: KEYS, now }), null)
})

test('a future timestamp is refused (clock skew)', () => {
  const now = 1_700_000_000_000
  const raw = serialize({ tab: 'x' }, { keys: KEYS, now: now + 1000 * 60 * 60 })
  assert.equal(parse(raw, { keys: KEYS, now }), null)
})

test('pick ignores a non-object', () => {
  assert.deepEqual(pick(null, KEYS), {})
  assert.deepEqual(pick('nope', KEYS), {})
})

test('withDefaults never invents keys and keeps defaults for missing ones', () => {
  const out = withDefaults({ tab: 'home', density: 'comfortable' }, { tab: 'create', density: 'compact', extra: true })
  assert.deepEqual(out, { tab: 'create', density: 'compact' })
})

test('clampScroll bounds the value', () => {
  assert.equal(clampScroll(-5, 100), 0)
  assert.equal(clampScroll('abc', 100), 0)
  assert.equal(clampScroll(50, 100), 50)
  assert.equal(clampScroll(500, 100), 100)
  assert.equal(clampScroll(50, 0), 0)
})
