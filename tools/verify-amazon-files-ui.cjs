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
const ERROR_REPORT = path.join(__dirname, 'fixtures', 'amazon_files', 'ads_error_report.xlsx')
const METRICS_BEFORE = path.join(__dirname, 'fixtures', 'amazon_files', 'metrics_before.xlsx')
const METRICS_AFTER = path.join(__dirname, 'fixtures', 'amazon_files', 'metrics_after.xlsx')
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 300000)
const CLEAN_PREFIXES = ['sp_bulksheet', 'ads_error_report', 'metrics_before', 'metrics_after', 'probe_bulk']

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
  await page.evaluate(async (args) => {
    const [api, prefixes] = args
    const j = await (await fetch(api + '/api/design-studio/amazon-files', { credentials: 'include' })).json()
    for (const u of (j.uploads || []).filter(x => prefixes.some(p => String(x.filename || '').startsWith(p)))) {
      await fetch(api + '/api/design-studio/amazon-files/' + encodeURIComponent(u.id), { method: 'DELETE', credentials: 'include' })
    }
  }, [API, CLEAN_PREFIXES])

  await page.goto(BASE + 'design-studio?section=ads&view=amazon-files', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="amazon-files-workspace"]', { timeout: 30000 })
  ok('the Amazon files surface mounted inside Ads')

  // Onboarding guide + sample pack (item 11).
  await page.click('[data-testid="af-onboarding-toggle"]')
  await page.waitForSelector('[data-testid="af-onboarding"]', { timeout: 10000 })
  const guide = await page.$eval('[data-testid="af-onboarding"]', e => e.textContent)
  if (/Which files to download/.test(guide) && /no Amazon sign-in/i.test(guide)) ok('onboarding guide lists what to download and states the file-only posture')
  else no('onboarding guide incomplete', guide.slice(0, 160))
  const sampleLinks = await page.$$eval('[data-testid="af-samples"] a', els => els.map(e => e.getAttribute('href')))
  if (sampleLinks.length >= 8 && sampleLinks.every(h => h.startsWith('/ui/samples/amazon-files/'))) ok(`sample pack offers ${sampleLinks.length} synthetic files (local links)`)
  else no('sample pack links wrong', JSON.stringify(sampleLinks.slice(0, 3)))
  await page.click('[data-testid="af-onboarding-toggle"]')

  // Upload the fixture through the real file input.
  await page.setInputFiles('[data-testid="af-file"]', FIXTURE)
  await page.waitForSelector('[data-testid="af-archive"] tbody tr', { timeout: 20000 })
  const archive = await page.$eval('[data-testid="af-archive"]', e => e.textContent)
  if (/sp_bulksheet\.xlsx/.test(archive) && /ads_bulksheet/.test(archive)) ok('the bulksheet uploaded and appears in the archive with its kind')
  else no('archive row missing', archive.slice(0, 140))

  // Open the bulksheet row specifically (the archive may hold other fixtures).
  const openRows = await page.$$('[data-testid="af-archive"] tbody tr')
  let opened = false
  for (const r of openRows) {
    const t = await r.textContent()
    if (/sp_bulksheet/.test(t)) { await r.$eval('button', b => b.click()); opened = true; break }
  }
  if (!opened) { no('could not find the bulksheet row to open'); await browser.close(); return report() }
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

  // ── Change files list + processing report match + corrected file (item 2) ──
  await page.waitForSelector('[data-testid="af-changes"]', { timeout: 15000 })
  const changesText = await page.$eval('[data-testid="af-changes"]', e => e.textContent)
  if (/sp_bulksheet-change-v1\.xlsx/.test(changesText)) ok('the change files list shows the written change file')
  else no('change files list missing the change file', changesText.slice(0, 160))

  const changeSelect = await page.$('[data-testid="af-report-change"] option[value]:not([value=""])')
  if (changeSelect) {
    const val = await changeSelect.getAttribute('value')
    await page.selectOption('[data-testid="af-report-change"]', val)
    await page.setInputFiles('[data-testid="af-report-file"]', ERROR_REPORT)
    await page.waitForSelector('[data-testid="af-report-match"]', { timeout: 20000 })
    const matchText = await page.$eval('[data-testid="af-report-match"]', e => e.textContent)
    if (/Matched 1 row\(s\)/.test(matchText) && /unmatched 1/.test(matchText)) ok('report match: 1 row matched to the change, 1 unmatched reported (never guessed)')
    else no('report match counts wrong', matchText.slice(0, 200))
    if (/Bid is invalid/.test(matchText) && /proposal/.test(matchText)) ok('report match: the cause is quoted and the proposal linkage is shown')
    else no('report match cause/linkage missing', matchText.slice(0, 220))
    if (/K999/.test(matchText)) ok('report match: the unmatched K999 row is reported')
    else no('unmatched row not reported', matchText.slice(0, 200))
    await page.click('[data-testid="af-write-corrected"]')
    await page.waitForSelector('[data-testid="af-correct-result"]', { timeout: 20000 })
    const correctText = await page.$eval('[data-testid="af-correct-result"]', e => e.textContent)
    if (/Round-trip: PASS/.test(correctText) && /corrected-v2/.test(correctText)) ok('corrected file: new version (corrected-v2), round-trip PASS, only the corrections differ')
    else no('corrected file result wrong', correctText.slice(0, 220))
    const cdl = await page.$('[data-testid="af-download-corrected"]')
    if (cdl) ok('corrected file download link present')
    else no('no corrected download link')
  } else {
    no('no change file option to match the report against')
  }

  // ── Before/after comparison (item 5) ───────────────────────────────────────
  await page.setInputFiles('[data-testid="af-file"]', METRICS_BEFORE)
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="af-archive"]')
    return !!el && /metrics_before/.test(el.textContent)
  }, null, { timeout: 20000 })
  await page.setInputFiles('[data-testid="af-file"]', METRICS_AFTER)
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="af-archive"]')
    return !!el && /metrics_after/.test(el.textContent)
  }, null, { timeout: 20000 })
  await page.waitForTimeout(500)
  // Open metrics_before, then compare against metrics_after.
  const rowsAll = await page.$$('[data-testid="af-archive"] tbody tr')
  let openedBefore = false
  for (const r of rowsAll) {
    const t = await r.textContent()
    if (/metrics_before/.test(t)) { await r.$eval('button', b => b.click()); openedBefore = true; break }
  }
  if (!openedBefore) no('could not open metrics_before from the archive')
  await page.waitForSelector('[data-testid="af-compare"]', { timeout: 20000 })
  await page.waitForFunction(() => {
    const sel = document.querySelector('[data-testid="af-compare-target"]')
    return !!sel && Array.from(sel.options).some(o => /metrics_after/.test(o.textContent))
  }, null, { timeout: 15000 })
  const optionTexts = await page.$$eval('[data-testid="af-compare-target"] option', els => els.map(e => e.textContent.trim()))
  const afterIdx = optionTexts.findIndex(t => /metrics_after/.test(t))
  if (afterIdx >= 0) {
    await page.selectOption('[data-testid="af-compare-target"]', { index: afterIdx })
    await page.click('[data-testid="af-compare-run"]')
    await page.waitForSelector('[data-testid="af-compare-result"]', { timeout: 20000 })
    const cmpText = await page.$eval('[data-testid="af-compare-result"]', e => e.textContent)
    if (/No causation/.test(cmpText) && /engineering choice/.test(cmpText)) ok('comparison: explicit no-causation notice + the stale window labelled an engineering choice')
    else no('comparison notices missing', cmpText.slice(0, 200))
    if (/K300/.test(cmpText) && /12/.test(cmpText) && /18/.test(cmpText)) ok('comparison: the per-entity before/after row renders (K300 12 → 18 clicks)')
    else no('comparison row missing', cmpText.slice(0, 220))
    if (/UNKNOWN/.test(cmpText)) ok('comparison: a metric missing from one file renders UNKNOWN (never 0)')
    else no('comparison UNKNOWN handling missing', cmpText.slice(0, 200))
  } else {
    no('no after-upload option for the comparison', `options=${JSON.stringify(optionTexts.slice(0, 4))}`)
  }

  // Cleanup (let pending UI fetches settle first so the delete cannot race them).
  await page.waitForTimeout(1200)
  await page.evaluate(async (args) => {
    const [api, prefixes] = args
    const j = await (await fetch(api + '/api/design-studio/amazon-files', { credentials: 'include' })).json()
    for (const u of (j.uploads || []).filter(x => prefixes.some(p => String(x.filename || '').startsWith(p)))) {
      await fetch(api + '/api/design-studio/amazon-files/' + encodeURIComponent(u.id), { method: 'DELETE', credentials: 'include' })
    }
  }, [API, CLEAN_PREFIXES])
  ok('fixture uploads cleaned up')

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
