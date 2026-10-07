// v3 read-only client for NON-foundation local signal endpoints.
//
// The legacy `src/services/api.js` is DEPRECATED (unmounted v2 legacy pages);
// do not import it from v3 code. Foundation routes have their own client
// (`foundation/api.js`). This module covers the public/local app endpoints that
// back the operational rooms: system status, SourceScout catalog + summary,
// monitoring error-alerts, and Golden Goose health.
//
// Every helper resolves with parsed JSON, or throws an Error carrying
// { status, code } so callers can render honest loading / unavailable / empty /
// auth-blocked states. Nothing here fabricates data.

function fail(res, detail) {
  const err = new Error((detail && detail.message) || (detail && detail.code) || `http_${res.status}`)
  err.status = res.status
  err.code = detail && detail.code
  return err
}

// Read-only POST (semantic reads like search — no mutation is implied).
async function postJson(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body || {}),
  })
  if (!res.ok) {
    let detail = { code: `http_${res.status}` }
    try { const j = await res.json(); detail = j.detail || j.error || detail } catch { /* non-JSON */ }
    throw fail(res, detail)
  }
  return res.json()
}

async function get(path) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    let detail = { code: `http_${res.status}` }
    try {
      const j = await res.json()
      detail = j.detail || j.error || detail
    } catch { /* non-JSON body */ }
    const err = new Error((detail && detail.message) || (detail && detail.code) || `http_${res.status}`)
    err.status = res.status
    err.code = detail && detail.code
    throw err
  }
  return res.json()
}

export const signals = {
  systemStatus: () => get('/api/v1/status'),
  health: () => get('/health'),
  detailedHealth: () => get('/health/detailed'),
  sourceScout: () => get('/api/sourcescout'),
  sourceScoutSummary: () => get('/api/sourcescout/summary'),
  sourceScoutMatches: () => get('/api/sourcescout/matches'),
  sourceScoutMismatches: () => get('/api/sourcescout/mismatches'),
  sourceScoutReview: () => get('/api/sourcescout/review'),
  monitoringAlerts: () => get('/api/monitoring/error-alerts'),
  goldenGooseHealth: () => get('/api/golden-goose/health'),
  // Public, no-secrets invite validation (single invite by code).
  inviteLookup: (code) => get(`/api/v1/invites/${encodeURIComponent(code)}`),
  // AutothinK / Brain engine reads (presence-only; no credential values).
  autothinkModels: () => get('/api/autothink/models'),
  autothinkHistory: (limit = 20) => get(`/api/autothink/history?limit=${limit}`),
  brainModels: () => get('/api/v1/models'),
  // Memory Bank / Learning (local, read-only; search is a semantic read).
  memorySearch: (intent, opts = {}) => postJson('/api/v1/memory/search', {
    intent: intent || '',
    account_id: opts.accountId || 'default',
    entry_type: opts.entryType || null,
    limit: opts.limit || 10,
  }),
  learningPlaybooks: (accountId = 'default') => get(`/api/v1/learning/playbooks?account_id=${encodeURIComponent(accountId)}`),
  // Non-creative read-only projections over local SQLite data.
  ncCommerceOpsQueue: (limit = 200) => get(`/api/v1/noncreative/commerce-ops/queue?limit=${limit}`),
  ncListingsHealth: (limit = 200) => get(`/api/v1/noncreative/listings/health?limit=${limit}`),
  ncCompetitorObservations: (limit = 200) => get(`/api/v1/noncreative/competitor/observations?limit=${limit}`),
  ncActivity: (limit = 50) => get(`/api/v1/noncreative/activity?limit=${limit}`),
  ncKeywords: (limit = 200) => get(`/api/v1/noncreative/keywords?limit=${limit}`),
  ncSources: (limit = 100) => get(`/api/v1/noncreative/sources?limit=${limit}`),
  ncSessions: (limit = 100) => get(`/api/v1/noncreative/sessions?limit=${limit}`),
  ncAccounts: (limit = 100) => get(`/api/v1/noncreative/accounts?limit=${limit}`),
}

// Never-rejecting wrapper. Returns { ok, value } or { ok:false, error } so a
// component can render an honest state instead of crashing on a failed read.
export async function settle(promise) {
  try {
    return { ok: true, value: await promise }
  } catch (e) {
    return { ok: false, error: e }
  }
}

export default signals