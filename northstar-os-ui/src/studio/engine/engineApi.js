// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — LOCAL MEDIA ENGINE CLIENT (ComfyUI)
//
// Same-origin, cookie-authenticated, CSRF double-submit — identical transport
// rules to the rest of the suite. This module talks ONLY to the local
// design-studio API; the backend renders through the operator's own ComfyUI.
// No provider keys, no external hosts, nothing paid.
// ═══════════════════════════════════════════════════════════════════════════

const BASE = '/api/design-studio'

// 2026-10-16: the dev identity shim is gated on the COMPILE-TIME LOCAL_DEV
// constant (same rule as foundation/api.js), so a built bundle cannot carry the
// X-User-Id emitter — check-prod-bundle.cjs enforces the contract.
import { LOCAL_DEV } from '../../foundation/dev.js'

function headers(method) {
  const h = { 'Content-Type': 'application/json' }
  if (LOCAL_DEV) {
    try {
      // Local dev shim only (a built bundle has no ns-dev-session).
      const s = JSON.parse(localStorage.getItem('ns-dev-session') || 'null')
      if (s && s.userId) {
        h['X-User-Id'] = s.userId
        if (s.orgId) h['X-Org-Id'] = s.orgId
        if (s.role) h['X-Role'] = s.role
      }
    } catch { /* storage unavailable - hosted cookie auth is used */ }
  }
  const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes((method || 'GET').toUpperCase())
  if (unsafe) {
    const m = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
    if (m) h['X-CSRF-Token'] = decodeURIComponent(m[2])
  }
  return h
}

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    credentials: 'include',
    ...opts,
    headers: { ...headers(opts.method), ...(opts.headers || {}) },
  })
  let body = {}
  try { body = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const d = body && body.detail
    // Readable reason for every FastAPI detail shape (string / pydantic list /
    // object) - never a bare "HTTP 422" when the server explained itself.
    let msg = null
    if (typeof d === 'string' && d) msg = d
    else if (Array.isArray(d) && d.length && d[0] && d[0].msg) {
      const loc = Array.isArray(d[0].loc) ? d[0].loc.slice(-1)[0] : ''
      msg = loc ? `${loc}: ${d[0].msg}` : d[0].msg
    } else if (d && typeof d === 'object' && (d.message || d.code)) msg = d.message || d.code
    if (!msg) msg = `HTTP ${res.status}`
    const err = new Error(msg)
    err.status = res.status
    err.detail = d
    throw err
  }
  return body
}

export const engineApi = {
  /** Honest engine state: armed only when MEDIA_GEN_LIVE=1 AND ComfyUI answers. */
  status: () => req('/engine'),
  /** Render locally (sync). body: {kind, purpose, brief, tier, width, height, seed, text_safe} */
  generate: (body) => req('/generate', { method: 'POST', body: JSON.stringify(body) }),
  /** Queue a render on the async lane (tunnel-safe: 202 + poll job status). */
  generateAsync: (body) => req('/generate-async', { method: 'POST', body: JSON.stringify(body) }),
  /** Poll an async generation job. */
  job: (id) => req(`/generate-async/${id}`),
  /** Fetch one asset row (metadata carries text_fidelity for guarded renders). */
  asset: (id) => req(`/assets/${id}`),
  /** Typography pass: compose mockup templates + presets, then compose. */
  composeTemplates: () => req('/compose/templates'),
  composePresets: () => req('/compose/presets'),
  compose: (body) => req('/compose/mockup', { method: 'POST', body: JSON.stringify(body) }),
}

export function assetFileUrl(asset) {
  if (!asset) return ''
  return asset.file_url || (asset.id ? `${BASE}/assets/${asset.id}/file` : '')
}
