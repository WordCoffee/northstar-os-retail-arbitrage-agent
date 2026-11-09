// Which routes are workspace tabs, and the pure rules that manage them.
//
// A tab is a WORKSPACE, not a browser history entry: one tab per service, and
// navigating inside a service (`/product-finder/B0…`) re-points that tab
// instead of opening a second one. `/home` is Bojo's home, not a workspace, so
// it deliberately has no tab.
//
// This file is pure on purpose: no React, no DOM. The shell component that
// renders the strip (`TabBar.jsx`), the panels (`WorkspacePanels.jsx`) and the
// state hook (`useWorkspaceTabs.js`) all read the rules from here, so the
// behaviour can be unit-tested without a browser.
//
// Pinned to App.jsx by `tabRoutes.test.js`: every route pattern below must be a
// real `<Route>` in the app, and every service id must exist in
// `data/serviceRegistry.js`.

import { getService } from '../data/serviceRegistry.js'

/** sessionStorage key. Per browser tab, cleared when the tab is closed. */
export const TAB_STORAGE_KEY = 'ns-workspace-tabs'

// Service id -> the route patterns its panel can match. The panel map in
// `WorkspacePanels.jsx` renders exactly these patterns through
// `<Routes location={tab path}>`.
export const TAB_ROUTE_PATTERNS = {
  'design-studio': ['/design-studio/*'],
  'product-finder': ['/product-finder', '/product-finder/:id'],
  'golden-goose': ['/golden-goose', '/golden-goose/:id'],
  listings: ['/listings'],
  listingforge: ['/listingforge'],
  adpilot: ['/adpilot'],
  socialpulse: ['/socialpulse'],
  profitability: ['/profitability'],
  autothink: ['/autothink'],
  'keyword-tracker': ['/keyword-tracker'],
  'competitor-monitor': ['/competitor-monitor'],
}

export const TAB_SERVICE_IDS = Object.keys(TAB_ROUTE_PATTERNS)

/** `/a/b/` and `/a/b` are the same location; `/` stays `/`. */
export function normalizePath(path = '') {
  const trimmed = String(path).replace(/\/+$/, '')
  return trimmed || '/'
}

/**
 * The service whose workspace owns `pathname`, or null.
 *
 * Longest route wins, so a future `/listingforge/:id` is not swallowed by
 * `/listings`. Prefixes are matched on a segment boundary, so `/listings-old`
 * is not `/listings`.
 */
export function tabServiceForPath(pathname = '') {
  const path = normalizePath(pathname)
  let best = null
  for (const id of TAB_SERVICE_IDS) {
    const service = getService(id)
    if (!service || !service.route) continue
    const route = normalizePath(service.route)
    const owns = path === route || path.startsWith(route + '/')
    if (owns && (!best || route.length > normalizePath(best.route).length)) best = service
  }
  return best
}

/**
 * The tab a location belongs to, or null when the location is not a workspace.
 * Keeps the search string: filters inside a workspace (`?view=set`) are part of
 * the tab's state, and reloading the tab must return to them.
 */
export function tabForPath(pathname = '', search = '') {
  const service = tabServiceForPath(pathname)
  if (!service) return null
  const path = normalizePath(pathname)
  const qs = search && search !== '?' ? (search.startsWith('?') ? search : `?${search}`) : ''
  return {
    id: service.id,
    serviceId: service.id,
    label: service.label || service.id,
    path,
    search: qs,
    href: `${path}${qs}`,
  }
}

function cleanTab(raw) {
  if (!raw || typeof raw !== 'object') return null
  const id = String(raw.id || '')
  if (!TAB_SERVICE_IDS.includes(id)) return null
  const service = getService(id)
  if (!service) return null
  // A stored path that no longer belongs to this service is repaired to the
  // service's own route rather than trusted: a rename must not leave a tab
  // pointing at another room's URL.
  const stored = typeof raw.path === 'string' ? raw.path : ''
  const tab = tabForPath(stored)
  const safe = tab && tab.id === id ? tab : tabForPath(service.route)
  if (!safe) return null
  const search = typeof raw.search === 'string' && raw.search.startsWith('?') ? raw.search : ''
  return { ...safe, search, href: `${safe.path}${search}` }
}

