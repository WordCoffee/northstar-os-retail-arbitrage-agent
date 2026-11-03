// U9 — the PPC asteroid-field scene. The contrast test (sceneContrast.test.js)
// covers the palette automatically because it iterates SCENE_MAX_COLOR; these
// tests cover the renderer's own contract.

import test from 'node:test'
import assert from 'node:assert/strict'

import { createAsteroidField, ASTEROID_MAX_COLOR } from '../scene/asteroidField.js'
import { createScene, sceneMaxColor } from '../scene/scenes.js'

function fakeCtx() {
  const calls = { fillRect: 0, gradient: 0, save: 0, restore: 0, polygon: 0, stroke: 0 }
  return {
    calls,
    fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1,
    fillRect() { calls.fillRect += 1 },
    createRadialGradient() { calls.gradient += 1; return { addColorStop() {} } },
    beginPath() { calls.polygon += 1 },
    moveTo() {}, lineTo() {}, closePath() {}, fill() {}, stroke() { calls.stroke += 1 },
    save() { calls.save += 1 }, restore() { calls.restore += 1 },
    translate() {}, rotate() {},
  }
}

test('the field paints a background, a far belt, dust and near rocks', () => {
  const ctx = fakeCtx()
  const scene = createAsteroidField({ width: 1200, height: 800, seed: 3 })
  const info = scene.draw(ctx, { dt: 16, t: 0, mode: 'calm' })

  assert.equal(info.maxColor, ASTEROID_MAX_COLOR)
  assert.equal(info.mode, 'calm')
  assert.ok(info.rocks >= 40, 'the belt is a field, not a handful')
  assert.ok(ctx.calls.polygon >= 40, 'every rock is drawn as its own polygon')
  assert.ok(ctx.calls.fillRect >= 2, 'background plus dust')
  assert.equal(ctx.calls.save, ctx.calls.restore, 'save/restore stay balanced')
})

test('a working workspace speeds the belt up; subdued slows it down', () => {
  const calm = createAsteroidField({ width: 800, height: 600 })
  const intense = createAsteroidField({ width: 800, height: 600 })
  assert.equal(calm.draw(fakeCtx(), { dt: 16, mode: 'calm' }).mode, 'calm')
  assert.equal(intense.draw(fakeCtx(), { dt: 16, mode: 'intense' }).mode, 'intense')
  assert.ok(intense.speed > calm.speed)

  const subdued = createAsteroidField({ width: 800, height: 600 })
  subdued.draw(fakeCtx(), { dt: 16, mode: 'subdued' })
  assert.ok(subdued.speed < calm.speed)
})

test('the background is cached per size and mode, and rebuilt when either changes', () => {
  const ctx = fakeCtx()
  const scene = createAsteroidField({ width: 800, height: 600 })
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  const afterFirst = ctx.calls.gradient
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  assert.equal(ctx.calls.gradient, afterFirst, 'a second calm frame reuses the gradient')

  scene.draw(ctx, { dt: 16, mode: 'flare' })
  assert.ok(ctx.calls.gradient > afterFirst, 'a new mode builds a new background')

  const beforeResize = ctx.calls.gradient
  scene.resize(390, 844)
  scene.draw(ctx, { dt: 16, mode: 'flare' })
  assert.ok(ctx.calls.gradient > beforeResize, 'a resize rebuilds it')
})

test('the factory gives the PPC service its own renderer and palette', () => {
  const scene = createScene('ppc', { width: 800, height: 600 })
  assert.equal(typeof scene.draw, 'function')
  assert.equal(scene.paletteMax, ASTEROID_MAX_COLOR)
  assert.equal(sceneMaxColor('ppc'), ASTEROID_MAX_COLOR)
  assert.equal(scene.stars, undefined, 'the PPC scene is not the starfield fallback')
})

test('two fields with the same seed paint the same rocks', () => {
  const a = createAsteroidField({ width: 800, height: 600, seed: 7 })
  const b = createAsteroidField({ width: 800, height: 600, seed: 7 })
  const ca = fakeCtx()
  const cb = fakeCtx()
  a.draw(ca, { dt: 16, t: 0, mode: 'calm' })
  b.draw(cb, { dt: 16, t: 0, mode: 'calm' })
  assert.deepEqual(ca.calls, cb.calls, 'the renderer is deterministic')
})
