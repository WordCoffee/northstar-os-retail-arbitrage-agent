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
import { SAFE_ZONES, AMAZON_CAPS, AI_POLICY, SPEC_BY_ID, SPEC_SOURCES } from './specRegistry.js'

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
  const isSbv = isVideo && /Ads/i.test(doc.channel || '')

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
    push('ai-people-disclosure', hasTag ? 'pass' : 'flag',
      hasTag
        ? `Disclosure metadata will be written: ${AI_POLICY.syntheticPersonIptc.keyword} in ${AI_POLICY.syntheticPersonIptc.field}.`
        : `This document declares photorealistic AI people but the ${AI_POLICY.syntheticPersonIptc.keyword} tag is not set. Amazon may require disclosure.`)
  } else {
    push('ai-people-disclosure', 'flag',
      `If this asset contains photorealistic AI-generated people, Amazon requires the ${AI_POLICY.syntheticPersonIptc.keyword} tag (or the A+ upload checkbox). No people are declared on this document.`)
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
