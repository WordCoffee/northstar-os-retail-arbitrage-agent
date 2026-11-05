// Package Design sessions: what may be stored, and what may be restored.
//
// The page must never resurrect something that was not generated, and must never
// throw into render on a corrupt record. Every case below pins one of those.

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  PACKIFY_SESSIONS_KEY,
  PACKIFY_SESSIONS_MAX,
  PACKIFY_SESSIONS_TTL_MS,
  contentFor,
  decodeSessions,
  encodeSessions,
  sanitiseSessions,
} from './packifySessions.js'

const session = (id, extra = {}) => ({
  id,
  prompt: `prompt ${id}`,
  content: `spec ${id}`,
  model: 'local',
  at: '10:00',
  ...extra,
})

test('a generated session round-trips', () => {
  const raw = encodeSessions([session(1), session(2)], 2)
  const back = decodeSessions(raw)
  assert.equal(back.sessions.length, 2)
  assert.equal(back.active, 2)
  assert.equal(contentFor(back.sessions, back.active), 'spec 2')
})

test('the storage key is stable and versioned by the serializer', () => {
  assert.equal(PACKIFY_SESSIONS_KEY, 'ns-packify-sessions')
  const record = JSON.parse(encodeSessions([session(1)], 1))
  assert.equal(typeof record.v, 'number')
  assert.equal(typeof record.savedAt, 'number')
})

test('entries that do not look like a session are dropped, not rendered', () => {
  const cleaned = sanitiseSessions([
    session(1),
    null,
    'nope',
    { id: 2 },
    { id: 3, prompt: 5, content: 'x' },
    { id: 4, prompt: 'p', content: 'c' },
  ])
  assert.deepEqual(cleaned.map((s) => s.id), [1, 4])
})

test('oversized content is truncated rather than stored whole', () => {
  const cleaned = sanitiseSessions([session(1, { prompt: 'p'.repeat(500), content: 'c'.repeat(9000) })])
  assert.equal(cleaned[0].prompt.length, 200)
  assert.equal(cleaned[0].content.length, 8000)
})

test('the list is capped', () => {
  const many = Array.from({ length: PACKIFY_SESSIONS_MAX + 5 }, (_, i) => session(i + 1))
  assert.equal(sanitiseSessions(many).length, PACKIFY_SESSIONS_MAX)
})

test('corrupt JSON restores nothing instead of throwing', () => {
  assert.deepEqual(decodeSessions('{not json'), { sessions: [], active: null })
  assert.deepEqual(decodeSessions(null), { sessions: [], active: null })
  assert.deepEqual(decodeSessions(undefined), { sessions: [], active: null })
})

test('a future clock or an expired record restores nothing', () => {
  const raw = encodeSessions([session(1)], 1)
  const later = Date.now() + PACKIFY_SESSIONS_TTL_MS + 1000
  assert.deepEqual(decodeSessions(raw, { now: later }), { sessions: [], active: null })
})

test('an active id that no longer exists falls back to the newest session', () => {
  const raw = encodeSessions([session(7), session(9)], 999)
  const back = decodeSessions(raw)
  assert.equal(back.active, 7)
})

test('an empty session list restores an empty state, never a placeholder', () => {
  const raw = encodeSessions([], null)
  assert.deepEqual(decodeSessions(raw), { sessions: [], active: null })
  assert.equal(contentFor([], null), null)
})

test('contentFor is null for an unknown active id', () => {
  assert.equal(contentFor([session(1)], 42), null)
})
