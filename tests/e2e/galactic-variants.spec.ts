import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

// Localhost-only capture. Entry point under tests/e2e/, every URL 127.0.0.1 —
// the one case where Playwright Test is the default browser path rather than
// Chrome Connect.
//
// The 2026-10-31 theme set is ten FLUX 3 cluster plates. Each look is an image
// with a slow CSS camera drift and a CSS meteor field, so the test waits for
// the plate image and the variant marker instead of a WebGL "final" state.

const OUT = path.resolve('reports', 'theme_review')

const VARIANTS = [
  'orion-nursery', 'pleiades-veil', 'carina-cliffs', 'crab-pulsar',
  'andromeda-spiral', 'globular-core', 'magellanic-reef', 'black-hole-disk',
  'meteor-rain', 'rose-galaxy',
]

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true })
})

async function shoot(page, variantId, index) {
  await page.goto(`/ui/?galactic=${variantId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mb-shell')).toBeVisible({ timeout: 30000 })
  const backdrop = page.getByTestId('galactic-backdrop')
  await expect(backdrop).toHaveAttribute('data-galactic-variant', variantId, { timeout: 20000 })
  const plate = page.locator('img.galactic-cluster')
  await expect(plate).toBeVisible({ timeout: 20000 })
  await expect(plate).toHaveAttribute('src', /\/assets\/.*\.webp/)
  expect(await page.locator('.galactic-meteor').count()).toBeGreaterThan(0)
  await page.waitForTimeout(500)
  const file = path.join(OUT, `${String(index + 1).padStart(2, '0')}-${variantId}.png`)
  await page.screenshot({ path: file, fullPage: false })
}

test('capture the shipped theme (Orion’s Cradle)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await shoot(page, 'orion-nursery', 0)
  fs.copyFileSync(
    path.join(OUT, '01-orion-nursery.png'),
    path.join(OUT, '00-current.png'),
  )
})

for (const [i, id] of VARIANTS.entries()) {
  test(`variant ${i + 1}: ${id}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await shoot(page, id, i + 1)
  })
}
