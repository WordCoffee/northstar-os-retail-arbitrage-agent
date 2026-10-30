import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

// Localhost-only capture. Entry point under tests/e2e/, every URL 127.0.0.1 —
// the one case where Playwright Test is the default browser path rather than
// Chrome Connect.
//
// The Galactic plate is a one-shot WebGL render, so each shot waits for
// data-galactic-render="final" and for the variant id to match, instead of
// sleeping. A fixed sleep would race a slow GPU and capture a half-painted
// frame from the previous variant.

const OUT = path.resolve('reports', 'theme_review')

const VARIANTS = [
  'event-horizon', 'gargantua', 'sagittarius', 'andromeda', 'photon-ring',
  'nebula-bloom', 'quasar', 'void-architecture', 'solar-ash', 'observatory',
]

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true })
})

async function shoot(page, variantId, index) {
  await page.goto(`/ui/?galactic=${variantId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mb-shell')).toBeVisible({ timeout: 30000 })
  const plate = page.locator('canvas[data-testid="galactic-plate"]')
  await expect(plate).toBeVisible({ timeout: 15000 })
  await expect(plate).toHaveAttribute('data-galactic-render', 'final', { timeout: 40000 })
  await expect(plate).toHaveAttribute('data-galactic-variant', variantId, { timeout: 20000 })
  await page.waitForTimeout(600)
  const file = path.join(OUT, `${String(index + 1).padStart(2, '0')}-${variantId}.png`)
  await page.screenshot({ path: file, fullPage: false })
}

test('capture the shipped theme (event horizon)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await shoot(page, 'event-horizon', 0)
  fs.copyFileSync(
    path.join(OUT, '01-event-horizon.png'),
    path.join(OUT, '00-current.png'),
  )
})

for (const [i, id] of VARIANTS.entries()) {
  test(`variant ${i + 1}: ${id}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await shoot(page, id, i + 1)
  })
}
