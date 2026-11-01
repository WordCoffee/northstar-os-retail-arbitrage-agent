import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_SIMPLE_DESIGN,
  SIMPLE_DESIGNS,
  resolveSimpleDesign,
  simpleDesignById,
} from '../shell/simpleDesigns.js'

test('there are ten distinct simple-mode designs', () => {
  assert.equal(SIMPLE_DESIGNS.length, 10)
  assert.equal(new Set(SIMPLE_DESIGNS.map((d) => d.id)).size, 10)
  assert.equal(new Set(SIMPLE_DESIGNS.map((d) => d.backdrop)).size, 10)
  assert.ok(SIMPLE_DESIGNS.every((d) => d.name && d.intent && d.note))
})

test('query selects a design by id or index; storage is the fallback', () => {
  assert.equal(resolveSimpleDesign('?simple=terminal').id, 'terminal')
  assert.equal(resolveSimpleDesign('?design=3').id, 'observatory')
  assert.equal(resolveSimpleDesign('', 'theater').id, 'theater')
  assert.equal(resolveSimpleDesign('', '').id, DEFAULT_SIMPLE_DESIGN)
  assert.equal(simpleDesignById('not-a-design').id, DEFAULT_SIMPLE_DESIGN)
})
