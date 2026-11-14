// G1 for research: a query persists and reads back.
//
// The launch gate said "no end-to-end query → persist → read". Product Finder's lookup lived in
// React state, so a reload started the work over. This spec drives the real page, saves the
// lookup, reloads, and then asks the API directly — so the proof is the store, not the DOM's
// memory of it. A miss is saved as "no cached observation" on purpose: the honest fact is
// persisted rather than dropped.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md).

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 120000 })

const ASIN = 'B0ZZ9ZZ999' // valid shape, deliberately improbable in any cache

// The test uses a per-run ASIN, so the cleanup must delete THAT id, not the constant. It
// deleted ASIN before, which leaked one research row per project on every run (measured
// 2026-11-14).
let createdAsin = ''

// The API answers under the bff/v1 envelope; unwrap it in one place so the assertions read the
// same shape the page reads.
async function payload(res: any) {
  const body = await res.json()
  return body && body.contract === 'bff/v1' ? body.data : body
}

test.afterAll(async ({ request }) => {
  if (!createdAsin) return
  await request.delete(`http://127.0.0.1:8000/api/products/research/${createdAsin}`).catch(() => {})
})

test('research: lookup → save → reload → read back', async ({ page, request }) => {
  const asin = `${ASIN.slice(0, 9)}${Math.floor(Math.random() * 9)}`
  createdAsin = asin

  await page.goto('/ui/product-finder')
  await expect(page.locator('[data-testid="pf-add-first"]')).toBeVisible({ timeout: 45000 })
  await expect(page.locator('[data-testid="pf-saved-research"]')).toBeVisible({ timeout: 30000 })

  await page.locator('[data-testid="pf-asin-input"]').fill(asin)
  await page.locator('[data-testid="pf-add"]').click()

  // Either a cached observation or an honest miss; both are allowed to be saved.
  await expect
    .poll(async () => {
      const body = await page.locator('body').innerText()
      return body.includes(asin) && (await page.locator('[data-testid="pf-lookup-missing"]').count() > 0
        || await page.locator('[data-testid="pf-lookup-note"]').count() > 0)
    }, { timeout: 30000 })
    .toBe(true)

  await page.locator('[data-testid="pf-save-research"]').click()
  await expect(page.locator('[data-testid="pf-save-state"]')).toBeVisible({ timeout: 20000 })

  // The store is the proof, not the page.
  await expect
    .poll(async () => {
      const res = await request.get(`http://127.0.0.1:8000/api/products/research/${asin}`)
      if (!res.ok()) return false
      const body = await payload(res)
      return Boolean(body && body.research && body.research.asin === asin)
    }, { timeout: 20000 })
    .toBe(true)

  const stored = await payload(await request.get(`http://127.0.0.1:8000/api/products/research/${asin}`))
  expect(stored.research.status).toMatch(/observed|no_observation/)
  expect(stored.research.saved_at).toBeTruthy()

  // Reload: the saved row is still there, so the workbench resumes instead of restarting.
  await page.reload()
  const entry = page.locator(`[data-testid="pf-saved-${asin}"]`)
  await expect(entry).toBeVisible({ timeout: 30000 })
  expect(await entry.innerText()).toContain(asin)

  // And it survives the API too, not just this tab's cache.
  const again = await request.get('http://127.0.0.1:8000/api/products/research')
  expect(again.ok()).toBe(true)
  const list = await payload(again)
  expect((list.items || []).some((row: any) => row.asin === asin)).toBe(true)
})
