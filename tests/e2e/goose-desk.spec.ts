// U11 — the Golden Goose scene and workspace. Localhost only, seeded data, no
// live pulls: this spec never triggers an outbound supplier request.

import { test, expect, type Page } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

async function openGoose(page: Page) {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('wb-add').click()
  await page.getByTestId('wb-open-golden-goose').click()
  await expect(page.getByTestId('wb-panel-golden-goose')).toBeVisible({ timeout: 30000 })
}

test('the goose service loads the comet scene and a real desk', async ({ page }) => {
  await openGoose(page)

  // The single scene canvas swapped to the comet.
  const host = page.getByTestId('scene-host')
  await expect(host).toHaveAttribute('data-scene', 'goose', { timeout: 30000 })
  await expect(page.locator('[data-testid="scene-host"] canvas')).toHaveCount(1)

  // The room renders real surfaces, not a blank panel.
  const panel = page.getByTestId('wb-panel-golden-goose')
  await expect(panel.getByTestId('gg-evaluate')).toBeVisible({ timeout: 30000 })
  await expect(panel.getByTestId('gg-persisted-queue')).toBeVisible()

  // And the queue states its basis honestly (empty or not, never fabricated).
  const queue = panel.getByTestId('gg-persisted-queue')
  const text = await queue.innerText()
  expect(text.length).toBeGreaterThan(20)
  expect(text).toMatch(/persisted opportunit|No persisted opportunities|UNKNOWN/i)
})
