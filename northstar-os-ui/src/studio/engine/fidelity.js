// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — PRODUCT FIDELITY (reference lock + real-photo compositing)
//
// The rule this module enforces: the product itself is NEVER generated. The
// operator's real photograph is composited; generation is allowed only AROUND
// it (background, scene, lighting). Fidelity is then CHECKED, and export is
// blocked when the product region in the output differs from the locked
// reference beyond a threshold.
//
// Two halves, deliberately separated so the maths is testable without a DOM:
//   • `regionDiff()` — pure. Takes two RGBA buffers and returns a verdict.
//   • `extractRegion()` / `verifyFidelity()` — browser-side. Uses canvas to
//     read pixels, then calls the pure half.
//
// WHAT THIS CANNOT DO
//   Pixel diffing catches a product that was redrawn, warped, relit or
//   recoloured beyond the threshold. It does NOT catch a small, plausible edit
//   inside the product. The threshold is a tripwire, not a proof, and the UI
//   says so.
// ═══════════════════════════════════════════════════════════════════════════

// Default tripwire. 0.06 mean absolute channel difference = the product may
// drift by about 6% on average before export is blocked. Chosen to tolerate a
// genuine re-shoot under slightly different lighting, while catching a
// regenerated or heavily retouched product.
export const DEFAULT_THRESHOLD = 0.06

// A single channel may not move more than this in the WORST pixel, regardless
// of the average. Catches a locally destroyed label on an otherwise identical
// product.
export const DEFAULT_MAX_PIXEL_DELTA = 0.45

export const FIDELITY_MODES = [
  {
    id: 'locked',
    label: 'Reference locked',
    note: 'A real product photograph is locked as the reference. The product region of the export is diffed against it and export is blocked beyond the threshold.',
    enforceable: true,
  },
  {
    id: 'placed',
    label: 'Real photograph placed (no lock)',
    note: 'A real photograph is placed but no reference was locked, so nothing can be diffed. Treated as UNVERIFIED and reported as such.',
    enforceable: false,
  },
  {
    id: 'generated',
    label: 'Product region generated',
    note: 'The product region is not the operator\'s real photograph. This violates the fidelity rule: export is blocked.',
    enforceable: false,
    blocking: true,
  },
]

export const FIDELITY_MODE_BY_ID = Object.fromEntries(FIDELITY_MODES.map(m => [m.id, m]))

// ── Pure: the diff itself ──────────────────────────────────────────────────
/**
 * Mean and worst per-channel absolute difference between two RGBA buffers of
 * the same length, ignoring fully transparent pixels (which are background in
 * a masked reference).
 *
 * @param {Uint8ClampedArray|Uint8Array} a
 * @param {Uint8ClampedArray|Uint8Array} b
 * @param {{threshold?:number, maxPixelDelta?:number}} [opts]
 * @returns {{ok:boolean, mean:number, worst:number, compared:number,
 *            reason:string, threshold:number, maxPixelDelta:number}}
 */
export function regionDiff(a, b, opts = {}) {
  const threshold = opts.threshold ?? DEFAULT_THRESHOLD
  const maxPixelDelta = opts.maxPixelDelta ?? DEFAULT_MAX_PIXEL_DELTA

  if (!a || !b) {
    return { ok: false, mean: null, worst: null, compared: 0, reason: 'missing-buffer', threshold, maxPixelDelta }
  }
  if (a.length !== b.length) {
    return { ok: false, mean: null, worst: null, compared: 0, reason: 'length-mismatch', threshold, maxPixelDelta }
  }
  if (a.length === 0 || a.length % 4 !== 0) {
    return { ok: false, mean: null, worst: null, compared: 0, reason: 'not-rgba', threshold, maxPixelDelta }
  }

  let sum = 0
  let n = 0
  let worst = 0
  for (let i = 0; i < a.length; i += 4) {
    // Skip pixels that are transparent in EITHER buffer: a masked reference
    // has no product there, so there is nothing to compare.
    if (a[i + 3] === 0 || b[i + 3] === 0) continue
    for (let c = 0; c < 3; c++) {
      const d = Math.abs(a[i + c] - b[i + c]) / 255
      sum += d
      n++
      if (d > worst) worst = d
    }
  }

  if (n === 0) {
    return { ok: false, mean: null, worst: null, compared: 0, reason: 'nothing-to-compare', threshold, maxPixelDelta }
  }

  const mean = sum / n
  if (worst > maxPixelDelta) {
    return {
      ok: false, mean, worst, compared: n / 3, reason: 'worst-pixel-exceeded', threshold, maxPixelDelta,
      detail: `A single point on the product moved by ${(worst * 100).toFixed(1)}% (limit ${(maxPixelDelta * 100).toFixed(0)}%). A locally destroyed label or a redrawn edge looks like this.`,
    }
  }
  if (mean > threshold) {
    return {
      ok: false, mean, worst, compared: n / 3, reason: 'mean-exceeded', threshold, maxPixelDelta,
      detail: `The product region differs by ${(mean * 100).toFixed(1)}% on average (limit ${(threshold * 100).toFixed(0)}%). The product looks regenerated, warped, relit or recoloured.`,
    }
  }
  return {
    ok: true, mean, worst, compared: n / 3, reason: 'within-threshold', threshold, maxPixelDelta,
    detail: `Product region matches the locked reference: ${(mean * 100).toFixed(2)}% mean difference, worst point ${(worst * 100).toFixed(2)}%.`,
  }
}

