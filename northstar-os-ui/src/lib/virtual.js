/**
 * Windowing math for long lists (work order UI-20, item 9).
 *
 * Pure function: given the scroll offset, viewport height, row height and item
 * count, return the slice that must be mounted. Kept separate from React so the
 * edge cases (empty list, scrolled past the end, sub-pixel offsets) are testable.
 */

export function visibleRange({
  scrollTop = 0,
  viewport = 0,
  rowHeight = 40,
  count = 0,
  overscan = 4,
} = {}) {
  const h = Math.max(1, Number(rowHeight) || 1)
  const vp = Math.max(0, Number(viewport) || 0)
  const n = Math.max(0, Math.floor(Number(count) || 0))
  if (n === 0) return { start: 0, end: 0, offset: 0, total: 0 }

  const top = Math.max(0, Number(scrollTop) || 0)
  const first = Math.floor(top / h)
  const visible = Math.ceil(vp / h) || 1
  const start = Math.max(0, first - overscan)
  const end = Math.min(n, first + visible + overscan)

  return {
    start,
    end,
    offset: start * h,
    total: n * h,
  }
}

/** Row-count estimate so the scrollbar is honest before every row is measured. */
export function totalHeight(count, rowHeight) {
  return Math.max(0, Math.floor(Number(count) || 0)) * Math.max(1, Number(rowHeight) || 1)
}

export default { visibleRange, totalHeight }
