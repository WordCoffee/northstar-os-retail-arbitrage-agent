// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — SNAPPING
//
// Pixel-space snapping for the canvas stage. The document stores geometry in
// normalised units (0..1), but a designer thinks in screen pixels: an 8 px
// magnet must be 8 px on the glass, whatever the document raster size or the
// current zoom. So this module converts to display pixels, finds the nearest
// alignment within the threshold, and converts the result back.
//
// Targets, in order of construction:
//   • canvas start / centre / end on each axis
//   • every other layer's start / centre / end on each axis
//
// Every guide it returns names the target that actually fired, so the stage
// draws the line it snapped to and never a decorative one. Snapping never
// changes a layer's size when it is being moved, and never moves a layer when
// it is being resized.
// ═══════════════════════════════════════════════════════════════════════════

export const SNAP_PX = 8

const fin = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0)
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

/** Normalised rect + display size → pixel box. */
function toPx(rect, canvas) {
  const W = Math.max(1, fin(canvas && canvas.W) || 1)
  const H = Math.max(1, fin(canvas && canvas.H) || 1)
  return {
    W,
    H,
    x: fin(rect && rect.x) * W,
    y: fin(rect && rect.y) * H,
    // A zero-size layer still needs an anchor; 1 px keeps the maths sane.
    w: Math.max(1, fin(rect && rect.w) * W),
    h: Math.max(1, fin(rect && rect.h) * H),
  }
}

function layerBoxes(others, canvas) {
  return (Array.isArray(others) ? others : []).map((o) => ({
    ...toPx(o, canvas),
    label: (o && (o.name || o.kind)) || 'layer',
  }))
}

function axisTargets(canvasPx, boxes, axis) {
  const list = [
    { pos: 0, name: 'canvas start' },
    { pos: canvasPx / 2, name: 'canvas centre' },
    { pos: canvasPx, name: 'canvas end' },
  ]
  for (const b of boxes) {
    const start = axis === 'x' ? b.x : b.y
    const size = axis === 'x' ? b.w : b.h
    list.push(
      { pos: start, name: `${b.label} start` },
      { pos: start + size / 2, name: `${b.label} centre` },
      { pos: start + size, name: `${b.label} end` },
    )
  }
  return list
}

function boxEdges(x, size) {
  return [
    { id: 'start', pos: x },
    { id: 'center', pos: x + size / 2 },
    { id: 'end', pos: x + size },
  ]
}

/**
 * Nearest alignment for one axis. Ties keep the first target built (canvas
 * edges before layer edges), which is the stable, predictable choice.
 */
function snapAxis(edges, targets, threshold) {
  let best = null
  for (const e of edges) {
    for (const t of targets) {
      const d = t.pos - e.pos
      if (Math.abs(d) <= threshold && (!best || Math.abs(d) < Math.abs(best.d))) {
        best = { d, target: t, edge: e }
      }
    }
  }
  return best
}

/**
 * Snap a moving box. Size is preserved; only x/y move.
 * Returns normalised coordinates plus the guides that fired.
 */
export function snapMove(rect, { canvas, others = [], threshold = SNAP_PX } = {}) {
  const p = toPx(rect, canvas)
  const boxes = layerBoxes(others, canvas)
  const xTargets = axisTargets(p.W, boxes, 'x')
  const yTargets = axisTargets(p.H, boxes, 'y')
  const bx = snapAxis(boxEdges(p.x, p.w), xTargets, threshold)
  const by = snapAxis(boxEdges(p.y, p.h), yTargets, threshold)
  const x = p.x + (bx ? bx.d : 0)
  const y = p.y + (by ? by.d : 0)
  const guides = []
  if (bx) guides.push({ axis: 'x', at: bx.target.pos / p.W, name: bx.target.name })
  if (by) guides.push({ axis: 'y', at: by.target.pos / p.H, name: by.target.name })
  return {
    x: x / p.W,
    y: y / p.H,
    guides,
    snapped: { x: !!bx, y: !!by },
  }
}

/**
 * Snap a bottom-right resize. The top-left corner is fixed; only w/h change,
 * and only when their outer edge lands within the threshold of a target.
 */
export function snapResize(rect, { canvas, others = [], threshold = SNAP_PX } = {}) {
  const p = toPx(rect, canvas)
  const boxes = layerBoxes(others, canvas)
  const xTargets = axisTargets(p.W, boxes, 'x')
  const yTargets = axisTargets(p.H, boxes, 'y')
  const bx = snapAxis([{ id: 'end', pos: p.x + p.w }], xTargets, threshold)
  const by = snapAxis([{ id: 'end', pos: p.y + p.h }], yTargets, threshold)
  const wPx = p.w + (bx ? bx.d : 0)
  const hPx = p.h + (by ? by.d : 0)
  const guides = []
  if (bx) guides.push({ axis: 'x', at: bx.target.pos / p.W, name: bx.target.name })
  if (by) guides.push({ axis: 'y', at: by.target.pos / p.H, name: by.target.name })
  return {
    w: clamp(wPx / p.W, 0.02, 1),
    h: clamp(hPx / p.H, 0.02, 1),
    guides,
    snapped: { x: !!bx, y: !!by },
  }
}

export default { SNAP_PX, snapMove, snapResize }
