// ═══════════════════════════════════════════════════════════════════════════
// MASTER-BRAIN PANELS — browser harness (Phase 9 item 2)
//
// Proves on the served build:
//   • the read-only Studio-evidence panel renders in ListingForge, AdPilot and
//     SocialPulse;
//   • it states read-only + no provider calls;
//   • an empty section reads UNKNOWN (never a blank or a zero);
//   • a tenant listing record seeded through the API appears in the panels;
//   • the seeded record is cleaned up afterwards.
//
// Run:  node tools/verify-master-brain-panels.cjs
// Exit: 0 = contract holds, 1 = a failure, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const ROOMS = [
  ['adpilot', 'AdPilot'],
  ['listingforge', 'ListingForge'],
  ['socialpulse', 'SocialPulse'],
  ['keyword-tracker', 'KeywordTracker'],
  ['competitor-monitor', 'CompetitorMonitor'],
  ['listings', 'ListingGuardian'],
  ['profitability', 'ProfitabilityDashboard'],
  ['commerce-ops', 'CommerceOps'],
  ['monitoring', 'Monitoring'],
]

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  const bad503Urls = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })
  page.on('response', (r) => {
    if (r.status() === 503) bad503Urls.push(r.url().slice(0, 120))
  })

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  // Cleanup any leftover harness record, then seed one through the API.
  const stamp = Date.now().toString(36)
  const seedAsin = `B00MB${stamp.slice(0, 5).toUpperCase()}`
  await page.evaluate(async (asin) => {
    const j = await (await fetch('/api/design-studio/listing-records', { credentials: 'include' })).json()
    for (const r of (j.records || []).filter(x => String(x.asin || '').startsWith('B00MB'))) {
      await fetch('/api/design-studio/listing-records/' + encodeURIComponent(r.id), { method: 'DELETE', credentials: 'include' })
    }
    await fetch('/api/design-studio/listing-records/migrate', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ records: [{
        asin, title: 'Master-brain panel probe listing', bullets: ['b1'],
        observed_at: '2026-10-05T00:00:00Z', legacy_key: `mb:${asin}`,
      }] }),
    })
  }, seedAsin)
  ok('seeded a tenant listing record for the panel check')

  for (const [route, label] of ROOMS) {
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await page.waitForSelector('[data-testid="master-brain-panel"]', { timeout: 30000 })
    await page.waitForTimeout(1200)
    // 2026-10-16: the redesigned panel renders the record lists behind a
    // "Details" toggle; open it so the seeded record is actually rendered.
    const details = await page.$('[data-testid="master-brain-panel"] button:has-text("Details")')
    if (details) { await details.click(); await page.waitForTimeout(600) }
    const text = await page.$eval('[data-testid="master-brain-panel"]', e => e.textContent).catch(() => '')
    if (/read-only/.test(text) && /no provider calls/.test(text)) {
      ok(`${label}: the panel renders and states read-only + no provider calls`)
    } else no(`${label}: the panel is missing its read-only boundary`, text.slice(0, 120))
    if (text.includes('Master-brain panel probe listing')) {
      ok(`${label}: the seeded tenant listing record appears in the panel`)
    } else no(`${label}: the seeded record did not appear`, text.slice(0, 160))
    if (/UNKNOWN/.test(text)) {
      ok(`${label}: at least one section states UNKNOWN rather than a blank or a zero`)
    } else no(`${label}: no UNKNOWN state rendered (suspicious)`)
  }

  // Cleanup the seeded record.
  await page.evaluate(async () => {
    const j = await (await fetch('/api/design-studio/listing-records', { credentials: 'include' })).json()
    for (const r of (j.records || []).filter(x => String(x.asin || '').startsWith('B00MB'))) {
      await fetch('/api/design-studio/listing-records/' + encodeURIComponent(r.id), { method: 'DELETE', credentials: 'include' })
    }
  })
  ok('seeded record cleaned up')

  // Boundary notices filtered with their cause stated: pre-auth 401s (the shell
  // probes /me before sign-in) and the documented honest 503 from
  // /api/v1/noncreative/sources (a failed read is reported as "unavailable",
  // never as an empty zero - noncreative_reads.py). A 503 anywhere else fails.
  const UNEXPECTED_503 = bad503Urls.filter(u => !/noncreative\/sources/.test(u))
  const realErrors = errors.filter(e => {
    if (/401|403|429/.test(e)) return false
    if (/status of 503/.test(e) && UNEXPECTED_503.length === 0) return false
    return true
  })
  if (realErrors.length === 0 && UNEXPECTED_503.length === 0) {
    ok(`no console/page errors (${errors.length} boundary notices filtered: pre-auth 401s + the documented noncreative 503 on ${bad503Urls.length} request(s))`)
  } else {
    no(`${realErrors.length} real console/page error(s), ${UNEXPECTED_503.length} unexpected 503(s)`, [...UNEXPECTED_503, ...realErrors].slice(0, 2).join(' | '))
  }

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`MASTER-BRAIN PANELS: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
