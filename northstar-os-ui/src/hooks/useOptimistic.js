import { useCallback, useState } from 'react'
import {
  createOptimisticState, begin, commit, rollback, isPending as isPendingIn,
} from '../lib/optimistic.js'

/**
 * Optimistic mutation (item 18).
 *
 *   const { value, run, pending } = useOptimistic({ done: false })
 *   run('toggle-1', (s) => ({ ...s, done: !s.done }), () => api.toggle())
 *
 * The value flips instantly; a rejection restores the snapshot and re-throws so
 * the caller can surface the error. Failures are never silent.
 */
export function useOptimistic(initial) {
  const [state, setState] = useState(() => createOptimisticState(initial))

  const run = useCallback(async (id, updater, task) => {
    setState((s) => begin(s, id, updater))
    try {
      const result = await task()
      setState((s) => commit(s, id))
      return result
    } catch (error) {
      setState((s) => rollback(s, id))
      throw error
    }
  }, [])

  return {
    value: state.value,
    pending: state.pending,
    settled: state.pending.length === 0,
    isPending: (id) => isPendingIn(state, id),
    run,
  }
}

export default useOptimistic
