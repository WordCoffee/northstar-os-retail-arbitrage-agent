// Asset Dashboard — localhost only (Playwright Test is the sanctioned path for
// tests/e2e against 127.0.0.1). The page reads state/deliverables through the
// dashboard API, so this spec asserts what a user actually sees: real packages,
// a real manifest, and one lane triggered end to end against local ComfyUI.
//
// The room shell only renders in Advanced mode, but the Design Studio is kept
// out of the Simple-mode chat replacement (App.jsx SIMPLE_KEEP_ADVANCED), so the
// default free-tier session reaches it. The spec runs exactly that default —
// no mode override, no localStorage seeding.

import { test, expect } from '@playwright/test'

const SECTION = '/ui/design-studio?section=deliverables'

test('the dashboard lists packages that exist on disk', async ({ page }) => {
  await page.goto(SECTION)
  await expect(page.getByTestId('asset-dashboard')).toBeVisible({ timeout: 30000 })

  const cards = page.getByTestId('dash-package')
  await expect(cards.first()).toBeVisible({ timeout: 20000 })
  expect(await cards.count()).toBeGreaterThan(0)

  // The card's title is the folder name on disk, not a decorative label.
  const runId = (await cards.first().locator('strong').first().innerText()).trim()
  expect(runId).toMatch(/^[A-Za-z0-9._-]{6,}$/)
  expect(runId).not.toContain(' ')
})

test('a manifest opens in the panel as JSON', async ({ page }) => {
  await page.goto(SECTION)
  const card = page.getByTestId('dash-package').first()
  await expect(card).toBeVisible({ timeout: 30000 })
  await card.getByTestId('dash-manifest').click()

  const panel = page.getByTestId('dash-manifest-panel')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('run_id')
  await expect(panel).toContainText('"files"')
})

test('the proposal queue lists discovered repositories without deciding them', async ({ page }) => {
  await page.goto(SECTION)
  await expect(page.getByTestId('asset-dashboard')).toBeVisible({ timeout: 30000 })

  // The queue loads after the packages, so wait for it to settle into either
  // real rows or its explicit empty state - never a silent void.
  const rows = page.getByTestId('dash-proposal')
  const empty = page.getByText('No undecided proposals')
  await expect(rows.first().or(empty)).toBeVisible({ timeout: 20000 })

  const count = await rows.count()
  if (count > 0) {
    await expect(rows.first().getByTestId('dash-approve')).toBeEnabled()
  }
})

test('a lane trigger fires the local endpoint and reports back', async ({ page }) => {
  test.setTimeout(180000)
  await page.goto(SECTION)
  const select = page.getByTestId('dash-asset')
  await expect(select).toBeVisible({ timeout: 30000 })
  await expect(select).not.toHaveValue('', { timeout: 20000 })

  await page.getByTestId('dash-run-cutout').click()

  const lastRun = page.getByTestId('dash-last-run')
  await expect(lastRun).toContainText('Cutout', { timeout: 15000 })
  await expect(lastRun).toContainText('done', { timeout: 120000 })
})
