// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — SOCIAL PREVIEW BUILDER
// Turns an operator-authored post (hook, caption, platform, attached artwork)
// into a design document the shared renderer paints at the platform's own
// aspect ratio. The preview is a REAL render of the operator's own copy — not a
// styled text box, and never a fabricated image.
// ═══════════════════════════════════════════════════════════════════════════

import { KIND, createDoc, layerId } from './doc.js'
import { ALL_FORMATS, DEFAULT_BRAND_KITS } from './presets.js'

// Platform -> the studio output format whose aspect ratio matches it.
export const PLATFORM_FORMAT = {
  'TikTok': 'tiktok',
  'Instagram Reels': 'meta-story',
  'Stories': 'meta-story',
  'X Thread': 'x-post',
  'Pinterest': 'pin',
  'YouTube Shorts': 'reel-frame',
  'Email': 'google-display',
}

export function formatForPlatform(platform) {
  const id = PLATFORM_FORMAT[platform] || 'meta-story'
  return ALL_FORMATS.find(f => f.id === id) || ALL_FORMATS[0]
}

/**
 * Build the preview document for a social post.
 *
 * @param {object} o
 * @param {string} o.hook       operator-authored hook / title
 * @param {string} o.caption    operator-authored caption
 * @param {string} o.platform   platform label (resolves the output format)
 * @param {string} [o.assetId]  attached artwork from the local asset store
 * @param {object} [o.kit]      brand kit
 * @param {string} [o.badge]    optional overlay badge text
 */
export function buildSocialDoc(o = {}) {
  const kit = o.kit || DEFAULT_BRAND_KITS[0]
  const fmt = formatForPlatform(o.platform)
  const doc = createDoc({
    name: `${o.platform || 'Post'} preview`,
    w: fmt.w, h: fmt.h, kitId: kit.id, channel: fmt.channel, family: 'Social preview',
  })

  const dark = kit.paper && isDarkish(kit.paper)
  const ink = kit.ink || '#1a1a1a'
  const paper = kit.paper || '#f5f0e8'
  const vertical = fmt.h > fmt.w

  doc.layers = [
    { id: layerId('BG'), kind: KIND.BG, name: 'Backdrop', fill: paper },
    {
      id: layerId('SH'), kind: KIND.SHAPE, name: 'Brand band', shape: 'rect',
      x: 0, y: vertical ? 0.7 : 0.74, w: 1, h: vertical ? 0.3 : 0.26,
      fill: kit.palette?.[2] || '#1d4a1d', radius: 0,
    },
  ]

  // Artwork occupies the upper region; copy sits in the brand band below.
  doc.layers.push({
    id: layerId('IM'), kind: o.assetId ? KIND.IMAGE : KIND.PRODUCT, name: 'Attached artwork',
    assetId: o.assetId || '', fit: 'cover', radius: 0.02,
    x: 0.06, y: 0.06, w: 0.88, h: vertical ? 0.42 : 0.4,
  })

  doc.layers.push({
    id: layerId('TX'), kind: KIND.TEXT, name: 'Hook', role: 'headline',
    x: 0.08, y: vertical ? 0.53 : 0.5, w: 0.84, h: 0.13,
    text: o.hook || 'Hook / title', size: vertical ? 0.052 : 0.058,
    weight: 700, color: dark ? paper : ink, align: 'left', uppercase: true,
  })

  doc.layers.push({
    id: layerId('TX'), kind: KIND.TEXT, name: 'Caption', role: 'subhead',
    x: 0.08, y: vertical ? 0.66 : 0.63, w: 0.84, h: 0.2,
    text: o.caption || 'Caption preview', size: 0.03,
    weight: 400, color: dark ? 'rgba(255,255,255,0.82)' : 'rgba(255,255,255,0.86)', align: 'left',
  })

  if (o.badge) {
    doc.layers.push({
      id: layerId('BD'), kind: KIND.BADGE, name: 'Badge',
      x: 0.08, y: vertical ? 0.86 : 0.84, w: 0.3, h: 0.07,
      text: o.badge, fill: kit.accent, color: paper, size: 0.024,
    })
  }

  doc.layers.push({
    id: layerId('TX'), kind: KIND.TEXT, name: 'Platform label', role: 'legal',
    x: 0.08, y: vertical ? 0.955 : 0.95, w: 0.84, h: 0.03,
    text: `${fmt.label} · ${fmt.w}×${fmt.h} · local preview`, size: 0.019,
    weight: 500, color: dark ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.6)', align: 'left',
  })

  return doc
}

function isDarkish(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim())
  if (!m) return false
  const n = parseInt(m[1], 16)
  return ((n >> 16) & 255) * 0.299 + ((n >> 8) & 255) * 0.587 + (n & 255) * 0.114 < 140
}
