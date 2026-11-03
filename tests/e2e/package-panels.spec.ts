// U8 final — package front/rear mode and the dieline overlay.
//
// The two things this must prove:
//   1. Panels keep their own layers: switching to Rear and back does not lose
//      the front's work, and the undo history is not cleared.
//   2. The dieline guides are drawn on the artboard but NEVER exported: the PNG
//      bytes are identical with the overlay on and off.

import { test, expect, type Page } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

async function openPackage(page: Page) {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('canvas-workspace')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('cw-type-package').click()
  await expect(page.getByTestId('cw-panel-front')).toBeVisible()
}

async function openPanel(page: Page) {
  const toggle = page.getByTestId('cw-panel-toggle')
  if (await toggle.isVisible() && (await toggle.getAttribute('aria-expanded')) !== 'true') {
    await toggle.click()
  }
  await page.getByTestId('cw-panel-properties').click()
  await expect(page.getByTestId('cw-properties')).toBeVisible()
}

async function layerCount(page: Page) {
  await openPanel(page)
  await page.getByTestId('cw-panel-layers').click()
  const n = await page.getByTestId('cw-layer').count()
  await page.getByTestId('cw-panel-properties').click()
  return n
}

test('front and rear panels keep their own layers', async ({ page }) => {
  await openPackage(page)

  // Front: background + headline.
  await page.getByTestId('cw-add-text').click()
  await openPanel(page)
  await page.getByTestId('cw-text-input').fill('Front headline')
  expect(await layerCount(page)).toBe(2)

  // Rear: a fresh panel with its own background.
  await page.getByTestId('cw-panel-back').click()
  await expect(page.getByTestId('cw-panel-back')).toHaveAttribute('aria-selected', 'true')
  expect(await layerCount(page)).toBe(1)

  await page.getByTestId('cw-add-text').click()
  await openPanel(page)
  await page.getByTestId('cw-text-input').fill('Rear copy')

  // Back to the front: its work is still there.
  await page.getByTestId('cw-panel-front').click()
  await openPanel(page)
  await page.getByTestId('cw-panel-layers').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(2)
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'Front headline' })).toHaveCount(1)

  // And the rear survived the round trip.
  await page.getByTestId('cw-panel-back').click()
  await expect(page.getByTestId('cw-layer')).toHaveCount(2)
  await expect(page.getByTestId('cw-layer').filter({ hasText: 'Rear copy' })).toHaveCount(1)
})

test('the dieline overlay draws guides and never reaches the export', async ({ page }) => {
  await openPackage(page)
  await openPanel(page)

  await page.getByTestId('cw-load-dieline').click()
  await expect(page.getByTestId('cw-dieline-state')).toContainText('Doypack', { timeout: 30000 })
  // The geometry sizes the artboard to the panel (150 x 210 mm at 4 px/mm).
  await expect(page.getByTestId('cw-doc-size')).toContainText('600x840')

  // The overlay is a real SVG on the artboard with guide shapes in it.
  const overlay = page.getByTestId('cw-dieline')
  await expect(overlay).toBeVisible()
  expect(await overlay.locator('rect, line').count()).toBeGreaterThan(2)

  // It must not be selectable: the artboard canvas is still the pointer target.
  const pointer = await page.evaluate(() => {
    const svg = document.querySelector('[data-testid="cw-dieline"]')
    return svg ? getComputedStyle(svg).pointerEvents : 'missing'
  })
  expect(pointer).toBe('none')

  // Export with the overlay ON, then OFF: identical bytes prove it is DOM-only.
  await page.getByTestId('cw-export-png').click()
  await expect(page.getByTestId('cw-export-status')).toContainText('PNG', { timeout: 30000 })
  const onBytes = await page.getByTestId('canvas-workspace').getAttribute('data-last-export')

  await page.getByTestId('cw-dieline-toggle').click()
  await expect(overlay).toHaveCount(0)
  await page.getByTestId('cw-export-png').click()
  await expect(page.getByTestId('cw-export-status')).toContainText('PNG', { timeout: 30000 })
  const offBytes = await page.getByTestId('canvas-workspace').getAttribute('data-last-export')

  expect(offBytes).toBe(onBytes)
  expect(String(onBytes)).toMatch(/^PNG \d+$/)
})
