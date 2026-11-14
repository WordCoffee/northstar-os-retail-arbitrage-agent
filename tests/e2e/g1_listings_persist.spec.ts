// G1 for Listings: compose a listing through the UI from supplied facts, persist it,
// and read it back on desktop Chromium and iPhone 12 WebKit.
//
// The compose step is the product's own hosted path — ListingForge's "Hosted listing
// proposal" panel -> POST /api/v1/reasoning/listing-proposal -> reasoning_tasks.
// listing_proposal -> the OpenCode Go adapter. It runs on the repository's verified
// free default model, which the owner changed to `beam-free` on 2026-11-13 (cost 0,
// live catalog $0/$0, one real completion proven), so no paid credit is consumed.
// `step-5-preview-free` was withdrawn upstream and is refused by name.
//
// The persistence step is the room's own Save Revision -> POST/PATCH
// /api/design-studio/listing-records. The read-back deliberately happens in NEW
// contexts with no browser storage: the desktop context here, and a real WebKit
// browser with the iPhone 12 descriptor for the phone. If the record only came
// back because of localStorage, this spec would fail.
//
// LOCALHOST ONLY (the narrow e2e exception in AGENTS.md). Runs once, in the
// desktop project, and opens its own WebKit engine for the phone read-back, so a
// full-suite pass does not compose the same listing twice.

import { test, expect, webkit, devices, type Page } from '@playwright/test'

test.describe.configure({ timeout: 300000 })

// Supplied facts. The composer is instructed to use ONLY these; it is not asked
// to invent certifications, dimensions, prices or availability.
const FACTS = {
  brand: 'Mogra Organics',
  title: "Mogra Organics Lion's Mane Mushroom Powder, 200 g Pouch, Single Ingredient",
  bullets: [
    'Single ingredient: ground lion\u2019s mane mushroom, nothing else added',
    'Finely ground powder for coffee, tea, soups and smoothies',
    '200 g resealable pouch; reseal after opening and store in a cool, dry place',
  ],
  description:
    "Mogra Organics Lion's Mane Mushroom Powder is a single-ingredient pantry staple. " +
    'The 200 g resealable pouch holds finely ground lion\u2019s mane mushroom for everyday ' +
    'use in coffee, tea, soups and smoothies. No other ingredients are added. Store in a ' +
    'cool, dry place and reseal the pouch after each use.',
  keywords: 'lions mane powder, mushroom coffee, mogra organics',
}

// A fresh container row per run, so a re-run never reads a previous run's copy.
const ASIN = `B0G1L${Date.now().toString(36).toUpperCase().slice(-5)}`

async function readBackInFreshContext(page: Page, expected: { title: string; bullets: string; description: string; keywords: string }) {
  await page.goto('/ui/listingforge?view=listings')
  const row = page.getByRole('row').filter({ hasText: ASIN })
  await expect(row).toBeVisible({ timeout: 45000 })

  await row.getByRole('button', { name: 'Edit' }).click()

  // Keywords are only rendered in Advanced mode; the server-backed record carries
  // them as backend_terms, so switch the mode rather than trusting local state.
  const advanced = page.getByRole('tab', { name: 'Advanced' })
  if (await advanced.count()) {
    await advanced.first().click()
  }

  const title = page.locator('label.sp-field', { hasText: 'Title' }).locator('input')
  const bullets = page.locator('label.sp-field', { hasText: 'Bullets' }).locator('textarea')
  const description = page.locator('label.sp-field', { hasText: 'Description' }).locator('textarea')
  const keywords = page.locator('label.sp-field', { hasText: 'Keywords' }).locator('input')

  await expect(title).toHaveValue(expected.title, { timeout: 30000 })
  await expect(bullets).toHaveValue(expected.bullets, { timeout: 30000 })
  await expect(description).toHaveValue(expected.description, { timeout: 30000 })
  await expect(keywords).toHaveValue(expected.keywords, { timeout: 30000 })
}

