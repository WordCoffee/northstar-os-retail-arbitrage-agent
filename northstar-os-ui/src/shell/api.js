// ═══════════════════════════════════════════════════════════════════════════
// SHELL CLIENT (V3) — /api/shell/context + /api/shell/hardware.
//
// Same transport rules as the rest of the suite: same-origin, cookie auth,
// CSRF double-submit, dev identity shim gated on the compile-time LOCAL_DEV
// constant (a built bundle cannot carry it).
// ═══════════════════════════════════════════════════════════════════════════

import { LOCAL_DEV } from '../foundation/dev.js'

function headers(method) {
  const h = { 'Content-Type': 'application/json' }
  if (LOCAL_DEV) {
    try {
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
  const res = await fetch(path, {
    credentials: 'include',
    ...opts,
    headers: { ...headers(opts.method), ...(opts.headers || {}) },
  })
  let body = {}
  try { body = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const d = body && body.detail
    let msg = null
    if (typeof d === 'string' && d) msg = d
    else if (d && typeof d === 'object' && (d.message || d.code)) msg = d.message || d.code
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return body
}

export const shellApi = {
  context: () => req('/api/shell/context'),
  hardware: () => req('/api/shell/hardware'),
}
