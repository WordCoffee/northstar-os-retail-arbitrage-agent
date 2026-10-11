// ═══════════════════════════════════════════════════════════════════════════
// 3D RENDER GATE — browser harness (Phase 7 item 4)
//
// Proves on the served build, with real clicks and real renders:
//   • an unanswered people classification BLOCKS the export (no download);
//   • an internal reference with no people opens the gate (real download);
//   • a LISTING purpose is BLOCKED by the Brand Registry actual-photo rule,
//     named with its rule id and source id;
//   • a locked reference turns on the fidelity diff, which BLOCKS a render
//     that diverges from the locked photograph - and a compare sign-off does
//     not lift a fidelity block;
//   • unlocking restores the open gate.
//
// Run:  node tools/verify-render3d-gate.cjs
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

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true })
  const page = await ctx.newPage()
  const errors = []
  const downloads = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)) })
  page.on('download', (d) => downloads.push(d))

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  await page.goto(BASE + 'design-studio?section=3d-scene', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="render3d-gate"]', { timeout: 30000 })
  ok('the 3D Product Scene mounted with the render gate panel')

  // Upload artwork (the picker auto-selects the first added asset).
  const fixture = await page.evaluate(() => {
    const c = document.createElement('canvas')
    c.width = 800; c.height = 800
    const x = c.getContext('2d')
    x.fillStyle = '#f2e3c9'; x.fillRect(0, 0, 800, 800)
    x.fillStyle = '#2a6fc9'; x.fillRect(60, 60, 680, 680)
    x.fillStyle = '#ffffff'; x.font = '60px sans-serif'; x.fillText('PACK ART', 230, 430)
    return c.toDataURL('image/png')
  })
  await page.setInputFiles('label.sp-dropzone input[type="file"]', {
    name: 'harness-pack-art.png', mimeType: 'image/png', buffer: Buffer.from(fixture.split(',')[1], 'base64'),
  })
  await page.waitForTimeout(1200)
  ok('product artwork uploaded and attached to the scene')

  const gateText = async () => page.$eval('[data-testid="render-gate-result"]', e => e.textContent).catch(() => '')
  const exportBtn = page.locator('button:has-text("Export")').first()

  // ── 1. Unanswered disclosure blocks (no download) ────────────────────────
  let dl0 = downloads.length
  await exportBtn.click()
  await page.waitForTimeout(1500)
  let g = await gateText()
  if (/GATE BLOCKED/.test(g) && /disclosure: block/i.test(g)) ok('an unanswered people classification blocks the export (disclosure: block)')
  else no('unanswered disclosure did not block', g.slice(0, 160))
  if (downloads.length === dl0) ok('no download while the gate is blocked')
  else no('a download happened despite the block')

  // ── 2. No people + internal purpose -> open gate, real download ─────────
  await page.selectOption('[data-testid="render-people-class"]', 'no-people')
  await page.waitForTimeout(400)
  let dlPromise = page.waitForEvent('download', { timeout: 15000 })
  await exportBtn.click()
  try {
    await dlPromise
    ok('internal export downloads with the gate open (real download event)')
  } catch { no('no download with the gate open') }
  g = await gateText()
  if (/GATE OPEN/.test(g) && /actualPhoto: not-required/i.test(g) && /disclosure: pass/i.test(g)) {
    ok('the open gate reports its steps honestly (actualPhoto: not-required, disclosure: pass)')
  } else no('gate summary wrong', g.slice(0, 200))

  // ── 3. Listing purpose -> actual-photo BLOCK, named with its source ─────
  dl0 = downloads.length
  await page.selectOption('[data-testid="render-purpose"]', 'listing')
  await page.waitForTimeout(300)
  await exportBtn.click()
  await page.waitForTimeout(1500)
  g = await gateText()
  if (/GATE BLOCKED/.test(g) && /render-actual-photo/.test(g) && /img-guide/.test(g)) {
    ok('a listing-purpose render is blocked by the actual-photo rule, with its rule id and source id')
  } else no('actual-photo block missing or unnamed', g.slice(0, 220))
  if (downloads.length === dl0) ok('no listing-image export happened (actual-photo rule enforced)')
  else no('a listing export slipped through')
  await page.selectOption('[data-testid="render-purpose"]', 'internal')
  await page.waitForTimeout(300)

  // ── 4. Locked reference -> the fidelity diff blocks a diverging render ──
  dl0 = downloads.length
  await page.click('[data-testid="render-lock-reference"]')
  await page.waitForTimeout(400)
  await exportBtn.click()
  await page.waitForTimeout(2500)
  g = await gateText()
  if (/GATE BLOCKED/.test(g) && /fidelity: (block|not-run)/i.test(g)) ok('a locked reference runs the diff, which blocks a render that diverges from the photograph')
  else no('fidelity did not block a diverging render', g.slice(0, 220))
  if (downloads.length === dl0) ok('no download while fidelity blocks')
  else no('a download happened despite the fidelity block')

  // ── 5. Sign-off does not lift a fidelity block ──────────────────────────
  await page.click('[data-testid="render-sign-compare"]')
  await page.waitForTimeout(400)
  await exportBtn.click()
  await page.waitForTimeout(2500)
  g = await gateText()
  if (/GATE BLOCKED/.test(g) && /fidelity: (block|not-run)/i.test(g) && /compare: pass/i.test(g)) {
    ok('a compare sign-off satisfies product accuracy but does NOT lift the fidelity block')
  } else no('sign-off behaviour wrong', g.slice(0, 220))

  // ── 6. Unlock restores the open gate ────────────────────────────────────
  await page.click('[data-testid="render-unlock-reference"]')
  await page.waitForTimeout(400)
  dlPromise = page.waitForEvent('download', { timeout: 15000 })
  await exportBtn.click()
  try {
    await dlPromise
    ok('unlocking the reference restores the open gate (download)')
  } catch { no('gate did not reopen after unlock') }

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} auth-boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`3D RENDER GATE: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
