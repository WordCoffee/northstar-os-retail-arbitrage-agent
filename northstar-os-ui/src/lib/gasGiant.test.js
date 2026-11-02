import test from 'node:test'
import assert from 'node:assert/strict'
import { createGasGiant, GAS_GIANT_MAX_COLOR } from '../scene/gasGiant.js'

function fakeCtx() {
  const calls = { fillRect: 0, ellipse: 0, arc: 0, gradient: 0, clip: 0, save: 0, restore: 0 }
  return {
    calls,
    fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1,
    fillRect() { calls.fillRect += 1 },
    createRadialGradient() { calls.gradient += 1; return { addColorStop() {} } },
    beginPath() {}, arc() { calls.arc += 1 }, fill() {}, stroke() {},
    ellipse() { calls.ellipse += 1 }, clip() { calls.clip += 1 },
    save() { calls.save += 1 }, restore() { calls.restore += 1 },
    translate() {}, rotate() {},
  }
}

test('the gas giant paints bands, rings and a warm spill', () => {
  const ctx = fakeCtx()
  const scene = createGasGiant({ width: 1200, height: 800, seed: 5 })
  const info = scene.draw(ctx, { dt: 16, t: 0, mode: 'calm' })

  assert.equal(info.maxColor, GAS_GIANT_MAX_COLOR)
  assert.equal(info.mode, 'calm')
  assert.ok(info.radius > 0)
  assert.ok(ctx.calls.ellipse >= 4, 'three back rings plus the front arc')
  assert.ok(ctx.calls.fillRect >= 8, 'background, haze, bands, dust')
  assert.equal(ctx.calls.save, ctx.calls.restore, 'save/restore stay balanced')
})

test('a working workspace speeds the spin up and the error state dims it', () => {
  const calm = createGasGiant({ width: 800, height: 600 })
  const intense = createGasGiant({ width: 800, height: 600 })
  assert.equal(calm.draw(fakeCtx(), { dt: 16, mode: 'calm' }).mode, 'calm')
  assert.equal(intense.draw(fakeCtx(), { dt: 16, mode: 'intense' }).mode, 'intense')
  assert.ok(intense.speed > calm.speed)
  assert.equal(intense.speed, 2.4)
})

test('the flare mode repaints the background cache instead of reusing calm', () => {
  const ctx = fakeCtx()
  const scene = createGasGiant({ width: 800, height: 600 })
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  const afterCalm = ctx.calls.gradient
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  assert.equal(ctx.calls.gradient, afterCalm, 'calm reuses its cached background')
  scene.draw(ctx, { dt: 16, mode: 'flare' })
  assert.ok(ctx.calls.gradient > afterCalm, 'a new mode builds a new background')
})

test('resizing rebuilds the cached background', () => {
  const ctx = fakeCtx()
  const scene = createGasGiant({ width: 800, height: 600 })
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  const before = ctx.calls.gradient
  scene.resize(390, 844)
  scene.draw(ctx, { dt: 16, mode: 'calm' })
  assert.ok(ctx.calls.gradient > before)
})
