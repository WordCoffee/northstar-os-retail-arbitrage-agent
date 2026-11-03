// U14(b) — a visual baseline for every interactive service, on both targets.
//
// The unit suites prove geometry and contrast by number; this spec records what
// a human actually sees when each service is open in the workbench. One PNG per
// service per project under reports/ty/shots/services/<project>/.
//
// Two things are deliberately masked so the image is a baseline of the SERVICE
// and not of the build:
//   • the dev banner (it prints the commit hash and build time)
//   • toasts (they expire on a 5 s TTL; a slow frame would catch one)
// Everything else - scene, glass, workspace - is recorded as rendered.
//
// LOCALHOST ONLY (127.0.0.1:8101), per the AGENTS.md e2e exception.

import { test, expect, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const WORKBENCH = '/ui/workbench'
const OUT = path.resolve('reports', 'ty', 'shots', 'services')

test.describe.configure({ timeout: 900000 })

async function revealTabs(page: Page) {
  const sw = page.getByTestId('wb-switcher')
  if (await sw.isVisible()) {
    if ((await sw.getAttribute('aria-expanded')) !== 'true') await sw.click()
    await expect(page.getByTestId('wb-tabs')).toBeVisible()
  }
}

test('capture every service surface for the visual baseline', async ({ page }, testInfo) => {
  const dir = path.join(OUT, testInfo.project.name)
  fs.mkdirSync(dir, { recursive: true })

  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await page.addStyleTag({
    content: '[data-testid="dev-banner"]{display:none!important}'
      + '[data-testid="toast"],.toast,.ns-toast{display:none!important}',
  })

  const captured: string[] = []

  const shoot = async (id: string) => {
    // Phones collapse the tab strip behind the switcher, so the tab is present
    // but not clickable until the strip is revealed. Without this the click
    // waits for actionability until the whole test times out (it did).
    await revealTabs(page)
    await page.getByTestId(`wb-tab-${id}`).click()

    // The panel must exist and hold real copy - a screenshot of a blank panel
    // is not a baseline, it is a bug with a filename.
    const panel = page.getByTestId(`wb-panel-${id}`)
    await expect(panel).toBeVisible({ timeout: 20000 })
    expect((await panel.innerText()).trim().length, `${id} rendered blank`).toBeGreaterThan(40)

    // Let the scene settle one beat after the tab swap, then shoot the shell
    // (not just the panel) so the theme and scene are in the frame too.
    await page.waitForTimeout(700)
    await page.screenshot({ path: path.join(dir, `${id}.png`), fullPage: false })
    captured.push(id)
  }

  // The workbench opens one tab by default, so that surface is never in the
  // picker's list. Capturing only the picker would leave it out of the baseline
  // (it did: 23 of 24 on the first run).
  const initial = await page.locator('[data-testid^="wb-tab-"]').evaluateAll((els) =>
    els.map((el) => String(el.getAttribute('data-testid')).replace('wb-tab-', '')))
  expect(initial.length, 'the workbench opened no tab').toBeGreaterThan(0)
  for (const id of initial) await shoot(id)

  await page.getByTestId('wb-add').click()
  const ids = (await page.locator('[data-testid^="wb-open-"]').evaluateAll((els) =>
    els.map((el) => String(el.getAttribute('data-testid')).replace('wb-open-', ''))))
    .filter((id) => !captured.includes(id))
  expect(ids.length, 'the picker offered no additional services').toBeGreaterThan(10)

  for (const id of ids) {
    await expect(page.getByTestId('wb-picker')).toBeVisible({ timeout: 20000 })
    await page.getByTestId(`wb-open-${id}`).click()
    await shoot(id)

    await revealTabs(page)
    await page.getByTestId(`wb-close-${id}`).click()
    if (!(await page.getByTestId('wb-picker').count())) {
      await page.getByTestId('wb-add').click()
    }
  }

  // The count is asserted from the same ids the loop walked, so a service that
  // silently stopped opening cannot leave an old PNG looking current.
  expect(captured.length).toBe(initial.length + ids.length)
  expect(new Set(captured).size).toBe(captured.length)
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.png'))
  expect(files.length).toBeGreaterThanOrEqual(captured.length)
})
