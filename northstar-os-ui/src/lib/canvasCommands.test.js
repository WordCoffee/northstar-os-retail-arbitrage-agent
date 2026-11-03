// U8 — the canvas instruction layer. The sentences below are the shapes a
// person actually types at Bojo; the assertions are about what the canvas does
// with them, and (just as important) what it refuses to do.

import test from 'node:test'
import assert from 'node:assert/strict'

import { parseInstruction, applyInstruction, describeCanvas, SCALE_STEP, TEXT_MAX } from './canvasCommands.js'
import { createDesign, addText, addImage, lastLayerId } from './studioCanvas.js'

function headlineDoc(text = 'Spring drop') {
  let doc = createDesign('ad')
  doc = addText(doc, { text, preset: 'headline' })
  return { doc, id: lastLayerId(doc) }
}

test('a sentence that is not a canvas instruction is refused, not approximated', () => {
  for (const s of ['', '   ', 'what is my ROI on this ASIN?', 'write me a listing']) {
    assert.equal(parseInstruction(s), null, `"${s}" must not parse as a canvas edit`)
  }
})

test('"make the headline bigger" scales exactly the headline', () => {
  const { doc, id } = headlineDoc()
  const parsed = parseInstruction('make the headline bigger')
  assert.equal(parsed.op, 'scale_text')
  assert.equal(parsed.role, 'headline')
  assert.equal(parsed.factor, SCALE_STEP)

  const out = applyInstruction(doc, parsed)
  assert.equal(out.ok, true)
  const layer = out.doc.layers.find((l) => l.id === id)
  const before = doc.layers.find((l) => l.id === id)
  assert.ok(layer.size > before.size)
  assert.equal(layer.size, before.size * (1 + SCALE_STEP))
  assert.match(out.summary, /20% bigger/)
})

test('an explicit percentage is honoured and clamped to the canvas limit', () => {
  const { doc } = headlineDoc()
  const out = applyInstruction(doc, parseInstruction('make the headline 50% bigger'))
  const layer = out.doc.layers.find((l) => l.kind === 'text')
  assert.ok(layer.size <= TEXT_MAX)

  let big = doc
  for (let i = 0; i < 20; i += 1) big = applyInstruction(big, parseInstruction('make the headline 50% bigger')).doc
  const capped = big.layers.find((l) => l.kind === 'text').size
  assert.equal(capped, TEXT_MAX, 'the canvas limit is a real ceiling')

  const again = applyInstruction(big, parseInstruction('make the headline bigger'))
  assert.equal(again.ok, false, 'a no-op at the ceiling is refused, not reported as done')
  assert.match(again.error, /already at the largest size/)
})

test('"make it smaller" only applies to the selected text layer', () => {
  const { doc, id } = headlineDoc()
  const parsed = parseInstruction('make the selected layer smaller')
  assert.equal(parsed.op, 'scale_text')
  assert.equal(parsed.selected, true)

  const refused = applyInstruction(doc, parsed, { selected: '' })
  assert.equal(refused.ok, false)
  assert.match(refused.error, /No text layer is selected/)

  const out = applyInstruction(doc, parsed, { selected: id })
  assert.equal(out.ok, true)
  assert.ok(out.doc.layers.find((l) => l.id === id).size < doc.layers.find((l) => l.id === id).size)
})

test('"set the headline to ..." keeps the operator words and touches nothing else', () => {
  const { doc, id } = headlineDoc('Old words')
  const parsed = parseInstruction('set the headline to Peak Potency, 6 oz')
  assert.equal(parsed.op, 'set_text')
  assert.equal(parsed.text, 'Peak Potency, 6 oz')

  const out = applyInstruction(doc, parsed)
  assert.equal(out.ok, true)
  assert.equal(out.doc.layers.find((l) => l.id === id).text, 'Peak Potency, 6 oz')
  assert.equal(out.doc.layers.length, doc.layers.length, 'no layer is added or removed')
  assert.equal(out.doc.w, doc.w)
  assert.equal(out.doc.h, doc.h)
})

test('a text instruction with no matching layer says what is missing', () => {
  const doc = createDesign('ad')
  const out = applyInstruction(doc, parseInstruction('make the headline bigger'))
  assert.equal(out.ok, false)
  assert.match(out.error, /no headline layer/i)
  assert.equal(out.doc, doc, 'a refusal returns the untouched document')
})

test('"add a headline saying ..." adds one layer with that text', () => {
  const doc = createDesign('social')
  const out = applyInstruction(doc, parseInstruction('add a headline saying Fresh stock'))
  assert.equal(out.ok, true)
  assert.equal(out.doc.layers.length, 2)
  const added = out.doc.layers[1]
  assert.equal(added.kind, 'text')
  assert.equal(added.text, 'Fresh stock')
  assert.equal(out.layerId, added.id)
})

test('"swap in the cutout" resolves an asset by name and refuses an unknown one', () => {
  let doc = createDesign('ad')
  doc = addImage(doc, { id: 'A-1', name: 'plate.png' })
  const imageId = lastLayerId(doc)
  const assets = [{ id: 'A-1', name: 'plate.png' }, { id: 'A-2', name: 'cutout.png' }]

  const parsed = parseInstruction('swap in the cutout')
  assert.equal(parsed.op, 'swap_asset')

  const out = applyInstruction(doc, parsed, { assets })
  assert.equal(out.ok, true)
  assert.equal(out.doc.layers.find((l) => l.id === imageId).assetId, 'A-2')

  const miss = applyInstruction(doc, parseInstruction('swap in the moon photo'), { assets })
  assert.equal(miss.ok, false)
  assert.match(miss.error, /No asset matches/)
})

test('"select the ..." selects by role and refuses an absent layer', () => {
  const { doc, id } = headlineDoc()
  const out = applyInstruction(doc, parseInstruction('select the headline'))
  assert.equal(out.ok, true)
  assert.equal(out.layerId, id)
  assert.equal(out.doc, doc, 'selection is not a document change')

  const miss = applyInstruction(doc, parseInstruction('select the image'))
  assert.equal(miss.ok, false)
})

test('describeCanvas is what Bojo is told: layers, text, sizes, assets', () => {
  let doc = createDesign('package')
  doc = addText(doc, { text: 'Peak Potency', preset: 'headline' })
  const imageId = lastLayerId(doc)
  doc = addImage(doc, { id: 'A-9', name: 'front.png' })

  const view = describeCanvas(doc, { selected: imageId, assets: [{ id: 'A-9', name: 'front.png' }] })
  assert.equal(view.contentType, 'package')
  assert.equal(view.w, 1275)
  assert.equal(view.h, 1650)
  assert.equal(view.selected, imageId)
  assert.equal(view.layers.length, 3)
  assert.equal(view.layers[1].text, 'Peak Potency')
  assert.equal(view.layers[1].role, 'headline')
  assert.deepEqual(view.assets, [{ id: 'A-9', name: 'front.png' }])
  assert.equal(describeCanvas(null), null)
})

test('no instruction can invent a property it did not name', () => {
  const { doc } = headlineDoc()
  const before = JSON.parse(JSON.stringify(doc))
  for (const sentence of [
    'make the headline bigger',
    'set the headline to New words',
    'add a subhead saying Small print',
    'select the background',
  ]) {
    applyInstruction(doc, parseInstruction(sentence), { assets: [] })
  }
  assert.deepEqual(doc, before, 'applyInstruction never mutates its input')
})
