// ux-07 — the workspace tab bar.
//
// What this proves, on the real app at 127.0.0.1:8101:
//   1. a workspace route opens exactly one tab, selected and correctly labelled
//   2. switching tabs does NOT remount the page: typed input and scroll offset
//      survive a round trip, and the page is not refetched
//   3. tabs switch from the keyboard (ArrowLeft/ArrowRight), with aria-selected
//      following the panel
//   4. closing the active tab lands on a surviving tab; closing the last tab
//      goes home, so the router is never left on a route whose tab is gone
//   5. the shell publishes the open tab and its state for Bojo
//
// LOCALHOST ONLY (127.0.0.1:8101), per the narrow e2e exception in AGENTS.md.
// No external host is contacted. The dev session works without the backend
// (foundation/session.jsx dev bypass), and every page used here renders from
// local fixtures, so a backend outage cannot make this spec pass or fail.

import { test, expect, type Page } from '@playwright/test'

test.use({ viewport: { width: 1280, height: 460 } })

const OUTLET = '[data-testid="workspace-outlet"]'
const TABS = '[data-testid="workspace-tabs"]'

async function openFromRail(page: Page, label: string) {
  // The rail item's accessible name carries its readiness chip ("Listing
  // Guardian Local"), so match the label as a prefix rather than exactly.
  await page.locator('aside.suite-rail').getByRole('button', { name: label }).click()
}

async function outletScrollTop(page: Page): Promise<number> {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel) as HTMLElement | null
    return el ? el.scrollTop : -1
  }, OUTLET)
}

test('a workspace route opens one selected tab', async ({ page }) => {
  await page.goto('/ui/listings', { waitUntil: 'domcontentloaded' })

  await expect(page.getByTestId('workspace-tabs')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('workspace-tabs')).toHaveAttribute('data-tab-count', '1')

  const tab = page.getByRole('tab', { name: 'Listing Guardian' })
  await expect(tab).toHaveAttribute('aria-selected', 'true')
  await expect(tab).toHaveAttribute('aria-controls', 'wst-panel-listings')
  await expect(tab).toHaveAttribute('tabindex', '0')

  const panel = page.locator('#wst-panel-listings')
  await expect(panel).toBeVisible()
  await expect(panel).toHaveAttribute('role', 'tabpanel')
  await expect(panel).toHaveAttribute('data-tab-path', '/listings')

  // The tab bar sits inside the chrome, above the outlet, and the outlet still
  // owns the page (the ux-06 frame is intact).
  await expect(page.getByTestId('shell-chrome')).toHaveAttribute('data-active-tab', 'listings')
  await expect(page.locator('header.top-nav')).toBeVisible()
  await expect(page.locator('aside.suite-rail')).toBeVisible()
})

test('switching tabs preserves input, scroll and loaded data (no remount)', async ({ page }) => {
  await page.goto('/ui/product-finder', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('tab', { name: 'SourceScout' })).toHaveAttribute('aria-selected', 'true')

  // Deliberately half-finished input: a remount would clear it.
  const asin = page.getByTestId('pf-asin-input')
  await asin.fill('B0TEST1234')

  // Scroll the outlet (the shell's scroll container) to a position that is not
  // the top. If the page were shorter than the viewport this stays 0 and the
  // assertion below is meaningless, so it is asserted first.
  const scrolled = await page.evaluate((sel) => {
    const el = document.querySelector(sel) as HTMLElement
    el.scrollTop = Math.min(220, Math.max(0, el.scrollHeight - el.clientHeight))
    return el.scrollTop
  }, OUTLET)
  expect(scrolled, 'SourceScout page is not tall enough to test scroll memory').toBeGreaterThan(0)

  // Open a second workspace from the rail, then come back.
  await openFromRail(page, 'Listing Guardian')
  await expect(page.getByRole('tab', { name: 'Listing Guardian' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByTestId('workspace-tabs')).toHaveAttribute('data-tab-count', '2')
  await expect(page.locator('#wst-panel-product-finder')).toBeHidden()

  // A hidden tab must not keep rebuilding. The input value and scroll offset
  // above already prove the page was not remounted; this counter is the extra
  // check that the hidden panel did not replay a request while it was behind.
  const requests: string[] = []
  page.on('request', (r) => {
    if (r.url().includes('/api/product-finder')) requests.push(r.url())
  })

  await page.getByRole('tab', { name: 'SourceScout' }).click()
  await expect(page.locator('#wst-panel-product-finder')).toBeVisible()
  await expect(page).toHaveURL(/\/ui\/product-finder$/)

  await expect(asin).toHaveValue('B0TEST1234')
  expect(await outletScrollTop(page)).toBe(scrolled)
  expect(requests, 'switching tabs refetched the workspace').toEqual([])
})

test('tabs switch from the keyboard and aria-selected follows the panel', async ({ page }) => {
  await page.goto('/ui/listings', { waitUntil: 'domcontentloaded' })
  await openFromRail(page, 'SourceScout')
  await expect(page.getByRole('tab', { name: 'SourceScout' })).toHaveAttribute('aria-selected', 'true')

  await page.getByRole('tab', { name: 'SourceScout' }).focus()
  await page.keyboard.press('ArrowLeft')

  const listings = page.getByRole('tab', { name: 'Listing Guardian' })
  await expect(listings).toHaveAttribute('aria-selected', 'true')
  await expect(listings).toBeFocused()
  await expect(page).toHaveURL(/\/ui\/listings$/)
  await expect(page.locator('#wst-panel-listings')).toBeVisible()

  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'SourceScout' })).toHaveAttribute('aria-selected', 'true')
  await expect(page).toHaveURL(/\/ui\/product-finder$/)
})

