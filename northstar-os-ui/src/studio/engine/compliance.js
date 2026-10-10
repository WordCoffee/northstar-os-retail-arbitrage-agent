// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — AMAZON COMPLIANCE PRE-FLIGHT
//
// Rules are DATA, versioned, sourced and dated — never code. Every row carries
// a source id from research/design_studio_deep_research_20261008/SOURCES.csv,
// an accessed date, and a date_sensitive flag, because Amazon states it
// "periodically updates our policies".
//
// Two levels, deliberately:
//   BLOCK — a deterministic rule the asset provably breaks. Export refuses
//           until the operator fixes it or explicitly overrides (overrides are
//           recorded in the document, never silent).
//   FLAG  — a heuristic that needs a human. Never auto-blocks; Amazon itself
//           reports rejecting Premium A+ over a brand logo and over text that
//           is part of the physical product, which no automatic check can judge.
//
// The checks run on the document the operator built, not on a rendered file,
// so they are free, instant, and available before any export is attempted.
//
// ═══════════════════════════════════════════════════════════════════════════

import { ALL_FORMATS, formatById } from './presets.js'
import { SAFE_ZONES, AMAZON_CAPS, AI_POLICY, SPEC_BY_ID, SPEC_SOURCES, freshnessOf } from './specRegistry.js'
import { disclosureRow, checkFilename } from './disclosure.js'
import { FIDELITY_MODE_BY_ID } from './fidelity.js'

const ACCESSED = '2026-10-09'

