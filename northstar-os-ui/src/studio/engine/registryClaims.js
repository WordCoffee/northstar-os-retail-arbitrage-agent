// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — REGISTRY CLAIMS (Phase 8 item 1)
//
// The claim updates of this phase, as data with their provenance. Rules:
//   • A claim citing only recorded Amazon-owned sources may be VERIFIED; a
//     claim assembled from dated non-Amazon sources stays REPORTED until an
//     Amazon-owned page is recorded. Nothing is upgraded by repetition.
//   • Every claim carries: source id(s), the source's pulled-at date, a tier,
//     a cadence (how often it should be re-read) and its date-sensitivity.
//   • The 75-character title figure is REPORTED and applied as a FLAG in the
//     listing mismatch check - never as a block, and never auto-truncated.
//   • A 10 MB size limit is UNCONFIRMED and is deliberately NOT enforced; the
//     register records that absence so nobody adds it by accident.
//   • A+ eligibility is never asserted by the studio: it says "confirm in
//     A+ Content Manager".
// ═══════════════════════════════════════════════════════════════════════════

import { SPEC_SOURCES } from './specRegistry.js'

export const CLAIM_TIERS = { BLOCK: 'BLOCK', FLAG: 'FLAG', INFO: 'INFO' }

export const TITLE_LIMIT_CHARS = 75

/** The accepted product-image formats, per the Product image guide (recorded
 * source). Animated GIF is excluded; a plain GIF is accepted. */
export const ACCEPTED_IMAGE_FORMATS = ['jpeg', 'jpg', 'tiff', 'tif', 'png', 'gif']

export function formatAccepted(format) {
  const f = String(format || '').toLowerCase().trim()
  if (!f) return { ok: true, detail: 'No explicit format; the pipeline exports PNG.' }
  const animated = f === 'gif-animated' || f === 'animated-gif' || f === 'animated_gif'
  if (animated) {
    return { ok: false, detail: 'Animated GIFs are not accepted; only JPEG, TIFF, PNG and non-animated GIF are.' }
  }
  if (ACCEPTED_IMAGE_FORMATS.includes(f)) {
    return { ok: true, detail: `Format ${f} is accepted (JPEG/TIFF/PNG/non-animated GIF).` }
  }
  return { ok: false, detail: `Format "${f}" is not in the accepted set (JPEG, TIFF, PNG, non-animated GIF).` }
}

/** The title rules captured from Amazon's "Product title requirements and
 * guidelines" page (Seller Central help; login-gated - captured by the owner on
 * 2026-10-11, one-or-two-sentence observation per the capture-task rules).
 * Every rule is applied as a FLAG in the listing mismatch check; the studio
 * NEVER edits a title. */
export const TITLE_RULES = [
  {
    id: 'title-length-75', tier: 'FLAG', status: 'VERIFIED',
    detail: `Title must be ${TITLE_LIMIT_CHARS} characters or fewer, including spaces. The brand name counts toward the ${TITLE_LIMIT_CHARS}. Bundles are not exempt.`,
  },
  {
    id: 'title-no-promotional', tier: 'FLAG', status: 'VERIFIED',
    detail: 'No promotional phrases (examples the studio checks: free shipping, best seller, sale, money-back guarantee, limited time, hot deal, % off, buy now). The example list is illustrative, not Amazon\u2019s full list.',
  },
  {
    id: 'title-special-chars', tier: 'FLAG', status: 'VERIFIED',
    detail: 'The characters ! $ ? _ { } ^ \u00ac \u00a6 are not allowed in a title.',
  },
  {
    id: 'title-same-word-twice', tier: 'FLAG', status: 'VERIFIED',
    detail: 'The same word must not appear more than twice.',
  },
  {
    id: 'title-applies-except', tier: 'INFO', status: 'VERIFIED',
    detail: 'Applies to all titles except media categories and except stores in Saudi Arabia, Egypt, T\u00fcrkiye and the UAE (date-sensitive scope).',
  },
  {
    id: 'title-rollout', tier: 'INFO', status: 'REPORTED',
    detail: 'Rollout: kicked off 2026-07-27, gradual, with a 14-day brand-owner review window for AI-suggested rewrites. Date-sensitive; REPORTED (owner capture, not re-observed here).',
  },
  {
    id: 'item-highlights', tier: 'INFO', status: 'VERIFIED',
    detail: 'Item Highlights is a separate field of up to 125 characters, comma-separated phrases. Flat-file/API support for it is UNKNOWN (not published).',
  },
]

// Illustrative promotional examples, NOT Amazon's full list (stated in the rule).
const PROMOTIONAL_EXAMPLES = [
  /\bfree\s+shipping\b/i, /\bbest\s*seller\b/i, /\bmoney[\s-]*back\b/i,
  /\blimited[\s-]*time\b/i, /\bhot\s+deal\b/i, /\bbuy\s+now\b/i,
  /\b\d+\s*%\s*off\b/i, /\bsale\b/i, /\bguarantee\b/i,
]