test('closing the active tab lands on a survivor; closing the last tab goes home', async ({ page }) => {
  await page.goto('/ui/listings', { waitUntil: 'domcontentloaded' })
  await openFromRail(page, 'SourceScout')
  await openFromRail(page, 'Profitability Dashboard')

  // Active now: Profitability (third tab). Close it -> the tab to its left.
  await expect(page.getByTestId('workspace-tabs')).toHaveAttribute('data-tab-count', '3')
  await page.getByTestId('tab-close-profitability').click()
  await expect(page.getByRole('tab', { name: 'Profitability' })).toHaveCount(0)
  await expect(page).toHaveURL(/\/ui\/product-finder$/)
  await expect(page.getByTestId('shell-chrome')).toHaveAttribute('data-active-tab', 'product-finder')

  // No dangling route: the URL always belongs to a tab that still exists.
  const active = await page.getByTestId('shell-chrome').getAttribute('data-active-tab')
  await expect(page.locator(`[data-testid="tab-${active}"]`)).toHaveCount(1)

  // Close the remaining two; the last one goes home and the strip empties.
  await page.getByTestId('tab-close-product-finder').click()
  await expect(page).toHaveURL(/\/ui\/listings$/)
  await page.getByTestId('tab-close-listings').click()
  await expect(page).toHaveURL(/\/ui\/home$/)
  await expect(page.getByTestId('workspace-tabs')).toHaveCount(0)
  await expect(page.getByTestId('shell-chrome')).toHaveAttribute('data-active-tab', '')
})

test('the shell tells Bojo which tab is open and what state it has', async ({ page }) => {
  await page.goto('/ui/product-finder', { waitUntil: 'domcontentloaded' })
  await openFromRail(page, 'Listing Guardian')

  const raw = await page.getByTestId('shell-chrome').getAttribute('data-tab-summary')
  expect(raw).toBeTruthy()
  const summary = JSON.parse(raw as string)
  expect(summary).toMatchObject({
    kind: 'workspace_tab',
    tabId: 'listings',
    serviceId: 'listings',
    label: 'Listing Guardian',
    path: '/listings',
    tabCount: 2,
  })
  expect(summary.openTabs.map((t: { id: string }) => t.id)).toEqual(['product-finder', 'listings'])

  // Same object on the global the chat surface can read, and it updates with
  // the switch (no stale summary).
  const fromGlobal = await page.evaluate(() => (globalThis as any).__northstarWorkspaceTab)
  expect(fromGlobal).toMatchObject({ tabId: 'listings', label: 'Listing Guardian' })

  await page.getByRole('tab', { name: 'SourceScout' }).click()
  await expect
    .poll(async () => {
      const next = await page.getByTestId('shell-chrome').getAttribute('data-tab-summary')
      return next ? JSON.parse(next).tabId : ''
    })
    .toBe('product-finder')
})
