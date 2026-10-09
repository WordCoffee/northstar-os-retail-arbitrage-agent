// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — DOCUMENT MODEL + CANVAS 2D RENDERER
//
// A design document is a flat layer list in NORMALISED coordinates (0..1 of
// the canvas). That is the whole trick that lets one master render correctly
// at 300×300 and 1920×640: geometry is relative, only raster size changes.
//
// Renderer contract:
//   • Pure and synchronous. It never fetches. Images arrive pre-decoded in an
//     `assets` map (id → HTMLImageElement); a missing id renders an honest
//     "asset not loaded" placeholder instead of silently dropping the layer.
//   • Deterministic. Same doc + same assets ⇒ same pixels.
//   • Never fabricates content. Placeholder text is text the operator typed.
// ═══════════════════════════════════════════════════════════════════════════

export const KIND = {
  BG: 'bg',
  SHAPE: 'shape',
  IMAGE: 'image',
  TEXT: 'text',
  PRODUCT: 'product',
  BADGE: 'badge',
}

export const KIND_LABEL = {
  bg: 'Background',
  shape: 'Shape',
  image: 'Image',
  text: 'Text',
  product: 'Product',
  badge: 'Badge',
}

let seq = 0
export function layerId(prefix = 'L') {
  seq += 1
  return `${prefix}-${Date.now().toString(36).slice(-4)}${seq.toString(36)}`
}

export function roundRectPath(ctx, x, y, w, h, r) {
  const rr = Math.max(0, Math.min(r, Math.min(w, h) / 2))
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.lineTo(x + w - rr, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr)
  ctx.lineTo(x + w, y + h - rr)
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h)
  ctx.lineTo(x + rr, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr)
  ctx.lineTo(x, y + rr)
  ctx.quadraticCurveTo(x, y, x + rr, y)
  ctx.closePath()
}

// ── Document factories ───────────────────────────────────────────────────────

