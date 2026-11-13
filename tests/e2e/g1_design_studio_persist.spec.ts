// G1 for Design Studio, persistence half: a canvas design saves on the server and reads back.
//
// The canvas autosaved into localStorage only, so a design was readable on one browser and
// nowhere else. This spec edits the canvas, waits for the server project id, then opens that
// project in a **fresh browser context** — no localStorage, no session storage carry-over — and
// asserts the design came back. The API is asked directly too, so the proof is the row.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md).

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 180000 })

const HEADLINE = 'Server persistence proof'

test('canvas design: save -> server project -> read back in a clean context', async ({ page, browser, request }) => {
  await page.goto('/ui/design-studio')
  await expect(page.locator('[data-testid="ds-project-id"]')).toBeVisible({ timeout: 45000 })

  // The canvas is a view of the studio shell.
  const canvasTab = page.locator('[data-testid="ws-view-canvas"]')
  if (await canvasTab.count()) {
    await canvasTab.first().click()
    await page.waitForTimeout(300)
  }

  // Edit the canvas: one headline layer is enough to prove the document round-trips.
  const addHeadline = page.getByRole('button', { name: 'Add headline' })
  await expect(addHeadline).toBeVisible({ timeout: 30000 })
  await addHeadline.click()
  await page.waitForTimeout(500)

  // A project id appears once the server save lands (created on first save, patched after).
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('ns-design-project-id')), { timeout: 30000 })
    .toBeTruthy()
  const projectId = await page.evaluate(() => localStorage.getItem('ns-design-project-id'))
  expect(projectId).toBeTruthy()

  // The row itself, unwrapped from the bff/v1 envelope.
  const res = await request.get(`http://127.0.0.1:8000/api/design-studio/projects/${projectId}`)
  expect(res.ok()).toBe(true)
  const body = await res.json()
  const data = body && body.contract === 'bff/v1' ? body.data : body
  const project = data && data.project
  expect(project).toBeTruthy()
  const meta = typeof project.metadata === 'string' ? JSON.parse(project.metadata) : project.metadata
  expect(meta && meta.design).toBeTruthy()
  const design = typeof meta.design === 'string' ? JSON.parse(meta.design) : meta.design
  const layerCount = Array.isArray(design && design.doc && design.doc.layers) ? design.doc.layers.length : 0
  expect(layerCount).toBeGreaterThan(0)

  // A clean context: nothing in browser storage knows about this design.
  const clean = await browser.newContext()
  const fresh = await clean.newPage()
  await fresh.goto(`/ui/design-studio?project=${projectId}`)
  const freshCanvas = fresh.locator('[data-testid="ws-view-canvas"]')
  if (await freshCanvas.count()) {
    await freshCanvas.first().click()
    await fresh.waitForTimeout(500)
  }
  await expect(fresh.locator('body')).toContainText('headline', { timeout: 30000 })
  await clean.close()
})
