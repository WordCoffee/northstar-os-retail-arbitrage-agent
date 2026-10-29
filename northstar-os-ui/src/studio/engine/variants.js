// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — SOCIAL VARIANT MATRIX  (REA candidate S5)
//
// Reverse-engineered from two sources, deliberately:
//
//  1. Documented crop semantics (Cloudinary "resizing and cropping", fetched
//     2026-10-29): a `fill`/cover crop scales until the shorter side fits, then
//     crops the longer side; what survives is decided by a GRAVITY point, and
//     `fit`/`pad` are the modes that avoid cropping entirely. Those are the
//     words this module uses, because they are the words the industry uses.
//
//  2. This repo's own SAFE_ZONES discipline (specRegistry.js): boxes in
//     NORMALISED 0..1 coordinates, both documented figures kept, and the
//     STRICTER union applied. Same rule here, inverted: instead of "where must
//     I not put things", this answers "what survives every crop" — the keep-IN
//     intersection across every target.
//
// What it never does: claim a safe region exists when it does not. If the
// targets disagree, `ok` is false and the reason is the outage.
// ═══════════════════════════════════════════════════════════════════════════

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

/**
 * One target's cover-crop of the master.
 * @param {{w:number,h:number}} master
 * @param {{id:string,w:number,h:number,focal?:{x:number,y:number}}} target
 * @param {{x:number,y:number}} focal default gravity
 */
export function cropFor(master, target, focal = { x: 0.5, y: 0.5 }) {
  const mw = Number(master.w), mh = Number(master.h)
  const tw = Number(target.w), th = Number(target.h)
  if (!(mw > 0 && mh > 0 && tw > 0 && th > 0)) {
    throw new Error(`cropFor needs positive sizes (master ${mw}x${mh}, target ${tw}x${th})`)
  }
  const g = target.focal || focal
  const scale = Math.max(tw / mw, th / mh)          // cover: the crop side is the longer one
  const cropW = tw / scale
  const cropH = th / scale
  const cx = clamp(g.x * mw - cropW / 2, 0, Math.max(0, mw - cropW))
  const cy = clamp(g.y * mh - cropH / 2, 0, Math.max(0, mh - cropH))
  return {
    id: target.id,
    scale: Number(scale.toFixed(4)),
    cropPx: { x: Math.round(cx), y: Math.round(cy), w: Math.round(cropW), h: Math.round(cropH) },
    cropNorm: {
      x: Number((cx / mw).toFixed(4)), y: Number((cy / mh).toFixed(4)),
      w: Number((cropW / mw).toFixed(4)), h: Number((cropH / mh).toFixed(4)),
    },
    upscale: scale > 1,
    gravity: { x: Number(g.x), y: Number(g.y) },
  }
}

/** Intersection of crop boxes in normalised master coordinates. Empty => no shared anchor. */
export function keepInIntersection(crops) {
  if (!crops.length) return null
  let x0 = 0, y0 = 0, x1 = 1, y1 = 1
  for (const c of crops) {
    x0 = Math.max(x0, c.cropNorm.x)
    y0 = Math.max(y0, c.cropNorm.y)
    x1 = Math.min(x1, c.cropNorm.x + c.cropNorm.w)
    y1 = Math.min(y1, c.cropNorm.y + c.cropNorm.h)
  }
  const w = Math.max(0, x1 - x0)
  const h = Math.max(0, y1 - y0)
  return {
    x: Number(x0.toFixed(4)), y: Number(y0.toFixed(4)),
    w: Number(w.toFixed(4)), h: Number(h.toFixed(4)),
    areaPct: Number((w * h * 100).toFixed(2)),
    empty: w <= 0.001 || h <= 0.001,
  }
}

/**
 * The whole matrix: per-target crops plus the region that survives all of them.
 * `ok` is false when no shared region exists — the honest answer, not a guess.
 */
export function buildVariantMatrix({ master, targets = [], focal = { x: 0.5, y: 0.5 } } = {}) {
  if (!master || !(master.w > 0) || !(master.h > 0)) {
    throw new Error('buildVariantMatrix needs the master canvas {w, h}')
  }
  if (!targets.length) {
    return { ok: false, reason: 'no target canvases selected', master, focal, variants: [], keepIn: null }
  }
  const variants = targets.map(t => cropFor(master, t, focal))
  const keepIn = keepInIntersection(variants)
  const warnings = []
  const upscaled = variants.filter(v => v.upscale).map(v => v.id)
  if (upscaled.length) {
    warnings.push(`needs upscaling (never ideal): ${upscaled.join(', ')}`)
  }
  if (keepIn && keepIn.empty) {
    return {
      ok: false,
      reason: 'no region survives every crop — these targets cannot share one anchor',
      master, focal, variants, keepIn, warnings,
    }
  }
  if (keepIn && keepIn.areaPct < 5) {
    warnings.push(`shared safe region is only ${keepIn.areaPct}% of the master; keep the logo out of it`)
  }
  return {
    ok: true,
    reason: null,
    master, focal, variants, keepIn, warnings,
    note: 'Cover-crop with a gravity point, per described crop semantics. The keep-In box is the '
        + 'STRICTER intersection across every target, the same rule SAFE_ZONES applies to Amazon '
        + 'keep-OUT boxes.',
  }
}
