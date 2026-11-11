// G1 for Golden Goose: generate -> persist -> read back, through the real UI.
//
// The gate that blocked launch was not "the page renders" — it was that a seller could evaluate an
// opportunity, see a decision, and lose it on reload: `POST /golden-goose/evaluate` computed the
// decision and never stored it. This spec drives the actual panel, then reloads and reads the same
// item back from the persisted queue and its own review route.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md). Sample row only: a sample decision can
// never be purchase-ready, which is the safe path to exercise persistence.

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 120000 })

test('Golden Goose: evaluate -> persists -> reads back after reload', async ({ page }) => {
  const itemId = `GG-E2E-${Date.now().toString(36).toUpperCase()}`

  await page.goto('/ui/golden-goose')
  const panel = page.locator('[data-testid="gg-evaluate"]')
  await expect(panel).toBeVisible({ timeout: 45000 })

  await page.getByPlaceholder('e.g. GG-001').fill(itemId)
  await page.locator('#gg-sample').check()
  await page.getByRole('button', { name: 'Evaluate', exact: true }).click()

  const result = page.locator('[data-testid="gg-evaluate-result"]')
  await expect(result).toBeVisible({ timeout: 30000 })
  const decisionText = (await result.innerText()).toLowerCase()
  expect(decisionText).not.toContain('sign in required')

  // Reload: an evaluation that is not stored disappears here, which is exactly the defect.
  await page.reload()
  await expect(page.locator('[data-testid="gg-evaluate"]')).toBeVisible({ timeout: 45000 })

  const queue = page.locator('[data-testid="gg-persisted-queue"]')
  await expect(queue).toBeVisible({ timeout: 30000 })
  await expect
    .poll(async () => (await queue.innerText()).includes(itemId), { timeout: 20000 })
    .toBe(true)

  // And it is readable on its own route, not only in a list.
  await page.goto(`/ui/golden-goose/${itemId}`)
  const review = page.locator('[data-testid="gg-persisted-review"]')
  await expect(review).toBeVisible({ timeout: 30000 })
  // Positive signal only: the review names the item and has stopped saying it is loading.
  await expect
    .poll(async () => {
      const text = await review.innerText()
      return text.includes(itemId) && !/loading/i.test(text.split('\n')[0])
    }, { timeout: 20000 })
    .toBe(true)
  expect(await page.locator('[data-testid="gg-review-not-found"]').count()).toBe(0)
})