// ── A SECOND, TIGHTER CHECK: the label region ─────────────────────────────
// Calibration (tools/test-fidelity-freshness.mjs) shows the 6% AVERAGE test is
// blind to small in-product edits: a label text change moved the mean by 0.67%
// and a logo swap by 0.58%, both far under the limit. The worst-pixel tripwire
// caught all four in-product classes, and THAT is the second check.
//
// This function gives the operator a sharper lever on top of it: name the label
// region and diff it at a much tighter tolerance, because that is the part of
// the product Amazon cares most about and the part a generative step damages
// first.
export const DEFAULT_LABEL_THRESHOLD = 0.02

export function labelRegionDiff(refBytes, outBytes, opts = {}) {
  const threshold = opts.threshold ?? DEFAULT_LABEL_THRESHOLD
  // Inside the label the tripwire is near-zero: any real change to printed text
  // or a logo should register, because there is no legitimate reason for the
  // label pixels to move.
  const r = regionDiff(refBytes, outBytes, { threshold, maxPixelDelta: opts.maxPixelDelta ?? 0.10 })
  if (r.reason === 'nothing-to-compare') {
    return { ...r, ok: false, reason: 'label-region-empty', detail: 'The label region has no opaque pixels in one of the images, so nothing could be compared. Name the label region correctly.' }
  }
  return {
    ...r,
    check: 'label-region',
    detail: r.ok
      ? `Label region matches (${(r.mean * 100).toFixed(2)}% mean, worst ${(r.worst * 100).toFixed(1)}%).`
      : `LABEL REGION CHANGED: ${(r.mean * 100).toFixed(2)}% mean, worst ${(r.worst * 100).toFixed(1)}% (limits ${(threshold * 100).toFixed(1)}% / ${((opts.maxPixelDelta ?? 0.10) * 100).toFixed(0)}%). Printed text and logos must not be regenerated.`,
  }
}

// WHAT REMAINS UNDETECTABLE (documented, not implied)
export const FIDELITY_BLIND_SPOTS = [
  'An edit that keeps every pixel within the worst-pixel tolerance across the whole product region. A subtle recolour of a small area can stay under it.',
  'A change to the product that is itself plausible: a slightly different label position, a different but similar product of the same shape and colour.',
  'Anything the operator photographs afresh and locks as the new reference. A new reference resets the comparison, so the reference itself is the trust anchor.',
  'Semantic errors. The diff cannot tell whether the pack now says the wrong size; it can only tell that the pixels moved.',
]

/** Scale a normalised rect (0..1) to pixel coordinates inside a WxH image. */
export function regionToPixels(region, width, height) {  const r = region || { x: 0, y: 0, w: 1, h: 1 }
  const x = Math.max(0, Math.min(width - 1, Math.round((r.x ?? 0) * width)))
  const y = Math.max(0, Math.min(height - 1, Math.round((r.y ?? 0) * height)))
  const w = Math.max(1, Math.min(width - x, Math.round((r.w ?? 1) * width)))
  const h = Math.max(1, Math.min(height - y, Math.round((r.h ?? 1) * height)))
  return { x, y, w, h }
}

