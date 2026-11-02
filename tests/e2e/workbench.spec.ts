// U3 — the shell. Localhost only (Playwright Test is the sanctioned path for
// tests/e2e against 127.0.0.1).
//
// Asserts the frame a user actually gets: the workbench opens from the top nav,
// a service tab loads, a second service opens beside it, the first tab's state
// survives a switch, and the phone layout does not overflow.

import { test, expect } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

// Rendering the studio + dashboard inside a tab is heavier than a static page;
// the default 30 s per-test budget is not enough on a cold Vite transform.
test.describe.configure({ timeout: 120000 })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { window.sessionStorage.removeItem('ns-ux-tabs') } catch { /* ignore */ }
  })
})

test('the workbench opens from the top nav and shows the shell', async ({ page }) => {
  await page.goto('/ui/home')
  await expect(page.getByTestId('ns-workbench-open')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('ns-workbench-open').click()
  await expect(page).toHaveURL(/\/ui\/workbench/)
  await expect(page.getByTestId('workbench-shell')).toBeVisible()
  await expect(page.getByTestId('bojo-dock')).toBeVisible()
  await expect(page.getByTestId('wb-tabbar')).toBeVisible()
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
  await page.getByTestId('wb-panel-design-studio').getByRole('button', { name: 'Asset Dashboard' }).click()

  // Put the design tab into a specific state: pick a non-default source asset.
  const select = page.getByTestId('dash-asset')
  await expect(select).toBeVisible({ timeout: 30000 })
  await expect.poll(async () => select.locator('option').count(), { timeout: 20000 })
    .toBeGreaterThan(1)
  const chosen = await select.locator('option').nth(1).getAttribute('value')
  await select.selectOption(chosen)

  // Open a second service from the picker.
  await page.getByTestId('wb-add').click()
  await expect(page.getByTestId('wb-picker')).toBeVisible()
  await page.getByTestId('wb-open-golden-goose').click()
  await expect(page.getByTestId('wb-panel-golden-goose')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('wb-panel-design-studio')).toBeHidden()

  // Back to the design tab: the select still holds the chosen asset.
  await page.getByTestId('wb-tab-design-studio').click()
  await expect(page.getByTestId('wb-panel-design-studio')).toBeVisible()
  await expect(page.getByTestId('dash-asset')).toHaveValue(chosen)
})

test('closing a tab never leaves the shell empty', async ({ page }) => {
  await page.goto(WORKBENCH)
  await page.getByTestId('wb-add').click()
  await page.getByTestId('wb-open-profitability').click()
  await expect(page.getByTestId('wb-panel-profitability')).toBeVisible({ timeout: 30000 })

  await page.getByTestId('wb-close-design-studio').click()
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