// ── Rule register ────────────────────────────────────────────────────────────
export const RULES = [
  {
    id: 'raster-range', level: 'block', scope: 'all', kind: 'size',
    label: 'Longest side within Amazon\u2019s published range',
    detail: 'All listing images must be 500–10,000 px on the longest side.',
    source: 'S415/S416', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'raster-zoom', level: 'flag', scope: 'all', kind: 'size',
    label: 'Longest side above 1,000 px for zoom',
    detail: 'Amazon: \u201cwe prefer images to be larger than 1,000 pixels on the longest side to allow for zoom\u201d.',
    source: 'S416', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'main-white-bg', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'MAIN image background is white',
    detail: 'The main image must show only the product on a white background.',
    source: 'S415', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'main-fill', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'Product fills at least 85% of the frame',
    detail: 'Amazon states the product must fill at least 85% of the image.',
    source: 'S415', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'main-no-overlay', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'No text, logo, badge, border, colour block or watermark on MAIN',
    detail: 'Prohibited on the main image over the product or in the background.',
    source: 'S415', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'aplus-module-size', level: 'block', scope: 'Amazon A+', kind: 'size',
    label: 'Matches the module\u2019s published minimum size',
    detail: 'Images smaller than the module minimum will not be scaled up.',
    source: 'S410', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'no-animated-gif', level: 'block', scope: 'all', kind: 'format',
    label: 'Export format is accepted',
    detail: 'JPEG/TIFF/PNG accepted; animated GIFs are not supported by Amazon\u2019s servers.',
    source: 'S415', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'caps-headline', level: 'block', scope: 'ads', kind: 'copy',
    label: 'Headline is not ALL CAPS',
    detail: 'Sentence case only for self-service ad products; ALL CAPS is rejected.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'title-case', level: 'flag', scope: 'ads', kind: 'copy',
    label: 'Headline is not Title Case',
    detail: 'Title Case and MIXED case are rejected for self-service ad products.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'pressure-punct', level: 'block', scope: 'ads', kind: 'copy',
    label: 'No repeated question/exclamation marks',
    detail: 'Repeated \u201c?\u201d or \u201c!\u201d, or more than two ellipses in a headline, are rejected.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'cta-end-punct', level: 'block', scope: 'ads', kind: 'copy',
    label: 'Call to action has no end punctuation',
    detail: 'Any end punctuation in calls to action (e.g. \u201cShop now!\u201d) is rejected.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'special-chars', level: 'block', scope: 'ads', kind: 'copy',
    label: 'No special characters substituting letters',
    detail: 'Numerals, \u201c*\u201d, \u201c@\u201d or periods in place of letters, or to shorten words (\u201cH8\u201d, \u201cB.E.S.T.\u201d, \u201cw/out\u201d).',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'pressure-language', level: 'flag', scope: 'ads', kind: 'copy',
    label: 'No urgency or pressure language',
    detail: 'Language creating urgency (\u201cHurry while supplies last!\u201d) is prohibited.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'personal-language', level: 'flag', scope: 'ads', kind: 'copy',
    label: 'Avoids \u201cyou\u201d / \u201cyour\u201d',
    detail: 'Amazon\u2019s own example of copy to avoid: \u201cUse our supplement to solve your weight issues\u201d.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'superiority', level: 'block', scope: 'all', kind: 'claims',
    label: 'No unsubstantiated superiority claim',
    detail: '\u201cbest\u201d, \u201ctop selling\u201d, \u201chealthiest\u201d and similar will not be approved without substantiation.',
    source: 'S400/S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'competitor-named', level: 'block', scope: 'all', kind: 'claims',
    label: 'No competitor named',
    detail: 'Competitors may not be explicitly called out by name; a \u201cleading brand\u201d reference is permitted.',
    source: 'S403', accessed: ACCESSED, dateSensitive: true,
  },
  {
    id: 'brand-prohibited', level: 'block', scope: 'all', kind: 'claims',
    label: 'No claim on the brand\u2019s prohibited list',
    detail: 'The operator\u2019s own prohibited-claims list, recorded in the brand profile.',
    source: 'operator', accessed: ACCESSED, dateSensitive: false,
  },
  {
    id: 'text-on-image-legibility', level: 'flag', scope: 'all', kind: 'copy',
    label: 'On-image text is rendered as vector',
    detail: 'The most-repeated seller complaint is garbled on-image text. This studio draws text on a canvas, never through a model.',
    source: 'SELLER_PAIN_POINTS theme 2', accessed: ACCESSED, dateSensitive: false,
  },
  {
    id: 'image-text-not-indexed', level: 'flag', scope: 'all', kind: 'copy',
    label: 'On-image text is not indexed by search',
    detail: 'Amazon states text inside images is not read by search engines or screen readers, so keyword-bearing image text is not an SEO play.',
    source: 'AMAZON_REQUIREMENTS', accessed: ACCESSED, dateSensitive: true,
  },
  // ── Phase 2 rules (2026-10-10), from research/design-studio Tracks B + E ──
  {
    id: 'store-safe-zone', level: 'flag', scope: 'Amazon Store', kind: 'layout',
    label: 'Important content sits inside the Store safe zone',
    detail: 'Store heroes are cropped 16% each side below 1500px wide and the brand logo covers a further 18% of the left; image tiles with link titles obscure ~19% (rectangle) or ~12% (square) at the bottom.',
    source: 'stores-hero / stores-content', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'store-no-embedded-text', level: 'flag', scope: 'Amazon Store', kind: 'copy',
    label: 'Text is a Store text field, not baked into the image',
    detail: 'Amazon does not encourage embedded image text because it is unreadable by external search engines and screen readers. Use the Image with text tile.',
    source: 'stores-content', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'sbv-video-spec', level: 'block', scope: 'Amazon Ads', kind: 'video',
    label: 'Sponsored Brands video meets every published spec',
    detail: 'Duration 6-45s, 16:9 square pixel (or 9:16 vertical), MP4/MOV, H.264/H.265 Main or Baseline, 23.976-30fps, min 1 Mbps video, audio PCM/AAC/MP3 at min 96 kbps and 44.1 kHz, 500 MB cap.',
    source: 'sponsored-brands-video / sbv API guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'sbv-text-safe-area', level: 'flag', scope: 'Amazon Ads', kind: 'layout',
    label: 'No text in the bottom-right corner of the video',
    detail: 'On-screen text must be legible on mobile and must not enter the bottom-right corner or the platform UI strip.',
    source: 'sponsored-brands-video', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'ai-people-disclosure', level: 'flag', scope: 'all', kind: 'policy',
    label: 'Photorealistic AI people are disclosed',
    detail: 'A+ Content requires the IPTC keyword contains-synthetic-performer in dc:subject (XMP), or the AI-generated people checkbox at upload, when an image contains photorealistic AI-generated people.',
    source: 'A+ content guidelines (GW8U76SSNTRTBX7)', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'brand-registry-not-a-mockup', level: 'flag', scope: 'all', kind: 'policy',
    label: 'Generated mockups are never used as Brand Registry proof',
    detail: 'Brand Registry enrollment requires an actual photo; mock-ups and digitally altered product images are not valid proof of IP ownership and may cause removal from the program.',
    source: 'Brand Registry Application Guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'aplus-alt-text', level: 'block', scope: 'Amazon A+', kind: 'copy',
    label: 'Every A+ image module has descriptive alt text',
    detail: 'Alt text is a required field; alt text that does not describe the image for screen-reader users can result in content rejection.',
    source: 'A+ content guidelines (GW8U76SSNTRTBX7)', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'aplus-file-size', level: 'block', scope: 'Amazon A+', kind: 'size',
    label: 'A+ image is under 2 MB and RGB',
    detail: 'Individual A+ files must stay under 2 MB, be RGB (CMYK is not supported), and be at least 72 dpi. Animated GIFs are prohibited.',
    source: 'A+ content guidelines (GW8U76SSNTRTBX7)', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'ad-char-caps', level: 'block', scope: 'ads', kind: 'copy',
    label: 'Ad copy respects the published character caps',
    detail: 'Headline 50 chars (30 JP), brand name 25, Amazon DSP body text 100, disclaimer 60, CTA under 30 chars with no punctuation.',
    source: 'ads overview / brand profile policy', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'sbv-vertical-date-sensitive', level: 'flag', scope: 'Amazon Ads', kind: 'video',
    label: '9:16 vertical is not the default SB video aspect',
    detail: 'The 16:9 square-pixel variant is the documented default. The 9:16 vertical appears in the Ads API guide and depends on campaign goal and surface availability, so it is a warning — never a block.',
    source: 'sbv ads API guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'spec-sourced', level: 'block', scope: 'all', kind: 'policy',
    label: 'This format has a recorded source',
    detail: 'A format with no captured Amazon source cannot be exported, so a spec from one ad product can never be silently applied to another.',
    source: 'spec registry', accessed: '2026-10-10', dateSensitive: false,
  },
  // ── Non-SB video families (SP video, Display video) ──────────────────────
  {
    id: 'video-spec', level: 'block', scope: 'Amazon Ads', kind: 'video',
    label: 'This video format meets its own published spec',
    detail: 'Each video family is checked against ITS OWN registry row. Sponsored Products video is 7 seconds and longer with no published maximum; Sponsored Display video is 6-45 seconds. Neither may be checked against the Sponsored Brands range.',
    source: 'spv guide / display video creative', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'video-reconciled', level: 'flag', scope: 'Amazon Ads', kind: 'policy',
    label: 'Two Amazon figures recorded; the stricter is enforced',
    detail: 'Amazon publishes 1 Mbps AND 4 Mbps for video, and 92 kbps AND 192 kbps for audio, on two pages describing different placements. Both are stored with their source and the stricter is enforced. The display table also repeats the "Minimum duration" label on two rows, recorded as a source defect and read as min 6s / max 45s.',
    source: 'display video creative / ads overview / streaming TV', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'video-audio-removed', level: 'flag', scope: 'Amazon Ads', kind: 'video',
    label: 'Audio is removed on this placement',
    detail: 'Amazon documents that audio WILL BE REMOVED for Sponsored Products video, so an audio mix must not be mastered and the absence of audio is not a defect.',
    source: 'spv guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'video-product-frame', level: 'flag', scope: 'Amazon Ads', kind: 'video',
    label: 'Product occupies enough of the video frame',
    detail: 'Amazon requires the product to take up 50% or more of the video frame for Sponsored Products video.',
    source: 'spv guide', accessed: '2026-10-10', dateSensitive: true,
  },
  // ── MAIN IMAGE: the full documented prohibition set (directive item 2) ───
  {
    id: 'main-entire-product', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'The entire product is inside the frame',
    detail: 'The product and all its features must be clearly visible. A product cropped by the frame edge fails.',
    source: 'main-image-detail', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-shown-once', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'The product is shown once',
    detail: 'The main image must not include multiple images of the same single product.',
    source: 'main-image-detail', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-single-unit', level: 'flag', scope: 'amz-main', kind: 'main',
    label: 'One unit plus included accessories only',
    detail: 'Show only one unit of the product, plus any accessories that come with it. Extra units imply a pack the buyer will not receive.',
    source: 'img-guide / main-image-detail', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-no-props', level: 'flag', scope: 'amz-main', kind: 'main',
    label: 'No props that are not included',
    detail: 'Props that are not part of what the buyer receives must not appear on the main image.',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-no-packaging', level: 'flag', scope: 'amz-main', kind: 'main',
    label: 'No packaging unless the packaging is a product feature',
    detail: 'Show the product out of its packaging unless the packaging itself is a feature the buyer receives (a consumable or a collectible).',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-no-mannequins', level: 'flag', scope: 'amz-main', kind: 'main',
    label: 'No mannequins in the main image',
    detail: 'Mannequins are prohibited on the main image for apparel categories.',
    source: 'style-guides-main', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'main-no-amazon-marks', level: 'block', scope: 'amz-main', kind: 'main',
    label: 'No Amazon marks or badges',
    detail: 'Amazon\'s Choice, Best Seller, Prime and similar Amazon badges or marks must not be placed on the image.',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  // ── ALL IMAGES (directive item 2, second half) ───────────────────────────
  {
    id: 'all-no-review-imagery', level: 'block', scope: 'all', kind: 'claims',
    label: 'No review imagery or claims',
    detail: 'Star ratings, review counts, review quotes and review screenshots must not be placed on an image. Amazon supplies the real review data on the page.',
    source: 'ads-overview / general policies', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'all-no-pricing', level: 'block', scope: 'all', kind: 'claims',
    label: 'No pricing or savings claims on the image',
    detail: 'Pricing, discount and savings claims on an image go stale the moment the price changes and are treated as a claim. Keep price out of the creative.',
    source: 'ads-overview / general policies', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'all-no-seller-info', level: 'block', scope: 'all', kind: 'claims',
    label: 'No seller or contact information',
    detail: 'URLs, email addresses, phone numbers, social handles and off-Amazon seller information must not appear on an image.',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  // ── TECHNICAL RULES (directive item 3) ──────────────────────────────────
  {
    id: 'dpi-min-72', level: 'block', scope: 'all', kind: 'size',
    label: 'Resolution is at least 72 dpi',
    detail: 'Amazon requires at least 72 dpi. A file that records a lower density is rejected by the upstream check even when the pixel dimensions are correct.',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'color-space-rgb', level: 'block', scope: 'all', kind: 'format',
    label: 'Colour space is RGB',
    detail: 'Amazon converts CMYK to RGB, which can shift colour. Supply RGB (sRGB) so what you approve is what ships.',
    source: 'aplus-guide / img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
  {
    id: 'filename-pattern', level: 'flag', scope: 'all', kind: 'policy',
    label: 'Filename follows ID.VARIANT.ext',
    detail: 'Amazon documents the listing image filename pattern ID.VARIANT.ext — an identifier, a dot, a variant, a dot, and an accepted extension.',
    source: 'img-guide', accessed: '2026-10-10', dateSensitive: true,
  },
]

export const RULES_BY_ID = Object.fromEntries(RULES.map(r => [r.id, r]))

// ── What each rule needs before its result MEANS anything ───────────────────
//   'nothing'  — decided by the format alone (a size rule needs no artwork)
//   'artwork'  — needs real placed artwork; an empty canvas reports
//                `needs-artwork`, never a green pass
//   'export'   — only decidable from the exported file
//   'human'    — inherently a human judgement; reports `needs-review`
const RULE_NEEDS = {
  'raster-range': 'nothing',
  'raster-zoom': 'nothing',
  'main-white-bg': 'artwork',
  'main-fill': 'artwork',
  'main-no-overlay': 'artwork',
  'aplus-module-size': 'nothing',
  'no-animated-gif': 'nothing',
  'caps-headline': 'artwork',
  'title-case': 'artwork',
  'pressure-punct': 'artwork',
  'cta-end-punct': 'artwork',
  'special-chars': 'artwork',
  'pressure-language': 'artwork',
  'personal-language': 'artwork',
  'superiority': 'artwork',
  'competitor-named': 'artwork',
  'brand-prohibited': 'artwork',
  'text-on-image-legibility': 'artwork',
  'image-text-not-indexed': 'nothing',
  'store-safe-zone': 'artwork',
  'store-no-embedded-text': 'artwork',
  'sbv-video-spec': 'export',
  'sbv-text-safe-area': 'artwork',
  'ai-people-disclosure': 'human',
  'brand-registry-not-a-mockup': 'human',
  'aplus-alt-text': 'artwork',
  'aplus-file-size': 'export',
  'ad-char-caps': 'artwork',
  'sbv-vertical-date-sensitive': 'nothing',
  'spec-sourced': 'nothing',
  'video-spec': 'export',
  'video-reconciled': 'nothing',
  'video-audio-removed': 'nothing',
  'video-product-frame': 'artwork',
  'main-entire-product': 'artwork',
  'main-shown-once': 'artwork',
  'main-single-unit': 'artwork',
  'main-no-props': 'artwork',
  'main-no-packaging': 'artwork',
  'main-no-mannequins': 'artwork',
  'main-no-amazon-marks': 'artwork',
  'all-no-review-imagery': 'artwork',
  'all-no-pricing': 'artwork',
  'all-no-seller-info': 'artwork',
  'dpi-min-72': 'nothing',
  'color-space-rgb': 'nothing',
  'filename-pattern': 'nothing',
  'ai-generated-people-disclosure': 'human',
}

export function needsOf(ruleId) {
  return RULE_NEEDS[ruleId] || 'human'
}

// ── Prohibited vocabulary ────────────────────────────────────────────────────
const SUPERIORITY = [
  'best', 'top selling', 'top-selling', 'healthiest', 'no.1', 'number one',
  'the most', 'the biggest', 'the tastiest', 'world class', 'world-class',
  'unbeatable', 'best-selling', 'best selling',
]
const PRESSURE = [
  'hurry', 'while supplies last', "don't miss out", 'dont miss out',
  'last chance', 'act now', 'limited time only', 'only a few left', 'selling out fast',
]
const SPECIAL_CHAR_RE = [
  /\b[A-Za-z]*\d[A-Za-z]*\d[A-Za-z]*\b/,   // H8-style letter/num substitution
  /\b[A-Z]\.[A-Z]\.[A-Z]/,                  // B.E.S.T.
  /\bw\/out\b/i, /\bw\//i, /\bb\/c\b/i,
]
// Pressure compounds when two or more of these appear together.
const PRESSURE_MARKER_RE = /[!?]{1,}/g

// ── Helpers ──────────────────────────────────────────────────────────────────
function isAllCaps(s) {
  const letters = String(s).replace(/[^A-Za-z]/g, '')
  return letters.length > 3 && letters === letters.toUpperCase()
}
function isTitleCase(s) {
  const words = String(s).trim().split(/\s+/).filter(w => /[A-Za-z]/.test(w))
  if (words.length < 2) return false
  const minor = new Set(['a', 'an', 'the', 'and', 'or', 'but', 'for', 'nor', 'on', 'at', 'to', 'from', 'by', 'of', 'in', 'with'])
  return words.every((w, i) => {
    const c = w.replace(/[^A-Za-z]/g, '')
    if (!c) return true
    return (i === 0 || !minor.has(c.toLowerCase())) && c[0] === c[0].toUpperCase() && c.slice(1) === c.slice(1).toLowerCase()
  })
}
function nearWhite(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim())
  if (!m) return false
  const n = parseInt(m[1], 16)
  const r = (n >> 16) & 255; const g = (n >> 8) & 255; const b = n & 255
  return r >= 240 && g >= 240 && b >= 240
}

/**
 * Run the pre-flight over a document.
 *
 * @param {object} doc        the design document
 * @param {object} [ctx]
 * @param {object} [ctx.kit]  brand kit (for prohibited claims)
 * @param {string} [ctx.prohibited]  newline/comma separated prohibited claims
 * @param {string} [ctx.listingCopy] listing title+bullets for the
 *        cross-surface consistency check
 * @param {number} [ctx.exportBytes] measured size of the exported file
 * @returns {{verdict, results, blocked, flagged, passed, ready, total, overrideable}}
 */
export function checkCompliance(doc, ctx = {}) {
  if (!doc || !doc.layers) {
    return { verdict: 'unknown', results: [], blocked: [], flagged: [], passed: [], ready: 0, total: 0, overrideable: true }
  }

  const fmt = formatById(doc.formatId) || null
  // The authoritative row for safe zones, allowed dimensions and media type is
  // the SPEC REGISTRY, not the presets list — a preset only knows its size.
  const specRow = SPEC_BY_ID[doc.formatId] || null
  const isVideo = (specRow?.media || doc.media) === 'video'
  const longest = Math.max(doc.w || 0, doc.h || 0)
  const isMain = doc.formatId === 'amz-main'
  const isAd = /ad/i.test(doc.channel || '') || /Ad/i.test(doc.family || '')
  const isAplus = /A\+/i.test(doc.channel || '')

  const textLayers = doc.layers.filter(l => l.kind === 'text' && l.visible !== false)
  const badgeLayers = doc.layers.filter(l => l.kind === 'badge' && l.visible !== false)
  const productLayers = doc.layers.filter(l => l.kind === 'product' && l.visible !== false)
  const shapeLayers = doc.layers.filter(l => l.kind === 'shape' && l.visible !== false)
  const bgLayer = doc.layers.find(l => l.kind === 'bg')

  const allText = textLayers.map(l => String(l.text || '')).join(' \u00b7 ')
  const headline = (textLayers.find(l => l.role === 'headline') || textLayers[0] || {}).text || ''
  const ctaLayer = badgeLayers[0]
  const cta = ctaLayer ? String(ctaLayer.text || '') : ''

  const results = []
  const staleRules = []
  // An empty canvas must never report green. `hasArtwork` is what separates a
  // real verdict from a vacuous one.
  const hasArtwork = doc.layers.some(l =>
    (l.kind === 'product' && l.visible !== false) ||
    (l.kind === 'image' && l.visible !== false) ||
    (l.kind === 'text' && String(l.text || '').trim().length > 0))
  const push = (ruleId, level, detail, statusOverride) => {
    const need = needsOf(ruleId)
    let status = statusOverride || 'checked'
    if (!statusOverride) {
      if (need === 'artwork' && !hasArtwork) status = 'needs-artwork'
      else if (need === 'export' && !ctx.exportBytes && !ctx.durationSeconds) status = 'needs-artwork'
      else if (need === 'human') status = 'needs-review'
    }
    // A rule whose input is missing can never report a green pass.
    const effective = status === 'checked' ? level : (status === 'needs-artwork' ? 'incomplete' : 'review')
    const rule = RULES_BY_ID[ruleId]
    // Policy freshness: a rule citing a source past its re-check date is
    // reported as needing re-verification, never presented as current.
    const fresh = rule?.source ? freshnessOf(rule.source) : null
    results.push({ ...rule, level: effective, rawLevel: level, status, need, detail, freshness: fresh })
    if (fresh && fresh.status === 'stale') staleRules.push({ id: ruleId, source: rule.source, age: fresh.age, limit: fresh.limit })
  }

  // ── size ──
  push('raster-range',
    longest >= 500 && longest <= 10000 ? 'pass' : 'block',
    `Rendered at ${doc.w}×${doc.h} (longest side ${longest} px).`)
  push('raster-zoom',
    longest > 1000 ? 'pass' : (longest >= 500 ? 'flag' : 'block'),
    longest > 1000
      ? `Longest side ${longest} px supports zoom.`
      : `Longest side ${longest} px is under Amazon\u2019s 1,000 px zoom preference.`)

  if (isAplus && fmt && fmt.module) {
    const ok = doc.w >= fmt.w && doc.h >= fmt.h
    push('aplus-module-size', ok ? 'pass' : 'block',
      ok
        ? `${fmt.w}×${fmt.h} meets the ${fmt.module} minimum.`
        : `${doc.w}×${doc.h} is below the ${fmt.module} minimum of ${fmt.w}×${fmt.h}.`)
  }

  push('no-animated-gif', 'pass', 'This studio exports PNG; animated GIF is never produced.')

  // ── MAIN image ──
  if (isMain) {
    // A background counts as white only when the fill is near-white, or when a
    // NON-EMPTY gradient exists and every stop is near-white. The previous
    // `(gradient || []).every(...)` evaluated to TRUE on an empty array, so any
    // background without a gradient passed regardless of its fill — a
    // suppression-class bug the fixture test caught.
    const grad = bgLayer && Array.isArray(bgLayer.gradient) ? bgLayer.gradient : []
    const gradOk = grad.length > 0 && grad.every(c => nearWhite(c))
    const bgOk = bgLayer ? (nearWhite(bgLayer.fill) || gradOk) : false
    push('main-white-bg', bgOk ? 'pass' : 'block',
      bgOk
        ? (nearWhite(bgLayer?.fill) ? 'Background layer is white.' : `Background gradient is white (${grad.join(' → ')}).`)
        : `Background is ${bgLayer?.fill || grad.join(' → ') || 'missing'} — the main image requires pure white RGB 255,255,255.`)

    const fill = productLayers.reduce((s, l) => s + ((l.w || 0) * (l.h || 0)), 0)
    const fillOk = fill >= 0.85
    push('main-fill', fillOk ? 'pass' : 'block',
      `Product occupies ${Math.round(fill * 100)}% of the frame (85% required).`)

    const overlays = [
      ...textLayers.map(l => `text "${String(l.text || '').slice(0, 24)}"`),
      ...badgeLayers.map(l => `badge "${String(l.text || '').slice(0, 24)}"`),
      ...shapeLayers.map(l => `${l.shape || 'shape'} block`),
    ]
    push('main-no-overlay', overlays.length ? 'block' : 'pass',
      overlays.length ? `Overlays present: ${overlays.join(', ')}.` : 'No text, logo, badge, colour block or border layers.')
  }

  // ── copy ──
  const capsBlock = isAd && isAllCaps(headline)
  push('caps-headline', capsBlock ? 'block' : 'pass',
    capsBlock ? 'Headline is ALL CAPS — rejected for self-service ad products.' : 'Headline case is acceptable.')

  const titleFlag = isAd && !isAllCaps(headline) && isTitleCase(headline)
  push('title-case', titleFlag ? 'flag' : 'pass',
    titleFlag ? 'Headline is Title Case; sentence case is expected for self-service ads.' : 'Not Title Case.')

  const punctBlock = /[!?]{2,}|[?!]{1,}[?!]{1,}/.test(headline) || (headline.match(/\.\.\./g) || []).length > 2
  push('pressure-punct', punctBlock ? 'block' : 'pass',
    punctBlock ? 'Repeated question/exclamation marks or more than two ellipses in the headline.' : 'Punctuation within limits.')

  const ctaBad = /[!?]$/.test(cta.trim())
  push('cta-end-punct', ctaBad ? 'block' : 'pass',
    ctaBad ? `Call to action ends in punctuation ("${cta}").` : (cta ? 'Call to action has no end punctuation.' : 'No CTA badge present.'))

  const specialBad = SPECIAL_CHAR_RE.some(re => re.test(allText))
  push('special-chars', specialBad ? 'block' : 'pass',
    specialBad ? 'Text contains numerals or symbols substituting for letters.' : 'No special-character substitution found.')

  const pressureHit = PRESSURE.find(p => allText.toLowerCase().includes(p))
  const markerCount = (allText.match(PRESSURE_MARKER_RE) || []).length
  const pressureFlag = !!pressureHit || (isAllCaps(headline) && markerCount > 0)
  push('pressure-language', pressureFlag ? 'flag' : 'pass',
    pressureFlag ? `Urgency/pressure pattern found${pressureHit ? `: "${pressureHit}"` : ''}.` : 'No urgency language detected.')

  const personalHit = /\byou\b|\byour\b/i.test(allText)
  push('personal-language', personalHit ? 'flag' : 'pass',
    personalHit ? 'Copy addresses the reader as "you"/"your" — Amazon flags this pattern.' : 'No personal address found.')

  // ── claims ──
  const lower = allText.toLowerCase()
  const supHit = SUPERIORITY.find(s => lower.includes(s))
  push('superiority', supHit ? 'block' : 'pass',
    supHit ? `Unsubstantiated superiority claim: "${supHit}".` : 'No superiority claim detected.')

  const competitors = String(ctx.competitors || '').split(/[,\n]/).map(s => s.trim().toLowerCase()).filter(Boolean)
  const compHit = competitors.find(c => c.length > 2 && lower.includes(c))
  push('competitor-named', compHit ? 'block' : 'pass',
    compHit ? `Competitor named in copy: "${compHit}".` : 'No competitor named.')

  const prohibited = String(ctx.prohibited || '').split(/[,\n]/).map(s => s.trim().toLowerCase()).filter(Boolean)
  const probHit = prohibited.find(p => p.length > 2 && lower.includes(p))
  push('brand-prohibited', probHit ? 'block' : 'pass',
    probHit ? `Claim on the brand\u2019s prohibited list: "${probHit}".` : 'No prohibited claim found.')

  push('text-on-image-legibility',
    textLayers.length ? 'pass' : 'flag',
    textLayers.length ? 'Text layers render as canvas vector text, never model-generated pixels.' : 'No text layers to assess.')

  push('image-text-not-indexed', 'flag',
    'Keyword-bearing text inside this image is not indexed by Amazon search — treat it as a legibility feature, not an SEO one.')

  // ── Phase 2 checks (2026-10-10) ─────────────────────────────────────────
  const isStore = /Store/i.test(doc.channel || '')
  // SB video is identified by its OWN spec row, not by the channel string —
  // SP video and Display video also live under "Amazon Ads" and must not be
  // checked against the SB rule set.
  const isSbv = isVideo && !!specRow && specRow.id.startsWith('sbv')

  if (isStore) {
    // Store safe zone: content-bearing layers must sit inside keepIn and clear
    // of every keepOut box. We test the centre point plus the box overlap.
    const zoneId = specRow?.safe || fmt?.safe
    const zones = zoneId ? SAFE_ZONES[zoneId] : null
    if (zones) {
      const content = [...textLayers, ...badgeLayers]
      const hits = []
      for (const l of content) {
        const cx = (l.x || 0) + (l.w || 0) / 2
        const cy = (l.y || 0) + (l.h || 0) / 2
        for (const z of zones.keepOut || []) {
          if (cx >= z.x && cx <= z.x + z.w && cy >= z.y && cy <= z.y + z.h) {
            hits.push(`"${String(l.text || l.kind).slice(0, 20)}" in ${z.label}`)
          }
        }
      }
      push('store-safe-zone', hits.length ? 'flag' : 'pass',
        hits.length ? `Content inside an obscured/cropped zone: ${hits.join('; ')}.` : `Content clears the ${zones.note}.`)
    } else {
      push('store-safe-zone', 'pass', 'No safe zone defined for this Store format.')
    }
    push('store-no-embedded-text', textLayers.length ? 'flag' : 'pass',
      textLayers.length
        ? `${textLayers.length} text layer(s) baked into the image. Amazon recommends the Image with text tile instead, because embedded text is unreadable by external search engines and screen readers.`
        : 'No embedded image text — use the Store text tile for copy.')
  }

  if (isSbv) {
    const v = AMAZON_CAPS.video
    const dur = Number(ctx.durationSeconds || 0)
    const allowedDims = specRow?.allowedDims || fmt?.allowedDims
    const dimOk = !allowedDims || allowedDims.some(([w, h]) => w === doc.w && h === doc.h)
    const durOk = dur ? (dur >= v.durationMin && dur <= v.durationMax) : null
    const bits = [
      `Dimensions ${doc.w}×${doc.h}${dimOk ? ' OK' : ' — not in the published set'}`,
      dur ? `duration ${dur}s${durOk ? ' OK' : ` — must be ${v.durationMin}-${v.durationMax}s`}` : 'duration not supplied',
      `formats ${v.formats.join('/')}, codecs ${v.codecs.join('/')}, ${v.videoBitrateMinMbps} Mbps+, audio ${v.audioBitrateMinKbps} kbps / ${(v.audioSampleMinHz / 1000).toFixed(1)} kHz`,
    ]
    push('sbv-video-spec', dimOk && durOk !== false ? 'pass' : (durOk === false || !dimOk ? 'block' : 'flag'), bits.join('; ') + '.')

    // 16:9 is the documented default. The 9:16 vertical is date-sensitive and
    // is a WARN, never a block.
    if (specRow && specRow.aspectDefault === false) {
      push('sbv-vertical-date-sensitive', 'flag',
        `${specRow.label} is not the default. The 16:9 square-pixel variant is documented as the standard; 9:16 appears in the Ads API guide and depends on campaign goal and surface availability. Source: ${SPEC_SOURCES[specRow.source]?.label || specRow.source} · ${specRow.source} · ${specRow.dateSensitive ? 'date-sensitive' : 'stable'}.`)
    } else {
      push('sbv-vertical-date-sensitive', 'pass', 'This is the documented default 16:9 aspect.')
    }

    const zones = specRow?.safe ? SAFE_ZONES[specRow.safe] : null
    const corner = (zones?.keepOut || []).find(z => /bottom-right/i.test(z.label))
    let inCorner = false
    if (corner) {
      inCorner = textLayers.some(l => {
        const cx = (l.x || 0) + (l.w || 0) / 2
        const cy = (l.y || 0) + (l.h || 0) / 2
        return cx >= corner.x && cy >= corner.y
      })
    }
    push('sbv-text-safe-area', inCorner ? 'flag' : 'pass',
      inCorner ? 'Text sits in the bottom-right corner, which Amazon prohibits for SB video.' : 'Text clears the prohibited bottom-right corner.')
  }

  // ── Non-SB video families: SP video and Display video ────────────────────
  // Each uses ITS OWN row's published figures. A durationMax of null means
  // "no published maximum" (SP video), which is not the same as zero.
  if (isVideo && !isSbv && specRow && (specRow.id === 'spv-video' || specRow.id === 'display-video')) {
    const row = specRow
    const dur = Number(ctx.durationSeconds || 0)
    const lo = row.durationMin ?? null
    const hi = row.durationMax ?? null
    const dimOk = !row.allowedDims || row.allowedDims.some(([w, h]) => w === doc.w && h === doc.h)
    const tooShort = lo != null && dur > 0 && dur < lo
    const tooLong = hi != null && dur > 0 && dur > hi
    const durOk = dur > 0 ? (!tooShort && !tooLong) : null
    const durText = hi == null
      ? `${lo}s minimum, no published maximum`
      : `${lo}-${hi}s`
    push('video-spec', (dimOk && durOk !== false) ? 'pass' : (dimOk ? 'block' : 'block'),
      `Dimensions ${doc.w}×${doc.h}${dimOk ? ' OK' : ` — published set is ${(row.allowedDims || [[row.w, row.h]]).map(d => d.join('x')).join(', ')}`}; ` +
      `duration ${dur ? `${dur}s` : 'not supplied'}${durOk === false ? ` — must be ${durText}` : ` (${durText})`}; ` +
      `formats ${(row.videoFormats || AMAZON_CAPS.video.formats).join('/')}` +
      `${row.videoBitrateMin ? `, ${row.videoBitrateMin} Mbps+ enforced` : ''}` +
      `${row.audioRemoved ? ', AUDIO IS REMOVED on this placement' : row.audioBitrateMin ? `, audio ${row.audioBitrateMin} kbps+ enforced` : ''}.`)

    // Reconcile where Amazon publishes two figures.
    if (row.videoBitrateFigures || row.audioBitrateFigures) {
      const fmtFig = (f) => `${f.value} (${f.source})`
      push('video-reconciled', 'pass',
        `Two Amazon figures recorded and the stricter enforced. ` +
        `Video bitrate: ${(row.videoBitrateFigures || []).map(fmtFig).join(' vs ')} → enforcing ${row.videoBitrateMin} Mbps. ` +
        `Audio bitrate: ${(row.audioBitrateFigures || []).map(fmtFig).join(' vs ')} → enforcing ${row.audioBitrateMin} kbps. ` +
        `${row.reconciliation ? 'Source defect noted: the display table repeats the "Minimum duration" label (6s, then 45s); read as min 6s / max 45s.' : ''}`)
    }

    if (row.audioRemoved) {
      push('video-audio-removed', 'pass',
        'Amazon documents that audio will be removed for this format, so an audio mix must not be mastered. Do not treat the absence of audio as a defect.')
    }
    if (row.productFrameMin != null) {
      const fill = productLayers.reduce((s, l) => s + ((l.w || 0) * (l.h || 0)), 0)
      const ok = fill >= row.productFrameMin
      push('video-product-frame', ok ? 'pass' : 'flag',
        `Product occupies ${Math.round(fill * 100)}% of the frame; Amazon requires ${Math.round(row.productFrameMin * 100)}% or more.`)
    }
  }

  // ── MAIN image: the full documented prohibition set ─────────────────────
  if (isMain) {
    // Entire product inside the frame.
    const outside = productLayers.filter(l =>
      (l.x ?? 0) < 0 || (l.y ?? 0) < 0 || ((l.x ?? 0) + (l.w ?? 0)) > 1.001 || ((l.y ?? 0) + (l.h ?? 0)) > 1.001)
    push('main-entire-product', outside.length ? 'block' : 'pass',
      outside.length
        ? `${outside.length} product layer(s) extend past the frame edge, so the product is cropped.`
        : 'Every product layer sits inside the frame.')

    // Shown once: the SAME product asset appearing twice.
    const ids = productLayers.map(l => l.assetId || l.artId || l.label || '').filter(Boolean)
    const dupes = ids.filter((v, i) => ids.indexOf(v) !== i)
    push('main-shown-once', dupes.length ? 'block' : 'pass',
      dupes.length
        ? `The same product appears ${dupes.length + 1} times ("${dupes[0]}"). The main image must show the product once.`
        : 'The product is not repeated.')

    const units = Number(doc.meta?.units || 1)
    push('main-single-unit', units > 1 ? 'flag' : 'pass',
      units > 1 ? `${units} units are shown. Only one unit plus included accessories is permitted.` : 'One unit.')

    const props = productLayers.filter(l => l.isProp)
    push('main-no-props', props.length ? 'flag' : 'pass',
      props.length ? `${props.length} layer(s) are marked as props that are not included with the product.` : 'No non-included props.')

    const packaging = productLayers.filter(l => l.isPackaging && !l.packagingIsFeature)
    if (packaging.length || doc.meta?.packagingShown) {
      push('main-no-packaging', 'flag',
        'Packaging is shown. That is only allowed when the packaging itself is a product feature (a consumable or collectible).')
    } else {
      push('main-no-packaging', 'pass', 'No packaging shown.')
    }

    push('main-no-mannequins', doc.meta?.mannequin ? 'flag' : 'pass',
      doc.meta?.mannequin ? 'A mannequin is recorded on this asset; mannequins are prohibited on the main image.' : 'No mannequin.')

    const amazonMark = /amazon'?s choice|best ?seller|#1 best seller|prime\b|amazon prime|top rated/i.test(allText)
    push('main-no-amazon-marks', amazonMark ? 'block' : 'pass',
      amazonMark ? 'Text references an Amazon badge or mark, which must not be placed on the image.' : 'No Amazon badges or marks.')
  }

  // ── ALL images: review, pricing and seller information ──────────────────
  {
    const reviewHit = /\b\d(\.\d)?\s*(out of 5|stars?|★)|★{2,}|\brated\s+\d|\b\d[\d,]*\s+reviews?\b/i.test(allText)
    push('all-no-review-imagery', reviewHit ? 'block' : 'pass',
      reviewHit ? 'Text references a star rating or review count, which must not be placed on an image.' : 'No review imagery or claims.')

    const priceHit = /[$£€]\s?\d|\b\d+% ?off\b|\bsave\s+\d|\bmsrp\b|\bwas\s+[$£€]|\bnow\s+[$£€]|\blimited[- ]time price\b/i.test(allText)
    push('all-no-pricing', priceHit ? 'block' : 'pass',
      priceHit ? 'Text contains a price or a savings claim. Price on an image goes stale and is treated as a claim.' : 'No pricing or savings claims.')

    const sellerHit = /https?:\/\/|www\.|\b[\w.+-]+@[\w-]+\.[\w.]+\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|(^|\s)@[A-Za-z0-9_]{2,}/i.test(allText)
    push('all-no-seller-info', sellerHit ? 'block' : 'pass',
      sellerHit ? 'Text contains a URL, email address, phone number or social handle.' : 'No seller or contact information.')
  }

  // ── Technical rules ─────────────────────────────────────────────────────
  {
    const dpi = Number(doc.meta?.dpi || (fmt && fmt.dpi) || 0)
    push('dpi-min-72', dpi ? (dpi >= 72 ? 'pass' : 'block') : 'pass',
      dpi ? `${dpi} dpi.` : 'Density defaults to at least 72 dpi on export.')

    const cs = String(doc.meta?.colorSpace || 'sRGB').toLowerCase()
    const rgbOk = cs === 'srgb' || cs === 'rgb'
    push('color-space-rgb', rgbOk ? 'pass' : 'block',
      rgbOk ? `Colour space ${cs}.` : `Colour space is ${cs}. Supply RGB; a CMYK file is converted and can shift colour.`)

    const fn = checkFilename(doc.meta?.filename || doc.filename)
    push('filename-pattern', fn.ok ? 'pass' : 'flag', fn.detail)
  }

  // ── AI-generated people disclosure ──────────────────────────────────────
  {
    const row = disclosureRow(doc)
    results.push(row)
  }

  // ── Product fidelity (reference lock + compositing) ─────────────────────
  {
    const mode = doc.meta?.fidelityMode || 'placed'
    const m = FIDELITY_MODE_BY_ID[mode]
    const hasRef = !!doc.meta?.referenceDataUrl
    const blocking = !m || m.blocking || (mode === 'locked' && !hasRef)
    const status = (!m || m.blocking) ? 'checked' : (mode === 'locked' ? (hasRef ? 'checked' : 'needs-artwork') : 'needs-review')
    const level = (!m || m.blocking) ? 'block' : (mode === 'locked' ? (hasRef ? 'flag' : 'incomplete') : 'review')
    results.push({
      id: 'product-fidelity',
      level,
      rawLevel: level,
      status: status === 'needs-artwork' ? 'needs-artwork' : status,
      need: 'artwork',
      label: 'Product region matches the locked reference',
      detail: !m
        ? `Unknown fidelity mode "${mode}". Export is blocked rather than assumed safe.`
        : m.blocking
          ? m.note
          : mode === 'locked'
            ? (hasRef
              ? 'Reference locked. The exported product region is diffed against the reference and export is blocked beyond the threshold.'
              : 'Fidelity is locked but no reference image is attached, so nothing can be diffed.')
            : m.note,
      source: 'operator policy / product image guide (accuracy)',
      accessed: '2026-10-10',
      dateSensitive: false,
    })
  }

  // A format with no captured source can never be exported. This is what stops
  // an SB spec from silently standing in for an SP placement.
  {
    const src = specRow ? SPEC_SOURCES[specRow.source] : null
    const unsourced = !!(specRow && (specRow.unsourced || !src || src.confidence === 'UNSOURCED'))
    push('spec-sourced', unsourced ? 'block' : 'pass',
      unsourced
        ? `${specRow.label}: no Amazon source has been recorded for this format, so export is refused rather than guessing a spec.`
        : `Specification sourced from ${src ? src.label : 'the registry'} (${specRow ? specRow.source : 'n/a'}) · ${specRow ? (specRow.dateSensitive ? 'date-sensitive' : 'stable') : 'not in the registry'}.`)
  }

  // AI disclosure: a document that flags synthetic people must carry the tag.
  const marksSynthetic = !!doc.meta?.syntheticPeople
  const hasTag = !!doc.meta?.syntheticPerformerTag
  if (marksSynthetic || hasTag) {
    // The document declares synthetic people, so the requirement IS decidable.
    push('ai-people-disclosure', hasTag ? 'pass' : 'flag',
      hasTag
        ? `Disclosure metadata will be written: ${AI_POLICY.syntheticPersonIptc.keyword} in ${AI_POLICY.syntheticPersonIptc.field}.`
        : `This document declares photorealistic AI people but the ${AI_POLICY.syntheticPersonIptc.keyword} tag is not set. Amazon may require disclosure.`,
      'checked')
  } else {
    push('ai-people-disclosure', 'flag',
      `If this asset contains photorealistic AI-generated people, Amazon requires the ${AI_POLICY.syntheticPersonIptc.keyword} tag (or the A+ upload checkbox). No people are declared on this document.`,
      'needs-review')
  }

  // Brand Registry: every generated mockup is marketing-only.
  push('brand-registry-not-a-mockup', 'flag',
    AI_POLICY.brandRegistryEnrollment.rule)

  // A+ specific: alt text and file size.
  if (isAplus) {
    const imgs = [...productLayers, ...shapeLayers].filter(l => l.kind === 'product')
    const missingAlt = (doc.meta?.altText ? false : true) || imgs.some(l => !l.altText && !doc.meta?.altText)
    push('aplus-alt-text', missingAlt ? 'block' : 'pass',
      missingAlt ? 'No alt text recorded for this A+ module. Alt text is required and must describe the image for screen readers.' : 'Alt text present.')
    const bytes = Number(ctx.exportBytes || 0)
    const tooBig = bytes > AMAZON_CAPS.aplus.maxBytes
    push('aplus-file-size', tooBig ? 'block' : 'pass',
      bytes ? (tooBig ? `Export is ${(bytes / 1048576).toFixed(2)} MB — A+ images must stay under 2 MB.` : `Export ${(bytes / 1048576).toFixed(2)} MB is within the 2 MB A+ cap.`) : 'File size not measured yet (measured at export).')
  }

  // Ad character caps.
  if (isAd) {
    const caps = AMAZON_CAPS.ads
    const over = []
    if (headline && headline.length > caps.headlineMaxChars) over.push(`headline ${headline.length}/${caps.headlineMaxChars}`)
    if (cta && cta.length >= caps.ctaMaxChars) over.push(`CTA ${cta.length}/${caps.ctaMaxChars - 1}`)
    push('ad-char-caps', over.length ? 'block' : 'pass',
      over.length ? `Over the published caps: ${over.join(', ')}.` : 'Headline and CTA are within the published caps.')
  }

  // ── cross-surface consistency ──
  if (ctx.listingCopy) {
    const listing = String(ctx.listingCopy).toLowerCase()
    // A blocking claim in the creative that does not appear on the detail page.
    const creativeClaims = headline.split(/[,;:—–-]/).map(s => s.trim()).filter(s => s.length > 8)
    const mismatch = creativeClaims.filter(c => !listing.includes(c.toLowerCase()))
    if (mismatch.length) {
      results.push({
        id: 'claim-parity', level: 'flag',
        label: 'Creative claim not found on the detail page',
        detail: `Amazon requires ad claims to be the same as on the detail page. Not found verbatim: ${mismatch.map(m => `"${m.slice(0, 40)}"`).join(', ')}.`,
        source: 'S403', accessed: ACCESSED, dateSensitive: true,
      })
    }
  }

  const blocked = results.filter(r => r.level === 'block')
  const flagged = results.filter(r => r.level === 'flag')
  const passed = results.filter(r => r.level === 'pass')
  // Coverage: a rule that could not be decided yet is NOT a pass. An empty
  // canvas therefore can never show green.
  const needsArtwork = results.filter(r => r.status === 'needs-artwork')
  const needsReview = results.filter(r => r.status === 'needs-review')

  const verdict = blocked.length ? 'block'
    : flagged.length ? 'flag'
      : (needsArtwork.length || needsReview.length) ? 'incomplete'
        : 'pass'

  return {
    verdict, results, blocked, flagged, passed, needsArtwork, needsReview,
    stale: staleRules,
    ready: passed.length,
    checked: results.length - needsArtwork.length - needsReview.length,
    total: results.length,
    hasArtwork,
    overrideable: true,
  }
}

/** Which rules are in scope for a given document (for the inspector panel). */
export function rulesInScope(doc) {
  if (!doc) return RULES
  const isMain = doc.formatId === 'amz-main'
  const isAd = /ad/i.test(doc.channel || '') || /Ad/i.test(doc.family || '')
  const isAplus = /A\+/i.test(doc.channel || '')
  const isStore = /Store/i.test(doc.channel || '')
  return RULES.filter(r =>
    r.scope === 'all' ||
    (r.scope === 'amz-main' && isMain) ||
    (r.scope === 'ads' && isAd) ||
    (r.scope === 'Amazon A+' && isAplus) ||
    (r.scope === 'Amazon Store' && isStore)
  )
}
