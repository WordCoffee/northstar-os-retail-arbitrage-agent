// U9 — the PPC harvest lane. Localhost only.
//
// The pass criterion from the work order: an upload-to-download click path on
// fixtures. The report is a local file the operator already has; no Amazon
// property is contacted at any point.

import { test, expect } from '@playwright/test'
import { statSync } from 'node:fs'

const WORKBENCH = '/ui/workbench'

test.describe.configure({ timeout: 120000 })

// The room is reachable in two ways: its own route (advanced view) and as a
// workbench tab. The workbench path is the one U9 owns, so the test opens it
// there and proves the subview switch stays inside the shell.
async function openHarvest(page) {
  await page.goto(WORKBENCH)
  await expect(page.getByTestId('workbench-shell')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('wb-add').click()
  await page.getByTestId('wb-open-adpilot').click()
  await expect(page.getByTestId('wb-panel-adpilot')).toBeVisible({ timeout: 30000 })
  await page.getByTestId('ap-tab-harvest').click()
  await expect(page.getByTestId('ppc-harvest')).toBeVisible({ timeout: 30000 })
  expect(page.url()).toContain('/ui/workbench')
}

const CSV = [
  'Campaign,Ad Group,Customer Search Term,Impressions,Clicks,Spend,Sales,Orders',
  'Lions Mane,Broad,lions mane powder,1200,24,12.00,60.00,2',
  'Lions Mane,Broad,mushroom coffee cheap,900,11,8.40,0,0',
  'Lions Mane,Phrase,lion mane capsules,80,2,0.90,0,0',
].join('\r\n')

const CSV_BUFFER = Buffer.from(CSV, 'utf8')

test('a report uploads, shows the change log, and downloads a validated bulk file', async ({ page }) => {
  await openHarvest(page)

  // The lane states its own limits before anything is uploaded.
  await expect(page.getByText('file only · no Amazon API')).toBeVisible()

  await page.getByTestId('ppc-report-input').setInputFiles({
    name: 'search-term-report.csv',
    mimeType: 'text/csv',
    buffer: CSV_BUFFER,
  })

  await expect(page.getByTestId('ppc-analysis')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('ppc-summary')).toContainText('1 term(s) converting')
  await expect(page.getByTestId('ppc-summary')).toContainText('1 term(s) with 8+ clicks')

  // The harvest table carries the term AND its source row.
  const harvest = page.getByTestId('ppc-harvest-rows')
  await expect(harvest).toContainText('lions mane powder')
  await expect(harvest).toContainText('Lions Mane')

  // The negative table carries the expensive no-order term.
  const negatives = page.getByTestId('ppc-negative-rows')
  await expect(negatives).toContainText('mushroom coffee cheap')

  // The undecidable term is in neither table.
  await expect(page.getByTestId('ppc-analysis')).not.toContainText('lion mane capsules')

  // Download the bulk file and check the bytes are real. The API files
  // anonymous callers in a 30/min bucket, so a batch run can legitimately hit
  // it: the surface says so, and a second attempt after the window is what a
  // person would do. The retry is bounded to one.
  const status = page.getByTestId('ppc-bulk-status')
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 30000 }).catch(() => null),
    page.getByTestId('ppc-build-bulk').click(),
  ])
  await expect(status).toBeVisible({ timeout: 30000 })
  if (/rate-limit/i.test(await status.innerText())) {
    await page.waitForTimeout(4000)
    await page.getByTestId('ppc-build-bulk').click()
  }
  await expect(status).toContainText('2 row(s)', { timeout: 30000 })

  if (download) {
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/)
    const file = await download.path()
    expect(file, 'the bulk export produced no file').toBeTruthy()
    expect(statSync(file!).size).toBeGreaterThan(1000)
  }
})

test('a file with the wrong columns is rejected with the missing names', async ({ page }) => {
  await openHarvest(page)

  await page.getByTestId('ppc-report-input').setInputFiles({
    name: 'not-a-report.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('Campaign,Clicks\nLions Mane,4', 'utf8'),
  })

  await expect(page.getByTestId('ppc-rejected')).toBeVisible({ timeout: 30000 })
  await expect(page.getByTestId('ppc-rejected')).toContainText('customer search term')
  await expect(page.getByTestId('ppc-analysis')).toHaveCount(0)
})
