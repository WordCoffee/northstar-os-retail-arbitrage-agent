// ═══════════════════════════════════════════════════════════════════════════
// CHAT CORE CLIENT (S1) — sessions + the SSE turn stream.
//
// Same transport rules as the rest of the suite: same-origin, cookie auth,
// CSRF double-submit, and a dev identity shim gated on the compile-time
// LOCAL_DEV constant (a built bundle cannot carry it).
//
// The turn stream is read with fetch() + ReadableStream (NOT EventSource):
// the request carries a body, and this sidesteps the 6-connection cap.
// ═══════════════════════════════════════════════════════════════════════════

import { LOCAL_DEV } from '../foundation/dev.js'

const BASE = '/api/chat'

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
  const res = await fetch(BASE + path, {
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
    else if (Array.isArray(d) && d.length && d[0] && d[0].msg) msg = d[0].msg
    else if (d && typeof d === 'object' && (d.message || d.code)) msg = d.message || d.code
    throw new Error(msg || `HTTP ${res.status}`)
  }
  return body
}

export const chatApi = {
  health: () => req('/health'),
  sessions: (limit = 50) => req(`/sessions?limit=${limit}`),
  createSession: (body = {}) => req('/sessions', { method: 'POST', body: JSON.stringify(body) }),
  patchSession: (sid, body) => req(`/sessions/${sid}`, { method: 'PATCH', body: JSON.stringify(body) }),
  messages: (sid, limit = 500) => req(`/sessions/${sid}/messages?limit=${limit}`),
  cancelTurn: (turnId) => req(`/turns/${turnId}/cancel`, { method: 'POST', body: '{}' }),
}

/** Parse one SSE frame ("event: X\ndata: {...}") into {event, data} | null. */
export function parseFrame(frame) {
  const lines = String(frame || '').split('\n')
  let event = null
  let data = ''
  for (const ln of lines) {
    if (ln.startsWith('event: ')) event = ln.slice(7).trim()
    else if (ln.startsWith('data: ')) data += ln.slice(6)
  }
  if (!event) return null
  let parsed = {}
  try { parsed = JSON.parse(data || '{}') } catch { parsed = {} }
  return { event, data: parsed }
}

/** Same-origin file URL for a persisted studio asset (image, dieline, PDF). */
export function assetFileUrl(assetId) {
  return `/api/design-studio/assets/${assetId}/file`
}

/** Voice lane (S3): local whisper.cpp transcription. */
export const chatVoice = {
  status: () => req('/voice/status'),
  transcribe: async (blob) => {
    const fd = new FormData()
    fd.append('audio', blob, 'recording.webm')
    const h = headers('POST')
    delete h['Content-Type'] // multipart: the browser sets the boundary
    const res = await fetch(`${BASE}/voice/transcribe`, {
      method: 'POST', credentials: 'include', headers: h, body: fd,
    })
    let body = {}
    try { body = await res.json() } catch { /* empty body */ }
    if (!res.ok) {
      const d = body && body.detail
      throw new Error(typeof d === 'string' && d ? d : `HTTP ${res.status}`)
    }
    return body
  },
}

/**
 * Stream one turn. Calls onEvent({event, data}) per SSE frame.
 * Resolves when the stream ends; rejects on transport/HTTP errors only.
 */
export async function streamTurn(sessionId, body, onEvent, signal) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/turns`, {
    method: 'POST',
    credentials: 'include',
    headers: headers('POST'),
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    let detail = null
    try { const b = await res.json(); detail = b && b.detail } catch { /* no body */ }
    throw new Error(typeof detail === 'string' && detail ? detail : `HTTP ${res.status}`)
  }
  if (!res.body) throw new Error('streaming unsupported in this browser')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const ev = parseFrame(frame)
      if (ev) onEvent(ev)
    }
  }
  const tail = parseFrame(buffer)
  if (tail) onEvent(tail)
}
