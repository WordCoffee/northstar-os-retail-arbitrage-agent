// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — 3D PACKAGING VIEW
//
// A real 3D renderer on a plain Canvas 2D context: rotate a box mesh, shade
// six faces with a three-point light rig, and map the operator's own artwork
// onto individual faces with an affine texture transform. Painter's algorithm
// over per-face depth. No WebGL, no three.js, no external dependency.
//
// The output is honest geometry: a wireframe/box preview of the operator's own
// pack art. It is not a photoreal render and is never labelled as one.
// ═══════════════════════════════════════════════════════════════════════════

const FACES = [
  { key: 'front', verts: [4, 5, 6, 7], normal: [0, 0, 1] },
  { key: 'back', verts: [1, 0, 3, 2], normal: [0, 0, -1] },
  { key: 'right', verts: [5, 1, 2, 6], normal: [1, 0, 0] },
  { key: 'left', verts: [0, 4, 7, 3], normal: [-1, 0, 0] },
  { key: 'top', verts: [7, 6, 2, 3], normal: [0, 1, 0] },
  { key: 'bottom', verts: [0, 1, 5, 4], normal: [0, -1, 0] },
]

export const FACE_KEYS = FACES.map(f => f.key)

export function boxVertices(size) {
  const [hx, hy, hz] = size.map(v => v / 2)
  return [
    [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
    [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
  ]
}

function rotate(p, yaw, pitch, roll) {
  let [x, y, z] = p
  const cy = Math.cos(yaw); const sy = Math.sin(yaw)
  ;[x, z] = [x * cy + z * sy, -x * sy + z * cy]
  const cp = Math.cos(pitch); const sp = Math.sin(pitch)
  ;[y, z] = [y * cp - z * sp, y * sp + z * cp]
  const cr = Math.cos(roll); const sr = Math.sin(roll)
  ;[x, y] = [x * cr - y * sr, x * sr + y * cr]
  return [x, y, z]
}

function norm(v) {
  const m = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / m, v[1] / m, v[2] / m]
}

function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] }

/**
 * Build a full projection for a scene.
 * @returns {{project:(p:number[])=>[number,number,number], depth:(p:number[])=>number}}
 */
export function makeCamera({ yaw = -0.5, pitch = 0.2, roll = 0, fov = 900, distance = 3.2, cx, cy }) {
  const rot = (p) => rotate(p, yaw, pitch, roll)
  return {
    rot,
    project(p) {
      const [x, y, z] = rot(p)
      const d = Math.max(0.05, distance - z)
      const s = fov / d
      return [cx + x * s, cy - y * s, d]
    },
    depth(p) {
      const [, , z] = rot(p)
      return distance - z
    },
  }
}

/** Map an image onto a projected quad via an affine transform (p0→p1→p2→p3). */
export function drawTexturedQuad(ctx, img, p0, p1, p2, p3) {
  const x0 = p0[0]; const y0 = p0[1]
  const x1 = p1[0]; const y1 = p1[1]
  const x3 = p3[0]; const y3 = p3[1]
  // Solve affine: [a c e; b d f] maps (0,0),(1,0),(0,1) → p0,p1,p3.
  const a = x1 - x0
  const b = y1 - y0
  const c = x3 - x0
  const d = y3 - y0
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(p0[0], p0[1])
  ctx.lineTo(p1[0], p1[1])
  ctx.lineTo(p2[0], p2[1])
  ctx.lineTo(p3[0], p3[1])
  ctx.closePath()
  ctx.clip()
  ctx.transform(a, b, c, d, x0, y0)
  try {
    ctx.drawImage(img, 0, 0, 1, 1)
  } catch { /* zero-size image */ }
  ctx.restore()
}

