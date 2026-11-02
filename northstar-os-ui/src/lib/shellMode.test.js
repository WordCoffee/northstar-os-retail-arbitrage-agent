// U1 naming: the default view is Northstar. These tests pin the vocabulary and
// the migration, so an old stored value cannot silently demote a session and a
// future rename cannot drift the two names apart.

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_MODE,
  MODE_ALIASES,
  MODE_KEY,
  SHELL_DISPLAY_NAMES,
  SHELL_MODES,
  displayName,
  normaliseMode,
} from './shellMode.js'

test('the stored key stays ns-shell-mode (moving it would log everyone out)', () => {
  assert.equal(MODE_KEY, 'ns-shell-mode')
})

test('internal ids are unchanged: simple and advanced', () => {
  assert.deepEqual(SHELL_MODES, ['simple', 'advanced'])
  assert.equal(DEFAULT_MODE, 'simple')
})

test('display names: Northstar and Advanced view, never "Simple"', () => {
  assert.equal(SHELL_DISPLAY_NAMES.simple, 'Northstar')
  assert.equal(SHELL_DISPLAY_NAMES.advanced, 'Advanced view')
  for (const name of Object.values(SHELL_DISPLAY_NAMES)) {
    assert.doesNotMatch(name, /simple/i)
  }
})

test('legacy stored values still resolve', () => {
  assert.equal(normaliseMode('simple'), 'simple')
  assert.equal(normaliseMode('northstar'), 'simple')
  assert.equal(normaliseMode('Northstar'), 'simple')
  assert.equal(normaliseMode('standard'), 'simple')
  assert.equal(normaliseMode('default'), 'simple')
  assert.equal(normaliseMode('advanced'), 'advanced')
  assert.equal(normaliseMode('Advanced view'), 'advanced')
  assert.equal(normaliseMode('advanced-view'), 'advanced')
  assert.equal(normaliseMode('autothink'), 'advanced')
})

test('an unknown or empty value degrades to Northstar, never to advanced', () => {
  for (const value of [null, undefined, '', '   ', 'cinematic', 42, {}]) {
    assert.equal(normaliseMode(value), 'simple')
  }
})

test('every alias points at a canonical id', () => {
  for (const [alias, id] of Object.entries(MODE_ALIASES)) {
    assert.ok(SHELL_MODES.includes(id), `${alias} -> ${id}`)
    assert.equal(normaliseMode(alias), id)
  }
})

test('displayName accepts an id or an alias', () => {
  assert.equal(displayName('simple'), 'Northstar')
  assert.equal(displayName('northstar'), 'Northstar')
  assert.equal(displayName('advanced'), 'Advanced view')
  assert.equal(displayName('nonsense'), 'Northstar')
})
