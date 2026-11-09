// The shell decides which routes get chrome from one list (shellRoutes.js).
// These tests pin that list to the route table in App.jsx, so a route added to
// the table cannot silently disagree with the chrome decision.

import { test, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  SHELL_EXEMPT_PATHS,
  PUBLIC_SHELL_PATHS,
  PUBLIC_PATHS,
  isShellExempt,
  isPublicPath,
} from './shellRoutes.js'

const here = dirname(fileURLToPath(import.meta.url))
const APP = readFileSync(resolve(here, '../App.jsx'), 'utf8')
const ROUTE_PATHS = [...APP.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1])

test('App.jsx registers 72 routes', () => {
  expect(ROUTE_PATHS).toHaveLength(72)
})

test('every exempt path is a real route', () => {
  for (const p of SHELL_EXEMPT_PATHS) {
    expect(ROUTE_PATHS, `${p} is exempt but not registered in App.jsx`).toContain(p)
  }
})

test('exactly the entry surfaces are outside the shell', () => {
  expect(SHELL_EXEMPT_PATHS).toEqual(['/beta', '/beta/accept', '/sign-in', '/recovery', '/legal'])
  expect(isShellExempt('/listings')).toBe(false)
  expect(isShellExempt('/beta-ops/orgs')).toBe(false)
  expect(isShellExempt('/beta')).toBe(true)
  expect(isShellExempt('/beta/accept')).toBe(true)
  expect(isShellExempt('/sign-in')).toBe(true)
  expect(isShellExempt('/recovery')).toBe(true)
  expect(isShellExempt('/legal')).toBe(true)
})

test('/beta-signup is public but INSIDE the shell', () => {
  expect(PUBLIC_SHELL_PATHS).toEqual(['/beta-signup'])
  expect(isPublicPath('/beta-signup')).toBe(true)
  expect(isShellExempt('/beta-signup')).toBe(false)
  // The segment match must not treat /beta-signup as a child of /beta.
  expect(isShellExempt('/beta-signup')).toBe(false)
  expect(PUBLIC_PATHS).toContain('/beta-signup')
})

test('param and wildcard routes are classified without throwing', () => {
  for (const p of ['/product-finder/:id', '/design-studio/*', '*', '/support/:id']) {
    expect(typeof isShellExempt(p)).toBe('boolean')
  }
})
