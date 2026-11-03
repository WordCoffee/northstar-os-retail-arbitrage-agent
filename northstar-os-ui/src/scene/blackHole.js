// U10 — the Research scene: a black hole with an accretion disk and the
// lensed arcs that bend over its top and under its bottom.
//
// Procedural and original. The lensing is drawn as geometry (two arcs plus a
// photon ring), not as a post-effect, so the frame cost stays flat and the
// brightest pixel is knowable — which is what lets the contrast test prove the
// research panels stay readable through 0.72 glass.

import { mulberry32 } from './starfield.js'

/** Brightest pixel this scene may paint. The contrast test measures against it. */
export const BLACK_HOLE_MAX_COLOR = '#f0dcb4'

const SPEED = { calm: 1, intense: 2.1, flare: 1.6, subdued: 0.28 }

export function createBlackHole({ width = 1200, height = 800, seed = 17 } = {}) {
  const random = mulberry32(seed)
  let w = Math.max(1, width)
  let h = Math.max(1, height)
  let speed = 1
  let spin = 0
  let background = null
  let backgroundKey = ''
  let disk = null
  let diskKey = ''

  const stars = Array.from({ length: 80 }, () => ({
    x: random(), y: random(), s: 0.4 + random() * 1.1, tw: random() * 6.28,
  }))

  function resize(nextW, nextH) {
    w = Math.max(1, nextW)
    h = Math.max(1, nextH)
    background = null
    disk = null
  }

  function paintBackground(ctx, mode) {
    const key = `${w}x${h}:${mode}`
    if (background && backgroundKey === key) return background
    const g = ctx.createRadialGradient(w * 0.5, h * 0.52, 0, w * 0.5, h * 0.52, Math.max(w, h) * 0.85)
    g.addColorStop(0, mode === 'flare' ? 'rgba(240, 220, 180, 0.20)' : 'rgba(214, 176, 120, 0.12)')
    g.addColorStop(0.35, 'rgba(90, 64, 40, 0.10)')
    g.addColorStop(1, 'rgba(4, 4, 8, 0)')
    background = g
    backgroundKey = key
    return g
  }

  function draw(ctx, { dt = 16, t = 0, mode = 'calm' } = {}) {
    speed = SPEED[mode] || 1
    spin += dt * 0.00035 * speed

    const cx = w * 0.5
    const cy = h * 0.52
    const r = Math.min(w, h) * 0.17

    ctx.save()
    ctx.fillStyle = paintBackground(ctx, mode)
    ctx.fillRect(0, 0, w, h)

    // Distant stars, bent slightly toward the hole: the "data pulled to the
    // centre" reading, kept subtle so it never looks like a lens flare.
    for (const s of stars) {
      const dx = (s.x - 0.5) * w
      const dy = (s.y - 0.52) * h
      const d = Math.hypot(dx, dy) || 1
      const pull = Math.min(0.06, (r * 2.2) / d * 0.02)
      const x = cx + dx * (1 - pull)
      const y = cy + dy * (1 - pull)
      const tw = 0.35 + 0.3 * Math.sin(t * 0.001 + s.tw)
      ctx.globalAlpha = tw * (mode === 'subdued' ? 0.35 : 0.7)
      ctx.fillStyle = BLACK_HOLE_MAX_COLOR
      ctx.fillRect(x, y, s.s, s.s)
    }
    ctx.globalAlpha = 1

    // The accretion disk: an ellipse we only draw the FAR half of, then the
    // near half after the horizon so the front of the disk crosses the hole.
    const diskKeyNow = `${w}x${h}:${mode}`
    if (!disk || diskKey !== diskKeyNow) {
      disk = ctx.createLinearGradient(cx - r * 2.4, 0, cx + r * 2.4, 0)
      disk.addColorStop(0, mode === 'subdued' ? 'rgba(160, 130, 90, 0.10)' : 'rgba(214, 170, 110, 0.30)')
      disk.addColorStop(0.5, mode === 'flare' ? 'rgba(255, 236, 198, 0.55)' : 'rgba(240, 220, 180, 0.38)')
      disk.addColorStop(1, 'rgba(214, 170, 110, 0.14)')
      diskKey = diskKeyNow
    }

    const tilt = -0.30
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(tilt)
    ctx.strokeStyle = disk
    ctx.lineWidth = Math.max(2, r * 0.22)
    ctx.beginPath()
    ctx.ellipse(0, 0, r * 2.3, r * 0.62, 0, Math.PI, Math.PI * 2)
    ctx.stroke()

    // The lensed arcs: light from the far side bent up over the top and down
    // under the bottom. This is the shape the film made famous, drawn as two
    // arcs rather than a shader.
    ctx.strokeStyle = mode === 'subdued'
      ? 'rgba(200, 176, 140, 0.22)'
      : 'rgba(240, 220, 180, 0.42)'
    ctx.lineWidth = Math.max(1.5, r * 0.06)
    ctx.beginPath()
    ctx.ellipse(0, 0, r * 1.12, r * 1.42, 0, Math.PI * 1.06, Math.PI * 1.94)
    ctx.stroke()
    ctx.beginPath()
    ctx.ellipse(0, 0, r * 1.12, r * 1.42, 0, Math.PI * 0.06, Math.PI * 0.94)
    ctx.stroke()
    ctx.restore()

    // The horizon: a true black disc. Nothing is painted inside it, and the
    // scene's own maximum is never used here — a black hole is black.
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = '#04050a'
    ctx.fill()

    // Photon ring, brightest just outside the horizon.
    ctx.beginPath()
    ctx.arc(cx, cy, r * 1.035, 0, Math.PI * 2)
    ctx.strokeStyle = mode === 'subdued' ? 'rgba(220, 198, 160, 0.45)' : BLACK_HOLE_MAX_COLOR
    ctx.lineWidth = Math.max(1.2, r * 0.035)
    ctx.stroke()

    // The near half of the disk, in front of the hole.
    ctx.save()
    ctx.translate(cx, cy)
    ctx.rotate(tilt)
    ctx.strokeStyle = disk
    ctx.lineWidth = Math.max(2, r * 0.22)
    ctx.beginPath()
    ctx.ellipse(0, 0, r * 2.3, r * 0.62, 0, 0, Math.PI)
    ctx.stroke()
    ctx.restore()

    // A slow orbiting speck so the disk reads as turning, not as a still.
    const a = spin % (Math.PI * 2)
    ctx.beginPath()
    ctx.arc(cx + Math.cos(a) * r * 2.1, cy + Math.sin(a) * r * 0.55, Math.max(1, r * 0.03), 0, Math.PI * 2)
    ctx.fillStyle = mode === 'subdued' ? 'rgba(220, 198, 160, 0.35)' : BLACK_HOLE_MAX_COLOR
    ctx.fill()

    ctx.restore()
    return { maxColor: BLACK_HOLE_MAX_COLOR, mode, radius: r }
  }

  return {
    draw,
    resize,
    get speed() { return speed },
    get paletteMax() { return BLACK_HOLE_MAX_COLOR },
  }
}
