/**
 * Toast bus (work order UI-20, item 19).
 *
 * A module-level store rather than a provider: the app has several roots (shell,
 * studio, beta pages) and a notification must not depend on which tree emitted
 * it. <ToastCenter /> subscribes once; everyone else just calls toast().
 */
import { enqueue, dismiss as dropById, orderToasts } from './toastQueue.js'
import { announce } from './announce.js'

const subscribers = new Set()
let state = []

function emit() {
  for (const fn of subscribers) fn(state)
}

export function subscribe(fn) {
  subscribers.add(fn)
  fn(state)
  return () => subscribers.delete(fn)
}

export function getToasts() {
  return state
}

/**
 * toast(message)                       info
 * toast(message, 'error')              tone shorthand
 * toast(message, { tone, key, undo })  full form
 */
export function toast(msg, options = {}) {
  const opts = typeof options === 'string' ? { tone: options } : (options || {})
  state = enqueue(state, { msg, tone: opts.tone || 'info', key: opts.key, undo: opts.undo, sticky: opts.sticky })
  emit()
  if (msg) announce(String(msg), { assertive: (opts.tone || 'info') === 'error' })
  return state
}

export function dismiss(id) {
  state = dropById(state, id)
  emit()
}

export function undo(id) {
  const found = state.find((t) => t.id === id)
  if (found && typeof found.undo === 'function') {
    try { found.undo() } catch { /* the undo handler owns its failure */ }
  }
  dismiss(id)
}

export function ordered() {
  return orderToasts(state)
}

export default { toast, dismiss, undo, subscribe, getToasts, ordered }
