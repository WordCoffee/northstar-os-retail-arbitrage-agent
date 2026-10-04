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
  sourceScout: () => get('/api/sourcescout'),
  sourceScoutSummary: () => get('/api/sourcescout/summary'),
  sourceScoutMatches: () => get('/api/sourcescout/matches'),
  sourceScoutMismatches: () => get('/api/sourcescout/mismatches'),
  sourceScoutReview: () => get('/api/sourcescout/review'),
  monitoringAlerts: () => get('/api/monitoring/error-alerts'),
  goldenGooseHealth: () => get('/api/golden-goose/health'),
  // Public, no-secrets invite validation (single invite by code).
  inviteLookup: (code) => get(`/api/v1/invites/${encodeURIComponent(code)}`),
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