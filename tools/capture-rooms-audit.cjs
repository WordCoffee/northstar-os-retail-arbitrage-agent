// UI AUDIT — every room, desktop width: screenshots + console errors + timing +
// sample-state text detection. Evidence for the production-readiness plan.
//
// Run:  node tools/capture-rooms-audit.cjs
// Out:  reports/ui_audit_<STAMP>/ (one PNG per room + AUDIT.json + AUDIT.md)
// Exit: 0 = audit completed (findings are data, not failures), 2 = fatal.

const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const STAMP = new Date().toISOString().slice(0, 10).replace(/-/g, '')
const OUT = path.join(__dirname, '..', 'reports', `ui_audit_${STAMP}`)

const ROOMS = [
  ['command-center', '/home'],
  ['product-finder', '/product-finder'],
  ['design-studio', '/design-studio'],
  ['golden-goose', '/golden-goose'],
  ['listing-guardian', '/listings'],
  ['keyword-tracker', '/keyword-tracker'],
  ['competitor-monitor', '/competitor-monitor'],
  ['listingforge', '/listingforge'],
  ['adpilot', '/adpilot'],
  ['socialpulse', '/socialpulse'],
  ['profitability', '/profitability'],
  ['spreadsheet-lab', '/spreadsheet-lab'],
  ['commerce-ops', '/commerce-ops'],
  ['monitoring', '/monitoring'],
  ['autothink', '/autothink'],
  ['memory-bank', '/memory-bank'],
  ['shared-data', '/shared-data'],
  ['provider-adapters', '/provider-adapters'],
  ['master-brain', '/master-brain'],
  ['customer-workspace', '/customer-workspace'],
  ['setup', '/setup'],
  ['documents', '/documents'],
  ['plan', '/plan'],
  ['support', '/support'],
  ['account', '/account'],
]

// Console noise that is expected in the local stack (pre-auth 401s, the honest
// noncreative 503). 429 is NOT filtered: a rate-limited room is a finding.
const BOUNDARY = /401|403|noncreative\/sources.*503|status of 503.*Service Unavailable/i

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 20000 })
  console.log('PASS  signed in')

  const findings = []
  for (const [id, route] of ROOMS) {
    const errors = []
    const onConsole = (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)) }
    const onPageError = (e) => errors.push('pageerror: ' + String(e).slice(0, 160))
    page.on('console', onConsole)
    page.on('pageerror', onPageError)
    const t0 = Date.now()
    let status = 'ok'
    try {
      await page.goto(BASE.replace(/\/ui\/?$/, '') + '/ui' + route, { waitUntil: 'domcontentloaded', timeout: 30000 })
      await page.waitForTimeout(1800)
    } catch (e) {
      status = 'nav-failed: ' + String(e).slice(0, 100)
    }
    const ms = Date.now() - t0
    const bodyText = status === 'ok' ? (await page.evaluate(() => document.body.innerText.slice(0, 6000)).catch(() => '')) : ''
    const sampleBanners = (bodyText.match(/sample|Sample|SAMPLE|demo data|placeholder/gi) || []).length
    const partialLabels = (bodyText.match(/Partial|PARTIAL|Concept|LLM-gated|Cached|Sample\b/g) || []).length
    const buttons = status === 'ok' ? (await page.$$eval('button:not([disabled])', els => els.length).catch(() => -1)) : -1
    const realErrors = errors.filter(e => !BOUNDARY.test(e))
    const shot = path.join(OUT, `${id}.png`)
    if (status === 'ok') await page.screenshot({ path: shot, fullPage: false }).catch(() => {})
    page.off('console', onConsole)
    page.off('pageerror', onPageError)
    findings.push({ room: id, route, status, ms, buttons, sampleWords: sampleBanners, partialLabels, errors: realErrors, screenshot: status === 'ok' ? `${id}.png` : null })
    console.log(`${status === 'ok' ? 'ROOM ' : 'FAIL '} ${id.padEnd(18)} ${String(ms).padStart(5)}ms  buttons=${buttons}  sample-words=${sampleBanners}  partial-labels=${partialLabels}  errors=${realErrors.length}${realErrors.length ? ' :: ' + realErrors[0] : ''}`)
  }

  fs.writeFileSync(path.join(OUT, 'AUDIT.json'), JSON.stringify({ stamp: STAMP, base: BASE, rooms: findings }, null, 1))
  const md = ['# UI audit ' + STAMP, '', '| Room | Route | ms | buttons | sample-words | partial-labels | errors |', '|---|---|---|---|---|---|---|',
    ...findings.map(f => `| ${f.room} | ${f.route} | ${f.ms} | ${f.buttons} | ${f.sampleWords} | ${f.partialLabels} | ${f.errors.length}${f.errors.length ? ' :: ' + f.errors[0].replace(/\|/g, '/') : ''} |`)].join('\n')
  fs.writeFileSync(path.join(OUT, 'AUDIT.md'), md + '\n')
  await browser.close()
  console.log(`\nUI AUDIT: ${findings.length} rooms -> ${OUT}`)
  process.exit(0)
}

main().catch((e) => { console.error('FATAL ' + String(e).slice(0, 200)); process.exit(2) })
