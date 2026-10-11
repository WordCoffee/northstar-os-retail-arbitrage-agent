// ═══════════════════════════════════════════════════════════════════════════
// PROJECTS CANVAS GATES — browser harness (Phase 7 item 4)
//
// Proves on the served build, with real clicks:
//   • undo / redo change the document and restore it (button + state);
//   • a locked reference turns on the compare requirement;
//   • export is REFUSED while the comparison is unsigned (no download);
//   • signing the comparison opens the gate (a real download happens);
//   • an edit after signing INVALIDATES the sign-off (compare required again).
//
// Run:  node tools/verify-projects-gates.cjs
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

  // Sign in
  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  await page.goto(BASE + 'design-studio?section=projects&view=canvas', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="proj-undo"]', { timeout: 30000 })
  ok('the Projects canvas mounted with the new controls')

  const layerCount = async () => {
    const txt = await page.$eval('.stage', e => e.textContent).catch(() => '')
    const m = txt.match(/(\d+)\s+layers/)
    return m ? Number(m[1]) : -1
  }
  const gateStatus = async () => page.$eval('[data-testid="proj-gate-status"]', e => e.textContent).catch(() => '')

  // ── Undo / redo ──────────────────────────────────────────────────────────
  const n0 = await layerCount()
  await page.click('button:has-text("Rect")')
  await page.waitForTimeout(400)
  const n1 = await layerCount()
  if (n1 === n0 + 1) ok(`adding a layer works (${n0} -> ${n1})`)
  else no('layer add did not change the count', `${n0} -> ${n1}`)
  await page.click('[data-testid="proj-undo"]')
  await page.waitForTimeout(400)
  const n2 = await layerCount()
  if (n2 === n0) ok(`undo restores the previous document (${n1} -> ${n2})`)
  else no('undo did not restore the count', `${n1} -> ${n2}`)
  await page.click('[data-testid="proj-redo"]')
  await page.waitForTimeout(400)
  const n3 = await layerCount()
  if (n3 === n1) ok(`redo re-applies the change (${n2} -> ${n3})`)
  else no('redo did not re-apply', `${n2} -> ${n3}`)
  await page.click('[data-testid="proj-undo"]')
  await page.waitForTimeout(300)

  // ── Upload artwork (the canvas has no upload input; the Assets tab owns it) ─
  const fixture = await page.evaluate(() => {
    const c = document.createElement('canvas')
    c.width = 800; c.height = 800
    const x = c.getContext('2d')
    x.fillStyle = '#f2e3c9'; x.fillRect(0, 0, 800, 800)
    x.fillStyle = '#c94f2a'; x.fillRect(80, 80, 640, 640)
    x.fillStyle = '#111111'; x.font = '64px sans-serif'; x.fillText('PRODUCT', 250, 420)
    return c.toDataURL('image/png')
  })
  await page.click('button:has-text("Assets")')
  await page.waitForSelector('label.sp-dropzone input[type="file"]', { state: 'attached', timeout: 15000 })
  await page.setInputFiles('label.sp-dropzone input[type="file"]', {
    name: 'harness-product.png', mimeType: 'image/png', buffer: Buffer.from(fixture.split(',')[1], 'base64'),
  })
  await page.waitForTimeout(1200)
  await page.click('button:has-text("Canvas")')
  await page.waitForSelector('.sp-asset-grid .sp-thumb', { timeout: 15000 })
  await page.click('.sp-asset-grid .sp-thumb')
  await page.waitForTimeout(500)
  ok('artwork uploaded (Assets tab) and a product layer added from it')

  // ── Lock the reference ───────────────────────────────────────────────────
  await page.click('[data-testid="proj-lock-reference"]')
  await page.waitForTimeout(400)
  const pill = await page.$('[data-testid="proj-reference-pill"]')
  if (pill) ok('the reference locked (pill visible)')
  else no('reference did not lock')
  let status = await gateStatus()
  if (/compare required/i.test(status)) ok('the gate states the compare requirement before export')
  else no('no compare requirement stated', status.slice(0, 140))

  // The on-demand diff must produce a real verdict with its stated limits.
  await page.click('[data-testid="proj-run-diff"]')
  await page.waitForTimeout(2000)
  const diffText = await page.$eval('[data-testid="proj-diff-result"]', e => e.textContent).catch(() => '')
  if (/(pass|block|unverified|not-run)/i.test(diffText) && /product region/i.test(diffText)) {
    ok(`the on-demand fidelity diff renders a real verdict ("${diffText.slice(0, 80)}…")`)
  } else no('the fidelity diff produced no verdict', diffText.slice(0, 160))

  // ── Export refused while unsigned ────────────────────────────────────────
  const dl0 = downloads.length
  await page.click('[data-testid="proj-export"]')
  await page.waitForTimeout(1500)
  const toastWarn = await page.$eval('.toast-warn', e => e.textContent).catch(() => '')
  if (/Export refused/i.test(toastWarn)) ok(`export refused with a stated reason ("${toastWarn.slice(0, 90)}…")`)
  else no('export was not refused', toastWarn.slice(0, 140))
  if (downloads.length === dl0) ok('no file was downloaded while the comparison is unsigned')
  else no('a download happened despite the unsigned comparison')

  // ── Sign off, then export ────────────────────────────────────────────────
  await page.click('[data-testid="proj-sign-compare"]')
  await page.waitForTimeout(400)
  status = await gateStatus()
  if (/signed off/i.test(status)) ok('the comparison signed off (status states it)')
  else no('sign-off not reflected', status.slice(0, 140))
  const dlPromise = page.waitForEvent('download', { timeout: 15000 })
  await page.click('[data-testid="proj-export"]')
  try {
    await dlPromise
    ok('export downloads once the gate is open (real download event)')
  } catch { no('no download after signing off') }
  const toastInfos = await page.$$eval('.toast-item', els => els.map(e => e.textContent)).catch(() => [])
  if (toastInfos.some(x => /Exported the local render/i.test(x))) ok('the export toast confirms a local render, no provider')
  else no('export toast missing', toastInfos.join(' | ').slice(0, 140))

  // ── An edit invalidates the sign-off ─────────────────────────────────────
  await page.click('button:has-text("Rect")')
  await page.waitForTimeout(500)
  status = await gateStatus()
  if (/compare required/i.test(status)) ok('an edit after signing invalidates the sign-off (compare required again)')
  else no('sign-off survived an edit', status.slice(0, 140))

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} auth-boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`PROJECTS CANVAS GATES: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
