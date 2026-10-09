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
]

export const RULES_BY_ID = Object.fromEntries(RULES.map(r => [r.id, r]))

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
  const push = (ruleId, level, detail) => results.push({ ...RULES_BY_ID[ruleId], level, detail })

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
    const bgOk = bgLayer ? (nearWhite(bgLayer.fill) || (bgLayer.gradient || []).every(c => nearWhite(c))) : false
    push('main-white-bg', bgOk ? 'pass' : 'block',
      bgOk ? 'Background layer is white.' : `Background is ${bgLayer?.fill || (bgLayer?.gradradient || bgLayer?.gradient || []).join(' \u2192 ')} — the main image requires white.`)

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

  return {
    verdict: blocked.length ? 'block' : flagged.length ? 'flag' : 'pass',
    results, blocked, flagged, passed,
    ready: passed.length, total: results.length,
    overrideable: true,
  }
}

/** Which rules are in scope for a given document (for the inspector panel). */
export function rulesInScope(doc) {
  if (!doc) return RULES
  const isMain = doc.formatId === 'amz-main'
  const isAd = /ad/i.test(doc.channel || '') || /Ad/i.test(doc.family || '')
  return RULES.filter(r => r.scope === 'all' || (r.scope === 'amz-main' && isMain) || (r.scope === 'ads' && isAd))
}
