// U4 — the shell has to actually take on a service's identity, not just own a
// palette module. Localhost only (Playwright Test is the sanctioned path for
// tests/e2e against 127.0.0.1).

import { test, expect } from '@playwright/test'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { window.sessionStorage.removeItem('ns-ux-tabs') } catch { /* ignore */ }
  })
})

test('the cockpit adopts the active service theme and shifts on a switch', async ({ page }) => {
  await page.goto(WORKBENCH)
  const shell = page.getByTestId('workbench-shell')
  await expect(shell).toBeVisible({ timeout: 30000 })

  // The default tab is the Design Studio (theme: studio).
  await expect(shell).toHaveAttribute('data-wb-theme', 'studio')
  const studioAccent = await shell.evaluate(el =>
    getComputedStyle(el).getPropertyValue('--wb-accent').trim())
  expect(studioAccent.toLowerCase()).toBe('#e8b04b')

  // The warp duration is a token, so the switch animation is wired even when the
  // user's motion preference suppresses it. The transient `is-shifting` class is
  // covered by the hook's unit test (a 600 ms window is not a stable assertion).
  const shiftMs = await shell.evaluate(el =>
    getComputedStyle(el).getPropertyValue('--wb-shift-ms').trim())
  expect(shiftMs).toBe('600ms')

  await page.getByTestId('wb-add').click()
  await page.getByTestId('wb-open-golden-goose').click()
  await expect(shell).toHaveAttribute('data-wb-theme', 'goose')

  const gooseAccent = await shell.evaluate(el =>
    getComputedStyle(el).getPropertyValue('--wb-accent').trim())
  expect(gooseAccent.toLowerCase()).toBe('#5fd3a2')
})

test('the glass surfaces read the theme variables', async ({ page }) => {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })

  for (const testId of ['bojo-dock', 'wb-tabbar', 'wb-outlet']) {
    const locator = page.getByTestId(testId)
    if (await locator.count() === 0) continue // the dock is a bottom sheet on a phone
    const styles = await locator.evaluate((el) => {
      const cs = getComputedStyle(el)
      return { bg: cs.backgroundColor, hasGlass: el.classList.contains('glass') }
    })
    expect(styles.hasGlass, `${testId} is not a glass surface`).toBe(true)
    expect(styles.bg).not.toBe('rgba(0, 0, 0, 0)')
  }
})
