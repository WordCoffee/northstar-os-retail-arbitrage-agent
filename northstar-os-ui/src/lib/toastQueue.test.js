import test from 'node:test'
import assert from 'node:assert/strict'
import { enqueue, dismiss, orderToasts, priority, shouldAutoDismiss } from './toastQueue.js'

test('same key groups into one toast with a count', () => {
  let list = enqueue([], { msg: 'Saved', tone: 'success', key: 'save', createdAt: 1 })
  list = enqueue(list, { msg: 'Saved', tone: 'success', key: 'save', createdAt: 2 })
  assert.equal(list.length, 1)
  assert.equal(list[0].count, 2)
})

test('different keys stack', () => {
  let list = enqueue([], { msg: 'a', key: 'a', createdAt: 1 })
  list = enqueue(list, { msg: 'b', key: 'b', createdAt: 2 })
  assert.equal(list.length, 2)
})

test('error outranks success regardless of arrival order', () => {
  let list = enqueue([], { msg: 'saved', tone: 'success', key: 's', createdAt: 2 })
  list = enqueue(list, { msg: 'failed', tone: 'error', key: 'e', createdAt: 1 })
  const ordered = orderToasts(list)
  assert.equal(ordered[0].tone, 'error')
})

test('the cap drops the weakest oldest toast', () => {
  let list = []
  list = enqueue(list, { msg: 's1', tone: 'success', key: '1', createdAt: 1 }, { max: 3 })
  list = enqueue(list, { msg: 'i1', tone: 'info', key: '2', createdAt: 2 }, { max: 3 })
  list = enqueue(list, { msg: 'e1', tone: 'error', key: '3', createdAt: 3 }, { max: 3 })
  list = enqueue(list, { msg: 's2', tone: 'success', key: '4', createdAt: 4 }, { max: 3 })
  assert.equal(list.length, 3)
  assert.equal(list.some((t) => t.key === '1'), false, 'the oldest success was dropped')
  assert.ok(list.some((t) => t.tone === 'error'))
})

test('errors are sticky by default; successes are not', () => {
  const list = enqueue([], { msg: 'boom', tone: 'error', createdAt: 0 })
  assert.equal(list[0].sticky, true)
  assert.equal(shouldAutoDismiss(list[0], 10_000), false)
  const ok = enqueue([], { msg: 'ok', tone: 'success', createdAt: 0 })
  assert.equal(shouldAutoDismiss(ok[0], 10_000, 3200), true)
})

test('dismiss removes by id and is a no-op for an unknown id', () => {
  const list = enqueue([], { msg: 'x', id: 'fixed', createdAt: 0 })
  assert.deepEqual(dismiss(list, 'nope'), list)
  assert.equal(dismiss(list, 'fixed').length, 0)
})

test('priority ordering is total and unknown tones fall to info', () => {
  assert.equal(priority('error') > priority('warning'), true)
  assert.equal(priority('warning') > priority('info'), true)
  assert.equal(priority('info') > priority('success'), true)
  assert.equal(priority('nonsense'), priority('info'))
})

test('an unknown tone is normalised to info', () => {
  const list = enqueue([], { msg: 'x', tone: 'chartreuse', createdAt: 0 })
  assert.equal(list[0].tone, 'info')
})
