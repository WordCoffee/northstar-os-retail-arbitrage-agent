// SCENE ENGINE — one renderer, one scene, an honest teardown.
//
// There is no three.js in this repo (checked: `package.json` has react,
// react-dom and react-router-dom only, and `node_modules/three` does not
// exist). So a "scene" here is a procedural canvas-2D plate: a graded sky, three
// drifting nebula lobes, a deterministic star field and a few orbit arcs, drawn
// from the same palette and poster as the FLUX galactic assets under
// `src/assets/galactic/`. Nothing is fetched from the network.
//
// THE CONTRACT THIS FILE EXISTS TO PROVE:
//
//   • One live renderer at a time. `sceneRendererStats().live` is the number of
//     animation loops currently running in this document. Mounting a second
//     scene without disposing the first would make it 2; the host disposes
//     first, so a switch is 1 -> 1 and never 2.
//   • Teardown releases the loop AND the backing store. `dispose()` cancels the
//     pending frame, drops the 2D context reference and zeroes the canvas
//     dimensions, which frees the bitmap instead of leaving a detached plate
//     holding GPU memory.
//   • The mode is decided up front and is observable. `resolveSceneMode` turns
//     (webgl2, prefers-reduced-motion) into live | static | reduced. The surface
//     writes that to `data-scene-mode`, so the fallback is a fact in the DOM,
//     not a claim in a comment.
//   • WebGL2 is probed once per document on a throwaway canvas. A failed
//     `getContext('webgl2')` never locks the visible canvas, and a successful
//     probe releases its context immediately — a probe must not cost a GPU
//     context for the life of the tab.
//
// This module is DOM-free at import time and SSR-safe: everything that needs a
// window is passed in (or read lazily inside a function).

export const SCENE_MODES = Object.freeze({
  LIVE: 'live',
  STATIC: 'static',
  REDUCED: 'reduced',
})

export const SCENE_REASONS = Object.freeze({
  OK: 'ok',
  NO_WEBGL2: 'webgl2_unavailable',
  REDUCED_MOTION: 'prefers_reduced_motion',
  NO_CANVAS: 'no_canvas',
  NO_2D: 'no_2d_context',
  NO_SCHEDULER: 'no_frame_scheduler',
  PAINT_FAILED: 'paint_failed',
})

// ── the counter the tests assert on ─────────────────────────────────────────
let liveRenderers = 0
let renderersCreated = 0
let renderersDisposed = 0

export function sceneRendererStats() {
  return { live: liveRenderers, created: renderersCreated, disposed: renderersDisposed }
}

/** Test-only. Never call this from app code: it does not stop a running loop. */
export function resetSceneRendererStats() {
  liveRenderers = 0
  renderersCreated = 0
  renderersDisposed = 0
}

// ── environment probes ──────────────────────────────────────────────────────

const webglCache = new WeakMap()

/**
 * Is WebGL2 available in this document? Probed ONCE per document, on a detached
 * canvas, and the probe context is released straight away.
 */
export function detectWebGL2(host = globalThis) {
  const doc = host && host.document
  if (!doc || typeof doc.createElement !== 'function') return false
  if (webglCache.has(doc)) return webglCache.get(doc)
  let ok = false
  try {
    const probe = doc.createElement('canvas')
    const gl = typeof probe.getContext === 'function' ? probe.getContext('webgl2') : null
    ok = !!gl
    if (gl) {
      try {
        const lose = gl.getExtension && gl.getExtension('WEBGL_lose_context')
        if (lose && lose.loseContext) lose.loseContext()
      } catch { /* the probe dies with the detached canvas anyway */ }
    }
    probe.width = 0
    probe.height = 0
  } catch {
    ok = false
  }
  webglCache.set(doc, ok)
  return ok
}

export function prefersReducedMotion(host = globalThis) {
  try {
    return typeof host.matchMedia === 'function'
      && host.matchMedia('(prefers-reduced-motion: reduce)').matches === true
  } catch {
    return false
  }
}

