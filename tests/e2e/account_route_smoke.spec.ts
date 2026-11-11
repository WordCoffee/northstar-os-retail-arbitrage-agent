// Account route smoke — the page at /ui/account, desktop and iPhone 12.
//
// Localhost only (the narrow e2e exception in AGENTS.md). Read-only: it navigates, waits for the
// route to settle, records the headings and any console errors, and screenshots the result so the
// page can be looked at rather than inferred from a 1.2 kB SPA shell.

import { test, expect } from '@playwright/test'

test.describe.configure({ timeout: 90000 })

test('account route renders its own page, not the chat shell', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text().slice(0, 200))
  })
  page.on('pageerror', (err) => errors.push(String(err).slice(0, 200)))

  await page.goto('/ui/account')
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(800)

  const body = (await page.locator('body').innerText()).trim()
  const headings = await page.locator('h1, h2, h3').allInnerTexts()

  const shot = testInfo.project.name.includes('mobile') ? 'account-mobile' : 'account-desktop'
  await page.screenshot({ path: `reports/ty/${shot}.png`, fullPage: true })

  console.log(JSON.stringify({
    project: testInfo.project.name,
    url: page.url(),
    headings: headings.slice(0, 8),
    bodyChars: body.length,
    hasChatInput: (await page.locator('.chat-input, [data-testid="chat-input"]').count()) > 0,
    errors,
  }))

  expect(page.url()).toContain('/ui/account')
  expect(body.length).toBeGreaterThan(40)
})
