// Contract-01: ProductFinder must CALL /api/products/finder, not stage UNKNOWNs.
//
// The page named the endpoint only in comments before 2026-11-09. This spec
// proves three things a comment cannot:
//   1. adding an ASIN issues the request and the returned candidate is rendered;
//   2. a backend refusal is shown as a refusal and stages no row;
//   3. an ASIN the cache does not know is reported as absent, not invented.
//
// LOCALHOST ONLY (127.0.0.1), per the AGENTS.md e2e exception. No Amazon host is
// contacted; the endpoint is the local cache-only finder.

import { test, expect, type Page } from '@playwright/test'

const ROUTE = '/ui/product-finder'
const FINDER = '**/api/products/finder*'

async function seedRow(page: Page) {
  const response = await page.request.get('/api/products/finder?limit=100')
  expect(response.ok(), 'finder endpoint must answer before the page can').toBeTruthy()
  const payload = await response.json()
  const rows = (payload && payload.data && payload.data.evaluated) || []
  expect(rows.length, 'the local cache must hold at least one candidate').toBeGreaterThan(0)
  return rows.find((row: any) => row.asin && typeof row.amazon_price === 'number') || rows[0]
}

test('adding an ASIN calls the finder and renders the real cached row', async ({ page }) => {
  const row = await seedRow(page)

  const pending = page.waitForResponse(
    res => res.url().includes('/api/products/finder') && res.request().method() === 'GET',
  )

  await page.goto(ROUTE)
  await expect(page.getByTestId('pf-asin-input')).toBeVisible()
  await page.getByTestId('pf-asin-input').fill(row.asin)
  await page.getByTestId('pf-add').click()

  const response = await pending
  expect(response.status()).toBe(200)

  const table = page.locator('table').first()
  await expect(table).toContainText(row.asin)
  await expect(table).toContainText(row.name)
  if (typeof row.amazon_price === 'number') {
    await expect(table).toContainText(String(row.amazon_price))
  }
  await expect(page.getByTestId('pf-lookup-note')).toContainText(row.asin)
  await expect(page.getByTestId('pf-lookup-error')).toHaveCount(0)
})

test('a backend refusal is shown honestly and stages no row', async ({ page }) => {
  await page.route(FINDER, route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({
      detail: { code: 'finder_unavailable', message: 'cache is offline' },
    }),
  }))

  await page.goto(ROUTE)
  await page.getByTestId('pf-asin-input').fill('B0REFUSED1')
  await page.getByTestId('pf-add').click()

  const alert = page.getByTestId('pf-lookup-error')
  await expect(alert).toBeVisible()
  await expect(alert).toContainText('finder_unavailable')
  await expect(alert).toContainText('cache is offline')
  // No candidate came back, so no row is staged.
  await expect(page.locator('table').first()).toContainText('No records found')
})

test('an uncached ASIN is reported as absent, never invented', async ({ page }) => {
  await page.goto(ROUTE)
  await page.getByTestId('pf-asin-input').fill('B0ZZZZZZZZ')
  await page.getByTestId('pf-add').click()

  await expect(page.getByTestId('pf-lookup-missing')).toContainText('No cached observation')
  const table = page.locator('table').first()
  await expect(table).toContainText('B0ZZZZZZZZ')
  await expect(table).toContainText('Not in cache')
  await expect(table).toContainText('No cached observation')
})
