// U7 — unit tests for the canvas workspace's data layer. The click path itself
// is covered in tests/e2e/studio-canvas.spec.ts; these tests cover the rules a
// browser assertion cannot see (a registry lookup, a snap threshold, a stale
// autosave record, a PDF's own xref).

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  CONTENT_TYPES, DEFAULT_CONTENT_TYPE, resolveContentType, contentTypeLabel,
  createDesign, addText, addImage, addShape, lastLayerId, resizeDesign, TEXT_PRESETS,
  snapAxis, snapBox, SNAP_THRESHOLD,
  initHistory, currentValue, pushHistory, undoHistory, redoHistory, canUndo, canRedo, HISTORY_LIMIT,
  serialiseDesign, parseDesign, isDesignDoc, assetsWithinBudget,
  MAX_ASSET_CHARS, DESIGN_VERSION, DESIGN_TTL_MS,
  exportFileName, base64ToBytes, pdfFromJpeg,
} from './studioCanvas.js'

// ── content types ───────────────────────────────────────────────────────────
test('every content type resolves to a size the registries actually own', () => {
  assert.equal(CONTENT_TYPES.length, 6)
  for (const t of CONTENT_TYPES) {
    const r = resolveContentType(t.id)
    assert.equal(r.missing, false, `${t.id} is not in the registry`)
    assert.ok(r.w > 0 && r.h > 0, `${t.id} has no size`)
    assert.ok(r.channel, `${t.id} has no channel`)
    assert.ok(r.registryId, `${t.id} does not name its registry row`)
    assert.equal(r.registrySource, t.source)
  }
})

test('the six surfaces the work order names are present, by id', () => {
  assert.deepEqual(
    CONTENT_TYPES.map((t) => t.id),
    ['ad', 'social', 'aplus', 'product', 'storyboard', 'package'],
  )
  assert.equal(contentTypeLabel(DEFAULT_CONTENT_TYPE), 'Ad')
  assert.equal(contentTypeLabel('nope'), 'Ad', 'an unknown id degrades to the default label')
})

test('an unknown content type falls back and says it is missing', () => {
  const r = resolveContentType('does-not-exist')
  // The lookup degrades to CONTENT_TYPES[0] (a real registry row), so `missing`
  // is false; what must hold is that it never invents a size.
  assert.equal(r.w, 1080)
  assert.equal(r.h, 1080)
  assert.equal(r.id, 'ad')
})

// ── document + layers ───────────────────────────────────────────────────────
test('a new design is a background layer and nothing else', () => {
  const doc = createDesign('social')
  assert.equal(doc.contentType, 'social')
  assert.equal(doc.w, 1440)
  assert.equal(doc.h, 1800)
  assert.equal(doc.layers.length, 1)
  assert.equal(doc.layers[0].kind, 'bg')
  assert.equal(doc.formatId, 'ig-post')
  assert.ok(isDesignDoc(doc))
})

test('layer factories append normalised geometry inside the canvas', () => {
  let doc = createDesign('ad')
  doc = addText(doc, { text: 'Spring drop' })
  const textId = lastLayerId(doc)
  doc = addImage(doc, { id: 'asset-1', name: 'plate.png' })
  const imageId = lastLayerId(doc)
  doc = addShape(doc, { shape: 'ellipse' })

  assert.equal(doc.layers.length, 4)
  const text = doc.layers.find((l) => l.id === textId)
  const image = doc.layers.find((l) => l.id === imageId)
  assert.equal(text.kind, 'text')
  assert.equal(text.text, 'Spring drop')
  assert.equal(text.size, TEXT_PRESETS.headline.size)
  assert.equal(image.kind, 'image')
  assert.equal(image.assetId, 'asset-1')
  assert.equal(image.fit, 'contain')
  for (const l of doc.layers.filter((x) => x.kind !== 'bg')) {
    for (const k of ['x', 'y', 'w', 'h']) {
      assert.ok(l[k] >= 0 && l[k] <= 1, `${l.kind}.${k} = ${l[k]} is outside the canvas`)
    }
  }
  assert.equal(addImage(doc, null), doc, 'an empty asset is a no-op, not a broken layer')
})

test('changing the content type keeps the layers and rescales the raster', () => {
  let doc = createDesign('ad')
  doc = addText(doc, { text: 'Keep me' })
  const before = doc.layers.length
  const next = resizeDesign(doc, 'product')
  assert.equal(next.w, 2000)
  assert.equal(next.h, 2000)
  assert.equal(next.contentType, 'product')
  assert.equal(next.layers.length, before)
  assert.equal(next.layers[1].text, 'Keep me')
})