export function readSceneEnvironment(host = globalThis) {
  return {
    webgl2: detectWebGL2(host),
    reducedMotion: prefersReducedMotion(host),
  }
}

/**
 * Reduced motion wins over everything: an operator who asked for less motion
 * gets a poster, even on a GPU that could animate it.
 */
export function resolveSceneMode({ webgl2 = true, reducedMotion = false } = {}) {
  if (reducedMotion) return SCENE_MODES.REDUCED
  return webgl2 ? SCENE_MODES.LIVE : SCENE_MODES.STATIC
}

function defaultScheduler() {
  const g = globalThis
  const raf = typeof g.requestAnimationFrame === 'function' ? g.requestAnimationFrame.bind(g) : null
  const caf = typeof g.cancelAnimationFrame === 'function' ? g.cancelAnimationFrame.bind(g) : null
  return {
    now: () => (typeof g.performance !== 'undefined' && g.performance.now ? g.performance.now() : Date.now()),
    requestFrame: raf,
    cancelFrame: caf,
  }
}

// ── deterministic field ─────────────────────────────────────────────────────

function stringSeed(text) {
  let h = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function seeded(seed) {
  let s = seed >>> 0
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 4294967296
  }
}

/**
 * The same scene looks the same on every load — a star field that reshuffles on
 * each mount reads as noise, not as a place. Different scenes get different
 * fields because the seed is the variant id.
 */
export function starFieldFor(scene) {
  const count = Math.max(0, Math.min(400, Number(scene?.spec?.stars ?? 90)))
  const rand = seeded(stringSeed(String(scene?.variantId || scene?.id || 'scene')))
  const field = []
  for (let i = 0; i < count; i += 1) {
    field.push({
      x: rand(),
      y: rand(),
      r: 0.35 + rand() * 1.35,
      phase: rand() * Math.PI * 2,
      speed: 0.25 + rand() * 0.85,
      warm: rand() > 0.72,
    })
  }
  return field
}

