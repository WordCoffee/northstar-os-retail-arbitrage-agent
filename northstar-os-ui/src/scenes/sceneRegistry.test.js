// The registry is the only place that knows which service gets which scene.
// These tests pin it against the real tab list: a new workspace route without a
// scene fails here instead of silently showing the home field.

import { describe, it, expect } from 'vitest'
import {
  DEFAULT_SCENE_SERVICE,
  SCENE_SERVICE_IDS,
  sceneForService,
  sceneServiceIdForPath,
  sceneServiceRoutes,
} from './sceneRegistry.js'
import { TAB_SERVICE_IDS } from '../shell/tabRoutes.js'

describe('service coverage', () => {
  it('every workspace tab has a scene', () => {
    for (const id of TAB_SERVICE_IDS) {
      expect(SCENE_SERVICE_IDS).toContain(id)
    }
  })

  it('ids are unique and include the home fallback', () => {
    expect(new Set(SCENE_SERVICE_IDS).size).toBe(SCENE_SERVICE_IDS.length)
    expect(SCENE_SERVICE_IDS).toContain(DEFAULT_SCENE_SERVICE)
  })

  it('every scene has a poster from the shipped galactic assets', () => {
    for (const id of SCENE_SERVICE_IDS) {
      const scene = sceneForService(id)
      expect(scene.poster).toMatch(/\.webp$/)
      expect(scene.accent).toMatch(/^#[0-9a-f]{6}$/i)
      expect(scene.sky).toHaveLength(2)
      expect(scene.spec.stars).toBeGreaterThan(0)
    }
  })

  it('scenes are cached, so a re-render does not rebuild the field', () => {
    expect(sceneForService('listings')).toBe(sceneForService('listings'))
  })

  it('an unknown service falls back to the home scene, never null', () => {
    const scene = sceneForService('not-a-service')
    expect(scene.id).toBe(DEFAULT_SCENE_SERVICE)
    expect(scene.poster).toMatch(/\.webp$/)
  })

  it('each service route is its own prefix', () => {
    const routes = sceneServiceRoutes()
    expect(routes.length).toBe(SCENE_SERVICE_IDS.length - 1)
    expect(routes.find((r) => r.id === 'listings').route).toBe('/listings')
  })
})

describe('path -> scene', () => {
  it('maps a workspace route and its children', () => {
    expect(sceneServiceIdForPath('/listings')).toBe('listings')
    expect(sceneServiceIdForPath('/listings/abc')).toBe('listings')
    expect(sceneServiceIdForPath('/golden-goose/B012345')).toBe('golden-goose')
  })

  it('does not match on a partial segment', () => {
    expect(sceneServiceIdForPath('/listings-old')).toBe(DEFAULT_SCENE_SERVICE)
  })

  it('routes that are not workspaces get the home scene', () => {
    expect(sceneServiceIdForPath('/home')).toBe(DEFAULT_SCENE_SERVICE)
    expect(sceneServiceIdForPath('/admin')).toBe(DEFAULT_SCENE_SERVICE)
    expect(sceneServiceIdForPath('/sign-in')).toBe(DEFAULT_SCENE_SERVICE)
    expect(sceneServiceIdForPath('/')).toBe(DEFAULT_SCENE_SERVICE)
  })

  it('tolerates a trailing slash and an empty path', () => {
    expect(sceneServiceIdForPath('/profitability/')).toBe('profitability')
    expect(sceneServiceIdForPath('')).toBe(DEFAULT_SCENE_SERVICE)
  })
})
