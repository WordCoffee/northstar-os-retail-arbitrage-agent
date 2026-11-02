// U5 — the frame loop and the default scene, tested without a browser.

import test from 'node:test'
import assert from 'node:assert/strict'

import { createSceneController, bindVisibility } from '../scene/sceneController.js'
import { createStarfield, mulberry32 } from '../scene/starfield.js'

function manualFrames() {
  let callback = null
  const cancelled = []
  return {
    request(cb) { callback = cb; return cancelled.length + 100 },
    cancel(handle) { cancelled.push(handle); callback = null },
    tick(t) { const next = callback; callback = null; if (next) next(t) },
    get pending() { return !!callback },
    cancelled,
  }
}

test('the cinematic loop draws at ~60 fps and skips early frames', () => {
  const frames = manualFrames()
  const drawn = []
  const c = createSceneController({ fpsCap: 60, requestFrame: frames.request, cancelFrame: frames.cancel, draw: (f) => drawn.push(f.t) })
  c.start()
  frames.tick(0)
  frames.tick(16)
  frames.tick(20)   // 4 ms later: not due
  frames.tick(33)
  assert.deepEqual(drawn, [0, 16, 33])
  assert.equal(c.frames, 3)
  assert.equal(frames.pending, true)
})

test('the reduced loop caps at 30 fps', () => {
  const frames = manualFrames()
  const drawn = []
  const c = createSceneController({ fpsCap: 30, requestFrame: frames.request, cancelFrame: frames.cancel, draw: (f) => drawn.push(f.t) })
  c.start()
  frames.tick(0)
  frames.tick(16)   // not due at 30 fps
  frames.tick(34)
  assert.deepEqual(drawn, [0, 34])
})

test('still paints exactly one frame and stops', () => {
  const frames = manualFrames()
  let calls = 0
  const c = createSceneController({ fpsCap: 0, requestFrame: frames.request, cancelFrame: frames.cancel, draw: () => { calls += 1 } })
  c.start()
  frames.tick(0)
  frames.tick(16)
  assert.equal(calls, 1)
  assert.equal(c.running, false)
  assert.equal(frames.pending, false)
})

test('a hidden tab stops painting without losing the loop', () => {
  const frames = manualFrames()
  let calls = 0
  const c = createSceneController({ fpsCap: 60, requestFrame: frames.request, cancelFrame: frames.cancel, draw: () => { calls += 1 } })
  c.start()
  frames.tick(0)
  c.pause()
  frames.tick(16)
  frames.tick(40)
  assert.equal(calls, 1)
  assert.equal(frames.pending, true)
  c.resume()
  frames.tick(80)
  assert.equal(calls, 2)
})

test('stop cancels the pending frame — no leaked loop after unmount', () => {
  const frames = manualFrames()
  const c = createSceneController({ fpsCap: 60, requestFrame: frames.request, cancelFrame: frames.cancel, draw: () => {} })
  c.start()
  c.stop()
  assert.equal(c.running, false)
  assert.equal(frames.pending, false)
  assert.equal(frames.cancelled.length, 1)
})

test('visibility binding adds exactly one listener and removes the same one', () => {
  const listeners = new Set()
  const win = {
    document: {
      hidden: false,
      addEventListener: (name, fn) => { assert.equal(name, 'visibilitychange'); listeners.add(fn) },
      removeEventListener: (name, fn) => { listeners.delete(fn) },
    },
  }
  let hidden = 0
  let shown = 0
  const unbind = bindVisibility(win, { onHide: () => { hidden += 1 }, onShow: () => { shown += 1 } })
  assert.equal(listeners.size, 1)
  const fire = () => [...listeners].forEach((fn) => fn())
  win.document.hidden = true
  fire()
  win.document.hidden = false
  fire()
  assert.deepEqual([hidden, shown], [1, 1])
  unbind()
  assert.equal(listeners.size, 0)
})

test('a window without a document is a no-op, not a crash', () => {
  const unbind = bindVisibility({}, { onHide: () => { throw new Error('should not run') } })
  assert.equal(typeof unbind, 'function')
  unbind()
})

// --- the default scene ----------------------------------------------------

function fakeCtx() {
  const calls = { fillRect: 0, arc: 0, fill: 0, stroke: 0, gradient: 0, moveTo: 0, lineTo: 0 }
  return {
    calls,
    fillStyle: '', strokeStyle: '', globalAlpha: 1, lineWidth: 1,
    fillRect() { calls.fillRect += 1 },
    createRadialGradient() { calls.gradient += 1; return { addColorStop() {} } },
    beginPath() {}, arc() { calls.arc += 1 }, fill() { calls.fill += 1 },
    stroke() { calls.stroke += 1 }, moveTo() { calls.moveTo += 1 }, lineTo() { calls.lineTo += 1 },
  }
}

test('the starfield paints a background, a haze and every star', () => {
  const ctx = fakeCtx()
  const field = createStarfield({ width: 1200, height: 800, seed: 3 })
  const info = field.draw(ctx, { dt: 16, t: 0, mode: 'calm' })
  assert.equal(info.stars, field.stars.length)
  assert.equal(ctx.calls.fillRect, 2 + field.stars.length) // background + haze + stars
  assert.ok(ctx.calls.arc >= 2, 'planet body and rim')
  assert.ok(ctx.calls.gradient >= 1)
})

test('the same seed paints the same sky', () => {
  const a = createStarfield({ width: 900, height: 600, seed: 11 })
  const b = createStarfield({ width: 900, height: 600, seed: 11 })
  assert.deepEqual(a.stars.map(s => s.x), b.stars.map(s => s.x))
  assert.equal(mulberry32(5)(), mulberry32(5)())
})

test('a working workspace intensifies the drift', () => {
  const calm = createStarfield({ width: 900, height: 600, seed: 2 })
  const intense = createStarfield({ width: 900, height: 600, seed: 2 })
  calm.draw(fakeCtx(), { dt: 16, mode: 'calm' })
  intense.draw(fakeCtx(), { dt: 16, mode: 'intense' })
  assert.ok(intense.speed > calm.speed)
  assert.equal(calm.speed, 1)
  assert.equal(intense.speed, 2.2)
})

test('resizing reseeds the field to the new area', () => {
  const field = createStarfield({ width: 1600, height: 900, seed: 4 })
  const large = field.stars.length
  field.resize(390, 844)
  assert.ok(field.stars.length < large)
  assert.ok(field.stars.length >= 60)
})
