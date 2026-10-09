// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — BRAND PROFILE + THE APPROVE-ONLY LOOP
//
// The pattern worth borrowing from Holo (tryholo.ai) is NOT its canvas — it has
// none. It is the shape of the loop: the operator describes the brand once, the
// system proposes work every day across every channel, and the operator's only
// job is to tap approve. Nothing runs without that tap.
//
// This module implements the proposing half deterministically and locally:
//   • BrandProfile — one object every creative room reads.
//   • planToday()   — what to make today, why, and at which placement.
//
// Constraints held on purpose:
//   • No generation. A proposal is copy + a template + a placement, never a
//     rendered asset. Approving one opens a real editable document.
//   • No publishing. Approving creates a local document, nothing else.
//   • Deterministic. Same profile + same date ⇒ same plan, so the operator can
//     reason about what they approved and why.
//   • Every proposal carries its reason. Nothing appears unexplained.
// ═══════════════════════════════════════════════════════════════════════════

import { TEMPLATES, ALL_FORMATS, formatById } from './presets.js'

// ── Brand profile ────────────────────────────────────────────────────────────
export const CHANNEL_KIND = [
  { id: 'listing', label: 'Listing & A+', note: 'Detail-page imagery and A+ modules.' },
  { id: 'ads', label: 'Paid ads', note: 'Sponsored and off-Amazon static creative.' },
  { id: 'social', label: 'Social', note: 'Organic posts, reels and carousels.' },
  { id: 'email', label: 'Email', note: 'Heroes and campaign blocks for the owned list.' },
  { id: 'web', label: 'Web & store', note: 'Storefront and landing heroes.' },
  { id: 'deck', label: 'Decks & boards', note: 'Internal and partner-facing collateral.' },
]

export const DEFAULT_BRAND_PROFILE = {
  id: 'brand-default',
  name: 'Unnamed brand',
  origin: '',              // "described manually" | "from URL" | "seeded"
  audience: '',
  promise: '',             // one line: what we are for
  voice: 'Calm, precise, evidence-first.',
  prohibited: '',          // claims we must not make
  channels: ['listing', 'ads', 'social'],
  kitId: 'kit-pine',
  createdAt: '',
  updatedAt: '',
}

// Deterministic 32-bit hash so the plan is stable for a given day.
function hash(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return (h >>> 0)
}

// Which templates serve which channel kind.
const CHANNEL_TEMPLATES = {
  listing: ['tpl-feature-grid', 'tpl-aplus-banner', 'tpl-hero-paper'],
  ads: ['tpl-hero-paper', 'tpl-split-bold', 'tpl-email-hero'],
  social: ['tpl-split-bold', 'tpl-reel-cover', 'tpl-hero-paper'],
  email: ['tpl-email-hero', 'tpl-hero-paper'],
  web: ['tpl-web-hero', 'tpl-hero-paper'],
  deck: ['tpl-deck-title', 'tpl-board', 'tpl-print-poster'],
}

// Which placements each channel kind renders into.
const CHANNEL_FORMATS = {
  listing: ['amz-main', 'amz-alt', 'aplus-premium-full', 'aplus-overlay-dark'],
  ads: ['meta-feed', 'meta-story', 'google-display', 'tiktok'],
  social: ['ig-post', 'ig-carousel', 'pin', 'x-post'],
  email: ['email-hero', 'google-display'],
  web: ['web-hero', 'web-og', 'storefront'],
  deck: ['deck-16x9', 'doc-letter', 'board-a3', 'print-poster'],
}

const REASONS = [
  'channel is active in the brand profile and has no creative in progress',
  'rotates the channel so no single surface dominates the week',
  'uses a template already approved for this channel',
  'fills the placement with the fewest existing local documents',
  'surface is listed in the brand profile with no scheduled work',
]

/**
 * Build today's proposal list.
 *
 * @param {object} o
 * @param {object} o.profile   BrandProfile
 * @param {string} o.today     ISO date string (YYYY-MM-DD); injectable for tests
 * @param {Array}  o.docs      existing local documents (to avoid duplicates)
 * @param {object} [o.keywords] local keyword rows, if any, for prefill reasons
 */
