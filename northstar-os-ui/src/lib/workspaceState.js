/**
 * Persistent workspace state (work order UI-20, item 20).
 *
 * Checkpoints the parts of the UI a reload should not destroy: collapsed
 * sidebars, the active tab, scroll offsets, filters. Pure serialisation so the
 * rules are testable, with an explicit allowlist of keys.
 *
 * Rules that matter more than the storage call:
 *  - unknown keys are DROPPED, not merged: a stale build must never inject
 *    state a new build does not understand;
 *  - a version mismatch drops the record instead of guessing;
 *  - corrupt JSON drops the record instead of throwing into render;
 *  - a TTL expires stale state so "restore" never resurrects last month's tab.
 */

export const WORKSPACE_VERSION = 1
export const WORKSPACE_TTL_MS = 1000 * 60 * 60 * 24 * 14 // 14 days

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

/** Keep only allowlisted keys; drop anything the caller did not declare. */
export function pick(state, keys) {
  const out = {}
  if (!isPlainObject(state)) return out
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(state, key)) out[key] = state[key]
  }
  return out
}

export function serialize(state, {
  keys,
  version = WORKSPACE_VERSION,
  now = Date.now(),
} = {}) {
  const body = pick(state, keys || Object.keys(isPlainObject(state) ? state : {}))
  return JSON.stringify({ v: version, savedAt: now, state: body })
}

/**
 * Parse a stored record. Returns `null` when it must not be trusted, so the
 * caller falls back to defaults rather than rendering someone else's state.
 */
export function parse(raw, {
  keys,
  version = WORKSPACE_VERSION,
  now = Date.now(),
  ttlMs = WORKSPACE_TTL_MS,
} = {}) {
  if (typeof raw !== 'string' || !raw) return null
  let record
  try {
    record = JSON.parse(raw)
  } catch {
    return null
  }
  if (!isPlainObject(record) || record.v !== version) return null
  if (typeof record.savedAt !== 'number') return null
  if (ttlMs > 0 && now - record.savedAt > ttlMs) return null
  if (record.savedAt > now + 60_000) return null // clock skew: refuse the future
  if (!isPlainObject(record.state)) return null
  return keys ? pick(record.state, keys) : record.state
}

/** Merge restored state over defaults without letting restored keys invent new ones. */
export function withDefaults(defaults, restored) {
  if (!isPlainObject(restored)) return { ...defaults }
  const out = { ...defaults }
  for (const key of Object.keys(defaults)) {
    if (Object.prototype.hasOwnProperty.call(restored, key)) out[key] = restored[key]
  }
  return out
}

export function clampScroll(value, max) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.min(Math.floor(n), Math.max(0, Math.floor(Number(max) || 0)))
}

export default { WORKSPACE_VERSION, WORKSPACE_TTL_MS, pick, serialize, parse, withDefaults, clampScroll }
