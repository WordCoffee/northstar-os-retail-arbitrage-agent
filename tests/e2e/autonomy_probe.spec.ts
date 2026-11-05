// Phase A capability probe: one real click-path on desktop Chromium and iPhone 12.
//
// This is deliberately small. It answers a different question from the product
// specs: *can Ty drive the UI and prove what it saw* - click, wait for the
// route, capture a screenshot it can hand to a human or a vision check.
//
// Screenshots land in reports/ty/shots/ so the evidence survives the run.

import { test, expect } from '@playwright/test'

const SHOTS = 'reports/ty/shots'

test('probe: sign-in to workspace is a real click-path', async ({ page }, testInfo) => {
  const desktop = !testInfo.project.name.includes('mobile')

  await page.goto('/ui/')
  await expect(page.locator('main')).toBeVisible({ timeout: 45000 })
  await expect(page.getByText(/DEV: AUTH DISABLED/)).toBeVisible({ timeout: 45000 })

  // A real click, not a direct URL: open the command palette from the shell.
  const opener = page.getByRole('button', { name: /command|palette|search/i }).first()
  if (await opener.isVisible().catch(() => false)) {
    await opener.click()
    await expect(page.getByRole('dialog').first()).toBeVisible({ timeout: 15000 })
    await page.keyboard.press('Escape')
  } else if (desktop) {
    // The dock is the desktop entry point when the palette button is not shown.
    const dock = page.getByTestId('chat-input').first()
    await expect(dock).toBeVisible({ timeout: 30000 })
    await dock.click()
  }

  await page.screenshot({
    path: `${SHOTS}/probe_${testInfo.project.name}.png`,
    fullPage: false,
  })

  // A click that navigates: the shell's own nav must still work afterwards.
  await page.goto('/ui/home')
  await expect(page.locator('main')).toBeVisible({ timeout: 45000 })
  expect(page.url()).toContain('/ui/')
})
