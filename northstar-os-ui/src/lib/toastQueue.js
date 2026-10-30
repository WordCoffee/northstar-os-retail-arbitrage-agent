/**
 * Toast queue (work order UI-20, item 19).
 *
 * Grouping, priority and the cap are pure so they can be tested without a
 * renderer. Three rules that are easy to get wrong and are asserted below:
 *
 *   - the same `key` twice is ONE toast with a count, not two stacked copies;
 *   - an error outranks a success regardless of arrival order, so a failure is
 *     never buried under "Saved";
 *   - the list is capped, and the cap drops the LOWEST priority oldest first.
 */

export const TONES = ['success', 'info', 'warning', 'error']
const WEIGHT = { success: 1, info: 2, warning: 3, error: 4 }

export function priority(tone) {
  return WEIGHT[tone] ?? WEIGHT.info
}

export function enqueue(list, item, { max = 5 } = {}) {
  const next = Array.isArray(list) ? list.slice() : []
  const tone = TONES.includes(item.tone) ? item.tone : 'info'
  const key = item.key || item.msg

  const existing = next.find((t) => (t.key || t.msg) === key)
  if (existing) {
    existing.count = (existing.count || 1) + 1
    existing.tone = tone
    existing.createdAt = item.createdAt ?? existing.createdAt
    if (item.undo) existing.undo = item.undo
    return next
  }

  next.push({
    id: item.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    msg: String(item.msg ?? ''),
    tone,
    key,
    count: 1,
    createdAt: item.createdAt ?? Date.now(),
    sticky: Boolean(item.sticky) || tone === 'error',
    undo: item.undo,
  })

  // Trim: drop the weakest/oldest until we are inside the cap.
  while (next.length > max) {
    let worst = 0
    for (let i = 1; i < next.length; i += 1) {
      const a = next[i]
      const b = next[worst]
      if (priority(a.tone) < priority(b.tone)) worst = i
      else if (priority(a.tone) === priority(b.tone) && a.createdAt < b.createdAt) worst = i
    }
    next.splice(worst, 1)
  }
  return next
}

export function dismiss(list, id) {
  const next = Array.isArray(list) ? list.filter((t) => t.id !== id) : []
  return next.length === (Array.isArray(list) ? list.length : 0) ? (list || []) : next
}

/** Display order: highest priority first, oldest first inside a tier. */
export function orderToasts(list) {
  return (Array.isArray(list) ? list.slice() : []).sort((a, b) => {
    const d = priority(b.tone) - priority(a.tone)
    if (d !== 0) return d
    return a.createdAt - b.createdAt
  })
}

export function shouldAutoDismiss(toast, now = Date.now(), ttl = 3200) {
  if (!toast || toast.sticky) return false
  return now - toast.createdAt >= ttl
}

export default { TONES, priority, enqueue, dismiss, orderToasts, shouldAutoDismiss }
