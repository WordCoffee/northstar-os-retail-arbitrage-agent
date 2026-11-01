import { test, expect } from '@playwright/test'

// Localhost-only visual check for the standalone Galactic preview served on
// 127.0.0.1:8124. Entry point under tests/e2e, every URL is 127.0.0.1, so this
// is the documented Playwright Test local case.
test('the ten-theme preview renders plates and meteors', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('http://127.0.0.1:8124/', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Galactic themes' })).toBeVisible()
  await expect(page.locator('img.galactic-cluster')).toBeVisible()
  const meteors = await page.locator('.galactic-meteor').count()
  expect(meteors).toBeGreaterThan(4)
  await page.screenshot({ path: 'reports/theme_review/preview-orion.png', fullPage: false })
  await page.getByRole('button', { name: /Carina Ridge/ }).click()
  await expect(page.getByRole('heading', { name: 'Carina Ridge' })).toBeVisible()
  await expect(page.locator('img.galactic-cluster')).toHaveAttribute('src', /carina-cliffs/)
})
