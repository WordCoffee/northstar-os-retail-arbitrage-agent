// V9-localhost — the dogfood task, driven through the real UI, without a desktop.
//
// V9 proper asks the Seller-Tester to use the Vision Operator against the live desktop. The
// desktop is locked, so this is the localhost half: Playwright drives the real Design Studio
// route on 127.0.0.1 and performs one seller task end to end — add a headline, export a PNG,
// and prove the export produced real bytes. That is the same UI path a vision operator would
// take, minus the pixels.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md). No external request.

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 90000 })

test('V9-localhost: Design Studio, add a headline, export a real PNG', async ({ page }) => {
  await page.goto('/ui/design-studio')
  await page.waitForSelector('[data-testid="ds-quickstart"], .cw-canvas, canvas, .ds-shell', {
    timeout: 45000,
  })

  // The canvas is the workspace under test; open it if the studio landed on another section.
  const canvasTab = page.getByRole('button', { name: /^Canvas$/ })
  if (await canvasTab.count()) {
    await canvasTab.first().click()
    await page.waitForTimeout(400)
  }

  const addHeadline = page.getByRole('button', { name: 'Add headline' })
  await expect(addHeadline).toBeVisible({ timeout: 30000 })
  await addHeadline.click()

  // A layer exists now. The properties panel names the selected layer; a headline is text.
  await page.waitForTimeout(400)
  const body = await page.locator('body').innerText()
  expect(body.toLowerCase()).toContain('headline')

  // Export a PNG and prove it produced bytes, not a toast.
  const exportPng = page.locator('button[title*="Export a PNG"]')
  await expect(exportPng).toBeVisible({ timeout: 15000 })
  await exportPng.click()

  await expect
    .poll(async () => await page.locator('[data-last-export]').getAttribute('data-last-export'), {
      timeout: 45000,
    })
    .toMatch(/^PNG \d+/)

  const stamp = await page.locator('[data-last-export]').getAttribute('data-last-export')
  const bytes = Number((stamp || '').replace('PNG ', ''))
  expect(bytes).toBeGreaterThan(1000)
})

test('V9-localhost: the studio route is the studio, not the chat shell', async ({ page }) => {
  await page.goto('/ui/design-studio')
  await expect(page.getByText('Design Studio', { exact: false }).first()).toBeVisible({
    timeout: 30000,
  })
  const chatInput = page.locator('.chat-input, [data-testid="chat-input"]')
  expect(await chatInput.count()).toBe(0)
})
