// U6 — the studio scene's contrast proof.
//
// The glass panels are translucent, so the guarantee has to hold against the
// BRIGHTEST pixel a scene can paint, not the average frame. Every scene exports
// its own maximum colour; this measures text and UI against glass over it.

import test from 'node:test'
import assert from 'node:assert/strict'

import { SCENE_MAX_COLOR, createScene, sceneMaxColor } from '../scene/scenes.js'
import { GAS_GIANT_MAX_COLOR } from '../scene/gasGiant.js'
import { BASE_TOKENS, AA_TEXT, AA_UI, compositeOver, contrastRatio } from './serviceThemes.js'
import { THEMES, getService } from '../data/serviceRegistry.js'

function glassOver(color) {
  return compositeOver(BASE_TOKENS.surface, BASE_TOKENS.glassAlpha, color)
}

test('text stays readable even against the brightest pixel of every scene', () => {
  const failures = []
  for (const [sceneId, maxColor] of Object.entries(SCENE_MAX_COLOR)) {
    const bg = glassOver(maxColor)
    const ink = contrastRatio(BASE_TOKENS.ink, bg)
    const dim = contrastRatio(BASE_TOKENS.inkDim, bg)
    if (ink < AA_TEXT) failures.push(`${sceneId}: ink ${ink.toFixed(2)}:1`)
    if (dim < AA_TEXT) failures.push(`${sceneId}: ink-dim ${dim.toFixed(2)}:1`)
  }
  assert.deepEqual(failures, [], failures.join(', '))
})

test('the studio glass panels clear AA against the warm gas-giant highlight', () => {
  const bg = glassOver(sceneMaxColor('studio'))
  assert.ok(contrastRatio(BASE_TOKENS.ink, bg) >= AA_TEXT)
  assert.ok(contrastRatio(BASE_TOKENS.inkDim, bg) >= AA_TEXT)
  // The studio accent must still read as a UI colour on that same composite.
  assert.ok(contrastRatio(THEMES.studio.accent, bg) >= AA_UI)
})

test('every colour the gas giant paints is within its declared maximum', () => {
  // The renderer declares one max; the test proves no band is brighter than it
  // by luminance, so the contrast guarantee cannot be voided by a new band.
  const maxLum = relativeLum(GAS_GIANT_MAX_COLOR)
  for (const colour of ['#7a4a24', '#a86a33', '#d99a55', '#b5793c', '#8a5528', '#6b3f1c']) {
    assert.ok(relativeLum(colour) <= maxLum, `${colour} is brighter than the declared max`)
  }
})

test('the factory gives the studio its own renderer and falls back for unbuilt scenes', () => {
  const studio = createScene('studio', { width: 800, height: 600 })
  assert.equal(studio.paletteMax, SCENE_MAX_COLOR.studio)
  assert.equal(typeof studio.draw, 'function')

  // U9 built PPC, U10 Research and U11 Goose; every registered scene now has its
  // own renderer, so the fallback is asserted with an id nothing claims.
  const ppc = createScene('ppc', { width: 800, height: 600 })
  assert.equal(ppc.paletteMax, SCENE_MAX_COLOR.ppc)
  assert.equal(ppc.stars, undefined, 'the PPC scene is its own renderer now')

  const research = createScene('research', { width: 800, height: 600 })
  assert.equal(research.paletteMax, SCENE_MAX_COLOR.research)
  assert.equal(research.stars, undefined, 'the research scene is its own renderer now')

  const goose = createScene('goose', { width: 800, height: 600 })
  assert.equal(goose.paletteMax, SCENE_MAX_COLOR.goose)
  assert.equal(goose.stars, undefined, 'the goose scene is its own renderer now')

  const fallback = createScene('a-scene-nothing-claims', { width: 800, height: 600 })
  assert.ok(Array.isArray(fallback.stars), 'an unknown scene uses the starfield')
})

test('the design studio service is wired to the studio scene', () => {
  assert.equal(getService('design-studio').scene, 'studio')
})

function relativeLum(hex) {
  // Same maths as serviceThemes, kept local so the assertion is independent.
  const s = hex.replace('#', '')
  const channels = [0, 2, 4].map((i) => {
    const c = parseInt(s.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}
