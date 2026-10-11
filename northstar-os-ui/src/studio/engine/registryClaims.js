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

/** The title-length check the listing mismatch surface applies as a FLAG. */
export function titleLengthFlag(title) {
  const s = String(title || '')
  if (!s.trim()) return { flagged: false, length: 0, limit: TITLE_LIMIT_CHARS, detail: 'No title to check.' }
  const length = [...s].length
  if (length <= TITLE_LIMIT_CHARS) {
    return { flagged: false, length, limit: TITLE_LIMIT_CHARS, detail: `Title is ${length} characters (limit ${TITLE_LIMIT_CHARS} including spaces).` }
  }
  return {
    flagged: true, length, limit: TITLE_LIMIT_CHARS,
    review: 'FLAG (date-sensitive)',
    detail: `The local title is ${length} characters; the reported limit is ${TITLE_LIMIT_CHARS} including spaces for non-media categories (effective 2026-07-27, REPORTED). Shorten it, or confirm the current limit in Seller Central - nothing is auto-truncated.`,
  }
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
    claim: `Seller-side guidance puts the listing title limit at ${TITLE_LIMIT_CHARS} characters including spaces for non-media categories, effective 2026-07-27.`,
    source_id: 'style-guides',
    tier: CLAIM_TIERS.FLAG,
    cadence: '90d',
    effective_from: '2026-07-27',
    date_sensitive: true,
    status: 'REPORTED',
    enforcement: 'The listing mismatch check flags a longer title for human review; nothing is auto-truncated.',
    note: 'REPORTED until an Amazon-owned page recording the 75-character figure is captured. The style guides remain the registry source; the figure itself is not yet on a recorded Amazon-owned page.',
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
