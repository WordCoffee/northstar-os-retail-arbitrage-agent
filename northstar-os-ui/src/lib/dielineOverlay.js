// U8 — package panels and the dieline overlay, as data.
//
// Two ideas, both pure:
//   • A document carries more than one panel (front / rear / side). Switching
//     swaps the visible layer list and keeps every panel's own layers.
//   • A dieline's guide geometry (bleed / trim / fold / safe) is drawn for ONE
//     panel, normalised to that panel's box, so it lands on the artboard at true
//     proportions.
//
// The guides are DOM-only: `renderToCanvas` never receives them, which is why a
// guide can never reach an exported PNG or PDF. That is asserted in the e2e by
// exporting with the overlay on and off and comparing the byte counts.

export const PANELS = [
  { id: 'front', label: 'Front' },
  { id: 'back', label: 'Rear' },
  { id: 'gusset', label: 'Side / gusset' },
]

export const GUIDE_KINDS = [
  { id: 'bleed', label: 'Bleed', colour: 'rgba(255, 138, 128, 0.95)' },
  { id: 'trim', label: 'Trim', colour: 'rgba(255, 255, 255, 0.95)' },
  { id: 'fold', label: 'Fold', colour: 'rgba(126, 200, 255, 0.95)' },
  { id: 'safe', label: 'Safe zone', colour: 'rgba(158, 240, 158, 0.95)' },
]

/** Pixels per millimetre used when a dieline sizes the artboard. */
export const PX_PER_MM = 4

export function panelIds() {
  return PANELS.map((p) => p.id)
}

export function panelLabel(id) {
  const p = PANELS.find((x) => x.id === id)
  return p ? p.label : 'Front'
}

/**
 * The panel's box in sheet millimetres: `[x, y, w, h]`, or null when the dieline
 * does not describe that panel. A missing panel is a refusal, never a guess.
 */
export function panelRect(geometry, panelId) {
  const panels = (geometry && geometry.panels) || {}
  const box = panels[panelId]
  if (!Array.isArray(box) || box.length !== 4) return null
  const [x, y, w, h] = box.map(Number)
  if (!(w > 0) || !(h > 0)) return null
  return [x, y, w, h]
}

/** The artboard size in px for a panel at PX_PER_MM. */
export function panelSize(geometry, panelId, { pxPerMm = PX_PER_MM } = {}) {
  const box = panelRect(geometry, panelId)
  if (!box) return null
  return {
    w: Math.max(1, Math.round(box[2] * pxPerMm)),
    h: Math.max(1, Math.round(box[3] * pxPerMm)),
    mm: { w: box[2], h: box[3] },
  }
}

const clamp01 = (v) => Math.max(0, Math.min(1, v))

/**
 * Guide geometry for one panel, normalised to that panel (0..1 of the artboard).
 * Elements that fall outside the panel are clipped, not dropped, so a bleed
 * rectangle that extends past the trim still draws its visible edge.
 */
export function guidesForPanel(geometry, panelId, { kinds = null } = {}) {
  const box = panelRect(geometry, panelId)
  if (!box || !geometry) return { rects: [], lines: [] }
  const [px, py, pw, ph] = box
  const wanted = kinds ? new Set(kinds) : null
  const rects = []
  const lines = []

  for (const [kind, list] of Object.entries(geometry.guides || {})) {
    if (wanted && !wanted.has(kind)) continue
    for (const el of list || []) {
      if (el.kind === 'rect') {
        const x1 = clamp01((Number(el.x) - px) / pw)
        const y1 = clamp01((Number(el.y) - py) / ph)
        const x2 = clamp01((Number(el.x) + Number(el.w) - px) / pw)
        const y2 = clamp01((Number(el.y) + Number(el.h) - py) / ph)
        if (x2 - x1 <= 0 || y2 - y1 <= 0) continue
        rects.push({ kind, x: x1, y: y1, w: x2 - x1, h: y2 - y1 })
      } else if (el.kind === 'line') {
        lines.push({
          kind,
          x1: clamp01((Number(el.x1) - px) / pw),
          y1: clamp01((Number(el.y1) - py) / ph),
          x2: clamp01((Number(el.x2) - px) / pw),
          y2: clamp01((Number(el.y2) - py) / ph),
        })
      }
    }
  }
  return { rects, lines }
}

/** A short, honest description of what is being drawn and from where. */
export function describeOverlay(geometry, panelId) {
  if (!geometry) return 'No dieline loaded.'
  const box = panelRect(geometry, panelId)
  if (!box) return `This dieline has no ${panelLabel(panelId).toLowerCase()} panel.`
  const counts = Object.entries(geometry.guides || {})
    .map(([kind, list]) => `${list.length} ${kind}`)
    .join(', ')
  return `${geometry.title || geometry.template || 'Dieline'} · ${box[2]}x${box[3]} mm · ${counts}`
}