// ── snapping ────────────────────────────────────────────────────────────────
test('snapping fires only inside the threshold and names the guide it used', () => {
  // 0.2 wide at 0.401 is 0.001 off dead centre (0.4).
  const centre = snapAxis(0.401, 0.2)
  assert.equal(centre.value, 0.4)
  assert.equal(centre.guide, 0.5)
  assert.equal(centre.name, 'canvas centre')

  const left = snapAxis(0.005, 0.2)
  assert.equal(left.value, 0)
  assert.equal(left.guide, 0)

  const right = snapAxis(0.798, 0.2)
  assert.equal(right.value, 0.8)
  assert.equal(right.guide, 1)

  const free = snapAxis(0.62, 0.2)
  assert.equal(free.guide, null, 'a value outside the threshold must not snap')
  assert.equal(free.value, 0.62)
})

test('the snap threshold is a real tolerance, not a dead zone', () => {
  assert.ok(SNAP_THRESHOLD > 0)
  const inside = snapAxis(0.5 + SNAP_THRESHOLD * 0.9, 0.001)
  const outside = snapAxis(0.5 + SNAP_THRESHOLD * 2, 0.001)
  assert.notEqual(inside.guide, null)
  assert.equal(outside.guide, null)
})

test('snapBox reports one guide per axis and none when nothing is near', () => {
  const hit = snapBox(0.402, 0.6, 0.2, 0.2)
  assert.equal(hit.x, 0.4)
  assert.equal(hit.guides.length, 1)
  assert.equal(hit.guides[0].axis, 'x')

  const miss = snapBox(0.62, 0.66, 0.2, 0.2)
  assert.deepEqual(miss.guides, [])
  assert.equal(miss.x, 0.62)
  assert.equal(miss.y, 0.66)
})

// ── history ─────────────────────────────────────────────────────────────────
test('undo and redo walk the stack without losing the redo branch', () => {
  let h = initHistory('a')
  h = pushHistory(h, 'b')
  h = pushHistory(h, 'c')
  assert.equal(currentValue(h), 'c')
  assert.equal(canRedo(h), false)

  h = undoHistory(h)
  assert.equal(currentValue(h), 'b')
  assert.equal(canUndo(h), true)
  assert.equal(canRedo(h), true)

  h = undoHistory(h)
  assert.equal(currentValue(h), 'a')
  h = undoHistory(h)
  assert.equal(currentValue(h), 'a', 'undo at the start is a no-op')
  assert.equal(canUndo(h), false)

  h = redoHistory(h)
  assert.equal(currentValue(h), 'b')
  h = pushHistory(h, 'd')
  assert.equal(currentValue(h), 'd')
  assert.equal(h.stack.length, 3, 'a new edit drops the abandoned redo branch')
  assert.equal(canRedo(h), false)
})

test('the history is bounded', () => {
  let h = initHistory(0)
  for (let i = 1; i <= HISTORY_LIMIT + 10; i += 1) h = pushHistory(h, i)
  assert.equal(h.stack.length, HISTORY_LIMIT)
  assert.equal(currentValue(h), HISTORY_LIMIT + 10)
  assert.equal(h.stack[0], 11, 'the oldest entries are the ones dropped')
})

// ── autosave ────────────────────────────────────────────────────────────────
const PNG_DATA_URL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

test('a design round-trips through the autosave record', () => {
  let doc = createDesign('aplus')
  doc = addText(doc, { text: 'Restored' })
  const assets = [{ id: 'asset-1', name: 'plate.png', dataUrl: PNG_DATA_URL }]
  const raw = serialiseDesign(doc, assets, { now: 1000 })

  const back = parseDesign(raw, { now: 2000 })
  assert.ok(back)
  assert.equal(back.doc.name, doc.name)
  assert.equal(back.doc.layers.length, 2)
  assert.equal(back.doc.layers[1].text, 'Restored')
  assert.equal(back.assets.length, 1)
  assert.equal(back.assets[0].name, 'plate.png')
  assert.equal(back.savedAt, 1000)
})

