import test from 'node:test'
import assert from 'node:assert/strict'
import { moveItem, snapIndex, dragPreview } from './reorder.js'

const LIST = ['a', 'b', 'c', 'd']

test('moveItem moves without mutating the source', () => {
  const out = moveItem(LIST, 0, 2)
  assert.deepEqual(out, ['b', 'c', 'a', 'd'])
  assert.deepEqual(LIST, ['a', 'b', 'c', 'd'])
})

test('moveItem backwards', () => {
  assert.deepEqual(moveItem(LIST, 3, 0), ['d', 'a', 'b', 'c'])
})

test('moveItem clamps out-of-range indexes', () => {
  assert.deepEqual(moveItem(LIST, -5, 99), ['b', 'c', 'd', 'a'])
  assert.deepEqual(moveItem(LIST, 0, 0), LIST)
})

test('moveItem handles an empty list', () => {
  assert.deepEqual(moveItem([], 0, 1), [])
  assert.deepEqual(moveItem(null, 0, 1), [])
})

test('snapIndex maps an offset to the right slot', () => {
  assert.equal(snapIndex(0, { rowHeight: 40, count: 4 }), 0)
  assert.equal(snapIndex(45, { rowHeight: 40, count: 4 }), 1)
  assert.equal(snapIndex(130, { rowHeight: 40, count: 4 }), 3)
})

test('snapIndex counts the gap between rows', () => {
  // slots are 48px (40 row + 8 gap); the magnet owns the last 25% of a slot
  assert.equal(snapIndex(30, { rowHeight: 40, gap: 8, count: 4 }), 0)  // before the magnet
  assert.equal(snapIndex(40, { rowHeight: 40, gap: 8, count: 4 }), 1)  // inside it, snaps forward
})

test('snapIndex clamps to the list and handles zero count', () => {
  assert.equal(snapIndex(9999, { rowHeight: 40, count: 4 }), 3)
  assert.equal(snapIndex(100, { rowHeight: 40, count: 0 }), 0)
})

test('dragPreview reports the placeholder slot and whether anything moved', () => {
  const p = dragPreview(LIST, 1, 3)
  assert.deepEqual(p.items, ['a', 'c', 'd', 'b'])
  assert.equal(p.placeholderIndex, 3)
  assert.equal(p.changed, true)
  assert.equal(dragPreview(LIST, 2, 2).changed, false)
})
