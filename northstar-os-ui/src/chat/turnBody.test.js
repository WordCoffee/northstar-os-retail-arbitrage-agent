// ux-07b: a chat turn must carry the tab the operator is looking at.
//
// The shell publishes the summary (shell/tabRoutes.js `tabSummary`, published by
// shell/ShellLayout.jsx); `turnBody.js` narrows it for the model. These tests
// pin the resulting REQUEST BODY — present when a tab is open, absent when it
// is not — and pin ChatSurface to that builder, so the field cannot quietly
// stop being sent.

import { test, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { tabSummary } from '../shell/tabRoutes.js'
import { buildTurnBody, readPublishedTab, tabContextFromSummary } from './turnBody.js'

const here = dirname(fileURLToPath(import.meta.url))
const CHAT_SURFACE = readFileSync(resolve(here, 'ChatSurface.jsx'), 'utf8')

const listingsTab = { id: 'listings', serviceId: 'listings', label: 'Listings', path: '/listings', search: '' }
const finderTab = {
  id: 'product-finder', serviceId: 'product-finder', label: 'Product Finder',
  path: '/product-finder/B0ABCDEFGH', search: '?view=offers',
}

function summaryFor(activeTab) {
  return tabSummary({ tabs: activeTab ? [listingsTab, activeTab] : [listingsTab], activeTab })
}

test('an open tab narrows to id, route, title and a small state digest', () => {
  const tab = tabContextFromSummary(summaryFor(finderTab))
  expect(tab).toMatchObject({
    id: 'product-finder',
    route: '/product-finder/B0ABCDEFGH?view=offers',
    title: 'Product Finder',
    state: { view: 'offers', query: { view: 'offers' } },
  })
  // Nothing from the shell that the model cannot use (scroll offset, capture
  // time) and no page content is forwarded.
  expect(Object.keys(tab.state).sort()).toEqual(['openTabs', 'query', 'tabCount', 'view'])
  expect(tab.state.openTabs).toEqual(['listings', 'product-finder'])
})

test('a turn with a tab carries it in the request body', () => {
  const body = buildTurnBody({ content: 'what is this?', tab: tabContextFromSummary(summaryFor(finderTab)) })
  const wire = JSON.parse(JSON.stringify(body))   // exactly what streamTurn sends
  expect(wire.tab).toEqual({
    id: 'product-finder',
    route: '/product-finder/B0ABCDEFGH?view=offers',
    title: 'Product Finder',
    state: { view: 'offers', query: { view: 'offers' }, openTabs: ['listings', 'product-finder'], tabCount: 2 },
  })
  // The fields the turn already sent are untouched.
  expect(wire).toMatchObject({ content: 'what is this?', think: true, attachments: [] })
})

test('no open tab means the field is absent, not null and not an empty object', () => {
  const tab = tabContextFromSummary(summaryFor(null))
  expect(tab).toBeUndefined()
  const wire = JSON.parse(JSON.stringify(buildTurnBody({ content: 'hello', tab })))
  expect('tab' in wire).toBe(false)
  expect(wire.tab).toBeUndefined()
})

test('the published summary is read from the DOM attribute first, then the global', () => {
  const summary = summaryFor(finderTab)
  const doc = {
    querySelector: () => ({ getAttribute: () => JSON.stringify(summary) }),
  }
  const glob = { __northstarWorkspaceTab: summaryFor(listingsTab) }
  expect(readPublishedTab(doc, glob).id).toBe('product-finder')

  // No attribute (the chat can render outside the shell frame): the global.
  const bare = { querySelector: () => null }
  expect(readPublishedTab(bare, glob)).toMatchObject({ id: 'listings', title: 'Listings' })

  // Neither: no tab, so the turn simply has none.
  expect(readPublishedTab(bare, {})).toBeUndefined()
  // A malformed attribute must not throw a turn away.
  const broken = { querySelector: () => ({ getAttribute: () => '{not json' }) }
  expect(readPublishedTab(broken, {})).toBeUndefined()
})

test('ChatSurface builds its turn body from this module and reads the published tab', () => {
  expect(CHAT_SURFACE).toMatch(/import \{ buildTurnBody, readPublishedTab \} from '\.\/turnBody\.js'/)
  expect(CHAT_SURFACE).toMatch(/streamTurn\(sid, buildTurnBody\(\{/)
  expect(CHAT_SURFACE).toMatch(/tab: readPublishedTab\(\)/)
})