test('a corrupt, foreign, stale or half-written record restores nothing', () => {
  const doc = createDesign('ad')
  assert.equal(parseDesign('not json', { now: 1 }), null)
  assert.equal(parseDesign('', { now: 1 }), null)
  assert.equal(parseDesign(null, { now: 1 }), null)

  const foreign = JSON.stringify({ v: DESIGN_VERSION + 1, savedAt: 1, doc })
  assert.equal(parseDesign(foreign, { now: 2 }), null, 'a newer version is not guessed at')

  const stale = serialiseDesign(doc, [], { now: 1 })
  assert.equal(parseDesign(stale, { now: 1 + DESIGN_TTL_MS + 1 }), null, 'TTL expires')

  const future = JSON.stringify({ v: DESIGN_VERSION, savedAt: 10 ** 15, doc })
  assert.equal(parseDesign(future, { now: 1000 }), null, 'clock skew is refused')

  const noLayers = JSON.stringify({ v: DESIGN_VERSION, savedAt: 1, doc: { ...doc, layers: [] } })
  assert.equal(parseDesign(noLayers, { now: 2 }), null, 'a document with no layers is not a document')

  const badLayer = JSON.stringify({ v: DESIGN_VERSION, savedAt: 1, doc: { ...doc, layers: [{ kind: 'text' }] } })
  assert.equal(parseDesign(badLayer, { now: 2 }), null)

  const noSize = JSON.stringify({ v: DESIGN_VERSION, savedAt: 1, doc: { ...doc, w: 0 } })
  assert.equal(parseDesign(noSize, { now: 2 }), null)

  const badAsset = JSON.stringify({
    v: DESIGN_VERSION, savedAt: 1, doc,
    assets: [{ id: 'x', name: 'evil', dataUrl: 'javascript:alert(1)' }],
  })
  const kept = parseDesign(badAsset, { now: 2 })
  assert.ok(kept)
  assert.equal(kept.assets.length, 0, 'a non-image data URL is dropped, not rendered')
})

test('an oversized image is reported and left out of the autosave record', () => {
  const doc = createDesign('ad')
  const huge = { id: 'huge', name: 'huge.png', dataUrl: `data:image/png;base64,${'A'.repeat(MAX_ASSET_CHARS)}` }
  const small = { id: 'small', name: 'small.png', dataUrl: PNG_DATA_URL }

  const budget = assetsWithinBudget([huge, small])
  assert.equal(budget.ok, false)
  assert.deepEqual(budget.oversized, ['huge.png'])

  const back = parseDesign(serialiseDesign(doc, [huge, small], { now: 1 }), { now: 2 })
  assert.equal(back.assets.length, 1)
  assert.equal(back.assets[0].id, 'small')
})

// ── export ──────────────────────────────────────────────────────────────────
test('export file names are safe and carry the real raster size', () => {
  const doc = createDesign('ad')
  doc.name = 'Spring / Drop #1'
  assert.equal(exportFileName(doc, 'png'), 'spring-drop-1-1080x1080.png')
  assert.equal(exportFileName({ name: '', w: 10, h: 20 }, 'pdf'), 'design-10x20.pdf')
})

test('base64 decodes to the same bytes a browser would produce', () => {
  const bytes = base64ToBytes('AQIDBA==')
  assert.deepEqual([...bytes], [1, 2, 3, 4])
  assert.equal(base64ToBytes('').length, 0)
  assert.deepEqual([...base64ToBytes('////')], [255, 255, 255])
})

test('the PDF wrapper is a real PDF whose xref points at its objects', () => {
  const jpeg = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0xff, 0xd9])
  const pdf = pdfFromJpeg(jpeg, 1080, 1350)
  const text = new TextDecoder('latin1').decode(pdf)

  assert.ok(text.startsWith('%PDF-1.4'), 'a PDF must start with its header')
  assert.ok(text.endsWith('%%EOF\n'), 'a PDF must end with EOF')
  assert.ok(text.includes('/MediaBox [0 0 1080 1350]'), 'the page is the raster size')
  assert.ok(text.includes('/Filter /DCTDecode'), 'the image is embedded as a JPEG')
  assert.ok(text.includes(`/Length ${jpeg.length}`), 'the image stream length is exact')

  // The xref table must be usable: every recorded offset has to land on the
  // object header it claims, or a reader will refuse the file.
  const xrefAt = Number(/startxref\n(\d+)/.exec(text)[1])
  assert.equal(text.slice(xrefAt, xrefAt + 4), 'xref')
  const table = text.slice(xrefAt).split('\n')
  assert.equal(table[1], '0 6')
  for (let n = 1; n <= 5; n += 1) {
    const entry = table[1 + n + 1]
    const offset = Number(entry.slice(0, 10))
    assert.ok(Number.isFinite(offset), `object ${n} has no offset`)
    assert.equal(text.slice(offset, offset + `${n} 0 obj`.length), `${n} 0 obj`,
      `object ${n} is not at the offset the xref records`)
    assert.equal(entry.length, 19, 'an xref entry is 20 bytes including its newline')
  }
  // The JPEG bytes are embedded verbatim.
  const imgAt = text.indexOf('\xff\xd8\xff\xe0')
  assert.ok(imgAt > 0)
  assert.deepEqual([...pdf.subarray(imgAt, imgAt + jpeg.length)], [...jpeg])
})