export function createDoc({ formatId = 'meta-feed', w = 1080, h = 1080, name = 'Untitled', kitId = 'kit-pine', channel = 'Meta', family = 'Ad creative' } = {}) {
  return {
    id: `DOC-${Date.now().toString(36).toUpperCase()}`,
    name,
    formatId,
    channel,
    family,
    kitId,
    w,
    h,
    layers: [{ id: layerId('BG'), kind: KIND.BG, name: 'Background', fill: '#f5f0e8' }],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

// Instantiate a template at a given raster size. Template layers are copied
// (never mutated) so the template stays pristine for the next instantiation.
export function docFromTemplate(tpl, { w, h, kit }) {
  const doc = createDoc({
    name: tpl.name, w, h, kitId: kit?.id || 'kit-pine',
    channel: '', family: tpl.family,
  })
  doc.templateId = tpl.id
  doc.layers = tpl.layers.map((l, i) => ({
    ...l,
    id: layerId('L'),
    name: l.name || l.role || l.kind,
    z: i,
  }))
  if (kit) applyKit(doc, kit)
  return doc
}

export function applyKit(doc, kit) {
  if (!kit) return doc
  doc.kitId = kit.id
  // Substitute the kit's paper/ink/accent into text + badge layers. The
  // operator can always override afterwards.
  doc.layers = doc.layers.map(l => {
    if (l.kind === KIND.TEXT) {
      const dark = isDark(kit.paper)
      return { ...l, color: l.color && l.color !== '#1a1a1a' ? l.color : (dark ? '#f5f0e8' : '#1a1a1a') }
    }
    if (l.kind === KIND.BADGE) return { ...l, fill: kit.accent }
    return l
  })
  doc.updatedAt = new Date().toISOString()
  return doc
}

export function isDark(hex) {
  const c = normalizeHex(hex)
  if (!c) return false
  const [r, g, b] = c
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.5
}

export function normalizeHex(hex) {
  const m = /^#?([0-9a-f]{6}|[0-9a-f]{3})$/i.exec(String(hex || '').trim())
  if (!m) return null
  let h = m[1]
  if (h.length === 3) h = h.split('').map(c => c + c).join('')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

// ── Layer ops ────────────────────────────────────────────────────────────────

export function addLayer(doc, layer) {
  const l = { z: doc.layers.length, visible: true, locked: false, opacity: 1, ...layer }
  return { ...doc, layers: [...doc.layers, l], updatedAt: new Date().toISOString() }
}

export function updateLayer(doc, id, patch) {
  return {
    ...doc,
    layers: doc.layers.map(l => (l.id === id ? { ...l, ...patch } : l)),
    updatedAt: new Date().toISOString(),
  }
}

export function removeLayer(doc, id) {
  return { ...doc, layers: doc.layers.filter(l => l.id !== id), updatedAt: new Date().toISOString() }
}

export function duplicateLayer(doc, id) {
  const src = doc.layers.find(l => l.id === id)
  if (!src) return doc
  const copy = { ...src, id: layerId('L'), name: `${src.name} copy` }
  const idx = doc.layers.findIndex(l => l.id === id)
  const layers = [...doc.layers]
  layers.splice(idx + 1, 0, copy)
  return { ...doc, layers, updatedAt: new Date().toISOString() }
}

export function reorderLayer(doc, id, dir) {
  const idx = doc.layers.findIndex(l => l.id === id)
  if (idx < 0) return doc
  const target = idx + dir
  if (target < 0 || target >= doc.layers.length) return doc
  const layers = [...doc.layers]
  const [l] = layers.splice(idx, 1)
  layers.splice(target, 0, l)
  return { ...doc, layers, updatedAt: new Date().toISOString() }
}

// ── Text measurement ────────────────────────────────────────────────────────

function fontString(sizePx, weight, family) {
  return `${weight || 400} ${sizePx}px ${family || '"DM Sans", system-ui, sans-serif'}`
}

function setLetterSpacing(ctx, px) {
  // Chromium supports the canvas letterSpacing property; guard for others.
  if ('letterSpacing' in ctx) {
    try { ctx.letterSpacing = `${px}px` } catch { /* unsupported */ }
  }
}

export function wrapText(ctx, text, maxWidth) {
  const lines = []
  for (const para of String(text ?? '').split('\n')) {
    const words = para.split(/\s+/).filter(Boolean)
    if (!words.length) { lines.push(''); continue }
    let line = words[0]
    for (let i = 1; i < words.length; i += 1) {
      const test = `${line} ${words[i]}`
      if (ctx.measureText(test).width <= maxWidth) line = test
      else { lines.push(line); line = words[i] }
    }
    lines.push(line)
  }
  return lines
}

// ── Fit helpers ──────────────────────────────────────────────────────────────

export function fitRect(srcW, srcH, boxW, boxH, fit = 'contain') {
  if (!srcW || !srcH) return { x: 0, y: 0, w: boxW, h: boxH }
  const s = fit === 'cover'
    ? Math.max(boxW / srcW, boxH / srcH)
    : Math.min(boxW / srcW, boxH / srcH)
  const w = srcW * s
  const h = srcH * s
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h }
}

// ── Renderer ─────────────────────────────────────────────────────────────────

function drawShape(ctx, l, W, H) {
  const x = l.x * W; const y = l.y * H
  const w = l.w * W; const h = l.h * H
  ctx.save()
  ctx.globalAlpha *= (l.opacity ?? 1)
  if (l.shadow) { ctx.shadowColor = 'rgba(26,26,26,0.18)'; ctx.shadowBlur = h * 0.12; ctx.shadowOffsetY = h * 0.04 }
  ctx.fillStyle = l.fill || 'rgba(0,0,0,0.1)'
  if (l.shape === 'ellipse' || l.shape === 'circle') {
    ctx.beginPath()
    ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2)
  } else if (l.shape === 'triangle') {
    ctx.beginPath()
    ctx.moveTo(x + w / 2, y)
    ctx.lineTo(x + w, y + h)
    ctx.lineTo(x, y + h)
    ctx.closePath()
  } else if (l.shape === 'line') {
    ctx.fillRect(x, y + h / 2 - Math.max(1, h * 0.01), w, Math.max(1, h * 0.02))
    ctx.restore(); return
  } else {
    const r = (l.radius ?? 0) * W
    roundRectPath(ctx, x, y, w, h, r)
  }
  ctx.fill()
  if (l.stroke && l.strokeWidth) {
    ctx.shadowColor = 'transparent'
    ctx.strokeStyle = l.stroke
    ctx.lineWidth = l.strokeWidth * W
    ctx.stroke()
  }
  ctx.restore()
}

function drawText(ctx, l, W, H) {
  const x = l.x * W; const y = l.y * H
  const w = l.w * W; const h = l.h * H
  const sizePx = (l.size ?? 0.05) * H
  ctx.save()
  ctx.globalAlpha *= (l.opacity ?? 1)
  const family = l.font || '"DM Sans", system-ui, sans-serif'
  const weight = l.weight ?? 400
  const raw = String(l.text ?? '')
  const text = l.uppercase ? raw.toUpperCase() : raw
  ctx.font = fontString(sizePx, weight, family)
  ctx.textBaseline = 'top'
  setLetterSpacing(ctx, (l.tracking ?? 0) * sizePx)
  if (l.shadow) { ctx.shadowColor = 'rgba(0,0,0,0.28)'; ctx.shadowBlur = sizePx * 0.35; ctx.shadowOffsetY = sizePx * 0.06 }
  ctx.fillStyle = l.color || '#1a1a1a'
  const lineHeight = sizePx * (l.lineHeight ?? 1.22)
  const lines = wrapText(ctx, text, w)
  let total = lines.length * lineHeight
  let startY = y
  if (l.valign === 'middle') startY = y + (h - total) / 2
  else if (l.valign === 'bottom') startY = y + (h - total)
  lines.forEach((line, i) => {
    const lw = ctx.measureText(line).width
    let lx = x
    if (l.align === 'center') lx = x + (w - lw) / 2
    else if (l.align === 'right') lx = x + (w - lw)
    ctx.fillText(line, lx, startY + i * lineHeight)
  })
  setLetterSpacing(ctx, 0)
  ctx.restore()
}

function drawImageLike(ctx, l, W, H, img) {
  const x = l.x * W; const y = l.y * H
  const w = l.w * W; const h = l.h * H
  ctx.save()
  ctx.globalAlpha *= (l.opacity ?? 1)
  if (l.rot) {
    ctx.translate(x + w / 2, y + h / 2)
    ctx.rotate((l.rot * Math.PI) / 180)
    ctx.translate(-(x + w / 2), -(y + h / 2))
  }
  if (l.radius) {
    roundRectPath(ctx, x, y, w, h, l.radius * W)
    ctx.clip()
  }
  if (!img) {
    // Honest placeholder — never a fake render.
    ctx.fillStyle = 'rgba(138,138,122,0.10)'
    ctx.fillRect(x, y, w, h)
    ctx.strokeStyle = 'rgba(138,138,122,0.35)'
    ctx.setLineDash([6, 4])
    ctx.lineWidth = Math.max(1, W * 0.002)
    ctx.strokeRect(x, y, w, h)
    ctx.setLineDash([])
    ctx.fillStyle = '#8a8a7a'
    const s = Math.max(9, W * 0.012)
    ctx.font = fontString(s, 500, '"JetBrains Mono", monospace')
    ctx.textBaseline = 'middle'
    ctx.textAlign = 'center'
    ctx.fillText(l.assetId ? 'ASSET NOT LOADED' : 'NO IMAGE SELECTED', x + w / 2, y + h / 2)
    ctx.restore()
    return
  }
  const fit = fitRect(img.naturalWidth || img.width, img.naturalHeight || img.height, w, h, l.fit || 'cover')
  if (l.shadow) {
    ctx.shadowColor = 'rgba(26,26,26,0.30)'
    ctx.shadowBlur = h * 0.09
    ctx.shadowOffsetY = h * 0.03
  }
  ctx.drawImage(img, x + fit.x, y + fit.y, fit.w, fit.h)
  ctx.restore()
}

function drawProduct(ctx, l, W, H, img) {
  // Product layer: always `contain`, optional contact shadow drawn separately so
  // the asset itself is never distorted. `squash` is an explicit 2D tilt
  // simulation (never labelled as a 3D render).
  const x = l.x * W; const y = l.y * H
  const w = l.w * W; const h = l.h * H
  ctx.save()
  ctx.globalAlpha *= (l.opacity ?? 1)
  if (l.contactShadow !== false) {
    const gy = y + h * 0.97
    const grad = ctx.createRadialGradient(x + w / 2, gy, 0, x + w / 2, gy, w * 0.42)
    grad.addColorStop(0, 'rgba(26,26,26,0.26)')
    grad.addColorStop(1, 'rgba(26,26,26,0)')
    ctx.fillStyle = grad
    ctx.fillRect(x, gy - h * 0.12, w, h * 0.24)
  }
  if (!img) { drawImageLike(ctx, l, W, H, null); ctx.restore(); return }
  const squash = Math.max(0.25, Math.min(1, l.squash ?? 1))
  const dh = h * squash
  const oy = y + (h - dh) / 2
  const fit = fitRect(img.naturalWidth || img.width, img.naturalHeight || img.height, w, dh, 'contain')
  ctx.drawImage(img, x + fit.x, oy + fit.y, fit.w, fit.h)
  ctx.restore()
}

function drawBadge(ctx, l, W, H) {
  const x = l.x * W; const y = l.y * H
  const w = l.w * W; const h = l.h * H
  ctx.save()
  ctx.globalAlpha *= (l.opacity ?? 1)
  ctx.fillStyle = l.fill || '#1d4a1d'
  roundRectPath(ctx, x, y, w, h, h / 2)
  ctx.fill()
  ctx.fillStyle = l.color || '#f5f0e8'
  const sizePx = (l.size ?? 0.026) * H
  ctx.font = fontString(sizePx, l.weight ?? 600, '"DM Sans", system-ui, sans-serif')
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'center'
  ctx.fillText(String(l.text ?? '').toUpperCase(), x + w / 2, y + h / 2 + sizePx * 0.05)
  ctx.restore()
}

/**
 * Render a document into a 2D context sized exactly `W × H` device pixels.
 * `assets` is a Map/object of assetId → HTMLImageElement.
 */
export function renderDoc(ctx, doc, { W, H, assets = new Map(), grid = null } = {}) {
  ctx.save()
  ctx.clearRect(0, 0, W, H)
  const get = (id) => (assets instanceof Map ? assets.get(id) : assets[id])

  for (const l of doc.layers) {
    if (l.visible === false) continue
    switch (l.kind) {
      case KIND.BG: {
        ctx.save()
        ctx.globalAlpha *= (l.opacity ?? 1)
        if (l.gradient) {
          const g = ctx.createLinearGradient(0, 0, 0, H)
          g.addColorStop(0, l.gradient[0])
          g.addColorStop(1, l.gradient[1])
          ctx.fillStyle = g
        } else {
          ctx.fillStyle = l.fill || '#ffffff'
        }
        ctx.fillRect(0, 0, W, H)
        ctx.restore()
        break
      }
      case KIND.SHAPE: drawShape(ctx, l, W, H); break
      case KIND.TEXT: drawText(ctx, l, W, H); break
      case KIND.IMAGE: drawImageLike(ctx, l, W, H, get(l.assetId)); break
      case KIND.PRODUCT: drawProduct(ctx, l, W, H, get(l.assetId)); break
      case KIND.BADGE: drawBadge(ctx, l, W, H); break
      default: break
    }
  }

  if (grid) drawGrid(ctx, W, H, grid)
  ctx.restore()
}

export function drawGrid(ctx, W, H, grid) {
  const n = grid.cols || 3
  ctx.save()
  ctx.strokeStyle = 'rgba(196,148,26,0.55)'
  ctx.lineWidth = Math.max(1, W * 0.0015)
  for (let i = 1; i < n; i += 1) {
    const x = (W / n) * i
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
  }
  ctx.setLineDash([])
  ctx.strokeStyle = 'rgba(160,64,32,0.45)'
  const m = grid.safe || 0.06
  ctx.strokeRect(W * m, H * m, W * (1 - 2 * m), H * (1 - 2 * m))
  ctx.restore()
}

/** Render to an offscreen canvas at 1:1 raster size. */
export function renderToCanvas(doc, { assets, scale = 1, grid = null } = {}) {
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(doc.w * scale))
  canvas.height = Math.max(1, Math.round(doc.h * scale))
  const ctx = canvas.getContext('2d')
  renderDoc(ctx, doc, { W: canvas.width, H: canvas.height, assets, grid })
  return canvas
}

export function docToDataUrl(doc, { assets, scale = 1, type = 'image/png', quality = 0.92 } = {}) {
  return renderToCanvas(doc, { assets, scale }).toDataURL(type, quality)
}

export function downloadDataUrl(dataUrl, filename) {
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export function safeFileName(name) {
  return String(name || 'export').replace(/[^a-z0-9-_]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'export'
}

/** Shallow-clone a doc at another raster size (normalised geometry just works). */
export function rescaleDoc(doc, w, h) {
  return { ...doc, w, h, updatedAt: new Date().toISOString() }
}

export function cloneDoc(doc, name) {
  return {
    ...doc,
    id: `DOC-${Date.now().toString(36).toUpperCase()}`,
    name: name || `${doc.name} copy`,
    layers: doc.layers.map(l => ({ ...l, id: layerId('L') })),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}
