// Live sign-in walkthrough against a running local Compose stack (P2-T6 local
// verification). Uses real HTTP (NOT HTTPS) — this is not a hosted-TLS test.
//
// Credentials come from the isolated test accounts created by
// Northstar_backend/create_test_accounts.py. Pass them in as NS_TEST_EMAIL /
// NS_TEST_PASSWORD, or let this harness read them from the credentials file
// (NS_TEST_CREDENTIALS_PATH, else %LOCALAPPDATA%\NorthstarOS\test-credentials.json).
//
// Base URL via HARNESS_BASE_URL (default http://127.0.0.1/ui/).
// Passwords are never printed and never written to disk.

const fs = require('fs')
const os = require('os')
const path = require('path')
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'

function credentialsPath() {
  return process.env.NS_TEST_CREDENTIALS_PATH
    || path.join(process.env.LOCALAPPDATA || os.tmpdir(), 'NorthstarOS', 'test-credentials.json')
}

function loadAccount(role) {
  const file = credentialsPath()
  if (!fs.existsSync(file)) {
    console.error(`No credentials file at ${file}.`)
    console.error('Create the isolated test accounts first:')
    console.error('  cd Northstar_backend && python create_test_accounts.py')
    process.exit(2)
  }
  let record
  try {
    record = JSON.parse(fs.readFileSync(file, 'utf-8'))
  } catch (e) {
    console.error(`Could not parse ${file}: ${e.message}`)
    process.exit(2)
  }
  const account = (record.accounts || {})[role || 'subscriber']
  if (!account || !account.email) {
    console.error(`No '${role || 'subscriber'}' account in ${file}.`)
    process.exit(2)
  }
  if (!account.password) {
    console.error(`The '${role || 'subscriber'}' account has no password (it is not an activated account).`)
    process.exit(2)
  }
  return { email: account.email, password: account.password, tenantId: account.tenant_id }
}

const EMAIL = process.env.NS_TEST_EMAIL
const PW = process.env.NS_TEST_PASSWORD
let CREDS = null

