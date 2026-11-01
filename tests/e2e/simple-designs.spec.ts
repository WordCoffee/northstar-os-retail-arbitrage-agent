import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

// Localhost-only capture of the ten Simple-mode compositions.
const OUT = path.resolve('reports', 'theme_review', 'simple')
const DESIGNS = [
  'hearth', 'zen', 'observatory', 'constellation', 'split',
  'instrument', 'magazine', 'theater', 'workbench', 'terminal',
]

test.beforeAll(() => fs.mkdirSync(OUT, { recursive: true }))

for (const [i, id] of DESIGNS.entries()) {
  test(`simple design ${i + 1}: ${id}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 960 })
    // Keep the public design gallery free of the operator's real chat records.
    await page.route('**/api/chat/sessions**', (route) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sessions: [] }),
    }))
    await page.goto(`/ui/?simple=${id}`, { waitUntil: 'domcontentloaded' })
    await page.addStyleTag({ content: '[data-testid="dev-banner"]{display:none!important}' })
    const shell = page.getByTestId('mb-shell')
    await expect(shell).toBeVisible({ timeout: 30000 })
    await expect(shell).toHaveAttribute('data-simple-design', id, { timeout: 10000 })
    await expect(page.locator('.chat-shell')).toBeVisible()
    await page.waitForTimeout(500)
    await page.screenshot({ path: path.join(OUT, `${String(i + 1).padStart(2, '0')}-${id}.png`) })
  })
}

test('design picker switches composition', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/ui/', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('simple-design-trigger').click()
  await expect(page.getByRole('dialog', { name: 'Choose a Simple mode design' })).toBeVisible()
  await page.getByTestId('simple-design-terminal').click()
  await expect(page.getByTestId('mb-shell')).toHaveAttribute('data-simple-design', 'terminal')
})
