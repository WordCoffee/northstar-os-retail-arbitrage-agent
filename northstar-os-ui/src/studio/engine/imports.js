// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — IMPORTED-REPORT CLIENT (Phase 6 items 4-6)
//
// The imported-search-terms surface talks to the tenant-scoped backend:
//   • imports are archived per account (date + source label), and the same file
//     is idempotent — a re-import reports `duplicate`, never a second copy;
//   • every read returns `state: 'ready' | 'error'`. An unreachable backend is
//     UNKNOWN, never an empty list presented as "no data";
//   • nothing here makes a live or paid call. Fetching is triggered ONLY by an
//     explicit operator action (import click, tab open, filters).
//
// Brand Analytics is UNAVAILABLE until a file is imported: the client returns
// exactly what the server reports and never fabricates a stand-in.
// ═══════════════════════════════════════════════════════════════════════════

const BASE = '/api/design-studio'

async function api(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    let detail = null
    try { detail = (await res.json()).detail } catch { /* non-JSON body */ }
    const fallback = res.status === 401 ? 'sign-in required (this surface is tenant-scoped)' : `http-${res.status}`
    const err = new Error((detail && detail.message) || fallback)
    err.status = res.status
    err.code = detail && detail.code
    throw err
  }
  return res.json()
}

/** Upload one report. Explicit action only. Same file twice -> duplicate. */
export async function importReport({ kind, sourceLabel, filename, content, observedFrom, observedTo }) {
  try {
    const data = await api('/imports', {
      method: 'POST',
      body: JSON.stringify({
        kind,
        source_label: sourceLabel,
        filename: filename || null,
        content,
        observed_from: observedFrom || null,
        observed_to: observedTo || null,
      }),
    })
    return { state: data.state, data }
  } catch (e) {
    // Never present a failed import as an import. Show the reason instead.
    return { state: 'error', reason: String(e.message || e), code: e.code || null, status: e.status || null }
  }
}

export async function fetchImports(kind) {
  try {
    const q = kind ? `?kind=${encodeURIComponent(kind)}` : ''
    const data = await api(`/imports${q}`)
    return { state: 'ready', imports: data.imports || [], kinds: data.kinds || {}, note: data.note || '' }
  } catch (e) {
    return { state: 'error', imports: [], kinds: {}, reason: String(e.message || e) }
  }
}

export async function fetchTerms({ q = '', kind = '', limit = 200 } = {}) {
  try {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (kind) params.set('kind', kind)
    params.set('limit', String(limit))
    const data = await api(`/terms?${params.toString()}`)
    return { state: 'ready', terms: data.terms || [], counts: data.counts || null, note: data.note || '' }
  } catch (e) {
    return { state: 'error', terms: [], counts: null, reason: String(e.message || e) }
  }
}

/** Export is a direct browser download of the tenant-scoped CSV. */
export function termsExportHref({ q = '', kind = '' } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (kind) params.set('kind', kind)
  const qs = params.toString()
  return `${BASE}/terms/export${qs ? `?${qs}` : ''}`
}

/** Compose a brief from imported terms + the brand profile. No generation. */
export async function makeBrief({ termIds = null, q = '', limit = 25, brand = null, keywords = null, voiceSource = null, keywordsSource = null }) {
  try {
    const data = await api('/terms/brief', {
      method: 'POST',
      body: JSON.stringify({ term_ids: termIds, q, limit, brand, keywords, voice_source: voiceSource, keywords_source: keywordsSource }),
    })
    return { state: 'ready', brief: data }
  } catch (e) {
    return { state: 'error', reason: String(e.message || e) }
  }
}

/** The latest imported brand-voice file, as fields with provenance (item 6). */
export async function fetchBrandVoice() {
  try {
    const data = await api('/brand-voice')
    return { state: 'ready', ...data }
  } catch (e) {
    return { state: 'error', available: false, fields: {}, missing_fields: [], reason: String(e.message || e) }
  }
}

// ── Variants (item 6) ──────────────────────────────────────────────────────

export async function fetchVariants() {
  try {
    const data = await api('/variants')
    return { state: 'ready', variants: data.variants || [], metrics: data.metrics || [] }
  } catch (e) {
    return { state: 'error', variants: [], metrics: [], reason: String(e.message || e) }
  }
}

export async function createVariant(fields) {
  try {
    const data = await api('/variants', { method: 'POST', body: JSON.stringify(fields) })
    return { state: 'ready', variant: data.variant }
  } catch (e) {
    return { state: 'error', reason: String(e.message || e) }
  }
}

export async function addVariantMetric(variantId, fields) {
  try {
    const data = await api(`/variants/${encodeURIComponent(variantId)}/metrics`, {
      method: 'POST',
      body: JSON.stringify({ source: 'user', ...fields }),
    })
    return { state: 'ready', metrics: data.metrics || [] }
  } catch (e) {
    return { state: 'error', reason: String(e.message || e) }
  }
}

export async function importVariantMetrics({ content, filename }) {
  try {
    const data = await api('/variants/metrics/import', {
      method: 'POST',
      body: JSON.stringify({ content, filename: filename || null }),
    })
    return { state: 'ready', ...data }
  } catch (e) {
    return { state: 'error', reason: String(e.message || e) }
  }
}

export async function fetchCompare() {
  try {
    const data = await api('/variants/compare')
    return { state: 'ready', comparison: data.comparison || [], note: data.note || '', attributionGap: data.attribution_gap || '' }
  } catch (e) {
    return { state: 'error', comparison: [], reason: String(e.message || e) }
  }
}

/** Results CSV for the performance loop (item 7). Direct browser download. */
export function variantsExportHref() {
  return `${BASE}/variants/export`
}