let pass = 0
let fail = 0
const problems = []
const consoleErrors = []
const pageErrors = []
const failedRequests = []
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; problems.push(m + (d ? ' :: ' + d : '')); console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  CREDS = (EMAIL && PW)
    ? { email: EMAIL, password: PW }
    : loadAccount(process.env.NS_TEST_ROLE || 'subscriber')

  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })
  page.on('pageerror', (e) => pageErrors.push(String(e)))
  page.on('requestfailed', (r) => failedRequests.push(r.url() + ' :: ' + (r.failure() && r.failure().errorText)))

  // 1. Sign in at /ui/sign-in (hosted behavior: no local-dev flag).
  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', CREDS.email)
  await page.fill('#signin-pw', CREDS.password)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 12000 })
    ok('sign-in -> /ui/home')
  } catch { no('sign-in route', await page.evaluate(() => location.pathname)) }

  const token = await page.evaluate(() => { try { return localStorage.getItem('ns-access-token') } catch { return 'blocked' } })
  ;(token === null || token === '') ? ok('no access token in localStorage') : no('token in localStorage', String(token))

  const localDev = await page.evaluate(() => !!window.__NORTHSTAR_LOCAL_DEV__)
  !localDev ? ok('hosted build has no local-dev flag (dev shim off)') : no('local-dev flag present in served build')

  // 2. Direct load + refresh of a protected route.
  await page.goto(BASE + 'monitoring')
  await page.waitForTimeout(900)
  ;(await page.evaluate(() => location.pathname)) === '/ui/monitoring'
    ? ok('authenticated direct load /ui/monitoring stays')
    : no('monitoring direct load', await page.evaluate(() => location.pathname))
  await page.reload()
  await page.waitForTimeout(900)
  ;(await page.evaluate(() => location.pathname)) === '/ui/monitoring'
    ? ok('refresh keeps protected route authenticated')
    : no('refresh protected route', await page.evaluate(() => location.pathname))

  // 3. /me identifies the signed-in account.
  const me = await page.evaluate(async () => {
    const r = await fetch('/api/v1/foundation/me', { credentials: 'include' })
    return { status: r.status, body: await r.json() }
  })
  ;(me.status === 200 && me.body.user_id) ? ok('/me identifies user ' + me.body.user_id) : no('/me', JSON.stringify(me))

  // 3b. The AutothinK routes are authenticated for this session (P0-04).
  const autothink = await page.evaluate(async () => {
    const r = await fetch('/api/autothink/history?limit=1', { credentials: 'include' })
    return r.status
  })
  ;(autothink === 200 || autothink === 403) ? ok('/api/autothink/history answers for a signed-in session (' + autothink + ')') : no('/api/autothink/history', String(autothink))

  // 3c. Tenant isolation: a second tenant must not see this tenant's history.
  if (process.env.NS_TEST_ROLE !== 'other_tenant' && CREDS.tenantId) {
    const cross = await page.evaluate(async () => {
      const r = await fetch('/api/autothink/history?limit=1', {
        credentials: 'include',
        headers: { 'X-Tenant-Id': 'tenant-that-is-not-mine' },
      })
      return r.status
    })
    cross !== 200 ? ok('cross-tenant header cannot widen the session (' + cross + ')') : no('cross-tenant header accepted', String(cross))
  }

  // 4. State-changing request without CSRF -> 403.
  const noCsrf = await page.evaluate(async () => {
    const r = await fetch('/api/v1/foundation/auth/logout', { method: 'POST', credentials: 'include' })
    return r.status
  })
  noCsrf === 403 ? ok('logout without CSRF header -> 403') : no('logout no-csrf', String(noCsrf))

  // 5. With CSRF double-submit -> 200.
  const withCsrf = await page.evaluate(async () => {
    const m = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
    const csrf = m ? decodeURIComponent(m[2]) : ''
    const r = await fetch('/api/v1/foundation/auth/logout', {
      method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': csrf },
    })
    return { status: r.status, hadCsrf: !!csrf }
  })
  ;(withCsrf.hadCsrf && withCsrf.status === 200) ? ok('logout with CSRF header -> 200') : no('logout with csrf', JSON.stringify(withCsrf))

  // 6. /me is now 401.
  const me2 = await page.evaluate(async () => {
    const r = await fetch('/api/v1/foundation/me', { credentials: 'include' })
    return r.status
  })
  me2 === 401 ? ok('/me after logout -> 401') : no('/me after logout', String(me2))

  // 7. Direct protected-route load redirects to /ui/sign-in.
  await page.goto(BASE + 'monitoring')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/sign-in', null, { timeout: 9000 })
    ok('signed-out direct /ui/monitoring -> /ui/sign-in')
  } catch { no('signed-out redirect', await page.evaluate(() => location.pathname)) }

  // Browser logs "Failed to load resource" for the intentionally-triggered 401/403
  // probes; those are expected. Only unexpected console errors / JS exceptions fail.
  const expectedNoise = consoleErrors.filter((t) => /Failed to load resource/i.test(t));
  const realConsoleErrors = consoleErrors.filter((t) => !/favicon/i.test(t) && !/Failed to load resource/i.test(t));
  if (realConsoleErrors.length === 0) ok('no unexpected console errors (' + expectedNoise.length + ' expected non-2xx resource notices)');
  else no('console errors', realConsoleErrors.join(' | '));
  if (pageErrors.length === 0) ok('no uncaught JS exceptions'); else no('uncaught JS exceptions', pageErrors.join(' | '));
  const realFailed = failedRequests.filter((u) => !/favicon/i.test(u));
  if (realFailed.length === 0) ok('no failed network requests'); else no('failed requests', realFailed.join(' | '));

  await browser.close()
  console.log(`\nLIVE-SIGNIN RESULTS: ${pass} passed, ${fail} failed`)
  if (problems.length) { console.log('--- issues ---'); problems.forEach((p) => console.log('  ' + p)) }
  process.exit(fail ? 1 : 0)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })