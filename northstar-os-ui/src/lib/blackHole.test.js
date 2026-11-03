// U10 — the Research black-hole scene. The contrast test covers the palette
// automatically (it iterates SCENE_MAX_COLOR); these tests cover the renderer.

import test from 'node:test'
import assert from 'node:assert/strict'

import { createBlackHole, BLACK_HOLE_MAX_COLOR } from '../scene/blackHole.js'
import { createScene, sceneMaxColor } from '../scene/scenes.js'

function fakeCtx() {
  const calls = { fillRect: 0, gradient: 0, save: 0, restore: 0, arc: 0, ellipse: 0, stroke: 0, fill: 0 }
  return {
    calls,
    fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1,
    fillRect() { calls.fillRect += 1 },
    createRadialGradient() { calls.gradient += 1; return { addColorStop() {} } },
    createLinearGradient() { calls.gradient += 1; return { addColorStop() {} } },
    beginPath() {}, arc() { calls.arc += 1 }, ellipse() { calls.ellipse += 1 },
    fill() { calls.fill += 1 }, stroke() { calls.stroke += 1 },
    save() { calls.save += 1 }, restore() { calls.restore += 1 },
    translate() {}, rotate() {},
  }
}

test('the scene paints stars, a disk, two lensed arcs, the horizon and a ring', () => {
  const ctx = fakeCtx()
  const scene = createBlackHole({ width: 1200, height: 800, seed: 2 })
  const info = scene.draw(ctx, { dt: 16, t: 0, mode: 'calm' })

  assert.equal(info.maxColor, BLACK_HOLE_MAX_COLOR)
  assert.equal(info.mode, 'calm')
  assert.ok(info.radius > 0)
  assert.ok(ctx.calls.fillRect >= 80, 'the star field is drawn')
  assert.ok(ctx.calls.ellipse >= 4, 'far disk, two arcs, near disk')
  assert.ok(ctx.calls.arc >= 3, 'horizon, photon ring, orbiting speck')
  assert.equal(ctx.calls.save, ctx.calls.restore, 'save/restore stay balanced')
})

test('the horizon is painted pure black, never the palette maximum', () => {
  const seen = []
  const ctx = fakeCtx()
  const originalFill = ctx.fill.bind(ctx)
  ctx.fill = () => { seen.push(ctx.fillStyle); originalFill() }
  createBlackHole({ width: 800, height: 600 }).draw(ctx, { dt: 16, mode: 'calm' })
  assert.ok(seen.includes('#04050a'), 'the event horizon is black')
})

test('a working workspace speeds the disk up; subdued slows it', () => {
  const calm = createBlackHole({ width: 800, height: 600 })
  const intense = createBlackHole({ width: 800, height: 600 })
  calm.draw(fakeCtx(), { dt: 16, mode: 'calm' })
  intense.draw(fakeCtx(), { dt: 16, mode: 'intense' })
  assert.ok(intense.speed > calm.speed)

  const subdued = createBlackHole({ width: 800, height: 600 })
  subdued.draw(fakeCtx(), { dt: 16, mode: 'subdued' })
  assert.ok(subdued.speed < calm.speed)
})

test('gradients are cached per size and mode and rebuilt when either changes', () => {
  const ctx = fakeCtx()
  const scene = createBlackHole({ width: 800, height: 600 })
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  const afterFirst = ctx.calls.gradient
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  assert.equal(ctx.calls.gradient, afterFirst, 'a second calm frame reuses the gradients')

  scene.draw(ctx, { dt: 16, mode: 'flare' })
  assert.ok(ctx.calls.gradient > afterFirst, 'a new mode rebuilds them')

  const before = ctx.calls.gradient
  scene.resize(390, 844)
  scene.draw(ctx, { dt: 16, mode: 'flare' })
  assert.ok(ctx.calls.gradient > before, 'a resize rebuilds them')
})

test('the factory gives the research service its own renderer and palette', () => {
  const scene = createScene('research', { width: 800, height: 600 })
  assert.equal(typeof scene.draw, 'function')
  assert.equal(scene.paletteMax, BLACK_HOLE_MAX_COLOR)
  assert.equal(sceneMaxColor('research'), BLACK_HOLE_MAX_COLOR)
  assert.equal(scene.stars, undefined, 'the research scene is not the starfield fallback')
})

test('two scenes with the same seed paint the same frame', () => {
  const a = createBlackHole({ width: 800, height: 600, seed: 9 })
  const b = createBlackHole({ width: 800, height: 600, seed: 9 })
  const ca = fakeCtx()
  const cb = fakeCtx()
  a.draw(ca, { dt: 16, t: 0, mode: 'calm' })
  b.draw(cb, { dt: 16, t: 0, mode: 'calm' })
  assert.deepEqual(ca.calls, cb.calls)
})
