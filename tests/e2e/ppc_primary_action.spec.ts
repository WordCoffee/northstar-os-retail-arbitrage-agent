// PPC's real primary action, on the PPC surface.
//
// The claim under test: AdPilot's primary button is not a toast and not "make a plan" — it opens
// the seller's actual workflow (upload the exported report, approve row changes, get a NEW bulk
// file back). The workflow itself lives in one component (`AmazonFiles`); this spec proves the
// PPC page mounts it, that a file input exists, and that the button's state is honest.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md). No external request.

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 90000 })

test('AdPilot primary action opens the real report-to-bulk-file flow', async ({ page }) => {
  await page.goto('/ui/adpilot')
  await expect(page.getByText('AdPilot', { exact: false }).first()).toBeVisible({ timeout: 30000 })

  const action = page.locator('[data-testid="ap-bulk-action"]')
  await expect(action).toBeVisible({ timeout: 15000 })
  await expect(action).toHaveAttribute('aria-expanded', 'false')

  // Nothing is mounted until the primary action is taken.
  expect(await page.locator('[data-testid="ap-bulk-panel"]').count()).toBe(0)

  await action.click()

  const panel = page.locator('[data-testid="ap-bulk-panel"]')
  await expect(panel).toBeVisible({ timeout: 15000 })
  await expect(action).toHaveAttribute('aria-expanded', 'true')

  // The real flow: a file input to upload the seller's own report…
  const upload = panel.locator('input[type="file"]')
  expect(await upload.count()).toBeGreaterThan(0)
  await expect(upload.first()).toBeAttached()

  // …and the words of the actual transaction, not a plan.
  const text = (await panel.innerText()).toLowerCase()
  expect(text).toContain('upload')
  expect(text).toContain('bulk')

  await action.click()
  await expect(panel).toHaveCount(0)
})
