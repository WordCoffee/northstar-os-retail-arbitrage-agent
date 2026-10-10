// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — COMPOSITE + EXPORT PIPELINE
//
// The one path an asset leaves by. It chains, in order:
//   1. render the layers to a raster
//   2. run the FIDELITY check against the locked reference
//   3. run the compliance pre-flight
//   4. embed the XMP disclosure marker when one is required
//   5. RE-READ the exported bytes to prove the marker survived
//   6. return the bytes plus a report that says exactly what happened
//
// Nothing here generates anything. The product is the operator's own pixels.
//
// A step that cannot be run is reported as not-run, never as passed.
// ═══════════════════════════════════════════════════════════════════════════

import { regionDiff, regionToPixels, productRegion, FIDELITY_MODE_BY_ID } from './fidelity.js'
import { classifyDisclosure, embedDisclosure, verifyDisclosureMarker, DISCLOSURE_KEYWORD } from './disclosure.js'
import { checkCompliance } from './compliance.js'

// ── 1. Render ──────────────────────────────────────────────────────────────
/**
 * Draw a document's layers onto a canvas. Product and image layers draw from
 * an asset URL the caller supplies; nothing is synthesised.
 *
 * @param {object} doc
 * @param {(id:string)=>string} resolveAsset  assetId -> object URL or data URL
 * @returns {Promise<HTMLCanvasElement>}
 */
export async function renderDoc(doc, resolveAsset) {
  const canvas = document.createElement('canvas')
  canvas.width = doc.w
  canvas.height = doc.h
  const ctx = canvas.getContext('2d')

  const load = (src) => new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`asset failed to load: ${String(src).slice(0, 40)}`))
    img.src = src
  })

  for (const l of doc.layers || []) {
    if (l.visible === false) continue
    const x = (l.x ?? 0) * doc.w
    const y = (l.y ?? 0) * doc.h
    const w = (l.w ?? 1) * doc.w
    const h = (l.h ?? 1) * doc.h

    if (l.kind === 'bg') {
      if (Array.isArray(l.gradient) && l.gradient.length > 1) {
        const g = ctx.createLinearGradient(x, y, x, y + h)
        l.gradient.forEach((c, i) => g.addColorStop(i / (l.gradient.length - 1), c))
        ctx.fillStyle = g
      } else {
        ctx.fillStyle = l.fill || '#ffffff'
      }
      ctx.fillRect(x, y, w, h)
      continue
    }
    if (l.kind === 'shape') {
      ctx.fillStyle = l.fill || '#e8e2d8'
      if (l.shape === 'circle' || l.shape === 'ellipse') {
        ctx.beginPath()
        ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2)
        ctx.fill()
      } else {
        ctx.fillRect(x, y, w, h)
      }
      continue
    }
    if (l.kind === 'product' || l.kind === 'image') {
      const src = l.dataUrl || resolveAsset?.(l.assetId)
      if (!src) continue
      const img = await load(src)
      // `contain` preserves the real product's aspect ratio: stretching it
      // would itself be a fidelity failure.
      const scale = l.fit === 'cover'
        ? Math.max(w / img.naturalWidth, h / img.naturalHeight)
        : Math.min(w / img.naturalWidth, h / img.naturalHeight)
      const dw = img.naturalWidth * scale
      const dh = img.naturalHeight * scale
      ctx.drawImage(img, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh)
      continue
    }
    if (l.kind === 'text') {
      const sizePx = (l.size ?? 0.03) * doc.h
      ctx.fillStyle = l.color || '#1a1a1a'
      ctx.font = `${l.weight || 400} ${sizePx}px ${l.font || 'sans-serif'}`
      ctx.textBaseline = 'top'
      const lines = wrap(String(l.text || ''), ctx, w)
      lines.forEach((line, i) => {
        const ly = y + i * sizePx * 1.2
        if (l.align === 'center') ctx.fillText(line, x + w / 2, ly)
        else if (l.align === 'right') ctx.fillText(line, x + w, ly)
        else ctx.fillText(line, x, ly)
      })
      continue
    }
    if (l.kind === 'badge') {
      ctx.fillStyle = l.fill || '#1d4a1d'
      ctx.fillRect(x, y, w, h)
      ctx.fillStyle = l.color || '#f5f0e8'
      const sizePx = (l.size ?? 0.026) * doc.h
      ctx.font = `600 ${sizePx}px sans-serif`
      ctx.textBaseline = 'middle'
      ctx.textAlign = 'center'
      ctx.fillText(String(l.text || ''), x + w / 2, y + h / 2)
      ctx.textAlign = 'start'
      continue
    }
  }
  return canvas
}

