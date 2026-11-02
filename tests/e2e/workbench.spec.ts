// U3 — the shell. Localhost only (Playwright Test is the sanctioned path for
// tests/e2e against 127.0.0.1).
//
// Asserts the frame a user actually gets: the workbench opens from the top nav,
// a service tab loads, a second service opens beside it, the first tab's state
// survives a switch, and the phone layout does not overflow.
//
// Every control that the test taps is also hit-tested first: elementFromPoint at
// its centre must resolve inside that control. A fixed scene layer that paints
// over the shell still passes toBeVisible() and still receives a click in some
// browsers, so visibility alone is not evidence that a human can tap it.

import { test, expect, type Page } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

// Rendering the studio + dashboard inside a tab is heavier than a static page;
// the default 30 s per-test budget is not enough on a cold Vite transform.
test.describe.configure({ timeout: 120000 })

const isPhone = () => test.info().project.name.includes('mobile')

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { window.sessionStorage.removeItem('ns-ux-tabs') } catch { /* ignore */ }
  })
})

// The control must be the topmost element at its own centre. Returns the hit
// label on failure so a swallowed click names what swallowed it.
async function expectTopmost(page: Page, testId: string) {
  const el = page.getByTestId(testId)
  await expect(el).toBeVisible({ timeout: 30000 })
  await el.scrollIntoViewIfNeeded()
  const box = await el.boundingBox()
  expect(box, `${testId} has no bounding box`).not.toBeNull()
  const hit = await page.evaluate(({ x, y, id }) => {
    const node = document.elementFromPoint(x, y)
    if (!node) return 'none'
    if (node.closest(`[data-testid="${id}"]`)) return 'self'
    const cls = typeof node.className === 'string' ? node.className : ''
    return `${node.tagName.toLowerCase()}.${cls}`.replace(/\.$/, '')
  }, { x: box!.x + box!.width / 2, y: box!.y + box!.height / 2, id: testId })
  expect(hit, `${testId} is covered by ${hit}`).toBe('self')
}

// Phones collapse the tab strip behind the switcher; desktop always shows it.
async function revealTabs(page: Page) {
  const switcher = page.getByTestId('wb-switcher')
  if (await switcher.isVisible()) {
    await switcher.click()
    await expect(page.getByTestId('wb-tabs')).toBeVisible()
  }
}

test('the workbench opens from the top nav and shows the shell', async ({ page }) => {
  await page.goto('/ui/home')
  // The entry itself must be tappable at 390 px, not merely present in the DOM
  // and scrolled to by Playwright.
  await expectTopmost(page, 'ns-workbench-open')
  await page.getByTestId('ns-workbench-open').click()
  await expect(page).toHaveURL(/\/ui\/workbench/)
  await expect(page.getByTestId('workbench-shell')).toBeVisible()
  await expect(page.getByTestId('wb-tabbar')).toBeVisible()

  // Bojo has two homes: the left dock on desktop, the bottom sheet on a phone.
  if (isPhone()) {
    await expectTopmost(page, 'wb-sheet-toggle')
    // The sheet is collapsed to peek height on arrival; assert the mount, not
    // a 0 px box, then prove the toggle really opens it.
    await expect(page.getByTestId('wb-sheet')).toHaveCount(1)
    await page.getByTestId('wb-sheet-toggle').click()
    await expect(page.getByTestId('wb-sheet')).toHaveAttribute('data-state', 'half')
  } else {
    await expect(page.getByTestId('bojo-dock')).toBeVisible()
  }
})

test('a service tab loads its workspace', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('wb-panel-design-studio')).toBeVisible({ timeout: 30000 })
  // The studio opens on Projects; the dashboard is one section in.
  await page.getByTestId('wb-panel-design-studio').getByRole('button', { name: 'Asset Dashboard' }).click()
  await expect(page.getByTestId('asset-dashboard')).toBeVisible({ timeout: 30000 })
})

test('a second service opens as a tab and the first keeps its state', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('wb-panel-design-studio')).toBeVisible({ timeout: 30000 })

  // Put the design tab into a specific state: open the studio's Asset Dashboard.
  // On its own route that section is a query parameter; embedded in a tab it
  // lives in component state, so it can only survive if the tab stayed mounted.
  // (Deliberately not the asset <select>: that list comes from a rate-limited
  // endpoint and would make a shell test depend on API throttling.)
  await page.getByTestId('wb-panel-design-studio').getByRole('button', { name: 'Asset Dashboard' }).click()
  await expect(page.getByTestId('asset-dashboard')).toBeVisible({ timeout: 30000 })

  // Open a second service from the picker. The picker must be on top at the
  // point we tap, or the fixed scene layer is eating the click.
  await expectTopmost(page, 'wb-add')
  await page.getByTestId('wb-add').click()
  await expect(page.getByTestId('wb-picker')).toBeVisible()
  await expectTopmost(page, 'wb-open-golden-goose')
  await page.getByTestId('wb-open-golden-goose').click()
  await expect(page.getByTestId('wb-panel-golden-goose')).toBeVisible({ timeout: 30000 })
  // Still mounted, only hidden: the contract that keeps workspace state alive.
  await expect(page.getByTestId('wb-panel-design-studio')).toHaveCount(1)
  await expect(page.getByTestId('wb-panel-design-studio')).toBeHidden()

  // Back to the design tab: the dashboard section is still open.
  await revealTabs(page)
  await expectTopmost(page, 'wb-tab-design-studio')
  await page.getByTestId('wb-tab-design-studio').click()
  await expect(page.getByTestId('wb-panel-design-studio')).toBeVisible()
  await expect(page.getByTestId('asset-dashboard')).toBeVisible()
})

test('closing a tab never leaves the shell empty', async ({ page }) => {
  await page.goto(WORKBENCH)
  await page.getByTestId('wb-add').click()
  await expectTopmost(page, 'wb-open-profitability')
  await page.getByTestId('wb-open-profitability').click()
  await expect(page.getByTestId('wb-panel-profitability')).toBeVisible({ timeout: 30000 })

  await revealTabs(page)
  await expectTopmost(page, 'wb-close-design-studio')
  await page.getByTestId('wb-close-design-studio').click()
  await expectTopmost(page, 'wb-close-profitability')
  await page.getByTestId('wb-close-profitability').click()

  // The last close falls back to the default tab instead of a blank outlet.
  await expect(page.getByTestId('wb-panel-design-studio')).toBeVisible({ timeout: 30000 })
})

test('the phone layout does not overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 60000 })

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
})
