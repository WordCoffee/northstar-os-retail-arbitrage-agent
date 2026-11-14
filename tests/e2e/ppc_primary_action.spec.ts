// PPC's real primary action, end to end, in the browser.
//
// The claim under test: AdPilot's primary button opens the seller's actual workflow — upload the
// report the seller downloaded from Amazon, approve row changes, write a NEW bulk file, and
// download it. This spec drives that whole path through the UI (not the API), using the app's own
// sample bulksheet so nothing touches Amazon: no sign-in, no API, no credentials.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md). No external request.

import { test, expect } from '@playwright/test'
import { statSync } from 'node:fs'

test.describe.configure({ timeout: 180000 })

const SAMPLE =
  'http://127.0.0.1:8101/ui/samples/amazon-files/sp_bulksheet.xlsx'

test('AdPilot primary action drives upload → propose → approve → write → download', async ({ page, request }) => {
  const sample = await request.get(SAMPLE)
  expect(sample.ok(), 'the app sample bulksheet must be served').toBe(true)
  const buffer = await sample.body()
  expect(buffer.length).toBeGreaterThan(1000)

  await page.goto('/ui/adpilot')
  await expect(page.getByText('AdPilot', { exact: false }).first()).toBeVisible({ timeout: 30000 })

  const action = page.locator('[data-testid="ap-bulk-action"]')
  await expect(action).toBeVisible({ timeout: 15000 })
  await expect(action).toHaveAttribute('aria-expanded', 'false')
  expect(await page.locator('[data-testid="ap-bulk-panel"]').count()).toBe(0)

  await action.click()
  const panel = page.locator('[data-testid="ap-bulk-panel"]')
  await expect(panel).toBeVisible({ timeout: 15000 })
  await expect(action).toHaveAttribute('aria-expanded', 'true')

  // ── 1. Upload the file the seller downloaded from Amazon ────────────────────
  await panel.locator('[data-testid="af-file"]').setInputFiles({
    name: 'sp_bulksheet.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer,
  })

  const rows = page.locator('[data-testid="af-rows"]')
  await expect(rows).toBeVisible({ timeout: 60000 })
  await expect(rows.locator('tbody tr').first()).toBeVisible()

  // The app's sample carries a Keyword row (K300); a bid change is a real operator edit.
  const keywordRow = rows.locator('tbody tr').filter({ hasText: 'K300' }).first()
  await expect(keywordRow).toBeVisible()
  await keywordRow.getByLabel('bid').fill('1.10')

  // ── 2. Propose the change ──────────────────────────────────────────────────
  await page.locator('[data-testid="af-propose"]').click()

  const proposals = page.locator('[data-testid="af-proposals"]')
  await expect(proposals).toBeVisible({ timeout: 45000 })
  await expect(proposals).toContainText('K300')
  await expect(proposals).toContainText('1.10')

  // ── 3. Approve it ──────────────────────────────────────────────────────────
  const approve = proposals.locator('[data-testid^="af-approve-"]').first()
  await expect(approve).toBeVisible()
  await approve.click()
  // The list reloads from the store; the write button only enables on an approved proposal.
  await expect(page.locator('[data-testid="af-write"]')).toBeEnabled({ timeout: 45000 })

  // ── 4. Write the new bulk file ─────────────────────────────────────────────
  await page.locator('[data-testid="af-write"]').click()

  const written = page.locator('[data-testid="af-write-result"]')
  await expect(written).toBeVisible({ timeout: 60000 })
  await expect(written).toContainText('Round-trip: PASS')
  await expect(written).toContainText('The original upload was not modified')

  // ── 5. Download it ─────────────────────────────────────────────────────────
  const downloadPromise = page.waitForEvent('download', { timeout: 60000 })
  await page.locator('[data-testid="af-download"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.(xlsx|csv)$/i)
  const path = await download.path()
  expect(path, 'the change file must land on disk').toBeTruthy()
  expect(statSync(path as string).size).toBeGreaterThan(1000)

  // Closing the panel is still honest about state.
  await action.click()
  await expect(panel).toHaveCount(0)
})
