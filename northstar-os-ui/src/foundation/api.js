// Foundation API client — /api/v1/foundation/*
// Hosted authentication uses an HttpOnly session cookie (set by /auth/login),
// sent automatically same-origin. NO access token is stored in localStorage for
// hosted use. The local-development identity shim (X-User-Id headers) is used
// ONLY when LOCAL_DEV is explicitly enabled (see foundation/dev.js).

import { LOCAL_DEV } from './dev.js'

const BASE = '/api/v1/foundation'
const TOKEN_KEY = 'ns-access-token'

// DEPRECATED: retained only for backwards-compatible imports; hosted auth no
// longer reads or writes a localStorage access token.
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable */ }
}

export function getDevSession() {
  try {
    const raw = localStorage.getItem('ns-dev-session')
    if (!raw) return { userId: '', orgId: '', role: '', env: 'production', previewId: '' }
    return JSON.parse(raw)
  } catch {
    return { userId: '', orgId: '', role: '', env: 'production', previewId: '' }
  }
}

export function setDevSession(patch) {
  const next = { ...getDevSession(), ...patch }
  localStorage.setItem('ns-dev-session', JSON.stringify(next))
  return next
}

function readCookie(name) {
  try {
    const m = document.cookie.match(new RegExp('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)'))
    return m ? decodeURIComponent(m[2]) : ''
  } catch { return '' }
}

function headers(method, extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (LOCAL_DEV) {
    const s = getDevSession()
    if (s.userId) h['X-User-Id'] = s.userId
    if (s.orgId) h['X-Org-Id'] = s.orgId
    if (s.role) h['X-Role'] = s.role
    if (s.env) h['X-Env'] = s.env
    if (s.previewId) h['X-Preview-Id'] = s.previewId
  }
  // CSRF double-submit for cookie-auth state-changing requests.
  const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes((method || 'GET').toUpperCase())
  const csrf = readCookie('ns_csrf')
  if (unsafe && csrf) h['X-CSRF-Token'] = csrf
  return h
}

async function req(path, opts = {}) {
  const method = opts.method || 'GET'
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: headers(method, opts.headers),
    ...opts,
  })
  if (!res.ok) {
    let detail = { code: `http_${res.status}`, message: res.statusText }
    try {
      const j = await res.json()
      detail = j.detail || detail
    } catch { /* ignore */ }
    const err = new Error(detail.message || detail.code)
    err.code = detail.code
    err.status = res.status
    err.detail = detail
    throw err
  }
  return res.json()
}

