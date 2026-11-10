// The workspace spine as data: content types resolved from the registries that
// already exist, one undo history, and a versioned autosave record that refuses
// anything it cannot fully restore.

import { describe, expect, it } from 'vitest'
import {
  CONTENT_TYPES, DESIGN_STORE_KEY, DESIGN_TTL_MS, DESIGN_VERSION, MAX_ASSET_CHARS,
  addImage, addText, assetsWithinBudget, canRedo, canUndo, createDesign, currentValue,
  exportFileName, initHistory, parseDesign, pushHistory, redoHistory, resolveContentType,
  serialiseDesign, undoHistory,
} from '../../lib/studioCanvas.js'

const editedDoc = () => addText(createDesign('ad'), { text: 'Hello', preset: 'headline' })

describe('content types', () => {
  it('resolves every entry to a real raster size from a registry', () => {
    expect(CONTENT_TYPES.length).toBeGreaterThan(1)
    for (const t of CONTENT_TYPES) {
      const r = resolveContentType(t.id)
      expect(r.w).toBeGreaterThan(0)
      expect(r.h).toBeGreaterThan(0)
      expect(r.registryId).toBeTruthy()
      expect(r.missing).toBe(false)
    }
  })

  it('creates a design with one background layer, never seeded artwork', () => {
    const doc = createDesign('social')
    expect(doc.contentType).toBe('social')
    expect(doc.layers).toHaveLength(1)
    expect(doc.layers[0].kind).toBe('bg')
  })
})

describe('undo history', () => {
  it('walks back and forward and truncates the redo branch', () => {
    let h = initHistory('a')
    h = pushHistory(h, 'b')
    h = pushHistory(h, 'c')
    expect(currentValue(h)).toBe('c')
    expect(canUndo(h)).toBe(true)
    expect(canRedo(h)).toBe(false)

    h = undoHistory(h)
    expect(currentValue(h)).toBe('b')
    expect(canRedo(h)).toBe(true)

    h = pushHistory(h, 'd')
    expect(currentValue(h)).toBe('d')
    expect(canRedo(h)).toBe(false)
    expect(h.stack).toEqual(['a', 'b', 'd'])
  })

  it('caps the stack at the requested limit', () => {
    let h = initHistory(0)
    for (let i = 1; i <= 10; i += 1) h = pushHistory(h, i, 3)
    expect(h.stack).toHaveLength(3)
    expect(currentValue(h)).toBe(10)
  })
})

describe('autosave record', () => {
  it('round-trips the document and its assets under a versioned key', () => {
    expect(DESIGN_STORE_KEY).toBe('ns-ds-canvas')
    const doc = editedDoc()
    const assets = [{ id: 'A1', name: 'pixel.png', dataUrl: 'data:image/png;base64,AAAA' }]
    const raw = serialiseDesign(doc, assets, { now: 1000 })
    const parsed = parseDesign(raw, { now: 1000 })
    expect(parsed.doc.layers).toHaveLength(doc.layers.length)
    expect(parsed.doc.layers[1].text).toBe('Hello')
    expect(parsed.assets).toHaveLength(1)
    expect(parsed.savedAt).toBe(1000)
  })

  it('refuses corrupt, foreign and stale records', () => {
    const doc = editedDoc()
    expect(parseDesign('not json')).toBeNull()
    expect(parseDesign('')).toBeNull()
    expect(parseDesign(JSON.stringify({ ...JSON.parse(serialiseDesign(doc)), v: DESIGN_VERSION + 1 }))).toBeNull()
    const old = serialiseDesign(doc, [], { now: 1000 })
    expect(parseDesign(old, { now: 1000 + DESIGN_TTL_MS + 1 })).toBeNull()
    const future = JSON.parse(serialiseDesign(doc, [], { now: 1000 }))
    future.savedAt = 1000 + 120_000
    expect(parseDesign(JSON.stringify(future), { now: 1000 })).toBeNull()
  })

  it('drops an oversized image and the layer that pointed at it', () => {
    const big = { id: 'A-big', name: 'huge.png', dataUrl: `data:image/png;base64,${'A'.repeat(MAX_ASSET_CHARS)}` }
    expect(assetsWithinBudget([big]).ok).toBe(false)
    const doc = addImage(createDesign('ad'), big)
    expect(doc.layers.some((l) => l.assetId === 'A-big')).toBe(true)
    const parsed = parseDesign(serialiseDesign(doc, [big]), { now: Date.now() })
    expect(parsed.assets).toHaveLength(0)
    expect(parsed.doc.layers.some((l) => l.assetId === 'A-big')).toBe(false)
  })
})

describe('export filename', () => {
  it('sanitises the name and states the raster size', () => {
    expect(exportFileName({ name: 'My Design!', w: 1080, h: 1350 }, 'png')).toBe('my-design-1080x1350.png')
  })
})
