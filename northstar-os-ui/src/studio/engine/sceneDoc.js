// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — SCENE DOCUMENT BUILDER
// Turns a scene recipe + the operator's own product art + their own copy into
// a design document the shared renderer can paint and export. Deterministic
// and local: no photography is bundled, fetched, or implied.
// ═══════════════════════════════════════════════════════════════════════════

import { KIND, createDoc, layerId } from './doc.js'
import { sceneById } from './presets.js'

/**
 * @param {object} o
 * @param {string} o.sceneId       scene recipe id
 * @param {object} o.format        { id, label, w, h, channel }
 * @param {string} o.artId         asset id of the product cut-out (operator's own)
 * @param {object} [o.copy]        { headline, subhead, cta }
 * @param {object} [o.camera]      { yaw, pitch, tilt }
 * @param {object} [o.kit]         brand kit
 */
export function buildSceneDoc(o = {}) {
  const scene = sceneById(o.sceneId)
  const fmt = o.format || { id: 'meta-feed', label: 'Meta feed', w: 1080, h: 1080 }
  const doc = createDoc({
    name: `${scene.name} — ${fmt.label}`,
    w: fmt.w, h: fmt.h, kitId: o.kit?.id || 'kit-pine',
    channel: fmt.channel || '', family: 'Product scene',
  })
  doc.sceneId = scene.id
  doc.layers = [
    {
      id: layerId('BG'), kind: KIND.BG, name: 'Backdrop',
      gradient: scene.bg, sceneId: scene.id,
    },
  ]

  if (scene.backdrop === 'sweep' || scene.backdrop === 'surface') {
    doc.layers.push({
      id: layerId('SH'), kind: KIND.SHAPE, name: 'Surface', shape: 'ellipse',
      x: 0.08, y: 0.66, w: 0.84, h: 0.3, fill: scene.floor, opacity: 0.9,
    })
  }

  const cam = o.camera || {}
  const yaw = Number(cam.yaw ?? 0)
  const pitch = Number(cam.pitch ?? 0)
  const squash = Math.max(0.4, 1 - Math.max(0, pitch) / 190)
  const tilt = Math.max(-12, Math.min(12, yaw / 8))

  doc.layers.push({
    id: layerId('PR'), kind: KIND.PRODUCT, name: 'Product',
    assetId: o.artId || '', fit: 'contain',
    x: o.placement?.x ?? 0.24, y: o.placement?.y ?? 0.14,
    w: o.placement?.w ?? 0.52, h: o.placement?.h ?? 0.7,
    rot: tilt, squash, contactShadow: scene.backdrop !== 'flat',
  })

  if (o.copy?.headline) {
    doc.layers.push({
      id: layerId('TX'), kind: KIND.TEXT, name: 'Headline', role: 'headline',
      x: 0.06, y: 0.8, w: 0.88, h: 0.14,
      text: o.copy.headline, size: 0.055, weight: 700,
      color: o.kit?.ink || '#1a1a1a', align: 'center', uppercase: true,
    })
  }
  if (o.copy?.subhead) {
    doc.layers.push({
      id: layerId('TX'), kind: KIND.TEXT, name: 'Sub-head', role: 'subhead',
      x: 0.1, y: 0.92, w: 0.8, h: 0.06,
      text: o.copy.subhead, size: 0.028, weight: 400,
      color: o.kit?.ink || '#5a5a4a', align: 'center',
    })
  }
  return doc
}

/** Which scene layers a given `sceneId` produces — used for honest labelling. */
export function sceneLayerNames(sceneId) {
  const scene = sceneById(sceneId)
  const names = ['Backdrop gradient']
  if (scene.backdrop === 'sweep' || scene.backdrop === 'surface') names.push('Contact surface')
  names.push('Product (operator artwork)', 'Headline', 'Sub-head')
  return names
}