function hexToRgba(hex, alpha) {
  const value = String(hex || '#8fb4ff').replace('#', '')
  const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value
  const n = parseInt(full.slice(0, 6), 16)
  if (Number.isNaN(n)) return `rgba(143, 180, 255, ${alpha})`
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// ── the paint ───────────────────────────────────────────────────────────────

/**
 * One frame. `t` is seconds since the runtime started. Pure drawing: no reads
 * from layout beyond the size the caller measured.
 */
export function paintScene(ctx, scene, t, width, height, field = null) {
  const w = Math.max(1, Math.floor(width || 1))
  const h = Math.max(1, Math.floor(height || 1))
  const stars = field || starFieldFor(scene)
  const sky = scene?.sky || ['#0a1018', '#04060b']
  const accent = scene?.accent || '#8fb4ff'
  const spec = scene?.spec || {}
  const drift = Number.isFinite(spec.drift) ? spec.drift : 0.4
  const time = Number.isFinite(t) ? t : 0

  const wash = ctx.createLinearGradient(0, 0, 0, h)
  wash.addColorStop(0, sky[0])
  wash.addColorStop(1, sky[1])
  ctx.fillStyle = wash
  ctx.fillRect(0, 0, w, h)

  // Three nebula lobes, drifting at a fraction of a pixel per frame so the
  // motion is a breath, not a scroll.
  for (let i = 0; i < 3; i += 1) {
    const cx = w * (0.24 + 0.26 * i) + Math.sin(time * 0.06 * drift + i) * w * 0.015
    const cy = h * (0.34 + 0.16 * i) + Math.cos(time * 0.05 * drift + i) * h * 0.02
    const radius = Math.max(w, h) * (0.34 - 0.07 * i)
    const lobes = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
    lobes.addColorStop(0, hexToRgba(accent, 0.20 - 0.05 * i))
    lobes.addColorStop(1, hexToRgba(accent, 0))
    ctx.fillStyle = lobes
    ctx.fillRect(0, 0, w, h)
  }

  // Stars grow a little with duration so a long-running shell does not look
  // still, but the drift stays inside a 2px budget.
  ctx.save()
  for (const s of stars) {
    const twinkle = 0.55 + 0.45 * Math.sin(time * s.speed * 0.9 + s.phase)
    const x = s.x * w + Math.sin(time * 0.05 * drift + s.phase) * 1.6
    const y = s.y * h + Math.cos(time * 0.04 * drift + s.phase) * 1.2
    ctx.beginPath()
    ctx.arc(x, y, s.r, 0, Math.PI * 2)
    ctx.fillStyle = s.warm ? `rgba(255, 226, 190, ${0.75 * twinkle})` : `rgba(224, 236, 255, ${0.85 * twinkle})`
    ctx.fill()
  }
  ctx.restore()

  // Orbit arcs: the scene's "structure" cue. Squashed with a scale so they read
  // as a plane rather than as drawn circles.
  const arcs = Math.max(0, Math.min(4, Number(spec.arcs ?? 2)))
  const ax = w * (spec.ax ?? 0.5)
  const ay = h * (spec.ay ?? 0.62)
  for (let i = 0; i < arcs; i += 1) {
    const radius = Math.min(w, h) * (0.20 + 0.13 * i)
    ctx.save()
    ctx.translate(ax, ay)
    ctx.scale(1, 0.42)
    ctx.beginPath()
    ctx.arc(0, 0, radius, 0, Math.PI * 2)
    ctx.strokeStyle = hexToRgba(accent, 0.26 - 0.05 * i)
    ctx.lineWidth = 1
    ctx.stroke()
    ctx.restore()
  }

  // A single focal bead where the arcs meet, tinted by the scene accent.
  const bead = ctx.createRadialGradient(ax, ay, 0, ax, ay, Math.min(w, h) * 0.09)
  bead.addColorStop(0, hexToRgba(accent, 0.5))
  bead.addColorStop(1, hexToRgba(accent, 0))
  ctx.fillStyle = bead
  ctx.fillRect(0, 0, w, h)
}

// ── the runtime ─────────────────────────────────────────────────────────────

/**
 * @param {object} options
 * @param {HTMLCanvasElement} [options.canvas]
 * @param {object} options.scene
 * @param {{webgl2?: boolean, reducedMotion?: boolean}} [options.environment]
 * @param {{now: Function, requestFrame: Function|null, cancelFrame: Function|null}} [options.scheduler]
 * @param {(mode: string, reason: string) => void} [options.onModeChange]
 */
export function createSceneRuntime({
  canvas = null,
  scene,
  environment = {},
  scheduler = null,
  onModeChange = null,
} = {}) {
  if (!scene || typeof scene !== 'object') {
    throw new TypeError('createSceneRuntime needs a scene descriptor')
  }
  const clock = scheduler || defaultScheduler()
  let mode = resolveSceneMode(environment)
  let reason = mode === SCENE_MODES.REDUCED
    ? SCENE_REASONS.REDUCED_MOTION
    : (mode === SCENE_MODES.LIVE ? SCENE_REASONS.OK : SCENE_REASONS.NO_WEBGL2)

  let ctx = null
  let frameId = 0
  let started = false
  let disposed = false
  let paused = false
  let counting = false
  let frames = 0
  let startedAt = 0
  const field = starFieldFor(scene)

  renderersCreated += 1

  function degrade(next, why) {
    if (mode !== next) {
      mode = next
      reason = why || reason
      if (onModeChange) onModeChange(mode, reason)
    }
  }

  function cancel() {
    if (frameId && clock && typeof clock.cancelFrame === 'function') {
      clock.cancelFrame(frameId)
    }
    frameId = 0
  }

  // A canvas that cannot give a 2D context is the same story as no WebGL: the
  // poster is the honest answer, not a black rectangle.
  if (mode === SCENE_MODES.LIVE) {
    if (!canvas || typeof canvas.getContext !== 'function') {
      degrade(SCENE_MODES.STATIC, SCENE_REASONS.NO_CANVAS)
    } else if (!clock || typeof clock.requestFrame !== 'function') {
      degrade(SCENE_MODES.STATIC, SCENE_REASONS.NO_SCHEDULER)
    } else {
      try { ctx = canvas.getContext('2d') } catch { ctx = null }
      if (!ctx) degrade(SCENE_MODES.STATIC, SCENE_REASONS.NO_2D)
    }
  }

  function measure() {
    const w = Math.max(1, Math.floor(canvas.clientWidth || canvas.width || 0))
    const h = Math.max(1, Math.floor(canvas.clientHeight || canvas.height || 0))
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w
      canvas.height = h
    }
    return { w, h }
  }

  function frame(time) {
    if (disposed || paused || mode !== SCENE_MODES.LIVE) return
    frames += 1
    try {
      const { w, h } = measure()
      paintScene(ctx, scene, (time - startedAt) / 1000, w, h, field)
    } catch {
      // A device that cannot paint must not spin: stop, say why, show the poster.
      cancel()
      if (counting) { liveRenderers -= 1; counting = false }
      degrade(SCENE_MODES.STATIC, SCENE_REASONS.PAINT_FAILED)
      return
    }
    frameId = clock.requestFrame(frame)
  }

  function start() {
    if (disposed || started) return runtime
    started = true
    if (mode !== SCENE_MODES.LIVE) return runtime
    liveRenderers += 1
    counting = true
    startedAt = typeof clock.now === 'function' ? clock.now() : 0
    frames = 1
    try {
      const { w, h } = measure()
      paintScene(ctx, scene, 0, w, h, field)
    } catch {
      if (counting) { liveRenderers -= 1; counting = false }
      degrade(SCENE_MODES.STATIC, SCENE_REASONS.PAINT_FAILED)
      return runtime
    }
    frameId = clock.requestFrame(frame)
    return runtime
  }

  function pause() {
    if (disposed) return
    paused = true
    cancel()
  }

  function resume() {
    if (disposed || !paused) return
    paused = false
    if (mode === SCENE_MODES.LIVE && counting) frameId = clock.requestFrame(frame)
  }

  function dispose() {
    if (disposed) return
    disposed = true
    cancel()
    if (counting) { liveRenderers -= 1; counting = false }
    renderersDisposed += 1
    ctx = null
    if (canvas) {
      try {
        // Zeroing the dimensions frees the backing store immediately; leaving
        // them allocated keeps the plate alive after the scene is gone.
        canvas.width = 0
        canvas.height = 0
      } catch { /* detached canvas */ }
    }
  }

  const runtime = {
    sceneId: scene.id,
    variantId: scene.variantId,
    start,
    pause,
    resume,
    dispose,
    get mode() { return mode },
    get reason() { return reason },
    get frames() { return frames },
    get started() { return started },
    get paused() { return paused },
    get disposed() { return disposed },
  }
  return runtime
}

/**
 * One scene at a time, per host. This is what the shell mounts: `mount` always
 * disposes the resident scene before building the next one, so a tab switch is
 * 1 -> 1 renderers and never 1 -> 2.
 */
export function createSceneHost({ scheduler = null } = {}) {
  let current = null
  return {
    mount({ canvas = null, scene, environment = {} } = {}) {
      const replaced = current ? current.sceneId : null
      if (current) {
        current.dispose()
        current = null
      }
      current = createSceneRuntime({ canvas, scene, environment, scheduler })
      current.start()
      return { runtime: current, replaced }
    },
    unmount() {
      if (current) {
        current.dispose()
        current = null
      }
    },
    get current() { return current },
    get liveRenderers() { return liveRenderers },
  }
}
