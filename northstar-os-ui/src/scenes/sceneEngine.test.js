// The scene engine's lifecycle is the deliverable: one live renderer, released
// on switch, no loop at all in the two fallback modes. These tests drive the
// engine with a fake canvas and a fake frame clock, so the counts are real.

import { describe, it, expect, beforeEach } from 'vitest'
import {
  SCENE_MODES,
  SCENE_REASONS,
  createSceneHost,
  createSceneRuntime,
  detectWebGL2,
  paintScene,
  prefersReducedMotion,
  resetSceneRendererStats,
  resolveSceneMode,
  sceneRendererStats,
  starFieldFor,
} from './sceneEngine.js'
import { sceneForService } from './sceneRegistry.js'

function makeContext() {
  const calls = { fillRect: 0, stroke: 0, fill: 0, arc: 0 }
  const gradient = () => ({ addColorStop() {} })
  return {
    calls,
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 1,
    createLinearGradient: gradient,
    createRadialGradient: gradient,
    fillRect() { calls.fillRect += 1 },
    fill() { calls.fill += 1 },
    stroke() { calls.stroke += 1 },
    beginPath() {},
    arc() { calls.arc += 1 },
    save() {},
    restore() {},
    translate() {},
    scale() {},
  }
}

function makeCanvas({ width = 900, height = 600, twoD = true } = {}) {
  const ctx = twoD ? makeContext() : null
  const canvas = {
    clientWidth: width,
    clientHeight: height,
    width: 0,
    height: 0,
    contexts: [],
    getContext(type) {
      canvas.contexts.push(type)
      return type === '2d' ? ctx : null
    },
    ctx,
  }
  return canvas
}

function makeScheduler() {
  let now = 1000
  let nextId = 0
  const queue = new Map()
  return {
    now: () => now,
    requestFrame(cb) {
      nextId += 1
      queue.set(nextId, cb)
      return nextId
    },
    cancelFrame(id) { queue.delete(id) },
    tick(ms = 16) {
      now += ms
      const due = [...queue.entries()]
      queue.clear()
      for (const [, cb] of due) cb(now)
    },
    get pending() { return queue.size },
  }
}

const live = { webgl2: true, reducedMotion: false }

beforeEach(() => {
  resetSceneRendererStats()
})

describe('mode resolution', () => {
  it('animates only when WebGL2 exists and motion is allowed', () => {
    expect(resolveSceneMode({ webgl2: true, reducedMotion: false })).toBe(SCENE_MODES.LIVE)
  })

  it('falls back to a still frame without WebGL2', () => {
    expect(resolveSceneMode({ webgl2: false, reducedMotion: false })).toBe(SCENE_MODES.STATIC)
  })

  it('reduced motion wins even on a capable GPU', () => {
    expect(resolveSceneMode({ webgl2: true, reducedMotion: true })).toBe(SCENE_MODES.REDUCED)
  })
})

describe('one live renderer at a time', () => {
  it('a mount starts exactly one loop', () => {
    const scheduler = makeScheduler()
    const runtime = createSceneRuntime({
      canvas: makeCanvas(),
      scene: sceneForService('listings'),
      environment: live,
      scheduler,
    })
    runtime.start()
    expect(runtime.mode).toBe(SCENE_MODES.LIVE)
    expect(runtime.frames).toBe(1)
    expect(sceneRendererStats().live).toBe(1)
    expect(scheduler.pending).toBe(1)
    runtime.dispose()
  })

  it('switching scenes is 1 -> 1, never 1 -> 2', () => {
    const scheduler = makeScheduler()
    const host = createSceneHost({ scheduler })

    host.mount({ canvas: makeCanvas(), scene: sceneForService('listings'), environment: live })
    expect(sceneRendererStats()).toEqual({ live: 1, created: 1, disposed: 0 })

    const swap = host.mount({ canvas: makeCanvas(), scene: sceneForService('golden-goose'), environment: live })
    expect(swap.replaced).toBe('listings')
    expect(sceneRendererStats()).toEqual({ live: 1, created: 2, disposed: 1 })
    expect(host.current.sceneId).toBe('golden-goose')
    expect(scheduler.pending).toBe(1)

    host.unmount()
    expect(sceneRendererStats()).toEqual({ live: 0, created: 2, disposed: 2 })
  })

  it('unmount releases the loop and the backing store', () => {
    const scheduler = makeScheduler()
    const canvas = makeCanvas()
    const host = createSceneHost({ scheduler })
    host.mount({ canvas, scene: sceneForService('adpilot'), environment: live })
    expect(canvas.width).toBe(900)
    expect(scheduler.pending).toBe(1)

    host.unmount()
    expect(scheduler.pending).toBe(0)
    expect(canvas.width).toBe(0)
    expect(canvas.height).toBe(0)
    expect(sceneRendererStats().live).toBe(0)
  })

  it('dispose is idempotent', () => {
    const runtime = createSceneRuntime({
      canvas: makeCanvas(), scene: sceneForService('home'), environment: live, scheduler: makeScheduler(),
    })
    runtime.start()
    runtime.dispose()
    runtime.dispose()
    expect(sceneRendererStats()).toEqual({ live: 0, created: 1, disposed: 1 })
  })
})

