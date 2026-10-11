// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — LISTING CONTEXT (Phase 7 item 5)
//
// Reads the seller's OWN local listing records and shows them beside a creative
// brief. Sources are existing local stores only — no marketplace call, no
// provider call, nothing fetched:
//   • ListingForge browser records (`ns-studio-lf-listings`, lf-assets)
//   • the studio brand profile's detail-page copy (Projects › Brand)
//   • the studio's own A+ projects (section 'aplus') as the A+ module list
//
// Every field carries its source, observed time, freshness and limits. A field
// no store provides is UNKNOWN - never an empty string dressed as content.
// The mismatch check is deliberately conservative: a ranked creative term that
// does not appear in the listing copy is flagged as NEEDS HUMAN REVIEW, never
// auto-fixed and never called an error.
// ═══════════════════════════════════════════════════════════════════════════

const FRESH_DAYS = 90 // an engineering choice, stated in the UI, not an Amazon figure

// Phase 8 item 1: the reported 75-character title limit, applied as a FLAG.
import { titleLengthFlag } from './registryClaims.js'

function ageDays(iso) {
  if (!iso) return null
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return null
  return Math.max(0, Math.round((Date.now() - t) / 86400000))
}

function freshnessOf(iso) {
  const age = ageDays(iso)
  if (age === null) return { freshness: 'unknown', note: 'the record carries no usable date' }
  if (age <= FRESH_DAYS) return { freshness: 'current', note: `observed ${age} day(s) ago (freshness window ${FRESH_DAYS} days - an engineering choice, not an Amazon figure)` }
  return { freshness: 'stale', note: `observed ${age} day(s) ago - beyond the ${FRESH_DAYS}-day freshness window` }
}

function field(value, source, observedAt, limits) {
  const missing = value === null || value === undefined || (typeof value === 'string' && value.trim() === '')
  const f = freshnessOf(observedAt)
  return {
    value: missing ? null : value,
    missing,
    source,
    observed_at: observedAt || null,
    freshness: missing ? 'unknown' : f.freshness,
    freshness_note: f.note,
    limits: limits || [],
  }
}

/**
 * Build the listing context from the tenant store first, with the browser-local
 * ListingForge records as an explicit OFFLINE FALLBACK (Phase 8 item 3).
 *
 * @param {object} o
 * @param {Array} o.serverRecords  ds_listing_records rows (tenant store, primary)
 * @param {Array} o.forgeListings  ListingForge records (fallback only)
 * @param {object} o.brandProfile  the studio brand profile (or null)
 * @param {Array} o.aplusProjects  studio projects with section 'aplus' (or [])
 * @param {string} o.asin          the listing to read ('' = first)
 * @returns {{asin, fields, missing, listing_present, corpus, source_kind}}
 */
