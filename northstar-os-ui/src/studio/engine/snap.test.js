// Snapping is the part of the canvas a user feels first: a drag that lands a
// hair off an edge looks broken. These tests pin the contract in screen pixels,
// because the document itself stores normalised geometry.

import { describe, expect, it } from 'vitest'
import { SNAP_PX, snapMove, snapResize } from './snap.js'

const canvas = { W: 1000, H: 1000 }

describe('snapMove', () => {
  it('snaps a left edge that is 5 px from the canvas edge', () => {
    const box = snapMove({ x: 0.005, y: 0.6, w: 0.2, h: 0.1 }, { canvas })
    expect(box.x).toBeCloseTo(0, 10)
    expect(box.snapped.x).toBe(true)
    expect(box.guides).toContainEqual({ axis: 'x', at: 0, name: 'canvas start' })
  })

  it('leaves a left edge 9 px away alone', () => {
    const box = snapMove({ x: 0.009, y: 0.6, w: 0.2, h: 0.1 }, { canvas })
    expect(box.x).toBeCloseTo(0.009, 10)
    expect(box.snapped.x).toBe(false)
  })

  it('snaps a centre to the canvas centre', () => {
    const box = snapMove({ x: 0.406, y: 0.6, w: 0.2, h: 0.1 }, { canvas })
    expect(box.x).toBeCloseTo(0.4, 10)
    expect(box.guides).toContainEqual({ axis: 'x', at: 0.5, name: 'canvas centre' })
  })

  it('snaps to another layer edge, not only the canvas', () => {
    const others = [{ id: 'L1', kind: 'shape', name: 'Rectangle', x: 0.15, y: 0.1, w: 0.1, h: 0.1 }]
    // left edge 247 px → other layer's right edge 250 px
    const box = snapMove({ x: 0.247, y: 0.6, w: 0.1, h: 0.1 }, { canvas, others })
    expect(box.x).toBeCloseTo(0.25, 10)
    expect(box.snapped.x).toBe(true)
    expect(box.guides).toContainEqual({ axis: 'x', at: 0.25, name: 'Rectangle end' })
  })

  it('snaps both axes and reports both guides', () => {
    const box = snapMove({ x: 0.004, y: 0.005, w: 0.1, h: 0.1 }, { canvas })
    expect(box.x).toBeCloseTo(0, 10)
    expect(box.y).toBeCloseTo(0, 10)
    expect(box.guides.map((g) => g.axis).sort()).toEqual(['x', 'y'])
  })

  it('never changes size while moving', () => {
    const box = snapMove({ x: 0.004, y: 0.004, w: 0.37, h: 0.61 }, { canvas })
    expect(box.w).toBeUndefined()
    expect(box.h).toBeUndefined()
  })

  it('uses 8 px as the threshold', () => {
    expect(SNAP_PX).toBe(8)
    const justInside = snapMove({ x: 0.008, y: 0.6, w: 0.1, h: 0.1 }, { canvas })
    const justOutside = snapMove({ x: 0.0081, y: 0.6, w: 0.1, h: 0.1 }, { canvas })
    expect(justInside.x).toBeCloseTo(0, 10)
    expect(justOutside.x).toBeCloseTo(0.0081, 10)
  })
})

describe('snapResize', () => {
  it('snaps the bottom-right edge to another layer start', () => {
    const others = [{ id: 'L2', kind: 'shape', name: 'Panel', x: 0.6, y: 0.5, w: 0.2, h: 0.2 }]
    const box = snapResize({ x: 0, y: 0, w: 0.597, h: 0.3 }, { canvas, others })
    expect(box.w).toBeCloseTo(0.6, 10)
    expect(box.guides).toContainEqual({ axis: 'x', at: 0.6, name: 'Panel start' })
  })

  it('leaves a right edge outside the threshold alone', () => {
    const box = snapResize({ x: 0, y: 0, w: 0.489, h: 0.3 }, { canvas })
    expect(box.w).toBeCloseTo(0.489, 10)
    expect(box.snapped.x).toBe(false)
  })

  it('keeps the normalised minimum of 0.02', () => {
    // right edge 3 px from the canvas start would make a negative width
    const box = snapResize({ x: 0.01, y: 0, w: 0.02, h: 0.3 }, { canvas })
    expect(box.w).toBeGreaterThanOrEqual(0.02)
  })
})
