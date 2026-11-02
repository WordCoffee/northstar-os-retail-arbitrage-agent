// U4 — the theme system has to be provable, not pretty.
//
// Every theme is measured against the WORST frame its scene may paint behind the
// glass (not the flat panel colour), and every service in the registry gets a
// snapshot entry so a palette change cannot slip in unnoticed.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  BASE_TOKENS, AA_TEXT, AA_UI, themeIds, tokensFor, themeVars,
  worstComposite, contrastRatio, serviceThemeSnapshot, compositeOver,
} from './serviceThemes.js'
import { THEMES, SERVICE_REGISTRY } from '../data/serviceRegistry.js'

const here = dirname(fileURLToPath(import.meta.url))

test('contrast math matches the WCAG reference points', () => {
  assert.equal(contrastRatio('#000000', '#ffffff').toFixed(2), '21.00')
  assert.equal(contrastRatio('#ffffff', '#ffffff').toFixed(2), '1.00')
})

test('glass over a white frame still clears AA with the shipping ink', () => {
  const white = compositeOver(BASE_TOKENS.surface, BASE_TOKENS.glassAlpha, '#ffffff')
  assert.ok(contrastRatio(BASE_TOKENS.ink, white) >= AA_TEXT,
    `ink on white-glass is ${contrastRatio(BASE_TOKENS.ink, white).toFixed(2)}`)
})

test('every registry theme declares a complete token set', () => {
  for (const id of Object.keys(THEMES)) {
    const t = tokensFor(id)
    assert.ok(t, `theme ${id} has no tokens`)
    assert.equal(t.accent, THEMES[id].accent, `${id} accent drifted from the registry`)
    assert.equal(t.accentSoft, THEMES[id].accentSoft, `${id} accentSoft drifted from the registry`)
    assert.match(t.accentInk, /^#[0-9a-f]{6}$/i, `${id} needs an accent ink colour`)
    assert.match(t.sceneWorst, /^#[0-9a-f]{6}$/i, `${id} needs a worst-frame budget`)
  }
  assert.equal(themeIds().length, Object.keys(THEMES).length)
})

test('text clears AA against the worst composite in every theme', () => {
  const failures = []
  for (const id of Object.keys(THEMES)) {
    const bg = worstComposite(id)
    const ink = contrastRatio(BASE_TOKENS.ink, bg)
    const dim = contrastRatio(BASE_TOKENS.inkDim, bg)
    if (ink < AA_TEXT) failures.push(`${id}: ink ${ink.toFixed(2)}:1`)
    if (dim < AA_TEXT) failures.push(`${id}: ink-dim ${dim.toFixed(2)}:1`)
  }
  assert.deepEqual(failures, [], `AA text failures: ${failures.join(', ')}`)
})

test('the accent is usable as a UI colour and as a button surface', () => {
  const failures = []
  for (const id of Object.keys(THEMES)) {
    const t = tokensFor(id)
    const bg = worstComposite(id)
    const accent = contrastRatio(t.accent, bg)
    const onAccent = contrastRatio(t.accentInk, t.accent)
    if (accent < AA_UI) failures.push(`${id}: accent ${accent.toFixed(2)}:1`)
    if (onAccent < AA_TEXT) failures.push(`${id}: ink on accent ${onAccent.toFixed(2)}:1`)
  }
  assert.deepEqual(failures, [], `accent failures: ${failures.join(', ')}`)
})

test('an unknown theme falls back to neutral tokens instead of nothing', () => {
  assert.deepEqual(themeVars('no-such-theme'), themeVars('neutral'))
})

test('theme vars are CSS custom properties', () => {
  const vars = themeVars('studio')
  for (const [key, value] of Object.entries(vars)) {
    assert.match(key, /^--wb-/, `${key} is not a --wb- variable`)
    assert.equal(typeof value, 'string')
    assert.ok(value.length > 0, `${key} is empty`)
  }
  for (const required of ['--wb-accent', '--wb-accent-ink', '--wb-ink', '--wb-glass', '--wb-scene-worst']) {
    assert.ok(required in vars, `missing ${required}`)
  }
})

test('every service has a palette snapshot', () => {
  const snap = serviceThemeSnapshot()
  assert.equal(Object.keys(snap).length, SERVICE_REGISTRY.length)
  for (const service of SERVICE_REGISTRY) {
    assert.ok(snap[service.id], `no snapshot for ${service.id}`)
    assert.equal(snap[service.id].theme, service.theme)
  }
})

test('the palette snapshot matches the committed file', () => {
  const expected = JSON.parse(readFileSync(join(here, 'serviceThemes.snapshot.json'), 'utf8'))
  assert.deepEqual(serviceThemeSnapshot(), expected)
})
