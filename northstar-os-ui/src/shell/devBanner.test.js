// The dev notice is driven by the backend auth posture, not by a literal.

import { test, expect } from 'vitest'
import { DEV_BANNER_TEXT, devBannerVisible } from './devBanner.js'

test('the notice text is the one the smoke test and the ux scorecard assert', () => {
  expect(DEV_BANNER_TEXT).toBe('DEV: AUTH DISABLED — local loopback only')
})

test('visible when the backend resolved a dev_shim identity', () => {
  expect(devBannerVisible({ authMethod: 'dev_shim', localDev: false })).toBe(true)
})

test('visible in a dev build even before the session resolves', () => {
  expect(devBannerVisible({ authMethod: null, localDev: true })).toBe(true)
})

test('absent for a real jwt session in a built bundle', () => {
  expect(devBannerVisible({ authMethod: 'jwt', localDev: false })).toBe(false)
  expect(devBannerVisible({ authMethod: null, localDev: false })).toBe(false)
})
