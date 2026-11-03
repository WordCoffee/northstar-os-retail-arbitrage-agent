// U7 — the Design Studio canvas workspace, as data.
//
// Everything a user can do to a canvas that does NOT need a browser lives here:
// the content-type table, layer factories, snapping, an undo history that is a
// plain value, the autosave record, and a real PDF wrapper. The workspace
// component is then mostly rendering, which is the part a click-path test
// covers and this file does not have to.
//
// Rules that matter:
//  • Content types resolve through the registries that already exist
//    (`presets.js` formats, `specRegistry.js` Amazon specs). No size is typed
//    twice, so a spec fix propagates and a click-path test can never pass on a
//    canvas whose size the registry does not know.
//  • Geometry stays normalised (0..1), the contract `engine/doc.js` already
//    renders at any raster size.
//  • Autosave is versioned, TTL'd and validated. A corrupt, stale or foreign
//    record restores nothing rather than half a document.
//  • The PDF is written here because one page and one image does not justify a
//    dependency; it is a real PDF 1.4 with a DCTDecode image, and the test
//    parses the xref rather than trusting the header.

import {
  KIND, addLayer, layerId, rescaleDoc, safeFileName,
} from '../studio/engine/doc.js'
import { formatById } from '../studio/engine/presets.js'
import { specById } from '../studio/engine/specRegistry.js'

// ── Content types ───────────────────────────────────────────────────────────
// The six surfaces the work order names, each mapped to a format or spec the
// repo already documents. `source` says which registry owns the number.
export const CONTENT_TYPES = [
  { id: 'ad', label: 'Ad', note: 'Paid social / display creative', source: 'format', formatId: 'meta-feed' },
  { id: 'social', label: 'Social post', note: 'Instagram portrait feed post', source: 'format', formatId: 'ig-post' },
  { id: 'aplus', label: 'A+ module', note: 'Premium A+ full-width module', source: 'spec', specId: 'aplus-premium-full' },
  { id: 'product', label: 'Product image', note: 'Amazon listing main image', source: 'spec', specId: 'amz-main' },
  { id: 'storyboard', label: 'Clip storyboard', note: '16:9 video frame', source: 'format', formatId: 'landscape-frame' },
  { id: 'package', label: 'Package panel', note: 'Print label / package face', source: 'format', formatId: 'print-label' },
]

export const DEFAULT_CONTENT_TYPE = 'ad'

/**
 * Resolve a content type to real dimensions. An entry whose registry row has
 * disappeared resolves to `missing: true` with a 1080 square, and the UI says
 * so, rather than silently inventing a size that looks authoritative.
 */
export function resolveContentType(id) {
  const type = CONTENT_TYPES.find((t) => t.id === id) || CONTENT_TYPES[0]
  const base = type.source === 'spec' ? specById(type.specId) : formatById(type.formatId)
  if (!base) {
    return { ...type, w: 1080, h: 1080, channel: 'Custom', family: '', registryId: type.formatId || type.specId, missing: true }
  }
  return {
    ...type,
    w: base.w,
    h: base.h,
    channel: base.channel || '',
    family: base.group || base.family || '',
    registryId: base.id,
    registrySource: type.source,
    note: type.note,
    missing: false,
  }
}

export function contentTypeLabel(id) {
  const t = CONTENT_TYPES.find((c) => c.id === id)
  return t ? t.label : CONTENT_TYPES[0].label
}

