import test from 'node:test'
import assert from 'node:assert/strict'
import { chooseTier, probeEnvironment, FPS_CAP } from './sceneTiers.js'

test('reduced motion gets the still frame', () => {
  assert.equal(chooseTier({ reducedMotion: true, width: 1600 }), 'still')
})

test('no canvas support gets the still frame', () => {
  assert.equal(chooseTier({ webgl: false, width: 1600 }), 'still')
})

test('save-data gets the still frame', () => {
  assert.equal(chooseTier({ saveData: true, width: 1600 }), 'still')
})

test('phones and coarse pointers get the reduced tier', () => {
  assert.equal(chooseTier({ width: 390 }), 'reduced')
  assert.equal(chooseTier({ width: 1600, coarsePointer: true }), 'reduced')
  assert.equal(chooseTier({ width: 1600, deviceMemory: 2 }), 'reduced')
  assert.equal(chooseTier({ width: 1600, hardwareConcurrency: 4 }), 'reduced')
})

test('a strong desktop gets cinematic', () => {
  assert.equal(chooseTier({ width: 1920, deviceMemory: 16, hardwareConcurrency: 16 }), 'cinematic')
})

test('the tier owns the frame cap', () => {
  assert.equal(FPS_CAP.cinematic, 60)
  assert.equal(FPS_CAP.reduced, 30)
  assert.equal(FPS_CAP.still, 0)
})

test('probing without a window degrades to the still frame', () => {
  const env = probeEnvironment(null)
  assert.equal(env.webgl, false)
  assert.equal(chooseTier(env), 'still')
})

test('probeEnvironment survives a hostile window', () => {
  const env = probeEnvironment({
    matchMedia: () => { throw new Error('blocked') },
    document: null,
    innerWidth: 390,
  })
  assert.equal(env.reducedMotion, false)
  assert.equal(env.webgl, false)
  assert.equal(chooseTier(env), 'still')
})
