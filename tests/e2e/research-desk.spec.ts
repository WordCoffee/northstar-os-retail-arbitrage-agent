// U10 — the Research scene and workspace. Localhost only.
//
// Pass criterion from the work order: a click path plus a contrast check. The
// contrast check is the existing scene test (it iterates SCENE_MAX_COLOR, so the
// research palette is covered by construction); this spec proves the surface: the
// AutothinK tab loads the black-hole scene, and the research desk queries the
// local corpus and states honestly when it has nothing.

import { test, expect, type Page } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

async function openDesk(page: Page) {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('wb-add').click()
  await page.getByTestId('wb-open-autothink').click()
  await expect(page.getByTestId('wb-panel-autothink')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('at-tab-desk').click()
  await expect(page.getByTestId('research-desk')).toBeVisible({ timeout: 30000 })
}

test('the research service loads its black-hole scene and the desk', async ({ page }) => {
  await openDesk(page)

  // The scene swapped on the single canvas, and there is still exactly one.
  const host = page.getByTestId('scene-host')
  await expect(host).toHaveAttribute('data-scene', 'research', { timeout: 30000 })
  await expect(page.locator('[data-testid="scene-host"] canvas')).toHaveCount(1)

  // The desk states its own limits before any query.
  await expect(page.getByText('local corpus · no web crawl')).toBeVisible()
  await expect(page.getByTestId('rd-depth-note')).toContainText('records')
  await expect(page.getByTestId('rd-run')).toBeDisabled()
})

test('a query returns sources, or says the index has nothing', async ({ page }) => {
  await openDesk(page)

  await page.getByTestId('rd-query').fill('mushroom')
  await expect(page.getByTestId('rd-run')).toBeEnabled()

  // Depth is a choice with a stated cost, not a quality claim.
  await page.getByTestId('rd-depth-quick').click()
  await expect(page.getByTestId('rd-depth-note')).toContainText('first 10')

  await page.getByTestId('rd-run').click()
  await expect(page.getByTestId('rd-results')).toBeVisible({ timeout: 30000 })

  // Either real records with the API's own caveats, or the honest empty state.
  const count = await page.getByTestId('rd-count').innerText()
  if (/\b0 record/.test(count)) {
    await expect(page.getByTestId('rd-results')).toContainText('No record in the local index matches')
    await expect(page.getByTestId('rd-results')).toContainText('not evidence that nothing exists')
  } else {
    await expect(page.getByTestId('rd-caveats')).toBeVisible()
    await expect(page.getByTestId('rd-caveats')).toContainText('Deterministic keyword search')
    await expect(page.getByTestId('rd-count')).toContainText('quick depth')
  }
})
