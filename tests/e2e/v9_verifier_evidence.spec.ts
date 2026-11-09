// V9 verifier evidence — LOCALHOST ONLY (the narrow e2e exception in AGENTS.md).
//
// Added by the independent verifier on 2026-11-09 so the V9-localhost claim carries a screenshot a
// later reader can check, not just an assertion. It drives the same Design Studio path as
// v9_localhost.spec.ts, proves the PNG export produced real bytes, and saves a full-page screenshot
// to reports/ty/v9_verifier_screenshot.png. No external host, no credentials, no state change.

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 90000 })

test('V9 verifier: Design Studio export >1000 bytes, screenshot kept', async ({ page }) => {
  await page.goto('/ui/design-studio')
  await page.waitForSelector('[data-testid="ds-quickstart"], .cw-canvas, canvas, .ds-shell', {
    timeout: 45000,
  })

  const canvasTab = page.getByRole('button', { name: /^Canvas$/ })
  if (await canvasTab.count()) {
    await canvasTab.first().click()
    await page.waitForTimeout(400)
  }

  const addHeadline = page.getByRole('button', { name: 'Add headline' })
  await expect(addHeadline).toBeVisible({ timeout: 30000 })
  await addHeadline.click()
  await page.waitForTimeout(400)

  const exportPng = page.locator('button[title*="Export a PNG"]')
  await expect(exportPng).toBeVisible({ timeout: 15000 })
  await exportPng.click()

  await expect
    .poll(async () => await page.locator('[data-last-export]').getAttribute('data-last-export'), {
      timeout: 45000,
    })
    .toMatch(/^PNG \d+/)

  const stamp = (await page.locator('[data-last-export]').getAttribute('data-last-export')) || ''
  const bytes = Number(stamp.replace('PNG ', ''))
  expect(bytes).toBeGreaterThan(1000)

  await page.screenshot({ path: 'reports/ty/v9_verifier_screenshot.png', fullPage: true })
  console.log(`V9_VERIFIER export_bytes=${bytes}`)
})
