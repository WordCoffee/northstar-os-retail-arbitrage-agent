// U11 — the Golden Goose comet scene. The contrast test covers the palette
// automatically; these tests cover the renderer and the "list over the tail"
// constraint: nothing in the scene paints above the declared maximum.

import test from 'node:test'
import assert from 'node:assert/strict'

import { createComet, COMET_MAX_COLOR } from '../scene/comet.js'
import { createScene, sceneMaxColor } from '../scene/scenes.js'

function fakeCtx() {
  const calls = { fillRect: 0, gradient: 0, save: 0, restore: 0, arc: 0 }
  return {
    calls,
    fillStyle: '', globalAlpha: 1,
    fillRect() { calls.fillRect += 1 },
    createRadialGradient() { calls.gradient += 1; return { addColorStop() {} } },
    beginPath() {}, arc() { calls.arc += 1 }, fill() {},
    save() { calls.save += 1 }, restore() { calls.restore += 1 },
  }
}

test('the scene paints a star field, a tail ribbon and a nucleus', () => {
  const ctx = fakeCtx()
  const scene = createComet({ width: 1200, height: 800, seed: 4 })
  const info = scene.draw(ctx, { dt: 16, t: 0, mode: 'calm' })

  assert.equal(info.maxColor, COMET_MAX_COLOR)
  assert.equal(info.mode, 'calm')
  assert.ok(ctx.calls.fillRect > 150, 'stars + 120 tail particles + the glow')
  assert.equal(ctx.calls.arc, 1, 'one hard nucleus')
  assert.equal(ctx.calls.save, ctx.calls.restore, 'save/restore stay balanced')
})

test('the comet travels and wraps instead of leaving the sky for ever', () => {
  const scene = createComet({ width: 800, height: 600 })
  const first = scene.draw(fakeCtx(), { dt: 16, mode: 'calm' }).x
  const later = scene.draw(fakeCtx(), { dt: 16, mode: 'calm' }).x
  assert.ok(later > first, 'it moves forward')

  // `travel` advances by dt * 0.00012 and wraps at 1.4, so one full cycle of
  // travel lands the comet exactly where it was.
  const wrapped = scene.draw(fakeCtx(), { dt: 1.4 / 0.00012, mode: 'calm' }).x
  assert.ok(Math.abs(wrapped - later) < 1e-6, 'and wraps back to the same place')
})

test('a working workspace speeds the pass up; subdued slows it', () => {
  const calm = createComet({ width: 800, height: 600 })
  const intense = createComet({ width: 800, height: 600 })
  calm.draw(fakeCtx(), { dt: 16, mode: 'calm' })
  intense.draw(fakeCtx(), { dt: 16, mode: 'intense' })
  assert.ok(intense.speed > calm.speed)

  const subdued = createComet({ width: 800, height: 600 })
  subdued.draw(fakeCtx(), { dt: 16, mode: 'subdued' })
  assert.ok(subdued.speed < calm.speed)
})

test('nothing the comet paints is brighter than its declared maximum', () => {
  const scene = createComet({ width: 800, height: 600 })
  const seen = new Set()
  const ctx = fakeCtx()
  ctx.fillRect = () => { seen.add(String(ctx.fillStyle)) }
  scene.draw(ctx, { dt: 16, mode: 'flare' })
  for (const colour of seen) {
    // Either the declared max, a gradient object, or an rgba of the same hue.
    const ok = colour === COMET_MAX_COLOR
      || colour === '[object Object]'
      || /^rgba\(223, 240, 255,/.test(colour)
    assert.ok(ok, `unexpected fill colour ${colour}`)
  }
})

test('the factory gives the goose service its own renderer and palette', () => {
  const scene = createScene('goose', { width: 800, height: 600 })
  assert.equal(typeof scene.draw, 'function')
  assert.equal(scene.paletteMax, COMET_MAX_COLOR)
  assert.equal(sceneMaxColor('goose'), COMET_MAX_COLOR)
  assert.equal(scene.stars, undefined, 'the goose scene is not the starfield fallback')
})

test('two scenes with the same seed paint the same frame', () => {
  const a = createComet({ width: 800, height: 600, seed: 12 })
  const b = createComet({ width: 800, height: 600, seed: 12 })
  const ca = fakeCtx()
  const cb = fakeCtx()
  a.draw(ca, { dt: 16, t: 0, mode: 'calm' })
  b.draw(cb, { dt: 16, t: 0, mode: 'calm' })
  assert.deepEqual(ca.calls, cb.calls)
})