// Gate test: cheap, always runs, and never prints a credential value.
test('gate: the composer key is present and the provider is armed (by name only)', async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'runs once per suite')

  const gate = await request.get('/api/v1/reasoning/models')
  expect(gate.ok()).toBe(true)
  const gateBody = await gate.json()
  expect(gateBody.credential_env).toBe('OPENCODE_GO_API_KEY')
  expect(gateBody.enable_env).toBe('OPENCODE_GO_ENABLED')
  expect(gateBody.configured, 'OPENCODE_GO_API_KEY present').toBe(true)
  expect(gateBody.enabled, 'OPENCODE_GO_ENABLED=1').toBe(true)
  expect(gateBody.armed, 'hosted reasoning armed').toBe(true)
  expect(gateBody.runtime_default_model, 'verified runtime default').toBe('beam-free')
})

test('compose through the UI, persist to the tenant store, read back on desktop and iPhone 12 WebKit', async ({ page, browser, request }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'runs once; the phone read-back uses its own iPhone 12 WebKit engine')

  // ── 1. The gate, by name. No credential value is read or printed. ──────────
  const gate = await request.get('/api/v1/reasoning/models')
  expect(gate.ok()).toBe(true)
  const gateBody = await gate.json()
  expect(gateBody.configured, 'OPENCODE_GO_API_KEY present').toBe(true)
  expect(gateBody.enabled, 'OPENCODE_GO_ENABLED=1').toBe(true)
  expect(gateBody.armed, 'hosted reasoning armed').toBe(true)
  expect(gateBody.runtime_default_model, 'verified runtime default').toBe('beam-free')

  // ── 2. Create the container row through the room's own create form ────────
  // The room renders its form only for an empty account, so wait for the server
  // list to land before deciding, and use the same endpoint the form posts to
  // when the account already holds listings.
  const recordsLoaded = page.waitForResponse(
    r => r.url().includes('/api/design-studio/listing-records') && r.request().method() === 'GET',
    { timeout: 45000 },
  )
  await page.goto('/ui/listingforge?view=listings')
  await expect(page.getByRole('heading', { name: 'ListingForge' })).toBeVisible({ timeout: 45000 })
  await recordsLoaded
  // The room renders the empty-state form while the first fetch is in flight, then
  // swaps it for the table. Give the post-fetch render a moment, and take the table
  // as soon as it appears, before choosing a branch.
  await Promise.race([
    page.locator('.table-wrap table tbody tr').first().waitFor({ state: 'visible', timeout: 3000 }).catch(() => {}),
    page.waitForTimeout(800),
  ])

  const emptyForm = page.getByTestId('lf-listings-empty')
  if (await emptyForm.count()) {
    await page.getByLabel('ASIN').fill(ASIN)
    await page.getByLabel('Working title').fill("Mogra Organics Lion's Mane Powder draft")
    await emptyForm.getByRole('button', { name: 'Create listing', exact: true }).click()
  } else {
    const seed = await request.post('/api/design-studio/listing-records', {
      data: {
        asin: ASIN,
        title: "Mogra Organics Lion's Mane Powder draft",
        bullets: [],
        backend_terms: '',
        description: '',
        source: 'listingforge-local',
        legacy_key: `lf:${ASIN}`,
      },
    })
    expect(seed.ok()).toBe(true)
    const reloaded = page.waitForResponse(
      r => r.url().includes('/api/design-studio/listing-records') && r.request().method() === 'GET',
      { timeout: 45000 },
    )
    await page.reload()
    await reloaded
  }

  const createdRow = page.getByRole('row').filter({ hasText: ASIN })
  await expect(createdRow).toBeVisible({ timeout: 30000 })
  await createdRow.getByRole('button', { name: 'Edit' }).click()

  // ── 3. Supply the facts in the editor ─────────────────────────────────────
  await page.getByRole('tab', { name: 'Advanced' }).first().click()

  const titleField = page.locator('label.sp-field', { hasText: 'Title' }).locator('input')
  const bulletsField = page.locator('label.sp-field', { hasText: 'Bullets' }).locator('textarea')
  const descriptionField = page.locator('label.sp-field', { hasText: 'Description' }).locator('textarea')
  const keywordsField = page.locator('label.sp-field', { hasText: 'Keywords' }).locator('input')
  const brandField = page.locator('label.sp-field', { hasText: 'Brand' }).locator('input')

  await titleField.fill(FACTS.title)
  await bulletsField.fill(FACTS.bullets.join('\n'))
  await descriptionField.fill(FACTS.description)
  await keywordsField.fill(FACTS.keywords)
  await brandField.fill(FACTS.brand)

  // ── 4. Compose through the product's hosted listing proposal ──────────────
  const panel = page.getByTestId('lf-proposal')
  await expect(panel).toBeVisible()
  await expect(panel.getByText('armed', { exact: true }), 'the panel reports the provider armed').toBeVisible({ timeout: 30000 })
  await expect(panel.locator('#reasoning-model')).toHaveValue('beam-free')

  await panel.getByRole('button', { name: 'Generate proposal' }).click()

  // Wait for a terminal state, and keep the panel's exact words if it refused.
  let outcome: 'ok' | 'failed' = 'failed'
  let panelText = ''
  const deadline = Date.now() + 180000
  while (Date.now() < deadline) {
    panelText = await panel.innerText()
    if (panelText.includes('proposal ok')) { outcome = 'ok'; break }
    if (panelText.includes('proposal failed')) break
    await page.waitForTimeout(1000)
  }
  expect(
    outcome,
    `hosted compose did not return a proposal. Panel said:\n${panelText}`,
  ).toBe('ok')

  // The proposal's own copy is what we persist. Applying it closes the proposal
  // block, so waiting for that is the signal that the editor holds the proposal.
  const applyButton = panel.getByRole('button', { name: 'Apply to editor' })
  await expect(applyButton).toBeEnabled()
  await applyButton.click()
  await expect(applyButton).toBeHidden({ timeout: 15000 })

  const applied = {
    title: await titleField.inputValue(),
    bullets: await bulletsField.inputValue(),
    description: await descriptionField.inputValue(),
    keywords: await keywordsField.inputValue(),
  }
  expect(applied.title.length).toBeGreaterThan(0)
  expect(applied.bullets.split('\n').filter(Boolean).length).toBeGreaterThan(0)

  // ── 5. Persist through the room's own Save Revision ───────────────────────
  await page.getByRole('button', { name: 'Save Revision' }).first().click()

  const expectedBullets = applied.bullets.split('\n').map(s => s.trim()).filter(Boolean)
  let record: any = null
  const saveDeadline = Date.now() + 45000
  while (Date.now() < saveDeadline) {
    const list = await request.get('/api/design-studio/listing-records')
    expect(list.ok()).toBe(true)
    const body = await list.json()
    record = (body.records || []).find((r: any) => r.asin === ASIN) || null
    if (record && record.title === applied.title) break
    await page.waitForTimeout(500)
  }
  expect(record, `a tenant-store listing record exists for ${ASIN}`).toBeTruthy()
  expect(record.title).toBe(applied.title)
  expect(record.bullets).toEqual(expectedBullets)
  expect(record.description).toBe(applied.description)
  expect(record.backend_terms).toBe(applied.keywords)

  // ── 6. Read back: desktop Chromium, clean context ─────────────────────────
  const desktop = await browser.newContext({ ...devices['Desktop Chrome'] })
  const desktopPage = await desktop.newPage()
  await readBackInFreshContext(desktopPage, applied)
  await desktop.close()

  // ── 7. Read back: iPhone 12 WebKit, clean context ─────────────────────────
  const webkitBrowser = await webkit.launch({ headless: true })
  try {
    const phone = await webkitBrowser.newContext({ ...devices['iPhone 12'] })
    const phonePage = await phone.newPage()
    await readBackInFreshContext(phonePage, applied)
    await phone.close()
  } finally {
    await webkitBrowser.close()
  }

  test.info().annotations.push({
    type: 'g1-listings',
    description: `ASIN ${ASIN} · composed on beam-free · persisted ${record.id} · read back desktop Chromium + iPhone 12 WebKit`,
  })
})
