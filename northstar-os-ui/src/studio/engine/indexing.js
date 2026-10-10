// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — INDEXING HONESTY REGISTER (Phase 6 item 7)
//
// Every claim the studio records about what Amazon's search "indexes" lives
// here as data, with its source id (from specRegistry SOURCES), its confidence
// and the date the source was read. Rules of the register:
//
//   • An official Amazon source -> confidence VERIFIED. Anything else, however
//     plausible, is REPORTED and marked unofficial. Nothing is upgraded by
//     repetition.
//   • `supports_ranking` states whether a recorded source shows the subject
//     affects search ranking. For ALT TEXT and ON-IMAGE / IMAGE TEXT it is
//     `false` everywhere: no recorded Amazon source says imagery or alt text
//     improves ranking, and the studio will not advise them for ranking.
//   • A claim whose source id is not in the registry is UNSOURCED here, and the
//     UI must show it as such rather than dressing it up.
// ═══════════════════════════════════════════════════════════════════════════

import { SPEC_SOURCES } from './specRegistry.js'

export const CONFIDENCE = { VERIFIED: 'VERIFIED', REPORTED: 'REPORTED', UNSOURCED: 'UNSOURCED' }

// Subjects the register can speak about.
export const SUBJECT = {
  TEXT: 'listing text',
  BACKEND_TERMS: 'backend search terms',
  ALT_TEXT: 'alt text',
  IMAGE_TEXT: 'on-image text',
  IMAGE_FILE: 'image file metadata',
}

export const INDEXING_CLAIMS = [
  {
    id: 'text-indexed',
    surface: 'Listing images',
    subject: SUBJECT.TEXT,
    claim: 'Amazon search works from the text the listing carries (title, bullet points, description, structured attributes).',
    source_id: 'listing-quality',
    official: true,
    supports_ranking: true,
    note: 'Documented seller-side guidance; the wording is paraphrased.',
  },
  {
    id: 'backend-terms-indexed',
    surface: 'Listing images',
    subject: SUBJECT.BACKEND_TERMS,
    claim: 'Backend search terms are a documented field whose purpose is discoverability for queries the visible text does not cover.',
    source_id: 'style-guides',
    official: true,
    supports_ranking: true,
    note: 'The field exists and is documented; this register makes no claim about how strongly it weighs.',
  },
  {
    id: 'alt-text-purpose',
    surface: 'A+ / Brand Story',
    subject: SUBJECT.ALT_TEXT,
    claim: 'Amazon REQUIRES alt text for A+ modules containing images; its documented purpose is describing the image for assistive technology.',
    source_id: 'aplus-guide',
    official: true,
    supports_ranking: false,
    note: 'A requirement is not a ranking feature. No recorded Amazon source says alt text improves ranking.',
  },
  {
    id: 'image-text-main',
    surface: 'Listing images',
    subject: SUBJECT.IMAGE_TEXT,
    claim: 'The listing MAIN image must not carry text, logos, badges or colour blocks; on-image text is a compliance matter.',
    source_id: 'img-guide',
    official: true,
    supports_ranking: false,
    note: 'Compliance: an overlay can get the image rejected. No recorded source says on-image text improves ranking.',
  },
  {
    id: 'aplus-text-uniqueness',
    surface: 'A+ / Brand Story',
    subject: SUBJECT.IMAGE_TEXT,
    claim: 'Text baked into A+ images must be unique to A+; reusing listing-copy text in the image is rejected.',
    source_id: 'aplus-guide',
    official: true,
    supports_ranking: false,
    note: 'Prohibitive rule, not a lever.',
  },
  {
    id: 'filename-folklore',
    surface: 'Listing images',
    subject: SUBJECT.IMAGE_FILE,
    claim: 'UNOFFICIAL: image file names or EXIF metadata influence search ranking.',
    source_id: null,
    official: false,
    supports_ranking: false,
    note: 'Seller-forum folklore with no recorded Amazon source. Marked REPORTED/UNSOURCED; the studio does not advise it.',
  },
  {
    id: 'image-text-folklore',
    surface: 'A+ / Brand Story',
    subject: SUBJECT.IMAGE_TEXT,
    claim: 'UNOFFICIAL: putting keywords inside the image (or its alt text) lifts search ranking.',
    source_id: null,
    official: false,
    supports_ranking: false,
    note: 'No recorded Amazon source supports this. The studio must never present it as advice.',
  },
]

/** Claims for one surface (or all). */
export function claimsFor(surface) {
  return INDEXING_CLAIMS.filter(c => !surface || c.surface === surface)
}

/** An entry with no registry source id is UNSOURCED - never inferred as good. */
export function claimConfidence(claim) {
  if (!claim.source_id) return CONFIDENCE.UNSOURCED
  return SPEC_SOURCES[claim.source_id] ? (claim.official ? CONFIDENCE.VERIFIED : CONFIDENCE.REPORTED) : CONFIDENCE.UNSOURCED
}

/** The pulled-at date comes from the registry entry, so it cannot drift. */
export function claimPulledAt(claim) {
  const src = claim.source_id ? SPEC_SOURCES[claim.source_id] : null
  return (src && src.pulled) || null
}

/** Only claims that a recorded source says affect ranking AND the register
 * marks as ranking-relevant. Imagery and alt text are never in this list. */
export function claimsSupportingRanking() {
  return INDEXING_CLAIMS.filter(c => c.supports_ranking === true && claimConfidence(c) === CONFIDENCE.VERIFIED)
}

/** Guard used by the UI and the test harness: text that tells a user that alt
 * text or on-image text improves ranking is NEVER shown. */
export function rankingAdviceFor(subject) {
  if (subject === SUBJECT.ALT_TEXT || subject === SUBJECT.IMAGE_TEXT) {
    return {
      adviceable: false,
      statement: subject === SUBJECT.ALT_TEXT
        ? 'Alt text is required for accessibility. No recorded Amazon source says it improves search ranking, and this studio will not tell you it does.'
        : 'On-image text is a compliance matter (main-image prohibitions, A+ uniqueness). No recorded Amazon source says it improves search ranking, and this studio will not tell you it does.',
    }
  }
  return { adviceable: true, statement: null }
}
