/**
 * A+ module metrics (Phase 1, item 1).
 *
 * MIRROR of Northstar_backend/aplus_layout.py. Duplication is deliberate - the
 * UI cannot import Python - and it is safe because `src/lib/aplusMetrics.test.js`
 * parses the Python source and fails if any number here drifts.
 *
 * Sizes themselves are the Amazon-verified values in
 * Northstar_backend/specialists/image_aplus.py.
 */
export const APLUS_METRICS = {
  canvas: {
    header: { w: 970, h: 600 },
    logo: { w: 600, h: 180 },
    banner: { w: 970, h: 300 },
    sidebar: { w: 300, h: 400 },
    sidebar_thumb: { w: 350, h: 175 },
    four_tiles: { w: 970, h: 220 },
    three_tiles: { w: 970, h: 300 },
    single: { w: 300, h: 300 },
    comparison: { w: 970, h: 600 },
    premium_desktop: { w: 1464, h: 600 },
    premium_mobile: { w: 600, h: 450 },
  },
  tile: {
    three_tiles: { w: 300, h: 300, gap: 20 },
    four_tiles: { w: 220, h: 220, gap: 30 },
  },
  safeInset: 24,
  copyBand: 0.44,
  comparison: { labelW: 250, headerH: 90, rows: 4 },
  mobileGutter: 16,
}

/** Centred tile offsets for the tiled rows - same maths as _tiles() in Python. */
export function tileOffsets(kind) {
  const m = APLUS_METRICS.tile[kind]
  const canvasW = APLUS_METRICS.canvas[kind].w
  if (!m) return []
  const count = kind === 'three_tiles' ? 3 : 4
  const total = count * m.w + (count - 1) * m.gap
  const margin = Math.max(0, Math.floor((canvasW - total) / 2))
  return Array.from({ length: count }, (_, i) => margin + i * (m.w + m.gap))
}

/** Copy band rectangle for header/banner. */
export function copyBandRect(kind, side = 'left') {
  const c = APLUS_METRICS.canvas[kind]
  if (!c || (kind !== 'header' && kind !== 'banner')) return null
  const band = Math.round(c.w * APLUS_METRICS.copyBand)
  const even = band - (band % 2)
  const x = side === 'left' ? APLUS_METRICS.safeInset : c.w - even
  return { x, y: 0, w: even, h: c.h }
}

export default APLUS_METRICS
