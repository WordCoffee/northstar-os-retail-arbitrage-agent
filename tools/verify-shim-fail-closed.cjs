// ═══════════════════════════════════════════════════════════════════════════
// SHIM FAIL-CLOSED — browser harness (Phase 7 item 2)
//
// Proves, against the running Vite dev server:
//   1. submitting the dev shim identity NEVER reaches /auth/login (no real
//      credential attempt from the shim path, whatever the backend posture);
//   2. the failure is explicit (an alert naming the cause) and the URL stays;
//   3. nothing is logged that carries the demo password;
//   4. real credentials, explicitly typed, still sign in (the supported path).
//
// Run:  node tools/verify-shim-fail-closed.cjs
// Exit: 0 = contract holds, 1 = a violation, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const REAL_EMAIL = process.env.NS_TEST_EMAIL || 't2'
const REAL_PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
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

  const requests = []
  const consoleLines = []
  page.on('request', (r) => requests.push(r.url()))
  page.on('console', (m) => consoleLines.push(m.text()))
  page.on('pageerror', (e) => consoleLines.push('pageerror: ' + String(e)))

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 45000 })
  await page.waitForTimeout(2500)

  // The dev server prefills the shim identity. Confirm that is the state.
  const prefilled = await page.$eval('#signin-id', (el) => el.value)
  if (prefilled === 'T2') ok('dev server prefills the shim identity (T2)')
  else ftl('dev server did not prefill the shim identity', prefilled)

  const loginBefore = requests.filter((u) => u.includes('/auth/login')).length

  // 1+2+3: submit the shim identity.
  await page.click('form button[type="submit"]')
  await page.waitForTimeout(3500)

  const loginAfter = requests.filter((u) => u.includes('/auth/login')).length
  if (loginAfter === loginBefore) ok('the shim path made ZERO /auth/login requests (no real credential attempt)')
  else no(`the shim path attempted a credential login (${loginAfter - loginBefore} request(s))`)

  const meWithShim = requests.filter((u) => u.includes('/api/v1/foundation/me')).length
  if (meWithShim >= 1) ok('the shim attempt DID probe the identity endpoint (a real attempt, just refused)')
  else no('no /me probe happened - the shim attempt never ran')

  const alert = await page.$eval('[role="alert"]', (el) => el.textContent).catch(() => '')
  if (/could not authenticate/i.test(alert) && /nothing was sent to the credential endpoint/i.test(alert)) {
    ok('the failure is explicit and states that nothing was sent to the credential endpoint')
  } else no('no explicit fail-closed alert', alert.slice(0, 160))

  const path = await page.evaluate(() => location.pathname)
  if (path === '/ui/sign-in') ok('the URL stayed on /sign-in (no bounce, no silent navigation)')
  else no(`unexpected URL after the shim failure: ${path}`)

  const leaked = consoleLines.filter((l) => l.includes('123abc'))
  if (leaked.length === 0) ok(`nothing logged carries the demo password (${consoleLines.length} console line(s) checked)`)
  else no('a console line carries the demo password', leaked.slice(0, 2).join(' | '))

  // 4: real credentials, explicitly typed, still work.
  await page.fill('#signin-id', REAL_EMAIL)
  await page.fill('#signin-pw', REAL_PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('an explicitly typed real account signs in (the supported path)')
  } catch {
    no('real credential sign-in failed', await page.evaluate(() => location.pathname))
  }
  const realLogins = requests.filter((u) => u.includes('/auth/login')).length
  if (realLogins === loginBefore + 1) ok('exactly one /auth/login request, from the explicit real-account submit')
  else no(`unexpected /auth/login count: ${realLogins - loginBefore} (expected 1)`)

  await browser.close()
  console.log('')
  console.log(`SHIM FAIL-CLOSED: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  process.exitCode = (fail || fatal) ? 1 : 0
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
