import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createOptimisticState, begin, commit, rollback, isPending, isSettled,
} from './optimistic.js'

const add = (item) => (state) => ({ ...state, items: [...state.items, item] })

test('begin applies the change immediately', () => {
  let s = createOptimisticState({ items: [] })
  s = begin(s, 'a', add('one'))
  assert.deepEqual(s.value.items, ['one'])
  assert.ok(isPending(s, 'a'))
  assert.equal(isSettled(s), false)
})

test('commit keeps the value and clears the entry', () => {
  let s = createOptimisticState({ items: [] })
  s = begin(s, 'a', add('one'))
  s = commit(s, 'a')
  assert.deepEqual(s.value.items, ['one'])
  assert.ok(isSettled(s))
})

test('rollback restores the pre-change value', () => {
  let s = createOptimisticState({ items: ['base'] })
  s = begin(s, 'a', add('one'))
  s = rollback(s, 'a')
  assert.deepEqual(s.value.items, ['base'])
  assert.ok(isSettled(s))
})

test('rollback re-applies later in-flight updates', () => {
  let s = createOptimisticState({ items: [] })
  s = begin(s, 'a', add('a-item'))
  s = begin(s, 'b', add('b-item'))
  s = rollback(s, 'a')
  assert.deepEqual(s.value.items, ['b-item'])
  assert.equal(isPending(s, 'a'), false)
  assert.equal(isPending(s, 'b'), true)
})

test('reusing an id does not stack two entries', () => {
  let s = createOptimisticState({ items: [] })
  s = begin(s, 'a', add('one'))
  s = begin(s, 'a', add('two'))
  assert.equal(s.pending.length, 1)
  assert.deepEqual(s.value.items, ['one'])
})

test('rollback of an unknown id is a no-op', () => {
  const s = createOptimisticState({ items: [] })
  assert.equal(rollback(s, 'nope'), s)
})

test('begin rejects a missing id or updater', () => {
  const s = createOptimisticState({})
  assert.throws(() => begin(s, '', () => ({})))
  assert.throws(() => begin(s, 'x', null))
})
