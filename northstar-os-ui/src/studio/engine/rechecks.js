// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — RE-CHECK LOG CLIENT (tenant-scoped backend)
//
// Phase 5 item 2 moved the re-check log out of localStorage and into the
// tenant-scoped `ds_rechecks` store. This module:
//   • imports any existing LOCAL entries once, idempotently (the server enforces
//     it with a unique index on the legacy key), clearing the local copy only
//     after the server confirms;
//   • appends new entries to the backend;
//   • falls back to a clear UNKNOWN state when the backend cannot be reached,
//     never to a fabricated "no checks".
//
// A failed check is stored as a failure. Nothing here upgrades a verdict.
// ═══════════════════════════════════════════════════════════════════════════

const LOG_KEY = 'ns-ds-recheck-log'
const MIGRATED_KEY = 'ns-ds-rechecks-migrated-v1'

export function readLocalLog() {
  try {
    const raw = localStorage.getItem(LOG_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function writeLocalLog(entries) {
  try { localStorage.setItem(LOG_KEY, JSON.stringify(entries)) } catch { /* storage unavailable */ }
}

export function migrationDone() {
  try { return localStorage.getItem(MIGRATED_KEY) === '1' } catch { return false }
}

function markMigrated() {
  try { localStorage.setItem(MIGRATED_KEY, '1') } catch { /* ignore */ }
}

async function api(path, opts = {}) {
  const res = await fetch(`/api/design-studio${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const err = new Error(`http-${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

/**
 * Import local entries once. Clears the local copy ONLY when the server
 * confirms, and only for the entries it accepted.
 *
 * @returns {{ran:boolean, created?:number, skipped?:number, reason?:string}}
 */
export async function migrateLocalRechecks() {
  if (migrationDone()) return { ran: false, reason: 'already-migrated' }
  const local = readLocalLog()
  if (!local.length) { markMigrated(); return { ran: true, created: 0, skipped: 0 } }

  const entries = local.map((e, i) => ({
    assetId: e.assetId || null,
    checkedAt: e.checkedAt || null,
    user: e.user || 'operator',
    verdict: e.verdict || 'unknown',
    passed: !!e.passed,
    detail: e.detail || null,
    surface: e.surface || 'local',
    tagRequired: e.tagRequired === undefined ? null : !!e.tagRequired,
    // A stable key so a second import is a no-op.
    legacyKey: `local:${e.checkedAt || 'nodate'}:${e.assetId || 'noasset'}:${e.verdict}:${i}`,
  }))

  try {
    const data = await api('/rechecks/migrate', { method: 'POST', body: JSON.stringify({ entries }) })
    if (data.ok) {
      writeLocalLog([])
      markMigrated()
      return { ran: true, created: data.created, skipped: data.skipped }
    }
    return { ran: false, reason: 'server-reported-errors', errors: data.errors }
  } catch (e) {
    // Leave the local copy untouched: a failed import must not lose the record.
    return { ran: false, reason: String(e.message || e) }
  }
}

/** Append one entry to the backend. Returns the stored record or null. */
export async function appendRecheck(entry) {
  try {
    const data = await api('/rechecks', {
      method: 'POST',
      body: JSON.stringify({
        asset_id: entry.assetId || null,
        verdict: entry.verdict || 'unknown',
        passed: !!entry.passed,
        detail: entry.detail || null,
        surface: entry.surface || 'upload-check',
        tag_required: entry.tagRequired === undefined ? null : !!entry.tagRequired,
        checked_by: entry.user || 'operator',
        checked_at: entry.checkedAt || null,
      }),
    })
    return data.recheck || null
  } catch {
    // Keep the entry locally so nothing is lost, and say so by returning null.
    const local = readLocalLog()
    local.unshift(entry)
    writeLocalLog(local.slice(0, 200))
    return null
  }
}

/**
 * Read the log. `state` is 'ready' | 'error' | 'loading'. On error the caller
 * shows UNKNOWN, never an empty list presented as "no checks".
 */
export async function fetchRechecks(assetId) {
  try {
    const q = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''
    const data = await api(`/rechecks${q}`)
    return { state: 'ready', entries: data.rechecks || [], counts: data.counts || null }
  } catch (e) {
    const local = readLocalLog()
    return {
      state: local.length ? 'ready' : 'error',
      entries: local,
      counts: null,
      reason: String(e.message || e),
      // State this plainly: an unreachable backend is UNKNOWN, not zero.
      note: 'Backend unreachable; showing the local mirror. This is not a complete record.',
    }
  }
}
