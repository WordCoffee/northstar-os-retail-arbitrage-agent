// U12 — every interactive service is reachable and renders something.
//
// Pass criterion: the registry test is green (unit, U2), every service opens by
// click on both targets, and nothing renders blank. A service with no page of
// its own must say exactly that rather than pretend.
//
// The walk reads the picker's own list, so it covers whatever the registry holds
// without hard-coding ids.

import { test, expect, type Page } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 900000 })

// Phones collapse the tab strip behind the switcher; desktop always shows it.
async function revealTabs(page: Page) {
  const sw = page.getByTestId('wb-switcher')
  if (await sw.isVisible()) {
    if ((await sw.getAttribute('aria-expanded')) !== 'true') await sw.click()
    await expect(page.getByTestId('wb-tabs')).toBeVisible()
  }
}

async function expectNotBlank(page: Page, serviceId: string) {
  const panel = page.getByTestId(`wb-panel-${serviceId}`)
  await expect(panel).toBeVisible({ timeout: 20000 })

  const notice = panel.getByTestId('wb-not-wired')
  if (await notice.count()) {
    await expect(notice).toHaveAttribute('data-service-id', serviceId)
    const text = (await notice.innerText()).trim()
    expect(text.length, `${serviceId} notice is too thin to be honest`).toBeGreaterThan(40)
  } else {
    const text = (await panel.innerText()).trim()
    expect(text.length, `${serviceId} rendered blank`).toBeGreaterThan(40)
  }
}

test('every interactive service opens and renders something', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })

  await page.getByTestId('wb-add').click()
  const ids = await page.locator('[data-testid^="wb-open-"]').evaluateAll((els) =>
    els.map((el) => String(el.getAttribute('data-testid')).replace('wb-open-', '')))
  expect(ids.length, 'the picker offered no services').toBeGreaterThan(10)

  for (const id of ids) {
    await expect(page.getByTestId('wb-picker')).toBeVisible({ timeout: 20000 })
    await page.getByTestId(`wb-open-${id}`).click()
    await expectNotBlank(page, id)

    await revealTabs(page)
    await page.getByTestId(`wb-close-${id}`).click()

    // Closing the active tab falls back to the default tab; the picker is only
    // open while it is open, so reopen it for the next service.
    if (!(await page.getByTestId('wb-picker').count())) {
      await page.getByTestId('wb-add').click()
    }
  }
})