describe('the loop', () => {
  it('advances frames while visible and stops while paused', () => {
    const scheduler = makeScheduler()
    const canvas = makeCanvas()
    const runtime = createSceneRuntime({
      canvas, scene: sceneForService('profitability'), environment: live, scheduler,
    })
    runtime.start()
    scheduler.tick()
    scheduler.tick()
    expect(runtime.frames).toBe(3)
    expect(canvas.ctx.calls.fillRect).toBeGreaterThan(0)

    runtime.pause()
    expect(scheduler.pending).toBe(0)
    const frozen = runtime.frames
    scheduler.tick()
    expect(runtime.frames).toBe(frozen)

    runtime.resume()
    expect(scheduler.pending).toBe(1)
    scheduler.tick()
    expect(runtime.frames).toBe(frozen + 1)
    runtime.dispose()
  })

  it('draws a different field for a different scene', () => {
    const a = starFieldFor(sceneForService('listings'))
    const b = starFieldFor(sceneForService('adpilot'))
    expect(a.length).toBeGreaterThan(0)
    expect(a[0]).not.toEqual(b[0])
    expect(starFieldFor(sceneForService('listings'))[0]).toEqual(a[0])
  })
})

describe('fallback modes schedule no frames at all', () => {
  it('no WebGL2 -> static, and the canvas is never even asked for a context', () => {
    const scheduler = makeScheduler()
    const canvas = makeCanvas()
    const runtime = createSceneRuntime({
      canvas, scene: sceneForService('listings'), environment: { webgl2: false }, scheduler,
    })
    runtime.start()
    expect(runtime.mode).toBe(SCENE_MODES.STATIC)
    expect(runtime.reason).toBe(SCENE_REASONS.NO_WEBGL2)
    expect(canvas.contexts).toEqual([])
    expect(scheduler.pending).toBe(0)
    expect(sceneRendererStats().live).toBe(0)
    runtime.dispose()
  })

  it('reduced motion -> reduced, poster only, no requestAnimationFrame', () => {
    const scheduler = makeScheduler()
    const canvas = makeCanvas()
    const runtime = createSceneRuntime({
      canvas,
      scene: sceneForService('autothink'),
      environment: { webgl2: true, reducedMotion: true },
      scheduler,
    })
    runtime.start()
    expect(runtime.mode).toBe(SCENE_MODES.REDUCED)
    expect(runtime.reason).toBe(SCENE_REASONS.REDUCED_MOTION)
    expect(scheduler.pending).toBe(0)
    expect(canvas.contexts).toEqual([])
    runtime.dispose()
  })

  it('a canvas with no 2D context degrades to static', () => {
    const runtime = createSceneRuntime({
      canvas: makeCanvas({ twoD: false }),
      scene: sceneForService('home'),
      environment: live,
      scheduler: makeScheduler(),
    })
    runtime.start()
    expect(runtime.mode).toBe(SCENE_MODES.STATIC)
    expect(runtime.reason).toBe(SCENE_REASONS.NO_2D)
    runtime.dispose()
  })

  it('no canvas at all degrades to static', () => {
    const runtime = createSceneRuntime({
      canvas: null, scene: sceneForService('home'), environment: live, scheduler: makeScheduler(),
    })
    runtime.start()
    expect(runtime.mode).toBe(SCENE_MODES.STATIC)
    expect(runtime.reason).toBe(SCENE_REASONS.NO_CANVAS)
    runtime.dispose()
  })
})

describe('environment probes are defensive', () => {
  it('reports no WebGL2 when there is no document', () => {
    expect(detectWebGL2({})).toBe(false)
  })

  it('reports no reduced-motion preference when matchMedia is missing', () => {
    expect(prefersReducedMotion({})).toBe(false)
  })

  it('reads the documented media query when matchMedia exists', () => {
    const host = { matchMedia: (q) => ({ matches: q === '(prefers-reduced-motion: reduce)' }) }
    expect(prefersReducedMotion(host)).toBe(true)
  })
})

describe('paint', () => {
  it('fills the plate before drawing stars', () => {
    const ctx = makeContext()
    paintScene(ctx, sceneForService('listings'), 0, 640, 480)
    expect(ctx.calls.fillRect).toBeGreaterThan(0)
    expect(ctx.calls.arc).toBeGreaterThan(0)
  })
})
