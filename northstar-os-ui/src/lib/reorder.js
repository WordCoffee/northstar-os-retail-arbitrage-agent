/**
 * Reorder math + snap guides (work order UI-20, item 10).
 *
 * Drag reordering is easy to get wrong in two specific ways, so both are pure
 * functions here and tested:
 *
 *   moveItem   the array operation - must not mutate, must clamp out-of-range
 *   snapIndex  which slot a pointer is over, given row height + gap, so the
 *              placeholder snaps to a slot instead of floating between two
 */

export function moveItem(list, from, to) {
  const n = Array.isArray(list) ? list.length : 0
  if (n === 0) return []
  const a = Math.max(0, Math.min(n - 1, Math.floor(Number(from) || 0)))
  const b = Math.max(0, Math.min(n - 1, Math.floor(Number(to) || 0)))
  if (a === b) return list.slice()
  const next = list.slice()
  const [item] = next.splice(a, 1)
  next.splice(b, 0, item)
  return next
}

/**
 * Index for a pointer offset. `gap` is the space between rows; the magnet makes
 * the slot boundaries slightly sticky so a 1px wobble does not flicker.
 */
export function snapIndex(offsetY, { rowHeight = 40, gap = 0, count = 0, magnet = 0.25 } = {}) {
  const n = Math.max(0, Math.floor(Number(count) || 0))
  if (n === 0) return 0
  const slot = Math.max(1, Number(rowHeight) || 1) + Math.max(0, Number(gap) || 0)
  const y = Math.max(0, Number(offsetY) || 0)
  const within = y % slot
  let index = Math.floor(y / slot)
  // Sticky boundary: inside the last `magnet` fraction of a row, prefer the next.
  if (within > slot * (1 - magnet)) index += 1
  return Math.max(0, Math.min(n - 1, index))
}

/** Placeholder + displacement for a live drag preview. */
export function dragPreview(list, from, to) {
  const moved = moveItem(list, from, to)
  return {
    items: moved,
    placeholderIndex: Math.max(0, Math.min(moved.length - 1, Math.floor(Number(to) || 0))),
    changed: from !== to,
  }
}

export default { moveItem, snapIndex, dragPreview }
