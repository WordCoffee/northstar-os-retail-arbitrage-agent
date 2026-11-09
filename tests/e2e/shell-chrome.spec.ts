// ux-06 — shell chrome on every service route.
//
// The frame every authed route must render: TopNav + side nav (SuiteRail) + a
// workspace outlet, with the DevBanner above it. The route table is read from
// `northstar-os-ui/src/App.jsx` at run time, so this spec follows the table
// instead of a copy of it: adding a route adds it to this walk automatically.
//
// Classification comes from the same module the app uses
// (`northstar-os-ui/src/shell/shellRoutes.js`), and the unit test
// (`src/shell/shellRoutes.test.js`) pins that list to the table.
//
// LOCALHOST ONLY (127.0.0.1:8101) — the narrow e2e exception in AGENTS.md; the
// spec makes no external request.

import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { isShellExempt } from '../../northstar-os-ui/src/shell/shellRoutes.js'

test.describe.configure({ timeout: 900000 })

const APP_SOURCE = readFileSync(resolve('northstar-os-ui/src/App.jsx'), 'utf8')

/** "<Route path=\"…\">" in declaration order, exactly as App.jsx registers them. */
const ROUTE_PATHS: string[] = [...APP_SOURCE.matchAll(/<Route path="([^"]+)"/g)]
  .map((m) => m[1])

/** In-shell routes, minus the catch-all (asserted separately). */
const SHELL_ROUTES = ROUTE_PATHS.filter((p) => p !== '*' && !isShellExempt(p))

/** A concrete URL for a route pattern. */
function urlFor(pattern: string): string {
  const concrete = pattern.replace(/\/\*$/, '').replace(/:id/g, 'sample-1')
  return `/ui${concrete}`
}

async function expectChrome(page: Page, label: string) {
  await expect(page.getByTestId('shell-chrome'), `${label}: no shell-chrome frame`).toBeVisible({ timeout: 20000 })
  await expect(page.locator('header.top-nav'), `${label}: no TopNav`).toBeVisible({ timeout: 20000 })
  await expect(page.locator('aside.suite-rail'), `${label}: no side nav`).toBeVisible({ timeout: 20000 })
  await expect(page.getByTestId('workspace-outlet'), `${label}: no workspace outlet`).toBeVisible({ timeout: 20000 })
}

async function expectOutletOwnsThePage(page: Page, label: string) {
  const owns = await page.evaluate(() => {
    const outlet = document.querySelector('[data-testid="workspace-outlet"]')
    if (!outlet) return false
    // At least one child that is not the sr-only app-name paragraph.
    return Array.from(outlet.children).some(
      (el) => !(el instanceof HTMLParagraphElement && el.classList.contains('sr-only')),
    )
  })
  expect(owns, `${label}: the outlet rendered no page content`).toBe(true)
}

test('the route table is the 72 routes App.jsx registers', () => {
  expect(ROUTE_PATHS).toHaveLength(72)
  const exempt = ROUTE_PATHS.filter((p) => p !== '*' && isShellExempt(p))
  expect(exempt).toEqual(['/sign-in', '/recovery', '/beta', '/beta/accept', '/legal'])
  // 72 = 66 concrete in-shell patterns + the catch-all (asserted below) + 5
  // exempt entry surfaces.
  expect(SHELL_ROUTES).toHaveLength(66)
  expect(SHELL_ROUTES).not.toContain('*')
})

test('every in-shell route renders TopNav + side nav + an outlet', async ({ page }) => {
  for (const route of SHELL_ROUTES) {
    const url = urlFor(route)
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await expectChrome(page, route)
    await expectOutletOwnsThePage(page, route)
  }
})

test('the catch-all renders inside the shell, not a bare NotFound', async ({ page }) => {
  await page.goto('/ui/this-route-does-not-exist', { waitUntil: 'domcontentloaded' })
  await expectChrome(page, 'catch-all')
})

test('the chat-first frame keeps the chat inside the outlet', async ({ page }) => {
  for (const url of ['/ui/', '/ui/home']) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await expectChrome(page, url)
    // The chat is the page's own layout: the shell must frame it, not replace it.
    await expect(
      page.getByTestId('workspace-outlet').getByTestId('chat-input').first(),
    ).toBeVisible({ timeout: 30000 })
  }
})

test('a room keeps its own content area inside the outlet', async ({ page }) => {
  await page.goto('/ui/listings', { waitUntil: 'domcontentloaded' })
  await expectChrome(page, '/listings')
  await expect(
    page.getByTestId('workspace-outlet').getByRole('heading', { name: 'Listing Guardian' }),
  ).toBeVisible({ timeout: 30000 })

  await page.goto('/ui/product-finder', { waitUntil: 'domcontentloaded' })
  await expectChrome(page, '/product-finder')
  await expect(
    page.getByTestId('workspace-outlet').getByRole('heading', { name: 'SourceScout' }),
  ).toBeVisible({ timeout: 30000 })
})

test('entry surfaces stay outside the shell, and still carry the dev notice', async ({ page }) => {
  // /sign-in is a dev redirect to /home here, so its exemption is proved by the
  // unit test on shellRoutes.js rather than by a visit.
  for (const route of ['/beta', '/recovery', '/legal']) {
    await page.goto(`/ui${route}`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('main[data-testid="workspace-outlet"]')).toBeVisible({ timeout: 20000 })
    await expect(page.getByTestId('shell-chrome'), `${route}: rendered shell chrome`).toHaveCount(0)
    await expect(page.locator('header.top-nav'), `${route}: rendered TopNav`).toHaveCount(0)
    await expect(page.locator('aside.suite-rail'), `${route}: rendered the side nav`).toHaveCount(0)
    // The banner is above the chrome decision, so it survives the exemption.
    await expect(page.getByTestId('dev-banner'), `${route}: no dev banner`).toContainText('DEV: AUTH DISABLED')
  }
})
