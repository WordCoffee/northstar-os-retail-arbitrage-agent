import test from 'node:test'
import assert from 'node:assert/strict'
import { SHIFT_MS, shouldAnimateShift, prefersReducedMotion } from './themeShift.js'

test('first paint does not animate', () => {
  assert.equal(shouldAnimateShift('', 'studio'), false)
  assert.equal(shouldAnimateShift(null, 'studio'), false)
})

test('the same theme does not animate', () => {
  assert.equal(shouldAnimateShift('studio', 'studio'), false)
})

test('a real service switch animates', () => {
  assert.equal(shouldAnimateShift('studio', 'ppc'), true)
  assert.equal(SHIFT_MS, 600)
})

test('reduced motion always wins', () => {
  assert.equal(shouldAnimateShift('studio', 'ppc', true), false)
})

test('prefersReducedMotion is safe without a window or matchMedia', () => {
  assert.equal(prefersReducedMotion(null), false)
  assert.equal(prefersReducedMotion({}), false)
  assert.equal(prefersReducedMotion({ matchMedia: () => ({ matches: true }) }), true)
  assert.equal(prefersReducedMotion({ matchMedia: () => { throw new Error('nope') } }), false)
})
