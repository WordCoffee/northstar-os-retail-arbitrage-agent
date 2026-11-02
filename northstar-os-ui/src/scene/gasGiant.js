// U6 — the Design Studio scene: a ringed gas giant with warm light spilling
// across the edges of the cockpit.
//
// Procedural and original. The brightest colour the renderer can paint is
// exported so the contrast test can prove the studio's glass panels stay
// readable against it (the panels are translucent).

import { mulberry32 } from './starfield.js'

/** Brightest pixel this scene may paint. The contrast test measures against it. */
export const GAS_GIANT_MAX_COLOR = '#f6d9a0'

const BANDS = [
  { y: -0.62, h: 0.10, color: '#7a4a24' },
  { y: -0.44, h: 0.14, color: '#a86a33' },
  { y: -0.22, h: 0.10, color: '#d99a55' },
  { y: -0.02, h: 0.16, color: '#b5793c' },
  { y: 0.24, h: 0.12, color: '#8a5528' },
  { y: 0.44, h: 0.14, color: '#6b3f1c' },
]

const SPEED = { calm: 1, intense: 2.4, flare: 1.8, subdued: 0.35 }

export function createGasGiant({ width = 1200, height = 800, seed = 5 } = {}) {
  const random = mulberry32(seed)
  let w = width
  let h = height
  let speed = 1
  let spin = 0
  let background = null
  let backgroundKey = ''
  let shade = null
  let shadeKey = ''
  let spill = null
  let spillKey = ''

  const dust = Array.from({ length: 90 }, () => ({
    x: random(), y: random(), s: 0.4 + random() * 1.2, tw: random() * Math.PI * 2,
  }))

  function resize(nextW, nextH) {
    w = Math.max(1, nextW)
    h = Math.max(1, nextH)
    background = null
    shade = null
    spill = null
  }

  function paintBackground(ctx, mode) {
    const key = `${w}x${h}:${mode}`
    if (background && backgroundKey === key) return background
    const g = ctx.createRadialGradient(w * 0.62, h * 0.46, 0, w * 0.62, h * 0.46, Math.max(w, h) * 0.8)
    g.addColorStop(0, mode === 'flare' ? 'rgba(246, 217, 160, 0.34)' : 'rgba(232, 176, 75, 0.16)')
    g.addColorStop(0.45, 'rgba(80, 52, 26, 0.10)')
    g.addColorStop(1, 'rgba(5, 6, 12, 0)')
    background = g
    backgroundKey = key
    return g
  }

  function draw(ctx, { dt = 16, t = 0, mode = 'calm' } = {}) {
    speed = SPEED[mode] || 1
    spin += 0.00006 * dt * speed

    ctx.fillStyle = '#05060c'
    ctx.fillRect(0, 0, w, h)
    ctx.fillStyle = paintBackground(ctx, mode)
    ctx.fillRect(0, 0, w, h)

    // Dust motes drifting across the frame.
    for (const mote of dust) {
      const drift = ((mote.x * w - spin * w * 0.4) % w + w) % w
      ctx.globalAlpha = 0.25 + 0.35 * Math.sin(t * 0.0015 + mote.tw)
      ctx.fillStyle = '#f1e6d2'
      ctx.fillRect(drift, mote.y * h, mote.s, mote.s)
    }
    ctx.globalAlpha = 1

    const cx = w * 0.42
    const cy = h * 0.50
    const r = Math.min(w, h) * 0.30

    // Rings behind the planet.
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(-0.32)
    const ringR = r * 1.85
    ctx.strokeStyle = mode === 'subdued' ? 'rgba(190, 150, 100, 0.28)' : 'rgba(232, 190, 130, 0.52)'
    ctx.lineWidth = Math.max(2, r * 0.10)
    for (const scale of [1, 0.86, 0.72]) {
      ctx.beginPath()
      ctx.ellipse(0, 0, ringR * scale, ringR * 0.26 * scale, 0, 0, Math.PI * 2)
      ctx.stroke()
    }
    ctx.restore()

    // The planet, clipped so the bands follow the sphere.
    ctx.save()
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.clip()

    const shift = (spin * r * 0.6) % (r * 2)
    for (const band of BANDS) {
      const by = cy + band.y * r + shift * 0.15
      ctx.fillStyle = band.color
      ctx.fillRect(cx - r, by, r * 2, Math.max(2, band.h * r))
    }

    // Shading: lit from the upper-left, the terminator falls away to the right.
    if (!shade || shadeKey !== `${w}x${h}`) {
      shade = ctx.createRadialGradient(cx - r * 0.4, cy - r * 0.45, r * 0.1, cx, cy, r * 1.1)
      shade.addColorStop(0, 'rgba(255, 238, 205, 0.32)')
      shade.addColorStop(0.6, 'rgba(0, 0, 0, 0.06)')
      shade.addColorStop(1, 'rgba(0, 0, 0, 0.48)')
      shadeKey = `${w}x${h}`
    }
    ctx.fillStyle = shade
    ctx.fillRect(cx - r, cy - r, r * 2, r * 2)
    ctx.restore()

    // A warm rim so the sphere reads against the dark sky instead of dissolving
    // into it (the bands alone were invisible at 0.82 glass).
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.strokeStyle = mode === 'subdued' ? 'rgba(120, 100, 80, 0.35)' : 'rgba(246, 217, 160, 0.45)'
    ctx.lineWidth = Math.max(1.5, r * 0.02)
    ctx.stroke()

    // Warm light spilling over the planet's edge onto the cockpit glass.
    if (!spill || spillKey !== `${w}x${h}:${mode}`) {
      spill = ctx.createRadialGradient(cx, cy, r * 0.92, cx, cy, r * 1.9)
      spill.addColorStop(0, mode === 'flare' ? 'rgba(246, 217, 160, 0.38)' : 'rgba(232, 176, 75, 0.20)')
      spill.addColorStop(1, 'rgba(232, 176, 75, 0)')
      spillKey = `${w}x${h}:${mode}`
    }
    ctx.fillStyle = spill
    ctx.fillRect(0, 0, w, h)

    // Front half of the rings, drawn over the planet so the discs cross it.
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(-0.32)
    ctx.strokeStyle = mode === 'subdued' ? 'rgba(190, 150, 100, 0.22)' : 'rgba(246, 217, 160, 0.42)'
    ctx.lineWidth = Math.max(2, r * 0.08)
    ctx.beginPath()
    ctx.ellipse(0, 0, ringR, ringR * 0.26, 0, 0, Math.PI)
    ctx.stroke()
    ctx.restore()

    return { maxColor: GAS_GIANT_MAX_COLOR, mode, radius: r }
  }

  return {
    draw,
    resize,
    get speed() { return speed },
    get paletteMax() { return GAS_GIANT_MAX_COLOR },
  }
}
