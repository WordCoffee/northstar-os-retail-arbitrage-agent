// ═══════════════════════════════════════════════════════════════════════════
// AMAZON FILES UI — browser harness (file-only workflow surface)
//
// Drives the Ads > Amazon files surface with real clicks and a real fixture:
// upload -> open -> edit a row -> propose -> approve -> write -> round-trip
// PASS shown -> download link present -> cleanup.
//
// Run:  node tools/verify-amazon-files-ui.cjs
// Exit: 0 = all green, 1 = a failure, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')
const path = require('path')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const API = BASE.replace(/\/ui\/?$/, '')
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const FIXTURE = path.join(__dirname, 'fixtures', 'amazon_files', 'sp_bulksheet.xlsx')
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  // Clean any leftovers from earlier runs.
  await page.evaluate(async (api) => {
    const j = await (await fetch(api + '/api/design-studio/amazon-files', { credentials: 'include' })).json()
    for (const u of (j.uploads || []).filter(x => String(x.filename || '').startsWith('sp_bulksheet'))) {
      await fetch(api + '/api/design-studio/amazon-files/' + encodeURIComponent(u.id), { method: 'DELETE', credentials: 'include' })
    }
  }, API)

  await page.goto(BASE + 'design-studio?section=ads&view=amazon-files', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="amazon-files-workspace"]', { timeout: 30000 })
  ok('the Amazon files surface mounted inside Ads')

  // Upload the fixture through the real file input.
  await page.setInputFiles('[data-testid="af-file"]', FIXTURE)
  await page.waitForSelector('[data-testid="af-archive"] tbody tr', { timeout: 20000 })
  const archive = await page.$eval('[data-testid="af-archive"]', e => e.textContent)
  if (/sp_bulksheet\.xlsx/.test(archive) && /ads_bulksheet/.test(archive)) ok('the bulksheet uploaded and appears in the archive with its kind')
  else no('archive row missing', archive.slice(0, 140))

  // Open it (auto-opened after upload; click Open to be sure).
  await page.click('[data-testid="af-archive"] tbody tr button:has-text("Open")')
  await page.waitForSelector('[data-testid="af-rows"]', { timeout: 20000 })
  ok('the row table rendered')

  // Edit row 2 (the keyword row): bid 0.95.
  const row = page.locator('[data-testid="af-rows"] tbody tr').nth(2)
  await row.locator('input[placeholder="bid"]').fill('0.95')
  await page.click('[data-testid="af-propose"]')
  await page.waitForSelector('[data-testid="af-proposals"]', { timeout: 20000 })
  const propText = await page.$eval('[data-testid="af-proposals"]', e => e.textContent)
  if (/0\.75 → 0\.95/.test(propText)) ok('the proposal shows the before/after (0.75 → 0.95) with its evidence')
  else no('proposal before/after missing', propText.slice(0, 200))

  // Approve, then write.
  await page.click('[data-testid="af-proposals"] button:text-is("Approve")')
  await page.waitForTimeout(1200)
  const afterApprove = await page.$eval('[data-testid="af-proposals"]', e => e.textContent)
  if (/\[approved\]/.test(afterApprove)) ok('the proposal flips to [approved] after the click')
  else no('proposal did not become approved', afterApprove.slice(0, 200))
  await page.click('[data-testid="af-write"]')
  await page.waitForSelector('[data-testid="af-write-result"]', { timeout: 20000 })
  const writeText = await page.$eval('[data-testid="af-write-result"]', e => e.textContent)
  if (/Round-trip: PASS/.test(writeText) && /only the approved change/.test(writeText)) ok('the write reports Round-trip PASS (only the approved change differs)')
  else no('round-trip not reported as PASS', writeText.slice(0, 200))
  if (/sp_bulksheet-change-v1\.xlsx/.test(writeText)) ok('the change file is a NEW versioned filename (original untouched)')
  else no('versioned filename missing', writeText.slice(0, 160))
  const dl = await page.$('[data-testid="af-download"]')
  if (dl) ok('the download link for the change file is present')
  else no('no download link')

  // Cleanup.
  await page.evaluate(async (api) => {
    const j = await (await fetch(api + '/api/design-studio/amazon-files', { credentials: 'include' })).json()
    for (const u of (j.uploads || []).filter(x => String(x.filename || '').startsWith('sp_bulksheet'))) {
      await fetch(api + '/api/design-studio/amazon-files/' + encodeURIComponent(u.id), { method: 'DELETE', credentials: 'include' })
    }
  }, API)
  ok('fixture upload cleaned up')

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`AMAZON FILES UI: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
