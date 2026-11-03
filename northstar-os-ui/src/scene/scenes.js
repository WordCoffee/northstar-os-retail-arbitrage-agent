// Scene factory (U5/U6).
//
// One entry point so the shell never imports a renderer directly: adding a scene
// is one line here plus one registry entry. Unbuilt scenes fall back to the
// default starfield instead of rendering nothing.

import { createStarfield } from './starfield.js'
import { createGasGiant, GAS_GIANT_MAX_COLOR } from './gasGiant.js'
import { createAsteroidField, ASTEROID_MAX_COLOR } from './asteroidField.js'
import { createBlackHole, BLACK_HOLE_MAX_COLOR } from './blackHole.js'
import { createComet, COMET_MAX_COLOR } from './comet.js'

/** The brightest colour each scene may paint. Read by the contrast test. */
export const SCENE_MAX_COLOR = {
  default: '#e8eef7',
  studio: GAS_GIANT_MAX_COLOR,
  ppc: ASTEROID_MAX_COLOR,
  research: BLACK_HOLE_MAX_COLOR,
  goose: COMET_MAX_COLOR,
}

const BUILDERS = {
  default: createStarfield,
  studio: createGasGiant,
  ppc: createAsteroidField,
  research: createBlackHole,
  goose: createComet,
}

export function createScene(sceneId, options = {}) {
  const build = BUILDERS[sceneId] || createStarfield
  return build(options)
}

export function sceneMaxColor(sceneId) {
  return SCENE_MAX_COLOR[sceneId] || SCENE_MAX_COLOR.default
}
