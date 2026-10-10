// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — LOCALSTORAGE → BACKEND MIGRATION
//
// The Design Studio and the two merged rooms kept their records in the browser
// before the `ds_projects` / `ds_assets` / `ds_jobs` store existed. This module
// imports them ONCE per browser+account, idempotently (the server skips a record
// whose legacyKey it already holds), and never deletes the local copy until the
// server confirms the import.
//
// Rules:
//   • Nothing is sent unless the operator's session is authenticated.
//   • A failed import leaves localStorage untouched and reports why.
//   • Keys not in LOCAL_KEYS are ignored — this is not a general export tool.
//   • No record is invented; a malformed entry is reported, not repaired.
// ═══════════════════════════════════════════════════════════════════════════

const DONE_FLAG = 'ns-ds-migrated-v1'

// The exact localStorage keys the pre-backend rooms wrote, and how each maps.
// `room` is provenance only — it is stored in metadata, never used to guess.
export const LOCAL_KEYS = [
  // Creative Studio / Design Studio project board
  { key: 'ns-creative-briefs', store: 'projects', room: 'creative-studio', section: 'projects', kind: 'brief' },
  { key: 'ns-creative-variants', store: 'projects', room: 'creative-studio', section: 'projects', kind: 'variant' },
  { key: 'ns-creative-bundles', store: 'assets', room: 'creative-studio', kind: 'bundle' },
  { key: 'ds-docs', store: 'assets', room: 'design-studio', kind: 'document' },
  { key: 'ds-export-log', store: 'jobs', room: 'design-studio', kind: 'export' },
  { key: 'ds-kits', store: 'assets', room: 'design-studio', kind: 'brand-kit' },
  // Product Designer
  { key: 'pd-requests', store: 'jobs', room: 'product-designer', kind: 'request' },
  { key: 'pd-exports', store: 'jobs', room: 'product-designer', kind: 'export' },
  { key: 'pd-renders', store: 'assets', room: 'product-designer', kind: 'render' },
]

export function migrationDone() {
  try { return localStorage.getItem(DONE_FLAG) === '1' } catch { return false }
}

export function markMigrationDone() {
  try { localStorage.setItem(DONE_FLAG, '1') } catch { /* storage unavailable */ }
}

/** Read the known local keys. Returns the raw material and what was found. */
export function collectLocalRecords() {
  const found = []
  const raw = {}
  for (const spec of LOCAL_KEYS) {
    let value = null
    try {
      const s = localStorage.getItem(spec.key)
      if (!s) continue
      value = JSON.parse(s)
    } catch {
      found.push({ ...spec, count: 0, malformed: true })
      continue
    }
    if (!Array.isArray(value)) value = value && typeof value === 'object' ? [value] : []
    if (value.length === 0) continue
    raw[spec.key] = value
    found.push({ ...spec, count: value.length, malformed: false })
  }
  return { raw, found }
}

/** Build the migrate payload from the collected local records. */
export function buildMigratePayload(raw) {
  const payload = { projects: [], assets: [], jobs: [] }
  // A key whose items cannot be represented is NOT importable. Its records are
  // never sent, so its local copy must never be cleared — losing it silently
  // would be data loss dressed up as a successful migration.
  const unimportable = {}
  for (const spec of LOCAL_KEYS) {
    const items = raw[spec.key] || []
    let skipped = 0
    for (const it of items) {
      if (!it || typeof it !== 'object' || Array.isArray(it)) { skipped++; continue }
      const id = it.id || it.asin || it.name || String(Math.random())
      const legacyKey = `${spec.key}:${id}`
      const meta = {
        legacyKey,
        legacyRoom: spec.room,
        legacyKind: spec.kind,
        legacySource: spec.key,
      }
      const base = {
        name: it.name || it.title || it.campaign_name || `${spec.kind} ${String(id).slice(0, 12)}`,
        metadata: meta,
      }
      // Carry the WHOLE legacy record through, minus its id. The client used to
      // map only a handful of named fields, so everything else (objective,
      // formats, deliverables, purpose, tier...) was dropped here and never
      // reached the server's legacyFields preservation at all.
      const legacy = { ...it }
      delete legacy.id
      if (spec.store === 'projects') {
        payload.projects.push({
          ...legacy,
          ...base,
          section: spec.section || 'projects',
          asin: it.asin || null,
          brand: it.brand || null,
          brief: it.note || it.objective || null,
          state: it.state || it.status || 'draft',
        })
      } else if (spec.store === 'assets') {
        payload.assets.push({
          ...legacy,
          ...base,
          asset_type: spec.kind,
          mime_type: it.mime || it.mimeType || null,
          storage_key: it.path || it.storageKey || null,
          data_url: typeof it.dataUrl === 'string' && it.dataUrl.length < 1000000 ? it.dataUrl : null,
        })
      } else {
        payload.jobs.push({
          ...legacy,
          ...base,
          job_type: spec.kind,
          provider: 'local',
          status: it.status || 'complete',
          params: { legacy: true, room: spec.room },
        })
      }
    }
    if (skipped > 0) unimportable[spec.key] = { skipped, total: items.length }
  }
  return { payload, unimportable }
}

/**
 * Run the migration once. Returns a report; never throws.
 * @param {object} [opts]
 * @param {boolean} [opts.force]  re-run even if the done flag is set
 */
export async function migrateLocalStorage(opts = {}) {
  if (!opts.force && migrationDone()) {
    return { ran: false, reason: 'already-migrated' }
  }
  const { raw, found } = collectLocalRecords()
  const malformed = found.filter(f => f.malformed).map(f => f.key)
  const total = found.reduce((s, f) => s + f.count, 0)
  if (total === 0) {
    markMigrationDone()
    return { ran: true, created: { projects: 0, assets: 0, jobs: 0 }, found, note: 'nothing local to migrate' }
  }
  const { payload, unimportable } = buildMigratePayload(raw)
  const importable = payload.projects.length + payload.assets.length + payload.jobs.length
  const blockedKeys = Object.keys(unimportable)
  if (importable === 0) {
    // Nothing could be represented. Say so and keep every local copy.
    return { ran: false, reason: 'nothing-importable', found, unimportable }
  }
  try {
    const res = await fetch('/api/design-studio/migrate', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      // Leave localStorage untouched: a failed import must not lose work.
      return { ran: false, reason: `http-${res.status}`, found }
    }
    const data = await res.json()
    // Clear a local copy ONLY when every record in it was representable, the
    // server reported no errors, AND the server confirmed the import. A key
    // holding a record we could not represent, or a malformed JSON blob, is
    // LEFT IN PLACE and reported rather than silently discarded.
    if (data.ok) {
      for (const spec of LOCAL_KEYS) {
        if (!raw[spec.key]) continue
        if (blockedKeys.includes(spec.key) || malformed.includes(spec.key)) continue
        try { localStorage.removeItem(spec.key) } catch { /* ignore */ }
      }
      const kept = [...blockedKeys, ...malformed]
      if (kept.length === 0) markMigrationDone()
      return { ran: true, ...data, found, kept, unimportable }
    }
    return { ran: true, ...data, found, kept: [...blockedKeys, ...malformed], unimportable }
  } catch (e) {
    return { ran: false, reason: String(e.message || e), found }
  }
}
