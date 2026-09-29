// DEPRECATED (F11): legacy v2 backend API client. NOT imported by any v3 room
// (pages/internal, pages/customer, pages/admin, pages/public, foundation, or the
// v3 components). Retained only for the retired, unmounted top-level legacy pages
// (Hub/Ledger/TownCrier/etc.), which are scheduled for removal. Do not add new
// imports from v3 code; use `foundation/api.js` instead.
// Northstar OS — live backend API client
// All calls proxy through Vite to the FastAPI service on :8000.

const BASE = '/api'

async function req(path, opts = {}) {
  const { body, ...rest } = opts
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(rest.headers || {}) },
    body: body ? JSON.stringify(body) : undefined,
    ...rest
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const j = await res.json()
      if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  // --- Health / readiness ---
  health: () => fetch('/health').then((r) => r.json()),
  detailedHealth: () => fetch('/health/detailed').then((r) => r.json()),

  // --- Sourcescout / Prospector ---
  sourcescout: () => req('/sourcescout'),
  matches: () => req('/sourcescout/matches'),
  mismatches: () => req('/sourcescout/mismatches'),
  review: () => req('/sourcescout/review'),
  summary: () => req('/sourcescout/summary'),

  // --- Kirkland scanner (cache-first; live only when gate opened) ---
  scanner: () => req('/kirkland/scanner'),
  scan: (opts = {}) =>
    req('/kirkland/scan', {
      method: 'POST',
      body: {
        asins: opts.asins || [],
        min_profit: opts.minProfit ?? 5,
        min_velocity: opts.minVelocity ?? 3
      }
    }),
  live: () => req('/kirkland/live'),
  refresh: () => req('/kirkland/refresh', { method: 'POST' }),

  // --- Model / engine routing (AutothinK) ---
  models: () => req('/v1/models'),
  autothinkModels: () => req('/autothink/models'),
  autothinkRun: ({ query, provider = 'local', tier = 'T2', model } = {}) =>
    req('/autothink/run', { method: 'POST', body: { query, provider, tier, model } }),
  autothinkHistory: (limit = 20) => req(`/autothink/history?limit=${limit}`),

  // --- Catalog / warehouse ---
  stocked: () => req('/v1/catalog/stocked'),

  // --- Finance / credits ---
  credits: () => req('/v1/credits/me'),

  // --- Auth / plans ---
  me: () => req('/v1/auth/me'),
  plans: () => req('/v1/plans')
}

export default api