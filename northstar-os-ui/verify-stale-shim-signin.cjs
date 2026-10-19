// ═══════════════════════════════════════════════════════════════════════════
// STALE DEV-SHIM IDENTITY → REAL SIGN-IN — browser harness
//
// Reproduces the operator's exact stuck state against the running dev server:
//   1. submitting the PREFILLED demo pair fails closed with an explicit alert
//      (that is the documented dev-shim contract - see
//      tools/verify-shim-fail-closed.cjs);
//   2. that attempt PERSISTS a dev identity in localStorage (`ns-dev-session`),
//      because the shim branch calls session.updateDev(...) before refreshing;
//   3. a REAL local account must then sign in ANYWAY. The stale identity's
//      X-User-Id/X-Org-Id headers are attached to every foundation request
//      (foundation/api.js `headers()`), and foundation/api/deps.py resolves
//      `requested_org` from X-Org-Id - so a stale `X-Org-Id: org-t2` makes the
//      cookie-authenticated session fail closed with
//      403 cross_organization_access_denied on /me and the SPA bounces back to
//      /sign-in with no message at all. SignIn.jsx clears the dev identity
//      before a real login so the cookie is the sole identity;
//   4. the session must then survive a reload (no bounce back to /sign-in).
//
// Run:  node verify-stale-shim-signin.cjs
//       HARNESS_BASE_URL=http://127.0.0.1:8101/ui/ NS_TEST_EMAIL=t2 \
//       NS_TEST_PASSWORD=<local account password> node verify-stale-shim-signin.cjs
//
// Exit: 0 = contract holds, 1 = a violation, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 180000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 850 } })
  const page = await ctx.newPage()

  const loginUrls = []
  const meAfter = []
  let phase = 'shim'
  page.on('request', (r) => { if (r.url().includes('/auth/login')) loginUrls.push(r.url()) })
  page.on('response', (r) => {
    if (r.url().includes('/api/v1/foundation/me') && phase === 'real') {
      meAfter.push(r.status())
    }
  })

  // ---- 1: the prefilled shim pair fails closed -----------------------------
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 45000 })
  await page.waitForTimeout(2500)

  const prefilled = await page.$eval('#signin-id', (el) => el.value)
  if (prefilled === 'T2') ok('dev server still prefills the demo identity (T2)')
  else ftl('the demo identity is no longer prefilled', prefilled)

  const loginBefore = loginUrls.length
  await page.click('form button[type="submit"]')
  await page.waitForTimeout(3500)

  const alert = await page.$eval('[role="alert"]', (el) => el.textContent).catch(() => '')
  if (/could not authenticate/i.test(alert) && /nothing was sent to the credential endpoint/i.test(alert)) {
    ok('the demo pair still fails closed, explicitly, without touching the credential endpoint')
  } else no('the fail-closed alert changed', alert.slice(0, 200))

  if ((await page.evaluate(() => location.pathname)) === '/ui/sign-in') {
    ok('the shim failure did not navigate away')
  } else no('unexpected URL after the shim failure', await page.evaluate(() => location.pathname))

  // ---- 2: the poison is persisted ------------------------------------------
  const dev = await page.evaluate(() => {
    try { return JSON.parse(localStorage.getItem('ns-dev-session') || 'null') } catch { return null }
  })
  if (dev && dev.userId === 'demo-t2' && dev.orgId === 'org-t2') {
    ok('the shim attempt persisted the demo identity in localStorage (the stale-header trap)')
  } else no('the demo identity was not persisted; this scenario cannot be reproduced', JSON.stringify(dev))

  // ---- 3: a real local account signs in anyway -----------------------------
  phase = 'real'
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 20000 })
    ok(`a real account (${EMAIL}) signs in despite the stale dev identity`)
  } catch {
    no('the real account could not sign in', await page.evaluate(() => location.pathname))
    const alert2 = await page.$eval('[role="alert"]', (el) => el.textContent).catch(() => '')
    if (alert2) console.log('        alert: ' + alert2.slice(0, 200))
  }

  const newLogins = loginUrls.length - loginBefore
  if (newLogins === 1) ok('exactly one credential request came from the explicit real-account submit')
  else no(`unexpected credential request count: ${newLogins} (expected 1)`)

  if (meAfter.length >= 1 && meAfter.every((s) => s === 200)) {
    ok(`every post-login /me returned 200 (${meAfter.length} call(s))`)
  } else {
    no('a post-login /me did not return 200', JSON.stringify(meAfter))
  }

  // ---- 4: the session survives a reload ------------------------------------
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000)
  const afterReload = await page.evaluate(() => location.pathname)
  if (afterReload === '/ui/home') ok('the signed-in session survives a reload')
  else no('the reload bounced the session', afterReload)

  await browser.close()
  console.log('')
  console.log(`STALE-SHIM SIGN-IN: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  process.exitCode = (fail || fatal) ? 1 : 0
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