const FORBIDDEN_TITLE_CHARS = ['!', '$', '?', '_', '{', '}', '^', '\u00ac', '\u00a6']

/** All title-rule FLAGS for one title. Never mutates, never truncates. */
export function titleRuleFlags(title) {
  const s = String(title || '')
  const flags = []
  if (!s.trim()) return flags

  const length = [...s].length
  if (length > TITLE_LIMIT_CHARS) {
    flags.push({
      rule: 'title-length-75', review: 'FLAG (date-sensitive)',
      detail: `The title is ${length} characters; the limit is ${TITLE_LIMIT_CHARS} including spaces (brand name counts; bundles are not exempt). Shorten it or confirm the current limit in Seller Central - nothing is auto-truncated.`,
    })
  }

  const promo = PROMOTIONAL_EXAMPLES.find(re => re.test(s))
  if (promo) {
    flags.push({
      rule: 'title-no-promotional', review: 'FLAG',
      detail: `The title appears to carry a promotional phrase ("${s.match(promo)[0]}"). Amazon's guidelines prohibit promotional phrases; the check's example list is illustrative, not exhaustive.`,
    })
  }

  const badChars = FORBIDDEN_TITLE_CHARS.filter(c => s.includes(c))
  if (badChars.length) {
    flags.push({
      rule: 'title-special-chars', review: 'FLAG',
      detail: `The title contains characters Amazon does not allow: ${badChars.join(' ')}.`,
    })
  }

  const counts = {}
  for (const w of s.toLowerCase().split(/[^a-z0-9']+/).filter(Boolean)) {
    counts[w] = (counts[w] || 0) + 1
  }
  const repeated = Object.entries(counts).filter(([, n]) => n > 2).map(([w]) => w)
  if (repeated.length) {
    flags.push({
      rule: 'title-same-word-twice', review: 'FLAG',
      detail: `The same word appears more than twice: ${repeated.join(', ')}.`,
    })
  }
  return flags
}

/** Kept for callers that only need the length rule. */
export function titleLengthFlag(title) {
  const s = String(title || '')
  const length = [...s].length
  const flagged = length > TITLE_LIMIT_CHARS
  return {
    flagged, length, limit: TITLE_LIMIT_CHARS,
    review: flagged ? 'FLAG (date-sensitive)' : null,
    detail: flagged
      ? `The title is ${length} characters; the limit is ${TITLE_LIMIT_CHARS} including spaces (brand name counts; bundles are not exempt). Nothing is auto-truncated.`
      : `Title is ${length} characters (limit ${TITLE_LIMIT_CHARS} including spaces).`,
  }
}

/** Item Highlights: separate field, up to 125 characters, comma-separated
 * phrases. The flat-file/API column is UNKNOWN until Amazon publishes it. */
export const ITEM_HIGHLIGHTS = {
  id: 'item-highlights',
  maxChars: 125,
  format: 'comma-separated phrases',
  flat_file_column: null, // UNKNOWN - Amazon has not published it
  note: 'Item Highlights is a separate field of up to 125 characters. The flat-file/API column for it is UNKNOWN until Amazon publishes it; do not guess a column name.',
}

/** The notice ANY export that includes titles must carry (Phase 9 item 3). */
export function titleExportNotice() {
  return 'Item Highlights column: UNKNOWN - Amazon has not published the flat-file/API column for the Item Highlights field (up to 125 characters, comma-separated phrases). Do not invent a column; keep titles within 75 characters, avoid promotional phrases and the disallowed characters, and never repeat a word more than twice.'
}

/** The 10 MB listing-image size limit is UNCONFIRMED and NOT enforced. */
export const IMAGE_SIZE_BLOCK = {
  id: 'image-size-10mb-unconfirmed',
  enforced: false,
  detail: 'A 10 MB listing-image size limit is UNCONFIRMED and is NOT enforced by the studio. The A+ 2 MB per-file limit is a different, recorded rule.',
}

export const REGISTRY_CLAIMS = [
  {
    id: 'title-length-75',
    subject: 'Listing title length',
    claim: `The listing title limit is ${TITLE_LIMIT_CHARS} characters or fewer including spaces. The brand name counts toward the limit and bundles are not exempt.`,
    source_id: 'title-guide',
    tier: CLAIM_TIERS.FLAG,
    cadence: '90d',
    effective_from: '2026-07-27',
    date_sensitive: true,
    status: 'VERIFIED',
    applies_except: ['media categories', 'stores in Saudi Arabia, Egypt, T\u00fcrkiye and the UAE'],
    enforcement: 'The listing mismatch check flags a longer title for human review; nothing is auto-truncated and no title is ever edited.',
    note: 'Captured by the owner on 2026-10-11 from the signed-in Seller Central page (login-gated; the studio attempted a public read and received the sign-in gate - no body observed here).',
  },
  {
    id: 'title-content-rules',
    subject: 'Listing title content',
    claim: 'Titles must not carry promotional phrases, must not use the characters ! $ ? _ { } ^ \u00ac \u00a6, and must not repeat the same word more than twice.',
    source_id: 'title-guide',
    tier: CLAIM_TIERS.FLAG,
    cadence: '90d',
    date_sensitive: true,
    status: 'VERIFIED',
    enforcement: 'titleRuleFlags() applies each rule as a FLAG in the listing mismatch check; the promotional example list is illustrative, not Amazon\u2019s full list.',
    note: 'Captured by the owner on 2026-10-11; the studio never edits a title.',
  },
  {
    id: 'title-rollout-2026-07-27',
    subject: 'Title-rule rollout',
    claim: 'Rollout kicked off 2026-07-27 and is gradual, with a 14-day brand-owner review window for AI-suggested rewrites.',
    source_id: 'title-guide',
    tier: CLAIM_TIERS.INFO,
    cadence: '30d',
    effective_from: '2026-07-27',
    date_sensitive: true,
    status: 'REPORTED',
    note: 'Owner capture, not re-observed this session; date-sensitive, so the register flags it.',
  },
  {
    id: 'item-highlights-field',
    subject: 'Item Highlights',
    claim: 'Item Highlights is a separate field of up to 125 characters holding comma-separated phrases. The flat-file/API column for it is UNKNOWN until Amazon publishes it.',
    source_id: 'title-guide',
    tier: CLAIM_TIERS.INFO,
    cadence: '90d',
    date_sensitive: true,
    status: 'VERIFIED',
    unknown_fields: ['flat_file_column'],
    enforcement: 'Any export that includes titles carries the UNKNOWN-column notice; no column name is ever invented.',
  },
  {
    id: 'ai-people-metadata-window',
    subject: 'AI-generated-people metadata',
    claim: 'The AI-generated-people metadata requirement dates across sources from 2026-07-22 to Amazon\u2019s announcement on 2026-07-27; the Product image guide is the authoritative method.',
    source_ids: ['ai-announce', 'ai-tag-ops', 'img-guide'],
    authoritative_source_id: 'img-guide',
    tier: CLAIM_TIERS.BLOCK,
    cadence: '30d',
    date_from: '2026-07-22',
    date_to: '2026-07-27',
    date_sensitive: true,
    status: 'REPORTED',
    note: 'The window is assembled from dated sources: the 2026-07-27 announcement is Amazon-owned, the operations detail is not. The method is authoritative only through the Product image guide.',
  },
  {
    id: 'image-formats',
    subject: 'Product image formats',
    claim: 'Accepted product-image formats are JPEG, TIFF, PNG and non-animated GIF, per the Product image guide.',
    source_id: 'img-guide',
    tier: CLAIM_TIERS.BLOCK,
    cadence: '180d',
    date_sensitive: true,
    status: null, // derived from the source's own confidence
    enforcement: 'compliance rule no-animated-gif checks an explicit export format.',
  },
  {
    id: 'image-size-10mb-unconfirmed',
    subject: 'Listing image file size',
    claim: IMAGE_SIZE_BLOCK.detail,
    source_id: null,
    tier: CLAIM_TIERS.INFO,
    cadence: '180d',
    date_sensitive: false,
    status: 'REPORTED',
    enforcement: 'NOT enforced by design - an unconfirmed figure must never block an export.',
  },
  {
    id: 'aplus-eligibility',
    subject: 'A+ / Premium A+ eligibility',
    claim: 'A+ and Premium A+ eligibility must be confirmed in the A+ Content Manager; the studio does not assert eligibility.',
    source_id: 'aplus-guide',
    tier: CLAIM_TIERS.INFO,
    cadence: '90d',
    date_sensitive: true,
    status: null, // derived from the source's own confidence
    display: 'confirm in A+ Content Manager',
  },
]

/** The pulled-at date comes from the registry source, so it cannot drift. */
export function claimPulledAt(claim) {
  const ids = claim.source_ids || (claim.source_id ? [claim.source_id] : [])
  const dates = ids.map(id => (SPEC_SOURCES[id] || {}).pulled).filter(Boolean)
  return dates.length ? dates[0] : null
}

/** VERIFIED only when every cited source resolves AND is an Amazon-owned,
 * non-REPORTED registry source; otherwise REPORTED/UNSOURCED. */
export function claimStatus(claim) {
  if (claim.status) return claim.status
  const ids = claim.source_ids || (claim.source_id ? [claim.source_id] : [])
  if (!ids.length) return 'UNSOURCED'
  const all = ids.every(id => SPEC_SOURCES[id])
  if (!all) return 'UNSOURCED'
  const confidences = ids.map(id => SPEC_SOURCES[id].confidence)
  return confidences.every(c => c === 'VERIFIED') ? 'VERIFIED' : 'REPORTED'
}

export function claimsFor(subject) {
  return REGISTRY_CLAIMS.filter(c => !subject || c.subject === subject)
}
