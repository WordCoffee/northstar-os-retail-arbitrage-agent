// The renderer is pure and synchronous, so it can be proved with a recording
// 2D context. These tests assert what the canvas is actually told to draw:
// a rectangle, typed text and a decoded image — and an honest placeholder when
// the asset is missing.

import { describe, expect, it } from 'vitest'
import {
  KIND, createDoc, addLayer, updateLayer, removeLayer, reorderLayer,
  renderDoc, rescaleDoc,
} from './doc.js'

function fakeCtx() {
  const calls = { fillText: [], drawImage: 0, fillRect: 0, fill: 0, stroke: 0 }
  const gradient = { addColorStop() {} }
  return {
    calls,
    save() {}, restore() {}, clearRect() {}, clip() {}, setLineDash() {},
    beginPath() {}, closePath() {}, moveTo() {}, lineTo() {},
    quadraticCurveTo() {}, ellipse() {}, translate() {}, rotate() {},
    createLinearGradient: () => gradient,
    createRadialGradient: () => gradient,
    measureText: (t) => ({ width: String(t).length * 10 }),
    fillText(t) { calls.fillText.push(String(t)) },
    fillRect() { calls.fillRect += 1 },
    strokeRect() {},
    fill() { calls.fill += 1 },
    stroke() { calls.stroke += 1 },
    drawImage() { calls.drawImage += 1 },
  }
}

const baseDoc = () => ({
  w: 100,
  h: 100,
  layers: [
    { id: 'bg', kind: KIND.BG, fill: '#f5f0e8' },
    { id: 'r1', kind: KIND.SHAPE, shape: 'rect', x: 0.1, y: 0.1, w: 0.2, h: 0.2, fill: '#1d4a1d' },
    { id: 't1', kind: KIND.TEXT, text: 'Hi', x: 0.1, y: 0.5, w: 0.5, h: 0.1, size: 0.1 },
    { id: 'i1', kind: KIND.IMAGE, assetId: 'A1', x: 0.5, y: 0.5, w: 0.3, h: 0.3, fit: 'cover' },
  ],
})

describe('document model', () => {
  it('creates one background layer and a real raster size', () => {
    const doc = createDoc({ w: 1080, h: 1350, name: 'Feed' })
    expect(doc.w).toBe(1080)
    expect(doc.h).toBe(1350)
    expect(doc.layers).toHaveLength(1)
    expect(doc.layers[0].kind).toBe(KIND.BG)
    expect(doc.layers[0].id).toBeTruthy()
  })

  it('appends layers with z, visibility, lock and opacity defaults', () => {
    const doc = addLayer(createDoc(), { id: 'L-x', kind: KIND.SHAPE, x: 0.1, y: 0.1, w: 0.2, h: 0.2 })
    const layer = doc.layers[doc.layers.length - 1]
    expect(layer.z).toBe(1)
    expect(layer.visible).toBe(true)
    expect(layer.locked).toBe(false)
    expect(layer.opacity).toBe(1)
  })

  it('patches, removes and reorders without mutating the input', () => {
    const doc = addLayer(createDoc(), { id: 'L-a', kind: KIND.TEXT, text: 'A', x: 0, y: 0, w: 0.5, h: 0.1 })
    const patched = updateLayer(doc, 'L-a', { text: 'B', x: 0.2 })
    expect(patched.layers[1].text).toBe('B')
    expect(doc.layers[1].text).toBe('A')

    const removed = removeLayer(patched, 'L-a')
    expect(removed.layers).toHaveLength(1)
    expect(removed.layers[0].id).toBe(patched.layers[0].id)

    const two = addLayer(patched, { id: 'L-b', kind: KIND.SHAPE, x: 0, y: 0, w: 0.1, h: 0.1 })
    const moved = reorderLayer(two, 'L-b', -1)
    expect(moved.layers[moved.layers.length - 1].id).toBe('L-a')
  })

  it('keeps normalised geometry when the raster size changes', () => {
    const doc = addLayer(createDoc(), { id: 'L-a', kind: KIND.SHAPE, x: 0.25, y: 0.25, w: 0.5, h: 0.5 })
    const next = rescaleDoc(doc, 1920, 1080)
    expect(next.w).toBe(1920)
    expect(next.layers[1].x).toBe(0.25)
    expect(next.layers[1].w).toBe(0.5)
  })
})

describe('renderDoc', () => {
  it('paints the background, the rectangle, the text and the image', () => {
    const ctx = fakeCtx()
    const assets = new Map([['A1', { naturalWidth: 40, naturalHeight: 20, width: 40, height: 20 }]])
    renderDoc(ctx, baseDoc(), { W: 1000, H: 1000, assets })
    expect(ctx.calls.fillRect).toBeGreaterThanOrEqual(1)
    expect(ctx.calls.fill).toBeGreaterThanOrEqual(1)
    expect(ctx.calls.fillText).toContain('Hi')
    expect(ctx.calls.drawImage).toBe(1)
  })

  it('draws an honest placeholder instead of dropping a missing asset', () => {
    const ctx = fakeCtx()
    renderDoc(ctx, baseDoc(), { W: 100, H: 100, assets: new Map() })
    expect(ctx.calls.drawImage).toBe(0)
    expect(ctx.calls.fillText).toContain('ASSET NOT LOADED')
  })

  it('skips a hidden layer', () => {
    const ctx = fakeCtx()
    const doc = baseDoc()
    doc.layers[2].visible = false
    renderDoc(ctx, doc, { W: 100, H: 100, assets: new Map() })
    expect(ctx.calls.fillText).not.toContain('Hi')
  })
})
