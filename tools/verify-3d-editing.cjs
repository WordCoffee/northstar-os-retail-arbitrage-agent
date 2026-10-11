// ═══════════════════════════════════════════════════════════════════════════
// 3D PRODUCT SCENE — editing harness (Phase 8 item 6)
//
// Proves on the served build, with real clicks:
//   • layers can be reordered (Move up/down actually change the list order);
//   • undo restores the previous scene document; redo re-applies the change;
//   • removing a layer is undoable (the layer comes back).
//
// Run:  node tools/verify-3d-editing.cjs
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

  await page.goto(BASE + 'design-studio?section=3d-scene', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('[data-testid="render3d-gate"]', { timeout: 30000 })
  // The Layers list lives in the Advanced inspector; switch if needed.
  if (!(await page.$('[data-testid="pd-layer-row"]'))) {
    const adv = page.locator('button:has-text("Advanced")').first()
    if (await adv.count()) { await adv.click(); await page.waitForTimeout(600) }
  }
  await page.waitForSelector('[data-testid="pd-layer-row"]', { timeout: 15000 })
  ok('the 3D scene mounted with the layer list and the new controls')

  const names = async () => page.$$eval('[data-testid="pd-layer-row"] .sp-layer-name', els => els.map(e => e.textContent.trim()))
  const before = await names()
  if (before.length >= 2) ok(`the scene has ${before.length} layers to reorder`)
  else { ftl('the scene has fewer than 2 layers; reorder cannot be tested', JSON.stringify(before)); await browser.close(); return report() }

  // ── Reorder: move the first row DOWN one position ────────────────────────
  await page.click('[data-testid="pd-layer-row"] [data-testid="pd-layer-down"]')
  await page.waitForTimeout(500)
  const afterMove = await names()
  if (afterMove[0] === before[1] && afterMove[1] === before[0]) {
    ok(`Move down swapped the first two layers ("${before[0]}" <-> "${before[1]}")`)
  } else no('reorder did not change the list order', JSON.stringify({ before: before.slice(0, 3), after: afterMove.slice(0, 3) }))

  // ── Undo restores the order; redo re-applies it ─────────────────────────
  await page.click('[data-testid="pd-undo"]')
  await page.waitForTimeout(500)
  const afterUndo = await names()
  if (JSON.stringify(afterUndo) === JSON.stringify(before)) ok('undo restored the previous layer order')
  else no('undo did not restore the order', JSON.stringify(afterUndo.slice(0, 3)))

  await page.click('[data-testid="pd-redo"]')
  await page.waitForTimeout(500)
  const afterRedo = await names()
  if (JSON.stringify(afterRedo) === JSON.stringify(afterMove)) ok('redo re-applied the reorder')
  else no('redo did not re-apply', JSON.stringify(afterRedo.slice(0, 3)))

  // Back to the original order for the next check.
  await page.click('[data-testid="pd-undo"]')
  await page.waitForTimeout(500)

  // ── Remove is undoable ──────────────────────────────────────────────────
  const beforeRemove = await names()
  await page.click('[data-testid="pd-layer-row"] [data-testid="pd-layer-remove"]')
  await page.waitForTimeout(500)
  const afterRemove = await names()
  if (afterRemove.length === beforeRemove.length - 1) ok(`removing a layer dropped the count (${beforeRemove.length} -> ${afterRemove.length})`)
  else no('remove did not change the layer count', `${beforeRemove.length} -> ${afterRemove.length}`)
  await page.click('[data-testid="pd-undo"]')
  await page.waitForTimeout(500)
  const restored = await names()
  if (restored.length === beforeRemove.length && JSON.stringify(restored) === JSON.stringify(beforeRemove)) {
    ok('undo restored the removed layer (and the order)')
  } else no('undo did not restore the removed layer', JSON.stringify(restored.slice(0, 3)))

  const realErrors = errors.filter(e => !/401|403|429/.test(e))
  if (realErrors.length === 0) ok(`no console/page errors (${errors.length} boundary notices filtered)`)
  else no(`${realErrors.length} real console/page error(s)`, realErrors.slice(0, 2).join(' | '))

  await browser.close()
  return report()

  function report() {
    console.log('')
    console.log(`3D EDITING: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
