// Operator-facing smoke: sign in as the local owner and prove the three
// reported regressions are gone.
//   1. the suite rail is populated (not the "Sign in to open your workspace" stub)
//   2. the account button (role pill / avatar) opens the Account page
//   3. every rail item navigates to a real, rendered page

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  page.on('pageerror', (e) => no('uncaught exception', String(e)))

  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  ok('signed in -> /ui/home')

  // 1. The rail is populated and no longer shows the sign-in stub.
  await page.waitForTimeout(1200)
  const railItems = await page.$$('.suite-rail-item')
  const stub = await page.$('.suite-rail-signin')
  if (stub) no('suite rail still shows the "Sign in to open your workspace" stub')
  else ok('suite rail no longer shows the sign-in stub')
  if (railItems.length >= 10) ok(`suite rail is populated (${railItems.length} services visible)`)
  else no('suite rail is short', `${railItems.length} items`)

  // The rail must list the internal suite for a platform admin.
  const labels = await page.$$eval('.suite-rail-item-label', (els) => els.map((e) => e.textContent))
  for (const expected of ['Command Center', 'SourceScout', 'ListingForge', 'AdPilot', 'AutothinK']) {
    if (labels.some((l) => l.includes(expected))) ok(`rail lists ${expected}`)
    else no(`rail is missing ${expected}`, labels.join(', '))
  }

  // 2. The account button opens the Account page.
  await page.click('.top-nav-account-btn, .top-nav-avatar')
  await page.waitForTimeout(1500)
  const where = await page.evaluate(() => location.pathname)
  if (where === '/ui/account') ok('account button opens /ui/account')
  else no('account button did not navigate', where)
  const hasError = await page.$('.state-error, [data-testid="state-error"]')
  if (!hasError) ok('account page rendered without an error state')
  else no('account page shows an error state')

  // 3. Every rail item navigates to a page that actually renders.
  // Re-query the items each time: navigating re-renders the rail, which
  // detaches the previously captured handles.
  const visited = []
  const total = (await page.$$('.suite-rail-item')).length
  for (let i = 0; i < Math.min(total, 22); i += 1) {
    const items = await page.$$('.suite-rail-item')
    if (i >= items.length) break
    const label = await items[i].$eval('.suite-rail-item-label', (e) => e.textContent).catch(() => '?')
    try {
      await items[i].click({ timeout: 2500 })
      await page.waitForTimeout(650)
      const path = await page.evaluate(() => location.pathname)
      if (!path.startsWith('/ui/')) { no(`rail item "${label}" left the app`, path); continue }
      const heading = await page.$eval('h1, h2', (e) => e.textContent).catch(() => '')
      if (!heading) no(`rail item "${label}" (${path}) rendered no heading`)
      visited.push(`${label} -> ${path}`)
    } catch (e) {
      no(`rail item "${label}" did not navigate`, String(e).slice(0, 90))
    }
  }
  ok(`${visited.length}/${Math.min(total, 22)} rail destinations navigated and rendered`)
  if (visited.length) { console.log('  ' + visited.join('\n  ')) }

  await browser.close()
  console.log(`\nOPERATOR SMOKE: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
