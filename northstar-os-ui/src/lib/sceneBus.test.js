import test from 'node:test'
import assert from 'node:assert/strict'
import { createSceneBus, modeForEvent, SCENE_EVENTS } from './sceneBus.js'

test('the event to mood mapping is fixed', () => {
  assert.equal(modeForEvent('idle'), 'calm')
  assert.equal(modeForEvent('working'), 'intense')
  assert.equal(modeForEvent('done'), 'flare')
  assert.equal(modeForEvent('error'), 'subdued')
  assert.equal(modeForEvent('nonsense'), 'calm')
})

test('every workspace event is accepted and an unknown one is refused', () => {
  const bus = createSceneBus()
  for (const event of SCENE_EVENTS) assert.equal(bus.emit(event), true, event)
  assert.equal(bus.emit('explode'), false)
  assert.equal(bus.last, 'error')
})

test('subscribers get the event and its mood; unsubscribe stops delivery', () => {
  const bus = createSceneBus()
  const seen = []
  const off = bus.subscribe((event, mode) => seen.push([event, mode]))
  bus.emit('working')
  off()
  bus.emit('done')
  assert.deepEqual(seen, [['working', 'intense']])
  assert.equal(bus.size, 0)
})

test('a throwing subscriber cannot stop the others', () => {
  const bus = createSceneBus()
  const seen = []
  bus.subscribe(() => { throw new Error('bad listener') })
  bus.subscribe((e) => seen.push(e))
  assert.equal(bus.emit('idle'), true)
  assert.deepEqual(seen, ['idle'])
})
