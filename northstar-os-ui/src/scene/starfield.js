// The default scene (U5): drifting starfield, a distant slowly turning planet,
// the occasional shooting star — 100% procedural, no external assets.
//
// Deterministic by seed so a test can assert exactly what was painted, and it
// takes its intensity from the event bus mode rather than owning a clock.

export function mulberry32(seed) {
  let a = seed >>> 0
  return function random() {
    a |= 0
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const SPEED = { calm: 1, intense: 2.2, flare: 1.6, subdued: 0.3 }

export function createStarfield({ width = 1200, height = 800, seed = 7, density = 9000 } = {}) {
  const random = mulberry32(seed)
  let w = width
  let h = height
  let speed = 1
  let shooting = null
  let sinceShooting = 0
  let stars = []
  let haze = null
  let hazeMode = ''
  const planet = { x: w * 0.78, y: h * 0.26, r: Math.max(36, Math.min(w, h) * 0.09), angle: 0 }

  function seedStars() {
    const count = Math.max(60, Math.round((w * h) / density))
    stars = []
    for (let i = 0; i < count; i += 1) {
      stars.push({
        x: random() * w,
        y: random() * h,
        z: 0.25 + random() * 0.75,
        r: 0.4 + random() * 1.5,
        tw: random() * Math.PI * 2,
      })
    }
  }
  seedStars()

  function resize(nextW, nextH) {
    w = Math.max(1, nextW)
    h = Math.max(1, nextH)
    haze = null
    planet.x = w * 0.78
    planet.y = h * 0.26
    planet.r = Math.max(36, Math.min(w, h) * 0.09)
    seedStars()
  }

  function draw(ctx, { dt = 16, t = 0, mode = 'calm' } = {}) {
    speed = SPEED[mode] || 1

    ctx.fillStyle = '#05060c'
    ctx.fillRect(0, 0, w, h)

    // Nebula haze. The flare brightens it for a moment; error desaturates it.
    // The gradient object is cached per mode: rebuilding it every frame at phone
    // resolution cost ~250 ms a frame in WebKit software rendering.
    if (!haze || hazeMode !== mode) {
      haze = ctx.createRadialGradient(w * 0.32, h * 0.24, 0, w * 0.32, h * 0.24, Math.max(w, h) * 0.65)
      haze.addColorStop(0, mode === 'flare'
        ? 'rgba(150, 176, 255, 0.20)'
        : mode === 'subdued' ? 'rgba(70, 80, 100, 0.10)' : 'rgba(86, 106, 190, 0.13)')
      haze.addColorStop(1, 'rgba(5, 6, 12, 0)')
      hazeMode = mode
    }
    ctx.fillStyle = haze
    ctx.fillRect(0, 0, w, h)

    for (const star of stars) {
      star.x -= (0.02 + star.z * 0.06) * speed * dt
      if (star.x < -2) star.x += w + 4
      const twinkle = 0.62 + 0.38 * Math.sin(t * 0.0012 + star.tw)
      ctx.globalAlpha = Math.max(0.08, Math.min(1, star.z * twinkle))
      ctx.fillStyle = '#e8eef7'
      ctx.fillRect(star.x, star.y, star.r, star.r)
    }
    ctx.globalAlpha = 1

    // The distant planet: a lit rim that rotates slowly. Never a foreground
    // element — it sits behind every panel.
    planet.angle += 0.00004 * dt * speed
    ctx.beginPath()
    ctx.arc(planet.x, planet.y, planet.r, 0, Math.PI * 2)
    ctx.fillStyle = '#141d2b'
    ctx.fill()
    ctx.beginPath()
    ctx.arc(
      planet.x - Math.cos(planet.angle) * planet.r * 0.2,
      planet.y - Math.sin(planet.angle) * planet.r * 0.2,
      planet.r * 0.92, 0, Math.PI * 2,
    )
    ctx.strokeStyle = mode === 'flare' ? 'rgba(232, 176, 75, 0.85)' : 'rgba(127, 176, 255, 0.5)'
    ctx.lineWidth = Math.max(1, planet.r * 0.035)
    ctx.stroke()

    // Occasional shooting star. One at a time, rate-limited by design.
    sinceShooting += dt
    if (!shooting && sinceShooting > 4200) {
      shooting = { x: w * (0.15 + random() * 0.6), y: h * (0.08 + random() * 0.2), life: 0 }
      sinceShooting = 0
    }
    if (shooting) {
      shooting.life += dt
      shooting.x += 0.38 * speed * dt
      shooting.y += 0.13 * speed * dt
      ctx.strokeStyle = 'rgba(232, 238, 247, 0.8)'
      ctx.lineWidth = 1.4
      ctx.beginPath()
      ctx.moveTo(shooting.x, shooting.y)
      ctx.lineTo(shooting.x - 26, shooting.y - 9)
      ctx.stroke()
      if (shooting.life > 900) shooting = null
    }

    return { stars: stars.length, planet: planet.r, mode }
  }

  return {
    draw,
    resize,
    get stars() { return stars },
    get planet() { return planet },
    get speed() { return speed },
  }
}
