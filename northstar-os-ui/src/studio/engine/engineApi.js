// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — LOCAL MEDIA ENGINE CLIENT (ComfyUI)
//
// Same-origin, cookie-authenticated, CSRF double-submit — identical transport
// rules to the rest of the suite. This module talks ONLY to the local
// design-studio API; the backend renders through the operator's own ComfyUI.
// No provider keys, no external hosts, nothing paid.
// ═══════════════════════════════════════════════════════════════════════════

const BASE = '/api/design-studio'

function headers(method) {
  const h = { 'Content-Type': 'application/json' }
  try {
    // Local dev shim only (a built bundle has no ns-dev-session).
    const s = JSON.parse(localStorage.getItem('ns-dev-session') || 'null')
    if (s && s.userId) {
      h['X-User-Id'] = s.userId
      if (s.orgId) h['X-Org-Id'] = s.orgId
      if (s.role) h['X-Role'] = s.role
    }
  } catch { /* storage unavailable - hosted cookie auth is used */ }
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
    const msg = (d && (d.message || d.code)) || `HTTP ${res.status}`
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
  /** Render locally. body: {kind, purpose, brief, tier, width, height, seed} */
  generate: (body) => req('/generate', { method: 'POST', body: JSON.stringify(body) }),
}

export function assetFileUrl(asset) {
  if (!asset) return ''
  return asset.file_url || (asset.id ? `${BASE}/assets/${asset.id}/file` : '')
}
