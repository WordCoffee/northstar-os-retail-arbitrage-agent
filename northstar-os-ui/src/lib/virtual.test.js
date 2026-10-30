import test from 'node:test'
import assert from 'node:assert/strict'
import { visibleRange, totalHeight } from './virtual.js'

test('empty list renders nothing', () => {
  assert.deepEqual(visibleRange({ count: 0 }), { start: 0, end: 0, offset: 0, total: 0 })
})

test('top of the list starts at zero and includes overscan below', () => {
  const r = visibleRange({ scrollTop: 0, viewport: 400, rowHeight: 40, count: 100, overscan: 2 })
  assert.equal(r.start, 0)
  assert.equal(r.end, 12)      // 10 visible + 2 overscan
  assert.equal(r.offset, 0)
  assert.equal(r.total, 4000)
})

test('scrolling shifts the window and the offset', () => {
  const r = visibleRange({ scrollTop: 800, viewport: 400, rowHeight: 40, count: 100, overscan: 2 })
  assert.equal(r.start, 18)    // 800/40 = 20, minus overscan 2
  assert.equal(r.end, 32)
  assert.equal(r.offset, 720)
})

test('never runs past the end', () => {
  const r = visibleRange({ scrollTop: 3800, viewport: 400, rowHeight: 40, count: 100, overscan: 4 })
  assert.equal(r.end, 100)
  assert.ok(r.start < r.end)
})

test('negative or garbage scroll is clamped to zero', () => {
  assert.equal(visibleRange({ scrollTop: -50, viewport: 200, rowHeight: 20, count: 10 }).start, 0)
  assert.equal(visibleRange({ scrollTop: 'abc', viewport: 200, rowHeight: 20, count: 10 }).start, 0)
})

test('zero viewport still mounts at least one row', () => {
  const r = visibleRange({ scrollTop: 0, viewport: 0, rowHeight: 40, count: 10, overscan: 0 })
  assert.equal(r.end - r.start, 1)
})

test('rowHeight below 1 cannot divide by zero', () => {
  const r = visibleRange({ scrollTop: 0, viewport: 100, rowHeight: 0, count: 5, overscan: 0 })
  assert.equal(r.total, 5)
})

test('totalHeight is count * rowHeight', () => {
  assert.equal(totalHeight(100, 40), 4000)
  assert.equal(totalHeight(0, 40), 0)
})
