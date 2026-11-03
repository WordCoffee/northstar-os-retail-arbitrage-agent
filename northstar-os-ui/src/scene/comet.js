// U11 — the Golden Goose scene: a comet pass.
//
// A bright nucleus with a dust tail that streams behind it, drifting slowly
// across the sky. The tail is drawn as a tapering ribbon of particles so a
// product list can sit over it and still read: nothing in this scene paints
// brighter than the declared maximum, and the contrast test proves the glass
// panels clear AA against it.
//
// Procedural and original; no film frames, no external assets.

import { mulberry32 } from './starfield.js'

/** Brightest pixel this scene may paint. The contrast test measures against it. */
export const COMET_MAX_COLOR = '#dff0ff'

const SPEED = { calm: 1, intense: 2.0, flare: 1.5, subdued: 0.3 }

export function createComet({ width = 1200, height = 800, seed = 23 } = {}) {
  const random = mulberry32(seed)
  let w = Math.max(1, width)
  let h = Math.max(1, height)
  let speed = 1
  let travel = 0
  let background = null
  let backgroundKey = ''

  const stars = Array.from({ length: 90 }, () => ({
    x: random(), y: random(), s: 0.4 + random() * 1.1, tw: random() * 6.28,
  }))
  // The tail: particles that lag the nucleus by a jittered amount, so the ribbon
  // has a soft edge instead of a hard wedge.
  const tail = Array.from({ length: 120 }, () => ({
    lag: random(),          // 0 = at the nucleus, 1 = far end
    spread: (random() - 0.5) * 2,
    size: 0.4 + random() * 1.4,
    alpha: 0.25 + random() * 0.55,
  }))

  function resize(nextW, nextH) {
    w = Math.max(1, nextW)
    h = Math.max(1, nextH)
    background = null
  }

  function paintBackground(ctx, mode) {
    const key = `${w}x${h}:${mode}`
    if (background && backgroundKey === key) return background
    const g = ctx.createRadialGradient(w * 0.3, h * 0.28, 0, w * 0.45, h * 0.4, Math.max(w, h))
    g.addColorStop(0, mode === 'flare' ? 'rgba(223, 240, 255, 0.16)' : 'rgba(150, 190, 220, 0.09)')
    g.addColorStop(0.5, 'rgba(20, 30, 44, 0.10)')
    g.addColorStop(1, 'rgba(3, 5, 9, 0)')
    background = g
    backgroundKey = key
    return g
  }

  function draw(ctx, { dt = 16, t = 0, mode = 'calm' } = {}) {
    speed = SPEED[mode] || 1
    travel += dt * 0.00012 * speed

    ctx.save()
    ctx.fillStyle = paintBackground(ctx, mode)
    ctx.fillRect(0, 0, w, h)

    // Stars.
    for (const s of stars) {
      const tw = 0.35 + 0.3 * Math.sin(t * 0.001 + s.tw)
      ctx.globalAlpha = tw * (mode === 'subdued' ? 0.35 : 0.7)
      ctx.fillStyle = COMET_MAX_COLOR
      ctx.fillRect(s.x * w, s.y * h, s.s, s.s)
    }
    ctx.globalAlpha = 1

    // The comet crosses left→right on a shallow diagonal, wrapping.
    const px = ((travel % 1.4) - 0.2) * w
    const py = h * 0.34 + Math.sin(travel * 6.283) * h * 0.03
    const dirX = 1
    const dirY = 0.34
    const len = Math.min(w, h) * 0.42

    // Tail: far particles first so the head paints over them.
    for (const p of tail) {
      const d = p.lag * len
      const x = px - dirX * d
      const y = py - dirY * d + p.spread * d * 0.22
      const fade = (1 - p.lag) * p.alpha * (mode === 'subdued' ? 0.45 : 1)
      ctx.globalAlpha = fade
      ctx.fillStyle = COMET_MAX_COLOR
      const s = p.size * (1 + p.lag * 1.6)
      ctx.fillRect(x, y, s, s)
    }
    ctx.globalAlpha = 1

    // Nucleus: a soft glow plus a hard core.
    const glow = ctx.createRadialGradient(px, py, 0, px, py, len * 0.28)
    glow.addColorStop(0, 'rgba(223, 240, 255, 0.55)')
    glow.addColorStop(1, 'rgba(223, 240, 255, 0)')
    ctx.fillStyle = glow
    ctx.fillRect(px - len * 0.28, py - len * 0.28, len * 0.56, len * 0.56)

    ctx.beginPath()
    ctx.arc(px, py, Math.max(2, len * 0.035), 0, Math.PI * 2)
    ctx.fillStyle = mode === 'subdued' ? 'rgba(200, 220, 240, 0.7)' : COMET_MAX_COLOR
    ctx.fill()

    ctx.restore()
    return { maxColor: COMET_MAX_COLOR, mode, x: px, y: py }
  }

  return {
    draw,
    resize,
    get speed() { return speed },
    get paletteMax() { return COMET_MAX_COLOR },
  }
}