// ── Document + layer factories ──────────────────────────────────────────────
// A new design is a background layer and nothing else: the workspace never
// seeds headlines or stock images, so "create a design" means exactly that.
export function createDesign(contentTypeId = DEFAULT_CONTENT_TYPE, { name = '' } = {}) {
  const t = resolveContentType(contentTypeId)
  const doc = {
    id: `DOC-${Date.now().toString(36).toUpperCase()}`,
    name: name || t.label,
    contentType: t.id,
    formatId: t.registryId,
    channel: t.channel,
    family: t.family,
    kitId: 'kit-pine',
    w: t.w,
    h: t.h,
    layers: [{ id: layerId('BG'), kind: KIND.BG, name: 'Background', fill: '#f5f0e8' }],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  return doc
}

export const TEXT_PRESETS = {
  // The three defaults stack without overlapping a two-line headline: a new
  // document's first headline + subhead is a legible pair, not a pile.
  headline: { size: 0.09, weight: 700, h: 0.16, y: 0.1, w: 0.8, x: 0.1 },
  subhead: { size: 0.045, weight: 600, h: 0.09, y: 0.34, w: 0.8, x: 0.1 },
  body: { size: 0.03, weight: 400, h: 0.14, y: 0.5, w: 0.8, x: 0.1 },
}

export function addText(doc, { text = 'Your headline', preset = 'headline', color = '#1a1a1a' } = {}) {
  const p = TEXT_PRESETS[preset] || TEXT_PRESETS.headline
  return addLayer(doc, {
    id: layerId('L'),
    kind: KIND.TEXT,
    name: `Text: ${String(text).slice(0, 24)}`,
    text,
    role: preset,
    x: p.x, y: p.y, w: p.w, h: p.h,
    size: p.size, weight: p.weight, color, align: 'left', valign: 'top',
  })
}

/** The layer id of the most recently added layer (factories append). */
export function lastLayerId(doc) {
  return doc.layers.length ? doc.layers[doc.layers.length - 1].id : ''
}

export function addImage(doc, asset, { fit = 'contain' } = {}) {
  if (!asset || !asset.id) return doc
  return addLayer(doc, {
    id: layerId('L'),
    kind: KIND.IMAGE,
    assetId: asset.id,
    name: asset.name || 'Image',
    x: 0.14, y: 0.3, w: 0.72, h: 0.52,
    fit,
  })
}

export function addShape(doc, { shape = 'rect', fill = '#1d4a1d' } = {}) {
  const box = shape === 'line'
    ? { x: 0.15, y: 0.55, w: 0.7, h: 0.02 }
    : { x: 0.18, y: 0.18, w: 0.32, h: 0.32 }
  return addLayer(doc, {
    id: layerId('L'),
    kind: KIND.SHAPE,
    name: shape === 'line' ? 'Line' : shape === 'ellipse' ? 'Ellipse' : 'Rectangle',
    shape, fill, ...box,
  })
}

/** Changing the content type keeps the layers and rescales the raster. */
export function resizeDesign(doc, contentTypeId) {
  const t = resolveContentType(contentTypeId)
  return {
    ...rescaleDoc(doc, t.w, t.h),
    contentType: t.id,
    formatId: t.registryId,
    channel: t.channel,
    family: t.family,
  }
}

// ── Package panels (U8) ─────────────────────────────────────────────────────
// A document can hold several panels. `doc.layers` is always the ACTIVE panel;
// the others live in `doc.panelLayers`. Switching is a document change (so it is
// undoable and autosaved) but it never clears the history stack, and each panel
// keeps its own layer tree.
export const PANEL_IDS = ['front', 'back', 'gusset']

function blankPanel() {
  return [{ id: layerId('BG'), kind: KIND.BG, name: 'Background', fill: '#f5f0e8' }]
}

export function switchPanel(doc, panelId) {
  const current = doc.activePanel || 'front'
  if (!PANEL_IDS.includes(panelId) || panelId === current) return doc
  const panelLayers = { ...(doc.panelLayers || {}), [current]: doc.layers }
  const target = panelLayers[panelId]
  return {
    ...doc,
    activePanel: panelId,
    panelLayers,
    layers: Array.isArray(target) && target.length ? target : blankPanel(),
    updatedAt: new Date().toISOString(),
  }
}

/** How many layers each panel holds, for the switcher's labels. */
export function panelCounts(doc) {
  const active = doc.activePanel || 'front'
  const out = {}
  for (const id of PANEL_IDS) {
    const layers = id === active ? doc.layers : (doc.panelLayers || {})[id]
    out[id] = Array.isArray(layers) ? layers.length : 0
  }
  return out
}

// ── Snapping ────────────────────────────────────────────────────────────────
// Canva-style guides: an edge or a centre lines up with the canvas edge or the
// canvas centre. `snapAxis` returns the value it would use and which guide fired,
// so the UI can draw the line it actually snapped to (never a decorative one).
export const SNAP_THRESHOLD = 0.012
export const SNAP_TARGETS = [0, 0.5, 1]

export function snapAxis(start, size, { threshold = SNAP_THRESHOLD } = {}) {
  const s = Math.max(0.02, Math.min(1, Number(size) || 0))
  const v = Number(start) || 0
  const candidates = [
    { at: 0, guide: 0, name: 'canvas start' },
    { at: 1 - s, guide: 1, name: 'canvas end' },
    { at: 0.5 - s / 2, guide: 0.5, name: 'canvas centre' },
    { at: 0.5 - s, guide: 0.5, name: 'right edge to centre' },
    { at: 0.5, guide: 0.5, name: 'left edge to centre' },
  ]
  let best = null
  for (const c of candidates) {
    const d = Math.abs(v - c.at)
    if (d <= threshold && (!best || d < best.d)) best = { ...c, d }
  }
  return best ? { value: best.at, guide: best.guide, name: best.name } : { value: v, guide: null, name: '' }
}

/** Both axes at once, for a drag handler. */
export function snapBox(x, y, w, h, opts) {
  const sx = snapAxis(x, w, opts)
  const sy = snapAxis(y, h, opts)
  return {
    x: sx.value, y: sy.value,
    guides: [
      sx.guide === null ? null : { axis: 'x', at: sx.guide, name: sx.name },
      sy.guide === null ? null : { axis: 'y', at: sy.guide, name: sy.name },
    ].filter(Boolean),
  }
}

// ── Undo history as a plain value ───────────────────────────────────────────
// React state holds this object; no mutation, so a test can walk it directly.
export const HISTORY_LIMIT = 50

export function initHistory(value) {
  return { stack: [value], index: 0 }
}

export function currentValue(history) {
  return history.stack[history.index]
}

export function pushHistory(history, value, limit = HISTORY_LIMIT) {
  const stack = [...history.stack.slice(0, history.index + 1), value]
  const trimmed = stack.slice(-Math.max(1, limit))
  return { stack: trimmed, index: trimmed.length - 1 }
}

export function undoHistory(history) {
  return history.index > 0 ? { ...history, index: history.index - 1 } : history
}

export function redoHistory(history) {
  return history.index < history.stack.length - 1 ? { ...history, index: history.index + 1 } : history
}

export function canUndo(history) { return history.index > 0 }
export function canRedo(history) { return history.index < history.stack.length - 1 }

// ── Autosave record ─────────────────────────────────────────────────────────
export const DESIGN_STORE_KEY = 'ns-ds-canvas'
export const DESIGN_VERSION = 1
export const DESIGN_TTL_MS = 1000 * 60 * 60 * 24 * 14
// A data URL larger than this is placed but NOT written to autosave: silently
// dropping it from storage while claiming "saved" would be a false claim, so the
// workspace says which image will not survive a reload.
export const MAX_ASSET_CHARS = 2_500_000

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)