export function buildListingContext({ serverRecords = [], forgeListings = [], brandProfile = null, aplusProjects = [], asin = '' } = {}) {
  const server = (serverRecords || []).find(r => r && (asin ? r.asin === asin : true)) || null
  const local = !server ? ((forgeListings || []).find(l => l && (asin ? l.asin === asin : true)) || null) : null
  const listing = server || local
  const fromServer = !!server
  const copy = (local && local.copy) || {}
  const assets = (local && Array.isArray(local.assets)) ? local.assets : []
  const modules = (aplusProjects || []).filter(p => (p.section || '') === 'aplus' && (!asin || !p.asin || p.asin === asin))

  const observed = fromServer
    ? (server.observed_at || null)
    : (local ? (local.updated || local.createdAt || null) : null)
  const listingLimits = fromServer
    ? [
      'A tenant-store listing record (server), migrated from your browser-local ListingForge records.',
      'A local record, not a marketplace read.',
    ]
    : [
      'FALLBACK: a browser-local ListingForge record (the tenant store was unreachable or has no record yet).',
      'Starter example rows ship with the studio until you edit or replace them.',
    ]
  const sourceLabel = fromServer ? 'tenant listing record (server)' : 'ListingForge local record (fallback)'

  const serverBullets = fromServer && Array.isArray(server.bullets) ? server.bullets : null
  const serverModules = fromServer && Array.isArray(server.aplus_modules) && server.aplus_modules.length ? server.aplus_modules : null
  const serverImages = fromServer && Array.isArray(server.images) && server.images.length ? server.images : null

  const fields = {
    asin: field(listing ? listing.asin : null, sourceLabel, observed, listingLimits),
    title: field(fromServer ? server.title : (copy.title || (local && local.title) || null), sourceLabel, observed, listingLimits),
    bullets: field(
      fromServer ? serverBullets : (Array.isArray(copy.bullets) ? copy.bullets : (typeof copy.bullets === 'string' && copy.bullets.trim() ? copy.bullets.split('\n').filter(Boolean) : null)),
      sourceLabel, observed, listingLimits,
    ),
    backend_terms: field(fromServer ? server.backend_terms : (copy.keywords || null), sourceLabel, observed, listingLimits),
    description: field(fromServer ? server.description : (copy.description || null), sourceLabel, observed, listingLimits),
    detail_page_copy: field(
      brandProfile && brandProfile.listingCopy ? brandProfile.listingCopy : null,
      'studio brand profile (detail-page copy for parity)',
      brandProfile && (brandProfile.updatedAt || brandProfile.createdAt) || null,
      ['A local brand-profile field; the operator maintains it by hand.'],
    ),
    images: field(
      fromServer ? serverImages : (assets.length ? `${assets.length} local asset record(s)` : null),
      fromServer ? sourceLabel : 'ListingForge local asset metadata',
      observed,
      ['Local metadata only; the image bytes live in this browser.'],
    ),
    aplus_modules: field(
      fromServer ? serverModules : (modules.length ? modules.map(m => m.name) : null),
      fromServer ? sourceLabel : 'studio A+ projects (your own records)',
      modules.length ? (modules[0].pulled_at || null) : null,
      ['This lists the studio projects you created for A+; it is not Amazon\'s published module list.'],
    ),
  }

  const missing = Object.entries(fields).filter(([, f]) => f.missing).map(([k]) => k)

  // The corpus the mismatch check reads: everything textual we actually have.
  const parts = []
  if (fields.title.value) parts.push(String(fields.title.value))
  if (fields.bullets.value) parts.push((Array.isArray(fields.bullets.value) ? fields.bullets.value : [fields.bullets.value]).join(' '))
  if (fields.backend_terms.value) parts.push(String(fields.backend_terms.value))
  if (fields.description.value) parts.push(String(fields.description.value))
  if (fields.detail_page_copy.value) parts.push(String(fields.detail_page_copy.value))

  return {
    asin: asin || (listing ? listing.asin : ''),
    listing_present: !!listing,
    source_kind: fromServer ? 'server' : (local ? 'local-fallback' : 'none'),
    fields,
    missing,
    corpus: parts.join(' ').toLowerCase(),
    note: listing
      ? (fromServer
        ? 'Read from the tenant-store listing record (migrated from your browser-local ListingForge records). A local record, not a live marketplace read.'
        : 'FALLBACK: read from the browser-local ListingForge record; the tenant store had no record. A local record, not a live marketplace read.')
      : 'No listing record exists in the tenant store or locally; every listing field is UNKNOWN.',
  }
}

const STOPWORDS = new Set(['with', 'from', 'that', 'this', 'your', 'you', 'and', 'the', 'for', 'into', 'over', 'under', 'each', 'than', 'then', 'when', 'what', 'will', 'have', 'has', 'are', 'our'])

/**
 * Conservative mismatch check.
 *
 * Always runs the title-length check (Phase 8 item 1: the reported 75-character
 * limit is applied as a FLAG, never a block). Term checks need a brief AND a
 * listing corpus; with no corpus the term state is UNKNOWN instead.
 */
export function mismatchFlags({ brief, context, max = 8 } = {}) {
  const flags = []

  // Title length: independent of any brief, from the local listing record.
  const title = context && context.fields && context.fields.title ? context.fields.title.value : null
  const tf = titleLengthFlag(title)
  if (tf.flagged) {
    flags.push({
      term: '(listing title)', kind: 'title-length', review: tf.review, detail: tf.detail,
    })
  }

  const hasCorpus = !!(context && context.corpus && context.corpus.trim() !== '')
  if (!hasCorpus || !brief) {
    const why = !hasCorpus
      ? 'No listing copy is available locally, so no term mismatch can be checked.'
      : 'Compose a brief to check its terms against the listing copy.'
    return {
      state: 'UNKNOWN',
      flags,
      note: why + (flags.length ? ' The title-length flag above did not need a brief.' : ''),
    }
  }

  for (const row of brief.ranked_terms || []) {
    const term = String(row.evidence.term || '').toLowerCase()
    if (!term) continue
    const words = term.split(/[^a-z0-9']+/).filter(w => w.length >= 4 && !STOPWORDS.has(w))
    if (!words.length) continue
    const absent = words.filter(w => !context.corpus.includes(w))
    if (absent.length) {
      flags.push({
        term: row.evidence.term,
        absent_words: absent,
        review: 'NEEDS HUMAN REVIEW',
        detail: `The creative ranks "${row.evidence.term}", but the local listing copy does not carry: ${absent.join(', ')}. Add the claim to the listing or drop it from the creative - the studio does not change either for you.`,
      })
    }
    if (flags.length >= max) break
  }
  const termFlags = flags.filter(f => f.kind !== 'title-length').length
  return {
    state: 'checked',
    flags,
    note: termFlags
      ? `${termFlags} ranked term(s) need a human look before the creative and the listing agree.`
      : (flags.length ? 'Every ranked term appears in the local listing copy; the title-length flag above still applies.' : 'Every ranked term appears in the local listing copy.'),
  }
}
