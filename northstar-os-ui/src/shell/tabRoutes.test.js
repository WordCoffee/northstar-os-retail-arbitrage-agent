// The tab rules are pure (tabRoutes.js), so they are tested here without a
// browser. The last two tests pin the tab route table and the panel map to the
// app: a workspace cannot be added on one side only.

import { test, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import {
  TAB_ROUTE_PATTERNS,
  TAB_SERVICE_IDS,
  TAB_STORAGE_KEY,
  closeTab,
  normalizePath,
  openTab,
  parseTabs,
  sameTabs,
  serializeTabs,
  tabForPath,
  tabServiceForPath,
  tabSummary,
} from './tabRoutes.js'
import { SERVICE_REGISTRY } from '../data/serviceRegistry.js'
import { TAB_PANELS } from './WorkspacePanels.jsx'

const here = dirname(fileURLToPath(import.meta.url))
const APP = readFileSync(resolve(here, '../App.jsx'), 'utf8')
const ROUTE_PATHS = [...APP.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1])

test('paths normalise without changing the root', () => {
  expect(normalizePath('/listings/')).toBe('/listings')
  expect(normalizePath('/listings')).toBe('/listings')
  expect(normalizePath('/')).toBe('/')
  expect(normalizePath('')).toBe('/')
})

test('a path maps to the workspace that owns it, on segment boundaries', () => {
  expect(tabServiceForPath('/listings')?.id).toBe('listings')
  expect(tabServiceForPath('/listings/')?.id).toBe('listings')
  expect(tabServiceForPath('/product-finder/B0ABCDEFGH')?.id).toBe('product-finder')
  expect(tabServiceForPath('/design-studio/scene/3d')?.id).toBe('design-studio')
  // Not a prefix match on a partial segment…
  expect(tabServiceForPath('/listings-old')).toBeNull()
  // …and /home is Bojo's home, not a workspace.
  expect(tabServiceForPath('/home')).toBeNull()
  expect(tabServiceForPath('/')).toBeNull()
})

test('a tab keeps the query string, because filters are part of its state', () => {
  const tab = tabForPath('/product-finder/', '?view=set')
  expect(tab).toMatchObject({
    id: 'product-finder',
    serviceId: 'product-finder',
    label: 'SourceScout',
    path: '/product-finder',
    search: '?view=set',
    href: '/product-finder?view=set',
  })
  expect(tabForPath('/product-finder', 'view=set')?.search).toBe('?view=set')
  expect(tabForPath('/home')?.path).toBeUndefined()
})

test('opening re-points the existing tab instead of adding a second one', () => {
  const first = tabForPath('/product-finder')
  const second = tabForPath('/product-finder/B0ABCDEFGH')
  const listed = openTab([], first)
  expect(listed.map((t) => t.id)).toEqual(['product-finder'])
  const moved = openTab(listed, second)
  expect(moved).toHaveLength(1)
  expect(moved[0].path).toBe('/product-finder/B0ABCDEFGH')
  // An unchanged location must not force an effect loop.
  expect(openTab(moved, second)).toBe(moved)
})

test('closing an inactive tab never navigates', () => {
  const tabs = [tabForPath('/listings'), tabForPath('/product-finder')]
  const result = closeTab(tabs, 'listings', 'product-finder')
  expect(result.tabs.map((t) => t.id)).toEqual(['product-finder'])
  expect(result.activeId).toBe('product-finder')
  expect(result.nextPath).toBeNull()
})

test('closing the active tab goes right, else left', () => {
  const tabs = [
    tabForPath('/listings'),
    tabForPath('/product-finder'),
    tabForPath('/profitability'),
  ]
  const right = closeTab(tabs, 'product-finder', 'product-finder')
  expect(right.tabs.map((t) => t.id)).toEqual(['listings', 'profitability'])
  expect(right.nextPath).toBe('/profitability')

  const left = closeTab(tabs, 'profitability', 'profitability')
  expect(left.nextPath).toBe('/product-finder')
})

test('LAST TAB RULE: closing the last tab goes home, strip empty, no dangling route', () => {
  const tabs = [tabForPath('/listings')]
  const result = closeTab(tabs, 'listings', 'listings')
  expect(result.tabs).toEqual([])
  expect(result.activeId).toBeNull()
  expect(result.nextPath).toBe('/home')
})

test('stored tabs survive corrupt JSON, unknown ids, duplicates and tampering', () => {
  expect(parseTabs(null)).toEqual({ tabs: [] })
  expect(parseTabs('{not json')).toEqual({ tabs: [] })
  expect(parseTabs('{"open":[]}')).toEqual({ tabs: [] })
  const parsed = parseTabs(JSON.stringify({
    open: [
      { id: 'listings', path: '/listings' },
      { id: 'listings', path: '/listings' },
      { id: 'gone-service', path: '/gone' },
      // A tampered path for a real service is repaired, not trusted.
      { id: 'product-finder', path: '/master-brain' },
      { id: 'no-path-at-all' },
    ],
  }))
  expect(parsed.tabs.map((t) => t.id)).toEqual(['listings', 'product-finder'])
  expect(parsed.tabs[1].path).toBe('/product-finder')
})

test('serialise -> parse round trip preserves open tabs and queries', () => {
  const tabs = [tabForPath('/listings'), tabForPath('/design-studio', '?section=projects')]
  expect(parseTabs(serializeTabs(tabs)).tabs).toEqual(tabs)
  expect(sameTabs(tabs, parseTabs(serializeTabs(tabs)).tabs)).toBe(true)
  expect(TAB_STORAGE_KEY).toBe('ns-workspace-tabs')
})

test('the Bojo summary names the open tab and its state, never invented data', () => {
  const tabs = [tabForPath('/listings'), tabForPath('/product-finder', '?view=set')]
  const summary = tabSummary({
    tabs, activeTab: tabs[1], scrollTop: 412.4, at: '2026-11-09T00:00:00.000Z',
  })
  expect(summary).toMatchObject({
    kind: 'workspace_tab',
    tabId: 'product-finder',
    serviceId: 'product-finder',
    label: 'SourceScout',
    path: '/product-finder',
    view: 'set',
    query: { view: 'set' },
    tabCount: 2,
    scrollTop: 412,
    capturedAt: '2026-11-09T00:00:00.000Z',
  })
  expect(summary.openTabs.map((t) => t.id)).toEqual(['listings', 'product-finder'])
  expect(tabSummary({})).toMatchObject({ tabId: '', tabCount: 0, openTabs: [] })
})

test('every tab route pattern is a real <Route> in App.jsx', () => {
  for (const id of TAB_SERVICE_IDS) {
    for (const pattern of TAB_ROUTE_PATTERNS[id]) {
      expect(ROUTE_PATHS, `${id}: ${pattern} is not registered in App.jsx`).toContain(pattern)
    }
  }
})

test('every tab id is a real interactive service, and has exactly one panel', () => {
  expect(Object.keys(TAB_PANELS).sort()).toEqual([...TAB_SERVICE_IDS].sort())
  for (const id of TAB_SERVICE_IDS) {
    const service = SERVICE_REGISTRY.find((s) => s.id === id)
    expect(service, `${id} is not in serviceRegistry`).toBeTruthy()
    expect(typeof service.route).toBe('string')
    expect(service.interactive).toBe(true)
  }
})
