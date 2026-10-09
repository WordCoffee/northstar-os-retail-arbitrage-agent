// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — AD CREATIVE BUILDER
// Turns operator-authored ad copy (headline, body, CTA) plus attached artwork
// into a design document rendered at each paid placement's own pixel size.
// This is what makes AdPilot's "Placements" a real creative renderer rather
// than an analytics table.
// ═══════════════════════════════════════════════════════════════════════════

import { KIND, createDoc, layerId } from './doc.js'
import { ALL_FORMATS, DEFAULT_BRAND_KITS } from './presets.js'

// Every paid placement the studio can render an ad creative for.
export const AD_PLACEMENTS = [
  { id: 'meta-feed', label: 'Meta feed', note: '1:1 in-feed, most common placement.' },
  { id: 'meta-story', label: 'Meta / Reels story', note: 'Full-screen vertical, safe zones matter.' },
  { id: 'google-display', label: 'Google display', note: 'Responsive display unit.' },
  { id: 'tiktok', label: 'TikTok', note: 'Vertical, top-view ad slot.' },
  { id: 'sponsored-brand', label: 'Sponsored brand', note: 'Headline + logo + product.' },
  { id: 'yt-thumb', label: 'YouTube thumbnail', note: '1280×720 preview card.' },
]

export function adFormat(id) {
  return ALL_FORMATS.find(f => f.id === id) || ALL_FORMATS[0]
}

/**
 * @param {object} o
 * @param {string} o.headline   operator-authored headline
 * @param {string} o.body       operator-authored body copy
 * @param {string} o.cta        operator-authored call to action
 * @param {string} o.placement  AD_PLACEMENTS id
 * @param {string} [o.assetId]  attached artwork from the local asset store
 * @param {object} [o.kit]      brand kit
 */
export function buildAdDoc(o = {}) {
  const kit = o.kit || DEFAULT_BRAND_KITS[0]
  const fmt = adFormat(o.placement)
  const doc = createDoc({
    name: `${fmt.label} ad creative`,
    w: fmt.w, h: fmt.h, kitId: kit.id, channel: fmt.channel, family: 'Ad creative',
  })

  const vertical = fmt.h > fmt.w
  const accent = kit.accent || '#c4941a'
  const ink = kit.ink || '#1a1a1a'
  const paper = kit.paper || '#f5f0e8'

  doc.layers = [
    { id: layerId('BG'), kind: KIND.BG, name: 'Backdrop', fill: paper },
    {
      id: layerId('SH'), kind: KIND.SHAPE, name: 'Accent block', shape: 'rect',
      x: 0, y: vertical ? 0.62 : 0.58, w: 1, h: vertical ? 0.38 : 0.42,
      fill: kit.palette?.[2] || '#1d4a1d',
    },
    {
      id: layerId('PR'), kind: o.assetId ? KIND.IMAGE : KIND.PRODUCT,
      name: 'Ad artwork', assetId: o.assetId || '', fit: 'cover', radius: 0.015,
      x: 0.04, y: 0.04, w: 0.92, h: vertical ? 0.34 : 0.32,
    },
    {
      id: layerId('TX'), kind: KIND.TEXT, name: 'Headline', role: 'headline',
      x: 0.06, y: vertical ? 0.4 : 0.36, w: 0.88, h: 0.13,
      text: o.headline || 'Ad headline', size: vertical ? 0.055 : 0.062,
      weight: 700, color: ink, align: 'left', uppercase: false,
    },
    {
      id: layerId('TX'), kind: KIND.TEXT, name: 'Body', role: 'subhead',
      x: 0.06, y: vertical ? 0.66 : 0.62, w: 0.88, h: 0.16,
      text: o.body || 'Supporting body copy.', size: 0.03,
      weight: 400, color: 'rgba(255,255,255,0.86)', align: 'left',
    },
  ]

  if (o.cta) {
    doc.layers.push({
      id: layerId('BD'), kind: KIND.BADGE, name: 'Call to action',
      x: 0.06, y: vertical ? 0.86 : 0.84, w: 0.34, h: 0.08,
      text: o.cta, fill: accent, color: paper, size: 0.026,
    })
  }

  doc.layers.push({
    id: layerId('TX'), kind: KIND.TEXT, name: 'Placement label', role: 'legal',
    x: 0.06, y: 0.955, w: 0.88, h: 0.028,
    text: `${fmt.label} · ${fmt.w}×${fmt.h} · local creative`,
    size: 0.018, weight: 500, color: 'rgba(255,255,255,0.6)', align: 'left',
  })

  return doc
}
