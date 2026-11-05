// Package Design sessions, kept across navigation.
//
// The page held its generated concepts in component state, so clicking into
// another room discarded every one of them. This module is the pure half of the
// fix: shape a session list for storage and decide what may be restored.
//
// The rules are the workspace serializer's rules, applied to content:
//   - anything that does not look like a session is dropped, never rendered;
//   - a version mismatch or corrupt record restores nothing rather than throwing;
//   - a TTL expires old sessions so "restore" cannot resurrect last month's work;
//   - a restored session is always one that was really generated - this module
//     never invents a session.

import { parse, serialize } from './workspaceState.js'

export const PACKIFY_SESSIONS_KEY = 'ns-packify-sessions'
export const PACKIFY_SESSIONS_MAX = 20
/** The content is long-lived; the workspace default (14 days) is the right scale. */
export const PACKIFY_SESSIONS_TTL_MS = 1000 * 60 * 60 * 24 * 14

const MAX_PROMPT = 200
const MAX_CONTENT = 8000

/** Keep only entries that are shaped like a generated session. */
export function sanitiseSessions(value) {
  if (!Array.isArray(value)) return []
  return value
    .filter((s) => s && typeof s === 'object'
      && typeof s.prompt === 'string' && typeof s.content === 'string'
      && Number.isFinite(Number(s.id)))
    .slice(0, PACKIFY_SESSIONS_MAX)
    .map((s) => ({
      id: Number(s.id),
      prompt: s.prompt.slice(0, MAX_PROMPT),
      content: s.content.slice(0, MAX_CONTENT),
      model: typeof s.model === 'string' ? s.model : '',
      at: typeof s.at === 'string' ? s.at : '',
    }))
}

/** The record to hand to localStorage. */
export function encodeSessions(sessions, active) {
  return serialize(
    { sessions: sanitiseSessions(sessions), active: active ?? null },
    { keys: ['sessions', 'active'] },
  )
}

/**
 * Restore `{ sessions, active }` from a stored record.
 *
 * `active` is only honoured when it still names a restored session; otherwise
 * the newest session is selected, so a deleted entry cannot leave the panel
 * pointing at nothing.
 */
export function decodeSessions(raw, { now = Date.now(), ttlMs = PACKIFY_SESSIONS_TTL_MS } = {}) {
  const empty = { sessions: [], active: null }
  let stored
  try {
    stored = parse(raw, { keys: ['sessions', 'active'], now, ttlMs })
  } catch {
    return empty
  }
  if (!stored) return empty
  const sessions = sanitiseSessions(stored.sessions)
  if (!sessions.length) return empty
  const wanted = Number(stored.active)
  const active = sessions.some((s) => s.id === wanted) ? wanted : sessions[0].id
  return { sessions, active }
}

/** The content to show for a restored session, or null when there is none. */
export function contentFor(sessions, active) {
  const session = (sessions || []).find((s) => s.id === active)
  return session ? session.content : null
}
