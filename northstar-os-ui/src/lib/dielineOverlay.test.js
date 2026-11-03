// U8 — package panels and the dieline overlay. The overlay is the part that must
// not lie: a guide drawn for the wrong panel, or a panel that silently forgets
// its layers, would be worse than no overlay at all.

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  PANELS, GUIDE_KINDS, PX_PER_MM, panelLabel, panelRect, panelSize,
  guidesForPanel, describeOverlay,
} from './dielineOverlay.js'
import {
  createDesign, addText, switchPanel, panelCounts, lastLayerId, isDesignDoc,
} from './studioCanvas.js'

// A geometry payload shaped exactly like the print lane's build meta.
const GEOMETRY = {
  template: 'doypack',
  title: 'Doypack 150x210mm + 40mm gusset',
  width_mm: 168,
  height_mm: 486,
  bleed_mm: 3,
  safe_mm: 4,
  confidence: 'planning dieline - not a die',
  panels: {
    front: [10, 100, 150, 210],
    back: [10, 320, 150, 210],
    gusset: [10, 240, 150, 40],
  },
  guides: {
    trim: [{ kind: 'rect', x: 10, y: 100, w: 150, h: 210, layer: 'trim' }],
    bleed: [{ kind: 'rect', x: 7, y: 97, w: 156, h: 216, layer: 'bleed' }],
    safe: [{ kind: 'rect', x: 14, y: 104, w: 142, h: 202, layer: 'safe' }],
    fold: [{ kind: 'line', x1: 10, y1: 240, x2: 160, y2: 240, layer: 'fold' }],
  },
}

test('the panel table is the one the work order names', () => {
  assert.deepEqual(PANELS.map((p) => p.id), ['front', 'back', 'gusset'])
  assert.equal(panelLabel('back'), 'Rear')
  assert.equal(panelLabel('nope'), 'Front')
})

test('a panel box comes from the dieline, never from a guess', () => {
  assert.deepEqual(panelRect(GEOMETRY, 'front'), [10, 100, 150, 210])
  assert.equal(panelRect(GEOMETRY, 'sideways'), null)
  assert.equal(panelRect({ panels: { front: [0, 0, 0, 10] } }, 'front'), null, 'a zero-width panel is not a panel')
  assert.equal(panelRect(null, 'front'), null)
})

test('the artboard takes the panel size at the declared scale', () => {
  const size = panelSize(GEOMETRY, 'front')
  assert.equal(size.w, 150 * PX_PER_MM)
  assert.equal(size.h, 210 * PX_PER_MM)
  assert.deepEqual(size.mm, { w: 150, h: 210 })
  assert.equal(panelSize(GEOMETRY, 'sideways'), null)
})

test('guides are normalised to the panel, not the sheet', () => {
  const { rects, lines } = guidesForPanel(GEOMETRY, 'front')
  const trim = rects.find((r) => r.kind === 'trim')
  assert.deepEqual(trim, { kind: 'trim', x: 0, y: 0, w: 1, h: 1 })

  // The bleed extends 3mm past the trim on every side; clipped to the panel.
  const bleed = rects.find((r) => r.kind === 'bleed')
  assert.equal(bleed.x, 0)
  assert.equal(bleed.y, 0)
  assert.equal(bleed.w, 1)
  assert.equal(bleed.h, 1)

  // The safe zone is inset 4mm: 4/150 and 4/210 of the panel.
  const safe = rects.find((r) => r.kind === 'safe')
  assert.ok(Math.abs(safe.x - 4 / 150) < 1e-9)
  assert.ok(Math.abs(safe.y - 4 / 210) < 1e-9)
  assert.ok(Math.abs(safe.w - 142 / 150) < 1e-9)
  assert.ok(Math.abs(safe.h - 202 / 210) < 1e-9)

  // The fold line (y=240) sits 140mm down the front panel's box, so within the
  // front panel it lands at 140/210 of the height.
  assert.equal(lines.length, 1)
  assert.equal(lines[0].kind, 'fold')
  assert.ok(Math.abs(lines[0].y1 - 140 / 210) < 1e-9)
  assert.ok(Math.abs(lines[0].y2 - 140 / 210) < 1e-9)
})

test('the rear panel gets its own guides, not the front one\'s', () => {
  const back = guidesForPanel(GEOMETRY, 'back')
  const trim = back.rects.find((r) => r.kind === 'trim')
  // The trim rect only covers the front panel, so on the rear panel it clamps to
  // a zero-height band and is dropped rather than drawn somewhere false.
  assert.equal(trim, undefined)
  const fold = back.lines.find((l) => l.kind === 'fold')
  assert.ok(fold, 'the fold line above the rear panel still draws')
  assert.ok(Math.abs(fold.y1 - (240 - 320) / 210) < 1e-9 || fold.y1 === 0)
})

test('guide kinds can be switched off without touching the rest', () => {
  const only = guidesForPanel(GEOMETRY, 'front', { kinds: ['safe'] })
  assert.deepEqual(only.rects.map((r) => r.kind), ['safe'])
  assert.equal(only.lines.length, 0)
  assert.equal(GUIDE_KINDS.length, 4)
  assert.deepEqual(GUIDE_KINDS.map((k) => k.id), ['bleed', 'trim', 'fold', 'safe'])
})

test('describeOverlay says what is drawn and from where', () => {
  assert.match(describeOverlay(GEOMETRY, 'front'), /Doypack/)
  assert.match(describeOverlay(GEOMETRY, 'front'), /150x210 mm/)
  assert.equal(describeOverlay(null, 'front'), 'No dieline loaded.')
  assert.match(describeOverlay({ panels: {} }, 'front'), /no front panel/)
})

// ── panels in the document ─────────────────────────────────────────────────
test('switching panels keeps each panel\'s own layers', () => {
  let doc = createDesign('package')
  doc = addText(doc, { text: 'Front headline' })
  const frontId = lastLayerId(doc)

  const rear = switchPanel(doc, 'back')
  assert.equal(rear.activePanel, 'back')
  assert.equal(rear.layers.length, 1, 'the rear panel starts with its own background')
  assert.notEqual(rear.layers[0].id, doc.layers[0].id, 'a fresh background, not the front one')

  const withRear = addText(rear, { text: 'Rear copy' })
  assert.equal(withRear.layers.length, 2)

  const backToFront = switchPanel(withRear, 'front')
  assert.equal(backToFront.activePanel, 'front')
  assert.equal(backToFront.layers.length, 2, 'the front still has its background + headline')
  assert.equal(backToFront.layers[1].id, frontId)
  assert.equal(backToFront.layers[1].text, 'Front headline')

  // And the rear survived the round trip.
  const rearAgain = switchPanel(backToFront, 'back')
  assert.equal(rearAgain.layers[1].text, 'Rear copy')
  assert.deepEqual(panelCounts(rearAgain), { front: 2, back: 2, gusset: 0 })
})

test('switching to the panel you are on, or to an unknown panel, is a no-op', () => {
  const doc = createDesign('package')
  assert.equal(switchPanel(doc, 'front'), doc)
  assert.equal(switchPanel(doc, 'lid'), doc)
})

test('the document still passes the autosave validator after a switch', () => {
  let doc = createDesign('package')
  doc = addText(doc, { text: 'Front' })
  doc = switchPanel(doc, 'back')
  assert.equal(isDesignDoc(doc), true)
  assert.equal(doc.panelLayers.front.length, 2)
})
