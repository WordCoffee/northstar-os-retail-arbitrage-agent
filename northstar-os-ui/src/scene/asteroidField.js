// U9 — the PPC scene: an asteroid field, drifting slowly across the belt.
//
// Procedural and original. The belt is the metaphor for a bid landscape: many
// small objects moving at their own speed, a few large ones that matter. It
// never paints over a control (the scene layer is pointer-events:none) and the
// brightest colour it may paint is exported so the contrast test can prove the
// PPC panels stay readable through 0.72 glass.

import { mulberry32 } from './starfield.js'

/** Brightest pixel this scene may paint. The contrast test measures against it. */
export const ASTEROID_MAX_COLOR = '#cfc4b4'

const SPEED = { calm: 1, intense: 2.2, flare: 1.7, subdued: 0.3 }

function makeRock(random, { near = false } = {}) {
  const sides = 5 + Math.floor(random() * 4)
  const shape = Array.from({ length: sides }, (_, i) => {
    const a = (i / sides) * Math.PI * 2
    const r = 0.62 + random() * 0.38
    return { a, r }
  })
  return {
    x: random(),
    y: near ? 0.62 + random() * 0.36 : 0.08 + random() * 0.84,
    size: near ? 0.055 + random() * 0.05 : 0.006 + random() * 0.022,
    spin: (random() - 0.5) * 0.6,
    phase: random() * Math.PI * 2,
    depth: near ? 1 : 0.35 + random() * 0.5,
    shape,
    sides,
  }
}

export function createAsteroidField({ width = 1200, height = 800, seed = 11 } = {}) {
  const random = mulberry32(seed)
  let w = Math.max(1, width)
  let h = Math.max(1, height)
  let speed = 1
  let drift = 0
  let background = null
  let backgroundKey = ''

  const belt = Array.from({ length: 46 }, () => makeRock(random))
  const near = Array.from({ length: 4 }, () => makeRock(random, { near: true }))
  const dust = Array.from({ length: 70 }, () => ({ x: random(), y: random(), s: 0.4 + random() * 1.1, tw: random() * 6.28 }))

  function resize(nextW, nextH) {
    w = Math.max(1, nextW)
    h = Math.max(1, nextH)
    background = null
  }

  function paintBackground(ctx, mode) {
    const key = `${w}x${h}:${mode}`
    if (background && backgroundKey === key) return background
    const g = ctx.createRadialGradient(w * 0.24, h * 0.28, 0, w * 0.4, h * 0.4, Math.max(w, h))
    g.addColorStop(0, mode === 'flare' ? 'rgba(207, 196, 180, 0.20)' : 'rgba(150, 160, 175, 0.10)')
    g.addColorStop(0.5, 'rgba(26, 32, 44, 0.10)')
    g.addColorStop(1, 'rgba(4, 6, 10, 0)')
    background = g
    backgroundKey = key
    return g
  }

  function paintRock(ctx, rock, t, alpha, tint) {
    const px = ((rock.x + drift * rock.depth * 0.12) % 1.15) - 0.075
    const cx = px * w
    const cy = rock.y * h
    const r = rock.size * Math.min(w, h)
    const spin = rock.phase + t * 0.00012 * rock.spin

    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(spin)
    ctx.globalAlpha *= alpha
    ctx.beginPath()
    rock.shape.forEach((p, i) => {
      const a = p.a + spin * 0.2
      const x = Math.cos(a) * r * p.r
      const y = Math.sin(a) * r * p.r * 0.86
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.closePath()
    ctx.fillStyle = tint.fill
    ctx.fill()
    ctx.strokeStyle = tint.rim
    ctx.lineWidth = Math.max(0.6, r * 0.09)
    ctx.stroke()
    ctx.restore()
  }

  function draw(ctx, { dt = 16, t = 0, mode = 'calm' } = {}) {
    speed = SPEED[mode] || 1
    drift += dt * 0.0016 * speed

    ctx.save()
    ctx.fillStyle = paintBackground(ctx, mode)
    ctx.fillRect(0, 0, w, h)

    // Far belt: dim, small, slow — the many keywords nobody is bidding on.
    const farTint = {
      fill: mode === 'subdued' ? 'rgba(120, 126, 138, 0.20)' : 'rgba(146, 152, 164, 0.30)',
      rim: mode === 'subdued' ? 'rgba(160, 166, 176, 0.18)' : 'rgba(207, 196, 180, 0.26)',
    }
    for (const rock of belt) paintRock(ctx, rock, t, 0.55 + rock.depth * 0.4, farTint)

    // Dust catching the light.
    ctx.save()
    for (const d of dust) {
      const x = ((d.x + drift * 0.02) % 1) * w
      const tw = 0.35 + 0.35 * Math.sin(t * 0.001 + d.tw)
      ctx.globalAlpha = tw * (mode === 'subdued' ? 0.4 : 0.8)
      ctx.fillStyle = ASTEROID_MAX_COLOR
      ctx.fillRect(x, d.y * h, d.s, d.s)
    }
    ctx.restore()

    // Near belt: the handful of big rocks that actually matter.
    const nearTint = {
      fill: mode === 'flare' ? 'rgba(207, 196, 180, 0.55)' : 'rgba(96, 104, 118, 0.72)',
      rim: mode === 'subdued' ? 'rgba(180, 174, 162, 0.30)' : 'rgba(207, 196, 180, 0.62)',
    }
    for (const rock of near) paintRock(ctx, rock, t, 1, nearTint)
    ctx.restore()

    return { maxColor: ASTEROID_MAX_COLOR, mode, rocks: belt.length + near.length }
  }

  return {
    draw,
    resize,
    get speed() { return speed },
    get paletteMax() { return ASTEROID_MAX_COLOR },
  }
}