function isLayer(l) {
  return isPlainObject(l) && typeof l.id === 'string' && l.id.length > 0 && typeof l.kind === 'string'
}

export function isDesignDoc(doc) {
  if (!isPlainObject(doc)) return false
  if (typeof doc.id !== 'string' || !doc.id) return false
  if (!(Number(doc.w) > 0) || !(Number(doc.h) > 0)) return false
  if (!Array.isArray(doc.layers) || !doc.layers.length) return false
  return doc.layers.every(isLayer)
}

function isAsset(a) {
  return isPlainObject(a)
    && typeof a.id === 'string' && a.id.length > 0
    && typeof a.dataUrl === 'string' && a.dataUrl.startsWith('data:image/')
}

export function assetsWithinBudget(assets = []) {
  const oversized = []
  for (const a of assets) {
    if (!a || typeof a.dataUrl !== 'string') continue
    if (a.dataUrl.length > MAX_ASSET_CHARS) oversized.push(a.name || a.id)
  }
  return { ok: oversized.length === 0, oversized }
}

export function serialiseDesign(doc, assets = [], { now = Date.now() } = {}) {
  const kept = (Array.isArray(assets) ? assets : []).filter(isAsset)
  const { ok } = assetsWithinBudget(kept)
  const body = {
    v: DESIGN_VERSION,
    savedAt: now,
    doc,
    assets: ok ? kept : kept.filter((a) => a.dataUrl.length <= MAX_ASSET_CHARS),
  }
  return JSON.stringify(body)
}

