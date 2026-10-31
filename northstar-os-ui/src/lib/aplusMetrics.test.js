import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { APLUS_METRICS, copyBandRect, tileOffsets } from '../studio/aplus/metrics.js'

/**
 * Parity guard (Phase 1, item 1).
 *
 * The UI cannot import Python, so metrics.js mirrors aplus_layout.py. This test
 * reads the Python source and fails on any drift - a duplicated constant is only
 * safe while something checks it.
 */
const here = dirname(fileURLToPath(import.meta.url))
const py = readFileSync(resolve(here, '../../../Northstar_backend/aplus_layout.py'), 'utf8')

function pythonCanvas() {
  const block = py.slice(py.indexOf('CANVAS: Dict'), py.indexOf('TILE: Dict'))
  const out = {}
  for (const m of block.matchAll(/"([a-z_]+)":\s*\((\d+),\s*(\d+)\)/g)) {
    out[m[1]] = { w: Number(m[2]), h: Number(m[3]) }
  }
  return out
}

function pythonTile() {
  const block = py.slice(py.indexOf('TILE: Dict'), py.indexOf('SAFE_INSET'))
  const out = {}
  for (const m of block.matchAll(/"([a-z_]+)":\s*\((\d+),\s*(\d+)\)/g)) {
    out[m[1]] = { w: Number(m[2]), h: Number(m[3]) }
  }
  return out
}

test('every canvas size matches the Python geometry module', () => {
  const pyCanvas = pythonCanvas()
  assert.ok(Object.keys(pyCanvas).length >= 11, 'parser found the Python canvas table')
  for (const [kind, size] of Object.entries(pyCanvas)) {
    assert.deepEqual(APLUS_METRICS.canvas[kind], size, kind)
  }
})

test('every tile size matches', () => {
  const pyTile = pythonTile()
  for (const [kind, size] of Object.entries(pyTile)) {
    assert.equal(APLUS_METRICS.tile[kind].w, size.w, kind)
    assert.equal(APLUS_METRICS.tile[kind].h, size.h, kind)
  }
})

test('scalar constants match Python', () => {
  const safe = py.match(/SAFE_INSET = (\d+)/)
  const copy = py.match(/COPY_BAND = ([\d.]+)/)
  const label = py.match(/COMPARISON_LABEL_W = (\d+)/)
  assert.equal(APLUS_METRICS.safeInset, Number(safe[1]))
  assert.equal(APLUS_METRICS.copyBand, Number(copy[1]))
  assert.equal(APLUS_METRICS.comparison.labelW, Number(label[1]))
})

test('tile offsets reproduce the Python centring', () => {
  // three 300px tiles, 20px gaps, centred in 970 -> 15, 335, 655
  assert.deepEqual(tileOffsets('three_tiles'), [15, 335, 655])
  // four 220px tiles, 30px gaps -> 0, 250, 500, 750
  assert.deepEqual(tileOffsets('four_tiles'), [0, 250, 500, 750])
})

test('copy band is even, inset on the left and flush on the right', () => {
  const left = copyBandRect('header', 'left')
  const right = copyBandRect('header', 'right')
  assert.equal(left.x, APLUS_METRICS.safeInset)
  assert.equal(left.w % 2, 0)
  assert.equal(right.x + right.w, APLUS_METRICS.canvas.header.w)
  assert.equal(copyBandRect('single'), null)
})