export const foundationApi = {
  me: () => req('/me'),  roles: () => req('/roles'),
  environment: () => req('/environment'),
  // Golden Goose (P5-T4) — org-scoped persisted routes
  goldenGooseQueue: () => req('/golden-goose/queue'),
  goldenGooseItem: (id) => req(`/golden-goose/${id}`),
  goldenGooseDecision: (id, body) => req(`/golden-goose/${id}/decision`, { method: 'POST', body: JSON.stringify(body || {}) }),
  goldenGooseEvaluate: (body) => req('/golden-goose/evaluate', { method: 'POST', body: JSON.stringify(body || {}) }),
  organizations: () => req('/organizations'),
  marketplaces: () => req('/marketplaces'),
  products: (limit = 50, offset = 0) => req(`/products?limit=${limit}&offset=${offset}`),
  product: (id) => req(`/products/${id}`),
  identitySubmit: (body) => req('/identity/submit', { method: 'POST', body: JSON.stringify(body) }),
  identityCandidates: () => req('/identity/candidates'),
  identityConflicts: () => req('/identity/conflicts'),
  observations: (productId, type) =>
    req(`/products/${productId}/observations${type ? `?observation_type=${type}` : ''}`),
  addObservation: (body) => req('/observations', { method: 'POST', body: JSON.stringify(body) }),
  providers: () => req('/providers'),
  provider: (key) => req(`/providers/${key}`),
  jobs: () => req('/jobs') /* list not exposed; create below */,
  createJob: (body) => req('/jobs', { method: 'POST', body: JSON.stringify(body) }),
  job: (id) => req(`/jobs/${id}`),
  run: (runId) => req(`/jobs/runs/${runId}`),
  cancelRun: (runId) => req(`/jobs/runs/${runId}/cancel`, { method: 'POST' }),
  usageSummary: () => req('/usage/summary'),
  usageEvents: (limit = 50) => req(`/usage/events?limit=${limit}`),
  approvals: () => req('/approvals'),
  createApproval: (body) => req('/approvals', { method: 'POST', body: JSON.stringify(body) }),
  decideApproval: (id, body) => req(`/approvals/${id}/decide`, { method: 'POST', body: JSON.stringify(body) }),
  cancelApproval: (id) => req(`/approvals/${id}/cancel`, { method: 'POST' }),
  audit: (limit = 100) => req(`/audit?limit=${limit}`),
  getPref: (key) => req(`/ui/preferences/${key}`),
  setPref: (key, value) => req(`/ui/preferences/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  previewStart: (body) => req('/preview/start', { method: 'POST', body: JSON.stringify(body) }),
  previewEnd: (previewId) => req(`/preview/end?preview_id=${previewId}`, { method: 'POST' }),
  previewActive: () => req('/preview/active'),

  // canonical economics (backend is authoritative; frontend consumes only)
  economicsContract: () => req('/economics/contract'),
  economicsCompute: (input) => req('/economics/compute', { method: 'POST', body: JSON.stringify({ input }) }),

  // public UI-mode signal (works before auth; local stack = private_beta)
  uiMode: () => req('/ui-mode'),

  // creative media readiness (read-only, provider-neutral; does NOT generate)
  mediaReadiness: () => req('/creative/readiness'),

  // creative LOCAL generation (armed only: MEDIA_GEN_LIVE=1 + loopback engine).
  // Resolves { ok, image (data URL), seconds, width, height, steps, seed,
  // prompt_id, bytes, mime, engine }. Refusals throw with err.code =
  // media_gate_off | engine_unreachable | timeout | engine_rejected | ...
  generateImage: (body) => req('/creative/generate', { method: 'POST', body: JSON.stringify(body || {}) }),

  // auth session (P2-T5b): cookie transport, no token returned to JS
  login: (email, password) => req('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => req('/auth/logout', { method: 'POST' }),

  // durable jobs & scheduler (1C-04)
  durableJobs: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return req(`/jobs-durable${q ? `?${q}` : ''}`)
  },
  durableJob: (id) => req(`/jobs-durable/${id}`),
  durableJobAudit: (id) => req(`/jobs-durable/${id}/audit`),
  durableRun: (runId) => req(`/jobs-durable/runs/${runId}`),
  queuePosture: () => req('/jobs-durable/queue-posture'),
  handlerRegistry: () => req('/jobs-durable/handler-registry'),
  createDurableJob: (body) => req('/jobs-durable', { method: 'POST', body: JSON.stringify(body) }),
  cancelDurableJob: (id, reason) => req(`/jobs-durable/${id}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) }),
  retryDurableJob: (id, reason) => req(`/jobs-durable/${id}/retry`, { method: 'POST', body: JSON.stringify({ reason }) }),
  schedules: (includeArchived = false) => req(`/schedules?include_archived=${includeArchived}`),
  schedule: (id) => req(`/schedules/${id}`),
  createSchedule: (body) => req('/schedules', { method: 'POST', body: JSON.stringify(body) }),
  scheduleEnable: (id) => req(`/schedules/${id}/enable`, { method: 'POST' }),
  scheduleDisable: (id) => req(`/schedules/${id}/disable`, { method: 'POST' }),
  scheduleArchive: (id) => req(`/schedules/${id}/archive`, { method: 'POST' }),
  schedulePosture: () => req('/schedules/posture'),

  // keyword & SEO intelligence (1C-05)
  keywordSearch: (q, limit = 50) => req(`/keywords/search?q=${encodeURIComponent(q || '')}&limit=${limit}`),
  keyword: (id) => req(`/keywords/${id}`),
  keywordCoverage: (id) => req(`/keywords/coverage/${id}`),
  keywordGaps: () => req('/keywords/gaps'),
  searchTerms: (limit = 200) => req(`/keywords/search-terms?limit=${limit}`),
  targetPerformance: () => req('/keywords/targets/performance'),
  keywordSources: () => req('/keywords/sources'),
  imports: () => req('/keywords/imports'),
  importStatus: (id) => req(`/keywords/imports/${id}`),
  importRejected: (id) => req(`/keywords/imports/${id}/rejected`),
  importDryRun: (file_name) => req('/keywords/imports/dry-run', { method: 'POST', body: JSON.stringify({ file_name }) }),
  importSubmit: (file_name, idempotency_key) => req('/keywords/imports', { method: 'POST', body: JSON.stringify({ file_name, idempotency_key }) }),
  rankHistory: (id) => req(`/keywords/rank-history/${id}`),
  keywordConflicts: () => req('/keywords/conflicts'),
  keywordProvenance: (id) => req(`/keywords/provenance/${id}`),

  // raw authenticated request (internal pages)
  rawReq: (path, opts = {}) => req(path, opts),

  // private-beta operations (1C UI sprint) — tester/owner surfaces
  planUsage: () => req('/plan-usage'),
  entitlements: () => req('/entitlements'),
  onboardingPack: () => req('/onboarding-pack'),
  onboardingStatus: () => req('/onboarding'),
  onboardingComplete: (step) => req('/onboarding/complete', { method: 'POST', body: JSON.stringify({ step }) }),
  supportTickets: () => req('/support/tickets'),
  supportSubmit: (body) => req('/support/tickets', { method: 'POST', body: JSON.stringify(body) }),
  supportTicket: (id) => req(`/support/tickets/${id}`),
  legalDocuments: () => req('/legal/documents'),
  legalAcceptanceStatus: () => req('/legal/acceptance/status'),
  legalAccept: (body) => req('/legal/acceptance', { method: 'POST', body: JSON.stringify(body) }),
  signup: (body) => req('/signup', { method: 'POST', body: JSON.stringify(body) }),

  // internal platform-admin surfaces
  adminDashboard: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return req(`/admin/dashboard${q ? `?${q}` : ''}`)
  },
  adminOrg: (orgId) => req(`/admin/dashboard/${orgId}`),
  adminOrgAction: (orgId, action, body = {}) =>
    req(`/admin/orgs/${orgId}/${action}`, { method: 'POST', body: JSON.stringify(body) }),
  adminOrgNote: (orgId, note) =>
    req(`/admin/orgs/${orgId}/notes`, { method: 'POST', body: JSON.stringify({ note }) }),
  adminOrgOverride: (orgId, body) =>
    req(`/admin/orgs/${orgId}/override`, { method: 'POST', body: JSON.stringify(body) }),
  adminExportUrl: '/api/v1/foundation/admin/dashboard/export',

  // invite issuance (platform-admin / owner) — the code is shown in the UI only
  invite: (body) => req('/invites', { method: 'POST', body: JSON.stringify(body) }),
}

export default foundationApi