export function parseDesign(raw, { now = Date.now(), ttlMs = DESIGN_TTL_MS } = {}) {
  if (typeof raw !== 'string' || !raw) return null
  let rec
  try { rec = JSON.parse(raw) } catch { return null }
  if (!isPlainObject(rec) || rec.v !== DESIGN_VERSION) return null
  if (typeof rec.savedAt !== 'number') return null
  if (ttlMs > 0 && now - rec.savedAt > ttlMs) return null
  if (rec.savedAt > now + 60_000) return null
  if (!isDesignDoc(rec.doc)) return null
  const assets = Array.isArray(rec.assets) ? rec.assets.filter(isAsset) : []
  return { doc: rec.doc, assets, savedAt: rec.savedAt }
}

// ── Export ──────────────────────────────────────────────────────────────────
export function exportFileName(doc, ext = 'png') {
  const base = safeFileName(doc && doc.name ? doc.name : 'design')
  const w = Math.max(1, Math.round(Number(doc && doc.w) || 0))
  const h = Math.max(1, Math.round(Number(doc && doc.h) || 0))
  return `${base}-${w}x${h}.${ext}`
}

export function base64ToBytes(b64) {
  const clean = String(b64 || '').replace(/[^A-Za-z0-9+/=]/g, '')
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4))
  let p = 0
  for (let i = 0; i < clean.length; i += 4) {
    const c0 = B64.indexOf(clean[i])
    const c1 = B64.indexOf(clean[i + 1])
    const c2 = B64.indexOf(clean[i + 2])
    const c3 = B64.indexOf(clean[i + 3])
    if (c0 < 0 || c1 < 0) break
    out[p++] = (c0 << 2) | (c1 >> 4)
    if (c2 >= 0) out[p++] = ((c1 & 15) << 4) | (c2 >> 2)
    if (c3 >= 0) out[p++] = ((c2 & 3) << 6) | c3
  }
  return out.subarray(0, p)
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

/**
 * A single-page PDF 1.4 that embeds a JPEG with /DCTDecode. Page geometry is
 * 1 pt per pixel (the PDF default 72 dpi), which the UI states.
 */
export function pdfFromJpeg(jpegBytes, width, height) {
  const w = Math.max(1, Math.round(Number(width) || 1))
  const h = Math.max(1, Math.round(Number(height) || 1))
  const img = jpegBytes instanceof Uint8Array ? jpegBytes : new Uint8Array(jpegBytes || [])
  const enc = new TextEncoder()
  const chunks = []
  const offsets = [0] // object 0 is the free head
  let length = 0
  const push = (part) => {
    const bytes = typeof part === 'string' ? enc.encode(part) : part
    chunks.push(bytes)
    length += bytes.length
  }
  const obj = (n, body) => {
    offsets[n] = length
    push(`${n} 0 obj\n${body}\nendobj\n`)
  }

  push('%PDF-1.4\n')
  obj(1, '<< /Type /Catalog /Pages 2 0 R >>')
  obj(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
  obj(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] `
    + '/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>')
  // The image stream is written in two parts so the byte length is exact.
  offsets[4] = length
  push(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} `
    + `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${img.length} >>\nstream\n`)
  push(img)
  push('\nendstream\nendobj\n')

  const content = `q\n${w} 0 0 ${h} 0 0 cm\n/Im0 Do\nQ\n`
  obj(5, `<< /Length ${enc.encode(content).length} >>\nstream\n${content}endstream`)

  const xrefAt = length
  let xref = 'xref\n0 6\n0000000000 65535 f \n'
  for (let n = 1; n <= 5; n += 1) {
    xref += `${String(offsets[n]).padStart(10, '0')} 00000 n \n`
  }
  push(xref)
  push(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`)

  const out = new Uint8Array(length)
  let at = 0
  for (const c of chunks) { out.set(c, at); at += c.length }
  return out
}

export default {
  CONTENT_TYPES,
  DEFAULT_CONTENT_TYPE,
  resolveContentType,
  createDesign,
  addText,
  addImage,
  addShape,
  resizeDesign,
  snapAxis,
  snapBox,
  initHistory,
  currentValue,
  pushHistory,
  undoHistory,
  redoHistory,
  canUndo,
  canRedo,
  serialiseDesign,
  parseDesign,
  assetsWithinBudget,
  exportFileName,
  base64ToBytes,
  pdfFromJpeg,
}