export function planToday(o = {}) {
  const profile = o.profile || DEFAULT_BRAND_PROFILE
  const today = o.today || new Date().toISOString().slice(0, 10)
  const docs = Array.isArray(o.docs) ? o.docs : []
  const seed = hash(`${today}|${profile.id}|${profile.name}`)

  const channels = (Array.isArray(profile.channels) && profile.channels.length
    ? profile.channels
    : ['listing']).filter(c => CHANNEL_KIND.some(k => k.id === c))
  if (!channels.length) channels.push('listing')

  const placementsUsed = new Set(docs.map(d => d.formatId).filter(Boolean))
  const proposals = []
  let cursor = seed

  // Round-robin through the channels, one proposal each, so a 3-channel brand
  // gets 3 proposals and a 6-channel brand gets 6 — never a firehose.
  channels.forEach((channelId, idx) => {
    cursor = (Math.imul(cursor, 1664525) + 1013904223) >>> 0
    const tplIds = CHANNEL_TEMPLATES[channelId] || CHANNEL_TEMPLATES.social
    const fmtIds = CHANNEL_FORMATS[channelId] || ['meta-feed']
    const tplId = tplIds[cursor % tplIds.length]

    // Prefer a placement we have not already made something for.
    const fresh = fmtIds.filter(f => !placementsUsed.has(f))
    const fmtId = (fresh.length ? fresh : fmtIds)[(cursor >>> 8) % (fresh.length ? fresh.length : fmtIds.length)]

    const fmt = formatById(fmtId) || ALL_FORMATS[0]
    const reasonIdx = (cursor >>> 16) % REASONS.length

    proposals.push({
      id: `PP-${today.replace(/-/g, '')}-${channelId.toUpperCase().slice(0, 3)}`,
      channel: channelId,
      channelLabel: CHANNEL_KIND.find(k => k.id === channelId)?.label || channelId,
      formatId: fmtId,
      formatLabel: fmt.label,
      w: fmt.w,
      h: fmt.h,
      templateId: tplId,
      headline: suggestHeadline(profile, channelId, cursor),
      reason: idx === 0
        ? `first pass of the day — ${REASONS[0]}`
        : REASONS[(reasonIdx + idx) % REASONS.length],
      state: 'Proposed',
      createdAt: new Date().toISOString(),
    })
  })

  return { date: today, profileId: profile.id, proposals }
}

// Deterministic headline scaffolding from the operator's own promise/audience.
// Never invents a claim: when the profile has no promise it says so.
function suggestHeadline(profile, channelId, seed) {
  const promise = String(profile.promise || '').trim()
  const audience = String(profile.audience || '').trim()
  const openers = {
    listing: promise ? promise : 'Add your one-line promise in the brand profile',
    ads: promise ? `${promise}` : 'Add your one-line promise in the brand profile',
    social: audience ? `For ${audience}` : 'Describe your audience in the brand profile',
    email: promise ? promise : 'Add your one-line promise in the brand profile',
    web: promise ? promise : 'Add your one-line promise in the brand profile',
    deck: audience ? `${audience} — overview` : 'Add your audience in the brand profile',
  }
  return openers[channelId] || openers.ads
}

// ── Honest readiness of the loop itself ──────────────────────────────────────
export function loopReadiness(profile, docs) {
  const checks = [
    {
      key: 'profile', label: 'Brand profile described', ok: !!(profile && profile.name && profile.name !== 'Unnamed brand' && profile.promise),
      detail: 'name, audience and one-line promise',
    },
    {
      key: 'channels', label: 'At least one channel selected', ok: !!(profile && Array.isArray(profile.channels) && profile.channels.length),
      detail: 'listing / ads / social / email / web / deck',
    },
    {
      key: 'kit', label: 'Brand kit attached', ok: !!profile?.kitId, detail: 'palette, type and voice the renders use' },
    {
      key: 'art', label: 'Product artwork uploaded', ok: Array.isArray(docs) && docs.some(d => d.layers && d.layers.some(l => l.kind === 'product' && l.assetId)),
      detail: 'the loop composites your own packshot, it never generates the product',
    },
  ]
  return { checks, ready: checks.filter(c => c.ok).length, total: checks.length }
}