function shade(hex, factor, warm) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim())
  if (!m) return `rgba(120,120,120,${Math.max(0, Math.min(1, factor))})`
  const n = parseInt(m[1], 16)
  let r = (n >> 16) & 255
  let g = (n >> 8) & 255
  let b = n & 255
  const k = Math.max(0, Math.min(1.6, factor))
  r = Math.min(255, r * k)
  g = Math.min(255, g * k)
  b = Math.min(255, b * k)
  if (warm) { r = Math.min(255, r * 1.06); b = Math.min(255, b * 0.93) }
  return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`
}

/**
 * Render a 3D packaging scene.
 *
 * opts.size      [w,h,d] box dimensions in arbitrary units
 * opts.faces     { front: {fill, assetId, gradient}, ... } per-face art
 * opts.camera    { yaw, pitch, roll, fov } (yaw/pitch/roll in RADIANS)
 * opts.lighting  { key, fill, rim, ambient, warm }
 * opts.floor     true → draw contact shadow + optional reflection
 * opts.edges     true → draw thin face edges
 */
export function renderBox(ctx, opts = {}) {
  const {
    W, H, size = [1, 1.35, 0.28], faces = {}, camera = {}, lighting = {},
    floor = true, edges = true, assets, bg, spinGuide = false,
  } = opts

  const Wd = W || ctx.canvas.width
  const Hd = H || ctx.canvas.height
  ctx.save()
  ctx.clearRect(0, 0, Wd, Hd)

  if (bg) {
    if (Array.isArray(bg)) {
      const g = ctx.createLinearGradient(0, 0, 0, Hd)
      g.addColorStop(0, bg[0]); g.addColorStop(1, bg[1])
      ctx.fillStyle = g
    } else {
      ctx.fillStyle = bg
    }
    ctx.fillRect(0, 0, Wd, Hd)
  }

  const cx = Wd / 2
  const floorY = Hd * 0.78
  const cy = Hd * 0.5
  const maxDim = Math.max(size[0], size[1], size[2])
  const fov = camera.fov ?? Math.min(Wd, Hd) * 0.62 / maxDim
  const cam = makeCamera({ ...camera, fov, cx, cy: floorY - (size[1] / 2) * (fov / (camera.distance ?? 3.2)) })

  const verts = boxVertices(size)
  const rig = {
    key: lighting.key ?? 1.0,
    fill: lighting.fill ?? 0.45,
    rim: lighting.rim ?? 0.5,
    ambient: lighting.ambient ?? 0.55,
    warm: !!lighting.warm,
  }
  // Light directions (world space, normalised).
  const keyDir = norm([Math.cos(0.9), 0.75, 0.55])
  const fillDir = norm([-0.8, 0.15, 0.5])
  const rimDir = norm([0.2, 0.4, -0.9])

  const projected = verts.map(v => cam.project(v))
  const getAsset = (id) => (assets instanceof Map ? assets.get(id) : assets ? assets[id] : null)

  // ── contact shadow ──
  if (floor) {
    const shadowScale = size[0] * 0.95
    const g = ctx.createRadialGradient(cx, floorY, 0, cx, floorY, shadowScale * (fov / 3.2) * 0.55)
    g.addColorStop(0, 'rgba(20,26,20,0.34)')
    g.addColorStop(0.55, 'rgba(20,26,20,0.16)')
    g.addColorStop(1, 'rgba(20,26,20,0)')
    ctx.save()
    ctx.translate(cx, floorY)
    ctx.scale(1, 0.22)
    ctx.translate(-cx, -floorY)
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(cx, floorY, shadowScale * (fov / 3.2) * 0.62, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }

  // ── faces, painter's algorithm ──
  const order = FACES.map(f => {
    const depth = f.verts.reduce((s, vi) => s + cam.depth(verts[vi]), 0) / 4
    const n = cam.rot(f.normal)
    const lambert = (ld) => Math.max(0, dot(norm(n), ld))
    const lum = rig.ambient
      + rig.key * 0.62 * lambert(keyDir)
      + rig.fill * 0.42 * lambert(fillDir)
      + rig.rim * 0.30 * lambert(rimDir)
    return { f, depth, lum }
  }).sort((a, b) => b.depth - a.depth)

  for (const { f, lum } of order) {
    const art = faces[f.key] || {}
    const p = f.verts.map(vi => projected[vi])
    const base = art.fill || '#e8e2d8'
    const img = art.assetId ? getAsset(art.assetId) : null

    ctx.save()
    ctx.beginPath()
    ctx.moveTo(p[0][0], p[0][1])
    ctx.lineTo(p[1][0], p[1][1])
    ctx.lineTo(p[2][0], p[2][1])
    ctx.lineTo(p[3][0], p[3][1])
    ctx.closePath()
    ctx.clip()

    if (art.gradient) {
      const b = f.bbox
      const g = ctx.createLinearGradient(p[0][0], p[0][1], p[2][0], p[2][1])
      g.addColorStop(0, shade(art.gradient[0], lum, rig.warm))
      g.addColorStop(1, shade(art.gradient[1], lum * 0.85, rig.warm))
      ctx.fillStyle = g
    } else {
      ctx.fillStyle = shade(base, lum, rig.warm)
    }
    ctx.fillRect(p[0][0], p[0][1], Math.abs(p[1][0] - p[0][0]) + Math.abs(p[3][1] - p[0][1]), 4000)

    if (img && img.naturalWidth) {
      // Keep the art inside the face with a small inset so the box edge reads.
      const inset = f.key === 'top' || f.key === 'bottom' ? 0.06 : 0.02
      const q = insetQuad(p, inset)
      drawTexturedQuad(ctx, img, q[0], q[1], q[2], q[3])
    }

    // specular sheen
    if ((art.gloss ?? 0.18) > 0.01) {
      const gx = (p[0][0] + p[2][0]) / 2
      const gy = (p[0][1] + p[2][1]) / 2
      const rad = Math.max(20, Math.abs(p[2][0] - p[0][0]) * 0.5)
      const gg = ctx.createRadialGradient(gx, gy, 0, gx, gy, rad)
      gg.addColorStop(0, `rgba(255,255,255,${art.gloss ?? 0.18})`)
      gg.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = gg
      ctx.fillRect(gx - rad, gy - rad, rad * 2, rad * 2)
    }
    ctx.restore()

    if (edges) {
      ctx.save()
      ctx.strokeStyle = 'rgba(26,26,26,0.28)'
      ctx.lineWidth = Math.max(1, Wd * 0.0012)
      ctx.beginPath()
      ctx.moveTo(p[0][0], p[0][1])
      ctx.lineTo(p[1][0], p[1][1])
      ctx.lineTo(p[2][0], p[2][1])
      ctx.lineTo(p[3][0], p[3][1])
      ctx.closePath()
      ctx.stroke()
      ctx.restore()
    }
  }

  if (spinGuide) {
    ctx.save()
    ctx.strokeStyle = 'rgba(196,148,26,0.7)'
    ctx.setLineDash([4, 6])
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.ellipse(cx, floorY, size[0] * (fov / 3.2) * 0.95, size[0] * (fov / 3.2) * 0.22, 0, 0, Math.PI * 2)
    ctx.stroke()
    ctx.restore()
  }

  ctx.restore()
}

/** Shrink a quad toward its centroid by a fraction. */
export function insetQuad(p, t) {
  const c = [
    p.reduce((s, q) => s + q[0], 0) / 4,
    p.reduce((s, q) => s + q[1], 0) / 4,
  ]
  return p.map(q => [q[0] + (c[0] - q[0]) * t, q[1] + (c[1] - q[1]) * t])
}

export const DEG = Math.PI / 180

/** Camera preset → radians. */
export function cameraToRadians(preset, overrides = {}) {
  return {
    yaw: (overrides.yaw ?? preset.yaw ?? 0) * DEG,
    pitch: (overrides.pitch ?? preset.pitch ?? 0) * DEG,
    roll: (overrides.roll ?? preset.roll ?? 0) * DEG,
    fov: overrides.fov,
    distance: overrides.distance ?? 3.2,
  }
}

/** Compute a talking-point description of the current camera (honest metadata). */
export function describeAngle(yawDeg, pitchDeg) {
  const yaw = ((yawDeg % 360) + 360) % 360
  const label = yaw < 15 || yaw > 345 ? 'front'
    : yaw < 75 ? 'front-right'
      : yaw < 105 ? 'right'
        : yaw < 165 ? 'back-right'
          : yaw < 195 ? 'back'
            : yaw < 255 ? 'back-left'
              : yaw < 285 ? 'left'
                : 'front-left'
  const pitch = pitchDeg > 35 ? 'high' : pitchDeg < -12 ? 'low' : 'eye level'
  return `${label} · ${pitch}`
}
