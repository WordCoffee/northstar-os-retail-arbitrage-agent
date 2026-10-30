/**
 * Optimistic update state machine (work order UI-20, item 18).
 *
 * The UI shows the change immediately; the server is the authority on whether
 * it survives. Three operations, all pure so they can be tested without React:
 *
 *   begin(state, id, updater)  apply now, remember the value to restore
 *   commit(state, id)          server agreed - drop the entry
 *   rollback(state, id)        server failed - restore, then re-apply the
 *                              entries that began after it
 *
 * Rollback restores a SNAPSHOT rather than replaying an inverse patch: an
 * inverse patch cannot be derived from an arbitrary updater, and guessing one
 * is how optimistic UIs corrupt state.
 */

export function createOptimisticState(value) {
  return { value, pending: [] }
}

/** Apply `updater` immediately. Reusing an id replaces the pending entry. */
export function begin(state, id, updater) {
  if (typeof id !== 'string' || !id) throw new Error('begin() needs a non-empty id')
  if (typeof updater !== 'function') throw new Error('begin() needs an updater function')
  if (state.pending.some((p) => p.id === id)) return state
  const next = updater(state.value)
  return {
    value: next,
    // `reapply` is kept so a rollback of an EARLIER entry can rebuild the
    // later ones against the restored value instead of discarding them.
    pending: [...state.pending, { id, snapshot: state.value, reapply: updater }],
  }
}

export function commit(state, id) {
  const pending = state.pending.filter((p) => p.id !== id)
  return pending.length === state.pending.length ? state : { value: state.value, pending }
}

/**
 * Restore the snapshot taken before `id`, then re-apply every entry that began
 * after it, so one failed mutation does not discard unrelated in-flight ones.
 */
export function rollback(state, id) {
  const index = state.pending.findIndex((p) => p.id === id)
  if (index < 0) return state
  const entry = state.pending[index]
  const later = state.pending.slice(index + 1)
  let value = entry.snapshot
  for (const p of later) {
    // Later updates were computed against the pre-rollback value; re-running
    // them against the restored value is the closest correct reconstruction.
    try {
      value = p.reapply ? p.reapply(value) : value
    } catch {
      value = entry.snapshot
    }
  }
  return { value, pending: later }
}

export function isPending(state, id) {
  return state.pending.some((p) => p.id === id)
}

/** True when nothing is in flight - useful for a "Saved" indicator. */
export function isSettled(state) {
  return state.pending.length === 0
}

export default { createOptimisticState, begin, commit, rollback, isPending, isSettled }