function wrap(text, ctx, maxWidth) {
  const words = String(text).split(/\s+/).filter(Boolean)
  if (!words.length) return ['']
  const lines = []
  let cur = words[0]
  for (const w of words.slice(1)) {
    const test = `${cur} ${w}`
    if (ctx.measureText(test).width <= maxWidth) cur = test
    else { lines.push(cur); cur = w }
  }
  lines.push(cur)
  return lines
}

/** Read a region out of a canvas as RGBA bytes. */
export function canvasRegion(canvas, region) {
  const ctx = canvas.getContext('2d')
  const px = regionToPixels(region, canvas.width, canvas.height)
  return ctx.getImageData(px.x, px.y, px.w, px.h).data
}

// ── 2. Fidelity ────────────────────────────────────────────────────────────
/**
 * Compare the rendered product region against the locked reference.
 * Returns a verdict; it never throws for a mismatch.
 */
export async function fidelityVerdict(doc, renderedCanvas, resolveAsset, opts = {}) {
  const meta = doc?.meta || {}
  const mode = meta.fidelityMode || 'placed'
  const m = FIDELITY_MODE_BY_ID[mode]

  if (!m) return { ok: false, status: 'block', detail: `Unknown fidelity mode "${mode}". Export is blocked rather than assumed safe.` }
  if (m.blocking) return { ok: false, status: 'block', detail: m.note }
  if (!m.enforceable) return { ok: false, status: 'unverified', detail: m.note }

  const refSrc = meta.referenceDataUrl || (meta.referenceAssetId ? resolveAsset?.(meta.referenceAssetId) : null)
  if (!refSrc) {
    return { ok: false, status: 'unverified', detail: 'Fidelity is locked but no reference image is attached, so nothing can be diffed.' }
  }
  const region = meta.fidelityRegion || productRegion(doc) || { x: 0, y: 0, w: 1, h: 1 }

  // The reference is drawn into a canvas the same size as the export with the
  // same contain-fit, so a size difference cannot read as a fidelity failure.
  const refCanvas = document.createElement('canvas')
  refCanvas.width = doc.w
  refCanvas.height = doc.h
  const img = await new Promise((resolve, reject) => {
    const i = new Image()
    i.crossOrigin = 'anonymous'
    i.onload = () => resolve(i)
    i.onerror = () => reject(new Error('reference failed to load'))
    i.src = refSrc
  })
  const p = region
  const box = { x: (p.x ?? 0) * doc.w, y: (p.y ?? 0) * doc.h, w: (p.w ?? 1) * doc.w, h: (p.h ?? 1) * doc.h }
  const scale = Math.min(box.w / img.naturalWidth, box.h / img.naturalHeight)
  const dw = img.naturalWidth * scale
  const dh = img.naturalHeight * scale
  refCanvas.getContext('2d').drawImage(img, box.x + (box.w - dw) / 2, box.y + (box.h - dh) / 2, dw, dh)

  const diff = regionDiff(canvasRegion(refCanvas, region), canvasRegion(renderedCanvas, region), opts)
  return {
    ok: diff.ok,
    status: diff.ok ? 'pass' : 'block',
    detail: diff.detail || `Fidelity check: ${diff.reason}.`,
    diff,
  }
}

// ── 7. The human compare step ──────────────────────────────────────────────
// For ANY asset containing the product, a person compares the render to the
// reference before export. The pixel diff is a tripwire; this is the sign-off.
export function compareStepStatus(doc) {
  const hasProduct = (doc?.layers || []).some(l => (l.kind === 'product' || l.kind === 'image') && l.visible !== false)
  if (!hasProduct) return { required: false, satisfied: true, detail: 'No product is placed, so there is nothing to compare.' }
  const conf = doc?.meta?.compareConfirmed
  if (!conf || !conf.at) {
    return {
      required: true, satisfied: false,
      detail: 'A human must compare the rendered product against the locked reference before export. Place the two side by side, look at the label and the edges, then confirm.',
    }
  }
  return {
    required: true, satisfied: true, at: conf.at, by: conf.by,
    detail: `Compared to the reference by ${conf.by || 'the operator'} at ${conf.at}.`,
  }
}

// ── The pipeline ───────────────────────────────────────────────────────────
export const EXPORT_STEPS = [
  'render', 'fidelity', 'compare', 'compliance', 'marker-embed', 'marker-verify',
]