/** The region a document's product occupies, in normalised coordinates. */
export function productRegion(doc) {
  const prods = (doc?.layers || []).filter(l => l.kind === 'product' && l.visible !== false)
  if (!prods.length) return null
  const x = Math.min(...prods.map(l => l.x ?? 0))
  const y = Math.min(...prods.map(l => l.y ?? 0))
  const right = Math.max(...prods.map(l => (l.x ?? 0) + (l.w ?? 0)))
  const bottom = Math.max(...prods.map(l => (l.y ?? 0) + (l.h ?? 0)))
  return { x, y, w: right - x, h: bottom - y }
}

// ── Browser side: extract pixels, then call the pure half ──────────────────
function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image failed to load'))
    img.src = src
  })
}

/** Read a region's RGBA pixels out of an image by drawing it to a canvas. */
export async function extractRegion(dataUrl, region, targetW, targetH) {
  const img = await loadImage(dataUrl)
  const w = targetW || img.naturalWidth
  const h = targetH || img.naturalHeight
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  // Both sides are drawn with the SAME letterboxing so a size difference does
  // not read as a fidelity failure.
  ctx.drawImage(img, 0, 0, w, h)
  const px = regionToPixels(region, w, h)
  return ctx.getImageData(px.x, px.y, px.w, px.h).data
}

/**
 * Full check. Returns a verdict the pre-flight can act on.
 * `fidelityCheck` is the ONLY caller that should decide whether to block.
 */
export async function verifyFidelity(doc, { threshold, maxPixelDelta } = {}) {
  const meta = doc?.meta || {}
  const mode = meta.fidelityMode || 'placed'
  const m = FIDELITY_MODE_BY_ID[mode]

  if (!m) {
    return { status: 'block', ok: false, detail: `Unknown fidelity mode "${mode}". Export is blocked rather than assumed safe.` }
  }
  if (m.blocking) {
    return { status: 'block', ok: false, detail: m.note }
  }
  if (!m.enforceable) {
    return { status: 'unverified', ok: false, detail: m.note }
  }
  if (!meta.referenceDataUrl || !meta.compositeDataUrl) {
    return { status: 'unverified', ok: false, detail: 'Fidelity is locked but the reference and the composite were not both supplied, so nothing can be diffed.' }
  }

  const region = meta.fidelityRegion || productRegion(doc) || { x: 0, y: 0, w: 1, h: 1 }
  const [ref, comp] = await Promise.all([
    extractRegion(meta.referenceDataUrl, region, meta.fidelityW, meta.fidelityH),
    extractRegion(meta.compositeDataUrl, region, meta.fidelityW, meta.fidelityH),
  ])
  const diff = regionDiff(ref, comp, { threshold, maxPixelDelta })
  return {
    status: diff.ok ? 'pass' : 'block',
    ok: diff.ok,
    detail: diff.detail || `Fidelity check: ${diff.reason}.`,
    diff,
  }
}

// ── Compositing contract ───────────────────────────────────────────────────
// The order that makes fidelity checkable at all: lock the real photo, place
// it opaquely, generate only around it, then diff.
export const COMPOSITE_STEPS = [
  { id: 'lock', label: 'Lock the real product photograph as the reference', note: 'Without a locked reference there is nothing to diff, and the asset stays UNVERIFIED.' },
  { id: 'place', label: 'Place the real photo as an opaque base layer', note: 'The product region is the operator\'s own pixels. It is never generated.' },
  { id: 'generate-around', label: 'Generate only the background and scene around the product mask', note: 'Generation must not cross the product region.' },
  { id: 'diff', label: 'Diff the exported product region against the reference', note: 'Export is blocked beyond the threshold.' },
]

// ── 7. Sample-size discipline for workflow claims ──────────────────────────
// Any claim this studio makes about a workflow must state how many assets it
// rests on. A claim with no sample size is refused rather than phrased
// carefully.
export function claim(subject, value, sampleSize, note) {
  const n = Number(sampleSize)
  if (!Number.isFinite(n) || n <= 0) {
    return { ok: false, subject, value: null, sampleSize: n, text: `No claim is made about ${subject}: it rests on ${Number.isFinite(n) ? n : 'no'} observations.` }
  }
  return { ok: true, subject, value, sampleSize: n, text: `${subject}: ${value} (n=${n})${note ? ' — ' + note : ''}` }
}

export function sampleLabel(n) {
  const v = Number(n)
  if (!Number.isFinite(v) || v <= 0) return 'no sample'
  return `n=${v}`
}