/**
 * Read `{ open: [...] }` from storage text.
 *
 * Corrupt JSON, an empty list, unknown ids and duplicates all degrade to what
 * is still valid — never to an exception, and never to a tab that points at a
 * route that does not belong to it.
 */
export function parseTabs(raw) {
  if (!raw) return { tabs: [] }
  let parsed = null
  try { parsed = JSON.parse(raw) } catch { return { tabs: [] } }
  const list = parsed && Array.isArray(parsed.open) ? parsed.open : []
  const tabs = []
  for (const item of list) {
    const tab = cleanTab(item)
    if (tab && !tabs.some((t) => t.id === tab.id)) tabs.push(tab)
  }
  return { tabs }
}

export function serializeTabs(tabs = []) {
  return JSON.stringify({ open: tabs.map((t) => ({ id: t.id, path: t.path, search: t.search })) })
}

/**
 * Add the tab for a location, or re-point the tab already open for its service.
 * Returns a new array; the caller keeps the old one if nothing changed.
 */
export function openTab(tabs = [], tab) {
  if (!tab) return tabs
  const index = tabs.findIndex((t) => t.id === tab.id)
  if (index === -1) return [...tabs, tab]
  const current = tabs[index]
  if (current.path === tab.path && current.search === tab.search) return tabs
  const next = tabs.slice()
  next[index] = tab
  return next
}

/**
 * Close one tab.
 *
 * Next tab: the one to the RIGHT, else the one to the left. Closing a tab that
 * is not active never navigates. Closing the LAST tab leaves an empty strip and
 * returns `/home`; that is the documented last-tab rule — the shell never
 * leaves the router pointing at a route whose tab has just been closed.
 */
export function closeTab(tabs = [], id, activeId = null) {
  const index = tabs.findIndex((t) => t.id === id)
  if (index === -1) return { tabs, activeId, nextPath: null }
  const next = tabs.filter((t) => t.id !== id)
  if (!next.length) return { tabs: [], activeId: null, nextPath: '/home' }
  if (activeId !== id) return { tabs: next, activeId, nextPath: null }
  const neighbour = next[Math.min(index, next.length - 1)]
  return { tabs: next, activeId: neighbour.id, nextPath: neighbour.href }
}

/** Shallow structural comparison, so effects do not loop on a new array. */
export function sameTabs(a = [], b = []) {
  if (a === b) return true
  if (a.length !== b.length) return false
  return a.every((t, i) => (
    t.id === b[i].id && t.path === b[i].path && t.search === b[i].search
  ))
}

/**
 * What the shell tells Bojo about the thing the operator is looking at.
 *
 * Only facts the shell actually owns: which workspace, where in it, which
 * other workspaces are open, and the last scroll offset it recorded for the
 * tab. Nothing is inferred about page content the shell cannot see.
 */
export function tabSummary({ tabs = [], activeTab = null, scrollTop = 0, at = null } = {}) {
  const query = {}
  if (activeTab?.search) {
    try {
      for (const [k, v] of new URLSearchParams(activeTab.search)) query[k] = v
    } catch { /* malformed search: report no filters */ }
  }
  return {
    kind: 'workspace_tab',
    tabId: activeTab?.id || '',
    serviceId: activeTab?.serviceId || '',
    label: activeTab?.label || '',
    path: activeTab?.path || '',
    search: activeTab?.search || '',
    view: query.view || '',
    query,
    openTabs: tabs.map((t) => ({ id: t.id, label: t.label, path: t.path })),
    tabCount: tabs.length,
    scrollTop: Number.isFinite(scrollTop) ? Math.max(0, Math.round(scrollTop)) : 0,
    capturedAt: at || new Date().toISOString(),
  }
}