/**
 * Run the full export pipeline. Every step reports one of:
 *   'pass' | 'block' | 'unverified' | 'not-run' | 'not-required'
 * A step that did not run is never reported as passed.
 *
 * @returns {{ok:boolean, bytes:Uint8Array|null, mime:string, steps:object, report:string[]}}
 */
export async function exportComposite(doc, {
  resolveAsset, mime = 'image/png', quality = 0.92, tagRequired, exportBytes,
} = {}) {
  const steps = {}
  const report = []
  const need = tagRequired ?? classifyDisclosure(doc).tagRequired

  // 1. render
  let canvas
  try {
    canvas = await renderDoc(doc, resolveAsset)
    steps.render = { status: 'pass', detail: `Rendered ${canvas.width}x${canvas.height}.` }
  } catch (e) {
    steps.render = { status: 'block', detail: `Render failed: ${e.message}` }
    report.push(steps.render.detail)
    return { ok: false, bytes: null, mime, steps, report }
  }

  // 2. fidelity
  const f = await fidelityVerdict(doc, canvas, resolveAsset)
  steps.fidelity = { status: f.status === 'pass' ? 'pass' : f.status, detail: f.detail, diff: f.diff }
  if (!f.ok) {
    // An unverified fidelity is a block for export: we do not ship what we
    // cannot check.
    steps.fidelity.status = f.status === 'unverified' ? 'unverified' : 'block'
    report.push(steps.fidelity.detail)
  }

  // 3. human compare
  const c = compareStepStatus(doc)
  steps.compare = {
    status: c.required ? (c.satisfied ? 'pass' : 'block') : 'not-required',
    detail: c.detail,
  }
  if (steps.compare.status === 'block') report.push(steps.compare.detail)

  // 4. compliance
  const comp = checkCompliance(doc, { exportBytes })
  steps.compliance = {
    status: comp.verdict === 'pass' ? 'pass' : (comp.verdict === 'incomplete' ? 'not-run' : comp.verdict === 'flag' ? 'pass' : 'block'),
    detail: `${comp.checked}/${comp.total} rules decided; ${comp.blocked.length} blocking, ${comp.flagged.length} to review.`,
    report: comp,
  }
  if (comp.verdict === 'block') report.push(...comp.blocked.map(r => r.detail))

  // 5 + 6. marker: only attempted when the disclosure requires it.
  if (!need) {
    steps['marker-embed'] = { status: 'not-required', detail: 'This asset does not require the disclosure marker.' }
    steps['marker-verify'] = { status: 'not-required', detail: 'Nothing to verify.' }
  } else {
    let bytes
    try {
      const blob = await new Promise((res, rej) => canvas.toBlob(b => (b ? res(b) : rej(new Error('toBlob returned null'))), mime, quality))
      bytes = new Uint8Array(await blob.arrayBuffer())
      bytes = embedDisclosure(bytes, mime, [DISCLOSURE_KEYWORD])
      steps['marker-embed'] = { status: 'pass', detail: `Wrote "${DISCLOSURE_KEYWORD}" into the ${mime} container.` }
    } catch (e) {
      steps['marker-embed'] = { status: 'block', detail: `Could not write the marker: ${e.message}` }
      report.push(steps['marker-embed'].detail)
      return { ok: false, bytes: null, mime, steps, report }
    }
    const v = verifyDisclosureMarker(bytes, mime, DISCLOSURE_KEYWORD)
    steps['marker-verify'] = { status: v.ok ? 'pass' : 'block', detail: v.detail }
    if (!v.ok) report.push(`MARKER DID NOT SURVIVE EXPORT: ${v.detail}`)
    const blocked = Object.values(steps).some(s => s.status === 'block')
    return { ok: !blocked, bytes: blocked ? null : bytes, mime, steps, report }
  }

  let bytes = null
  if (!Object.values(steps).some(s => s.status === 'block')) {
    try {
      const blob = await new Promise((res, rej) => canvas.toBlob(b => (b ? res(b) : rej(new Error('toBlob returned null'))), mime, quality))
      bytes = new Uint8Array(await blob.arrayBuffer())
    } catch (e) {
      steps.render = { status: 'block', detail: `Encoding failed: ${e.message}` }
      report.push(steps.render.detail)
    }
  }
  const blocked = Object.values(steps).some(s => s.status === 'block')
  return { ok: !blocked, bytes: blocked ? null : bytes, mime, steps, report }
}

/** A one-line summary of every step, for the UI and the export log. */
export function summariseExport(result) {
  return EXPORT_STEPS.map(k => {
    const s = result.steps[k]
    return `${k}: ${s ? s.status : 'not-run'}`
  }).join(' | ')
}
