// Credit meter: display-only arithmetic over the ledger, and honest error copy.
//
// The failure this guards against is a page that invents a balance and subtracts
// a cost locally. Every case below pins "read the ledger, or say you could not".

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  AI_DESIGN_COST,
  affordability,
  describeError,
  meterLine,
  normaliseMeter,
} from './creditMeter.js'

const ENVELOPE = {
  contract: 'bff/v1',
  status: 'ok',
  data: { balance: 49, allotment: 49, consumed: 0, class: 'compute', plan: 'foundation', period: 'month' },
  error: null,
  meta: { service: 'credits', version: 'v1' },
}

test('the bff envelope normalises to a real balance', () => {
  const meter = normaliseMeter(ENVELOPE)
  assert.equal(meter.ok, true)
  assert.equal(meter.balance, 49)
  assert.equal(meter.allotment, 49)
  assert.equal(meter.consumed, 0)
  assert.equal(meter.plan, 'foundation')
  assert.equal(meter.period, 'month')
})

test('a bare data object is accepted too', () => {
  const meter = normaliseMeter({ balance: 12, allotment: 20, plan: 'growth' })
  assert.equal(meter.ok, true)
  assert.equal(meter.balance, 12)
  assert.equal(meter.consumed, null, 'a missing consumed count stays unknown, not zero')
})

test('a missing payload is unknown, never a fabricated balance', () => {
  for (const payload of [null, undefined, {}, 'nope', 42]) {
    const meter = normaliseMeter(payload)
    assert.equal(meter.ok, false, `${JSON.stringify(payload)} must not yield a balance`)
    assert.equal(meter.balance, null)
    assert.ok(meter.reason)
  }
})

test('a non-numeric or negative balance is refused', () => {
  assert.equal(normaliseMeter({ data: { balance: 'lots' } }).reason, 'balance_missing')
  assert.equal(normaliseMeter({ data: { balance: -5 } }).reason, 'balance_missing')
  assert.equal(normaliseMeter({ data: { balance: Number.NaN } }).reason, 'balance_missing')
})

test('an error envelope is a named ledger error', () => {
  const meter = normaliseMeter({ status: 'error', data: { balance: 49 } })
  assert.equal(meter.ok, false)
  assert.equal(meter.reason, 'ledger_error')
})

test('an affordable run is allowed', () => {
  const verdict = affordability(normaliseMeter(ENVELOPE), AI_DESIGN_COST)
  assert.equal(verdict.ok, true)
  assert.equal(verdict.shortfall, 0)
})

test('an unaffordable run names the shortfall and the fix', () => {
  const meter = normaliseMeter({ data: { balance: 4, allotment: 49, plan: 'foundation' } })
  const verdict = affordability(meter, AI_DESIGN_COST)
  assert.equal(verdict.ok, false)
  assert.equal(verdict.reason, 'insufficient')
  assert.equal(verdict.shortfall, 6)
  assert.match(verdict.message, /costs 10 credits/)
  assert.match(verdict.message, /4 remain/)
  assert.match(verdict.message, /Top up or upgrade/)
})

test('an unreadable meter blocks the run instead of assuming credit', () => {
  const verdict = affordability(normaliseMeter(null), AI_DESIGN_COST)
  assert.equal(verdict.ok, false)
  assert.equal(verdict.reason, 'meter_unavailable')
  assert.match(verdict.message, /unavailable/)
})

test('the sidebar line never shows a number it did not read', () => {
  assert.match(meterLine(normaliseMeter(ENVELOPE)), /49 of 49 left on foundation/)
  assert.match(meterLine(normaliseMeter(null)), /balance unavailable/)
  assert.doesNotMatch(meterLine(normaliseMeter(null)), /\d+ of \d+/)
})

test('every transport failure becomes an actionable instruction', () => {
  const offline = describeError(Object.assign(new Error('Failed to fetch'), { status: 0 }))
  assert.equal(offline.tone, 'offline')
  assert.equal(offline.action, 'retry')
  assert.match(offline.message, /unreachable/)
  assert.match(offline.message, /retry/)

  const auth = describeError(Object.assign(new Error('nope'), { status: 401 }))
  assert.equal(auth.action, 'sign_in')

  const limited = describeError(Object.assign(new Error('slow down'), { status: 429 }))
  assert.equal(limited.action, 'retry')

  const server = describeError(Object.assign(new Error('boom'), { status: 500 }))
  assert.equal(server.tone, 'server')
  assert.match(server.message, /500/)

  const rejected = describeError(Object.assign(new Error('bad brief'), { status: 422 }))
  assert.equal(rejected.action, 'edit')
  assert.match(rejected.message, /bad brief/)
})
