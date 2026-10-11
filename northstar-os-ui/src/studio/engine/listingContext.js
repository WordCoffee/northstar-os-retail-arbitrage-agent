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
 * Build the listing context from local stores.
 *
 * @param {object} o
 * @param {Array} o.forgeListings  ListingForge records (browser store)
 * @param {object} o.brandProfile  the studio brand profile (or null)
 * @param {Array} o.aplusProjects  studio projects with section 'aplus' (or [])
 * @param {string} o.asin          the listing to read ('' = none selected)
 * @returns {{asin, fields, missing, listing_present, corpus}}
 */
export function buildListingContext({ forgeListings = [], brandProfile = null, aplusProjects = [], asin = '' } = {}) {
  const listing = (forgeListings || []).find(l => l && (asin ? l.asin === asin : true)) || null
  const copy = (listing && listing.copy) || {}
  const assets = (listing && Array.isArray(listing.assets)) ? listing.assets : []
  const modules = (aplusProjects || []).filter(p => (p.section || '') === 'aplus' && (!asin || !p.asin || p.asin === asin))

  const observed = listing ? (listing.updated || listing.createdAt || null) : null
  const listingLimits = [
    'A local ListingForge record (browser storage), not a marketplace read.',
    'Starter example rows ship with the studio until you edit or replace them.',
  ]

  const fields = {
    asin: field(listing ? listing.asin : null, 'ListingForge local record', observed, listingLimits),
    title: field(copy.title || (listing && listing.title) || null, 'ListingForge local record', observed, listingLimits),
    bullets: field(
      Array.isArray(copy.bullets) ? copy.bullets : (typeof copy.bullets === 'string' && copy.bullets.trim() ? copy.bullets.split('\n').filter(Boolean) : null),
      'ListingForge local record', observed, listingLimits,
    ),
    backend_terms: field(copy.keywords || null, 'ListingForge local record (keywords field)', observed, listingLimits),
    description: field(copy.description || null, 'ListingForge local record', observed, listingLimits),
    detail_page_copy: field(
      brandProfile && brandProfile.listingCopy ? brandProfile.listingCopy : null,
      'studio brand profile (detail-page copy for parity)',
      brandProfile && (brandProfile.updatedAt || brandProfile.createdAt) || null,
      ['A local brand-profile field; the operator maintains it by hand.'],
    ),
    images: field(
      assets.length ? `${assets.length} local asset record(s)` : null,
      'ListingForge local asset metadata',
      observed,
      ['Local metadata only; the image bytes live in this browser.'],
    ),
    aplus_modules: field(
      modules.length ? modules.map(m => m.name) : null,
      'studio A+ projects (your own records)',
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
    fields,
    missing,
    corpus: parts.join(' ').toLowerCase(),
    note: listing
      ? 'Read from your local ListingForge record. It is a local record, not a live marketplace read.'
      : 'No local ListingForge record matches this ASIN; every listing field is UNKNOWN.',
  }
}

const STOPWORDS = new Set(['with', 'from', 'that', 'this', 'your', 'you', 'and', 'the', 'for', 'into', 'over', 'under', 'each', 'than', 'then', 'when', 'what', 'will', 'have', 'has', 'are', 'our'])

/**
 * Conservative mismatch check: a ranked creative term whose distinctive words
 * do not appear anywhere in the listing copy is flagged for human review.
 * With no listing corpus, nothing is flagged - the state is UNKNOWN instead.
 */
export function mismatchFlags({ brief, context, max = 8 } = {}) {
  if (!context || !context.corpus || context.corpus.trim() === '') {
    return { state: 'UNKNOWN', flags: [], note: 'No listing copy is available locally, so no mismatch can be checked.' }
  }
  const flags = []
  for (const row of (brief && brief.ranked_terms) || []) {
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
  return {
    state: 'checked',
    flags,
    note: flags.length
      ? `${flags.length} ranked term(s) need a human look before the creative and the listing agree.`
      : 'Every ranked term appears in the local listing copy.',
  }
}
