// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — MOCKUP RENDERER
// Vector mockup surfaces drawn locally, with the operator's own artwork mapped
// into the print area using standard blend modes. Deterministic, offline, no
// stock photography bundled or fetched.
// ═══════════════════════════════════════════════════════════════════════════

import { MOCKUP_SURFACES } from './presets.js'

function poly(ctx, pts) {
  ctx.beginPath()
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)))
  ctx.closePath()
}

function tee(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  const b = [[0.32, 0.1], [0.68, 0.1], [0.73, 0.86], [0.27, 0.86]]
  poly(ctx, b.map(p))
  // rounded shoulders
  ctx.quadraticCurveTo(0.5 * W, 0.045 * H, 0.32 * W, 0.1 * H)
  ctx.quadraticCurveTo(0.5 * W, 0.055 * H, 0.68 * W, 0.1 * H)
  ctx.fill()
  // sleeves
  poly(ctx, [[0.32, 0.1], [0.13, 0.25], [0.2, 0.4], [0.3, 0.31]].map(p))
  ctx.fill()
  poly(ctx, [[0.68, 0.1], [0.87, 0.25], [0.8, 0.4], [0.7, 0.31]].map(p))
  ctx.fill()
  // neckline
  ctx.save()
  ctx.globalCompositeOperation = 'destination-out'
  ctx.beginPath()
  ctx.ellipse(0.5 * W, 0.1 * H, 0.115 * W, 0.045 * H, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function hoodie(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  poly(ctx, [[0.32, 0.14], [0.68, 0.14], [0.74, 0.88], [0.26, 0.88]].map(p))
  ctx.fill()
  poly(ctx, [[0.32, 0.14], [0.12, 0.3], [0.19, 0.46], [0.29, 0.36]].map(p))
  ctx.fill()
  poly(ctx, [[0.68, 0.14], [0.88, 0.3], [0.81, 0.46], [0.71, 0.36]].map(p))
  ctx.fill()
  // hood
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(0.38 * W, 0.16 * H)
  ctx.quadraticCurveTo(0.5 * W, 0.03 * H, 0.62 * W, 0.16 * H)
  ctx.quadraticCurveTo(0.5 * W, 0.1 * H, 0.38 * W, 0.16 * H)
  ctx.fill()
  ctx.restore()
  // pocket
  ctx.save()
  ctx.globalAlpha *= 0.5
  poly(ctx, [[0.36, 0.62], [0.64, 0.62], [0.64, 0.8], [0.36, 0.8]].map(p))
  ctx.stroke()
  ctx.restore()
}

function tote(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  poly(ctx, [[0.24, 0.3], [0.76, 0.3], [0.8, 0.88], [0.2, 0.88]].map(p))
  ctx.fill()
  ctx.save()
  ctx.strokeStyle = 'rgba(26,26,26,0.5)'
  ctx.lineWidth = Math.max(2, W * 0.014)
  ctx.beginPath()
  ctx.moveTo(0.34 * W, 0.31 * H)
  ctx.quadraticCurveTo(0.34 * W, 0.12 * H, 0.5 * W, 0.12 * H)
  ctx.quadraticCurveTo(0.66 * W, 0.12 * H, 0.66 * W, 0.31 * H)
  ctx.stroke()
  ctx.restore()
}

function mug(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  ctx.save()
  // handle
  ctx.strokeStyle = ctx.fillStyle
  ctx.lineWidth = Math.max(4, W * 0.045)
  ctx.beginPath()
  ctx.arc(0.76 * W, 0.58 * H, 0.13 * W, -Math.PI * 0.45, Math.PI * 0.45)
  ctx.stroke()
  ctx.restore()
  // body
  poly(ctx, [[0.28, 0.24], [0.72, 0.24], [0.68, 0.86], [0.32, 0.86]].map(p))
  ctx.fill()
  // rim
  ctx.save()
  ctx.globalAlpha *= 0.5
  ctx.beginPath()
  ctx.ellipse(0.5 * W, 0.24 * H, 0.22 * W, 0.045 * H, 0, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function jarLabel(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  // body
  poly(ctx, [[0.3, 0.18], [0.7, 0.18], [0.74, 0.9], [0.26, 0.9]].map(p))
  ctx.fill()
  // lid
  ctx.save()
  ctx.globalAlpha *= 0.85
  poly(ctx, [[0.28, 0.08], [0.72, 0.08], [0.72, 0.2], [0.28, 0.2]].map(p))
  ctx.fill()
  ctx.restore()
  // glass highlight
  ctx.save()
  ctx.globalAlpha *= 0.28
  ctx.fillStyle = '#ffffff'
  poly(ctx, [[0.35, 0.24], [0.39, 0.24], [0.36, 0.86], [0.32, 0.86]].map(p))
  ctx.fill()
  ctx.restore()
}

function boxFace(ctx, W, H) {
  const p = ([x, y]) => [x * W, y * H]
  // side
  poly(ctx, [[0.74, 0.2], [0.86, 0.28], [0.86, 0.86], [0.74, 0.78]].map(p))
  ctx.fill()
  // top
  poly(ctx, [[0.26, 0.2], [0.74, 0.2], [0.86, 0.28], [0.38, 0.28]].map(p))
  ctx.fill()
  // front (art target)
  poly(ctx, [[0.26, 0.2], [0.74, 0.2], [0.74, 0.78], [0.26, 0.78]].map(p))
  ctx.fill()
}

const BODIES = { tee, hoodie, tote, mug, label: jarLabel, 'box-face': boxFace }

/**
 * Render one mockup. `art` is an HTMLImageElement (or null).
 */
export function renderMockup(ctx, surfaceId, art, { W, H, blend = 'multiply', artOpacity = 0.94 } = {}) {
  const surface = MOCKUP_SURFACES.find(s => s.id === surfaceId) || MOCKUP_SURFACES[0]
  ctx.save()
  ctx.clearRect(0, 0, W, H)

  // soft studio backdrop
  const g = ctx.createLinearGradient(0, 0, 0, H)
  g.addColorStop(0, '#f7f5f0')
  g.addColorStop(1, '#e7e2d8')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, W, H)

  // ground shadow
  const sg = ctx.createRadialGradient(W * 0.5, H * 0.9, 0, W * 0.5, H * 0.9, W * 0.3)
  sg.addColorStop(0, 'rgba(26,26,26,0.20)')
  sg.addColorStop(1, 'rgba(26,26,26,0)')
  ctx.save()
  ctx.translate(W * 0.5, H * 0.9); ctx.scale(1, 0.16); ctx.translate(-W * 0.5, -H * 0.9)
  ctx.fillStyle = sg
  ctx.beginPath(); ctx.arc(W * 0.5, H * 0.9, W * 0.3, 0, Math.PI * 2); ctx.fill()
  ctx.restore()

  ctx.fillStyle = surface.tint
  ctx.strokeStyle = 'rgba(26,26,26,0.18)'
  ctx.lineWidth = Math.max(1, W * 0.003)
  ;(BODIES[surface.id] || tee)(ctx, W, H)

  // ── artwork in the print area ──
  const a = surface.area
  const ax = a.x * W
  const ay = a.y * H
  const aw = a.w * W
  const ah = a.h * H
  if (art) {
    ctx.save()
    ctx.beginPath()
    ctx.rect(ax, ay, aw, ah)
    ctx.clip()
    ctx.globalAlpha = artOpacity
    ctx.globalCompositeOperation = blend === 'normal' ? 'source-over' : blend
    const ar = (art.naturalWidth || art.width) / (art.naturalHeight || art.height) || 1
    const boxAr = aw / ah
    let dw = aw; let dh = ah
    if (ar > boxAr) dh = aw / ar
    else dw = ah * ar
    ctx.drawImage(art, ax + (aw - dw) / 2, ay + (ah - dh) / 2, dw, dh)
    ctx.restore()
  } else {
    ctx.save()
    ctx.setLineDash([6, 4])
    ctx.strokeStyle = 'rgba(138,138,122,0.5)'
    ctx.strokeRect(ax, ay, aw, ah)
    ctx.setLineDash([])
    ctx.fillStyle = '#8a8a7a'
    ctx.font = `500 ${Math.max(9, W * 0.026)}px "JetBrains Mono", monospace`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('NO ARTWORK', ax + aw / 2, ay + ah / 2)
    ctx.restore()
  }

  // print-area outline
  ctx.save()
  ctx.strokeStyle = 'rgba(196,148,26,0.55)'
  ctx.setLineDash([4, 3])
  ctx.lineWidth = Math.max(1, W * 0.0022)
  ctx.strokeRect(ax, ay, aw, ah)
  ctx.restore()

  ctx.restore()
}

export function mockupToDataUrl(surfaceId, art, size = 720, blend) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  renderMockup(ctx, surfaceId, art, { W: size, H: size, blend })
  return canvas.toDataURL('image/png')
}
