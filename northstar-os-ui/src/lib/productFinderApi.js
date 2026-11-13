// SourceScout transport: the ONE place /api/products/finder is called.
//
// Before 2026-11-09 ProductFinder.jsx named this endpoint only in comments and
// staged UNKNOWN rows in local state, so "it works" was never true. The page
// now asks the backend, maps the real cached candidate into a row, and labels
// a missing ASIN as absent instead of inventing metrics.
//
// Same transport rules as the rest of the suite: same-origin, cookie auth, dev
// identity shim gated on the compile-time LOCAL_DEV constant.

import { LOCAL_DEV } from '../foundation/dev.js'

export const FINDER_ENDPOINT = '/api/products/finder'

function headers() {
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
  return h
}

async function readError(res) {
  let code = `http_${res.status}`
  let message = res.statusText || 'request refused'
  try {
    const j = await res.json()
    const detail = j && (j.detail || j.error)
    if (detail && typeof detail === 'object') {
      code = detail.code || code
      message = detail.message || message
    } else if (detail) {
      message = String(detail)
    } else if (j && j.message) {
      message = String(j.message)
    }
  } catch { /* non-JSON refusal */ }
  return { code, message, status: res.status }
}

//: Ask the real endpoint for scored cached candidates. Throws an Error with
//: `.code` and `.status` when the backend refuses, so the page can render the
//: refusal instead of pretending a lookup succeeded.
export async function fetchFinderCandidates({ signal } = {}) {
  const res = await fetch(`${FINDER_ENDPOINT}?limit=100`, {
    credentials: 'include',
    headers: headers(),
    signal,
  })
  if (!res.ok) {
    const { code, message, status } = await readError(res)
    const err = new Error(message)
    err.code = code
    err.status = status
    throw err
  }
  const payload = await res.json()
  // /api/products/finder answers under the bff/v1 envelope; accept both shapes
  // so a future un-enveloped response does not silently render an empty table.
  const data = payload && payload.contract === 'bff/v1' ? payload.data : payload
  return {
    evaluated: Array.isArray(data && data.evaluated) ? data.evaluated : [],
    passed: Array.isArray(data && data.passed) ? data.passed : [],
    candidateCount: Number(data && data.candidate_count) || 0,
    filterSource: (data && data.filter_source) || 'unknown',
    thresholds: (data && data.thresholds) || {},
  }
}

function numberOrUnknown(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 'UNKNOWN'
}

//: Map a finder candidate into the row shape the workbench renders. Every
//: field the candidate does not carry stays UNKNOWN - the page must not draw a
//: number the backend did not observe.
export function candidateToRow(candidate, asin) {
  const c = candidate || {}
  const passed = c.universal_filter_passed === true
  return {
    asin: String(c.asin || asin || 'UNKNOWN'),
    title: c.name || 'UNKNOWN',
    brand: c.brand || 'UNKNOWN',
    category: 'UNKNOWN',
    price: numberOrUnknown(c.amazon_price),
    rank: 'UNKNOWN',
    offers: numberOrUnknown(c.fba_sellers),
    buybox: 'UNVERIFIED',
    margin: numberOrUnknown(c.roi_pct),
    monthlySales: numberOrUnknown(c.monthly_sales_estimate),
    rating: numberOrUnknown(c.rating),
    reviews: numberOrUnknown(c.reviews_count),
    reasons: Array.isArray(c.universal_filter_reasons) ? c.universal_filter_reasons : [],
    status: passed ? 'Passed filter' : 'Rejected',
    cached: true,
  }
}

//: The ASIN the operator asked about, or null when the cache has no observation
//: for it. Matching is exact on the normalised ASIN; no fuzzy substitution.
export function findCandidate(payload, asin) {
  if (!payload || !Array.isArray(payload.evaluated)) return null
  const wanted = String(asin || '').trim().toUpperCase()
  if (!wanted) return null
  return payload.evaluated.find(c => String(c && c.asin || '').toUpperCase() === wanted) || null
}

// ── The research log (G1) ──────────────────────────────────────────────────
// A lookup used to live in React state, so a reload started the work over. These two calls make
// the research persist: what the seller looked at, what the cache actually returned, and when.
// The row is copied, never recomputed — "no cached observation" is stored as the fact it is.
export async function saveResearch(body) {
  const res = await fetch('/api/products/research', {
    method: 'POST',
    credentials: 'include',
    headers: headers(),
    body: JSON.stringify(body || {}),
  })
  if (!res.ok) {
    const { code, message, status } = await readError(res)
    const err = new Error(message)
    err.code = code
    err.status = status
    throw err
  }
  const payload = await res.json()
  // The API answers under the bff/v1 envelope; accept both shapes so a future un-enveloped
  // response does not silently store nothing.
  return payload && payload.contract === 'bff/v1' ? payload.data : payload
}

export async function listResearch() {
  const res = await fetch('/api/products/research', { credentials: 'include', headers: headers() })
  if (!res.ok) {
    const { code, message, status } = await readError(res)
    const err = new Error(message)
    err.code = code
    err.status = status
    throw err
  }
  const payload = await res.json()
  const data = payload && payload.contract === 'bff/v1' ? payload.data : payload
  return Array.isArray(data && data.items) ? data.items : []
}
