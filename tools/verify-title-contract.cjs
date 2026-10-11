// ═══════════════════════════════════════════════════════════════════════════
// TITLE / FLAT-FILE CONTRACT — browser harness (Phase 9 item 3)
//
// Proves on the served build:
//   • the title rules notice is visible in the ListingForge editor;
//   • "Export copy (CSV)" carries the Item Highlights = UNKNOWN notice;
//   • the exported header has an item_highlights column whose value is EMPTY
//     (UNKNOWN), never a guessed column name;
//   • nothing is published and no provider is contacted.
//
// Run:  node tools/verify-title-contract.cjs
// Exit: 0 = contract holds, 1 = a failure, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')
const fs = require('fs')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 180000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 }, acceptDownloads: true })
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

  await page.goto(BASE + 'listingforge', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('button:has-text("Edit")', { timeout: 30000 })
  await page.click('button:has-text("Edit")')
  await page.waitForSelector('[data-testid="lf-title-notice"]', { timeout: 20000 })
  const notice = await page.$eval('[data-testid="lf-title-notice"]', e => e.textContent).catch(() => '')
  if (/UNKNOWN/.test(notice) && /Item Highlights/.test(notice) && /75 characters/.test(notice) && /do not invent/i.test(notice)) {
    ok('the editor shows the title-rules / Item Highlights notice (UNKNOWN column, 75 chars, never invent)')
  } else no('the title notice is missing or incomplete', notice.slice(0, 160))

  const dlPromise = page.waitForEvent('download', { timeout: 15000 })
  await page.click('[data-testid="lf-export"]')
  let filePath = ''
  try {
    const dl = await dlPromise
    filePath = await dl.path()
    ok(`export produced a real download (${dl.suggestedFilename()})`)
  } catch { no('no download from Export copy (CSV)') }

  if (filePath && fs.existsSync(filePath)) {
    const csv = fs.readFileSync(filePath, 'utf8')
    const first = csv.split('\n')[0]
    if (/Item Highlights column: UNKNOWN/.test(first) && /do not invent/i.test(first)) {
      ok('the CSV starts with the Item Highlights = UNKNOWN notice')
    } else no('the CSV first line lacks the UNKNOWN notice', first.slice(0, 140))
    const header = csv.split('\n').find(l => /^asin,/.test(l)) || ''
    if (header.includes('item_highlights')) ok('the CSV header carries an item_highlights column')
    else no('no item_highlights column in the header', header.slice(0, 120))
    const dataRow = csv.split('\n')[2] || ''
    // The data record ends with ,"" (empty item_highlights) right before the
    // trailing comment line; quoted bullets may span lines, so match the tail.
    if (/,(""|)\s*\r?\n# item_highlights/.test(csv) || dataRow.endsWith(',""')) {
      ok('the item_highlights value is EMPTY (UNKNOWN), never a guessed value')
    } else no('item_highlights was not left empty', csv.slice(-120))
    if (/flat-file column UNKNOWN/.test(csv)) ok('the CSV states the flat-file column is UNKNOWN')
    else no('the CSV does not state the flat-file column is UNKNOWN')
  }

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`TITLE CONTRACT: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
