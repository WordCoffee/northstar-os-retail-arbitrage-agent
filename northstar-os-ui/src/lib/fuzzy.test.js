import test from 'node:test'
import assert from 'node:assert/strict'
import { score, rank } from './fuzzy.js'

test('empty query matches everything with a neutral score', () => {
  assert.equal(score('', 'anything'), 0)
  assert.equal(score('   ', 'anything'), 0)
})

test('non-subsequence is null, not zero', () => {
  assert.equal(score('zzz', 'settings'), null)
  assert.equal(score('abc', 'cba'), null)
})

test('subsequence matches and returns a number', () => {
  const s = score('set', 'Settings')
  assert.equal(typeof s, 'number')
  assert.ok(s > 0)
})

test('a word-boundary hit scores above an identical span without one', () => {
  // `set` covers 3 characters in both targets; only "Settings" starts on a boundary.
  const boundary = score('set', 'Settings')
  const midWord = score('set', 'asset')
  assert.ok(boundary > midWord, `${boundary} should beat ${midWord}`)
})

test('exact prefix outranks a scattered match', () => {
  const prefix = score('bill', 'Billing')
  const scattered = score('bill', 'Bedrock illustration lane')
  assert.ok(prefix > scattered, `${prefix} should beat ${scattered}`)
})

test('shorter target wins a tie', () => {
  const short = score('cmd', 'cmd')
  const long = score('cmd', 'cmd palette settings page')
  assert.ok(short > long)
})

test('rank keeps stable order for equal scores', () => {
  const items = [{ label: 'Alpha' }, { label: 'Alpha' }, { label: 'Beta' }]
  const out = rank('alpha', items)
  assert.equal(out.length, 2)
  assert.equal(out[0].label, 'Alpha')
})

test('rank accepts a function key and drops non-matches', () => {
  const items = [{ id: 1, name: 'Create listing' }, { id: 2, name: 'Billing' }]
  const out = rank('list', items, (i) => i.name)
  assert.equal(out.length, 1)
  assert.equal(out[0].id, 1)
})
