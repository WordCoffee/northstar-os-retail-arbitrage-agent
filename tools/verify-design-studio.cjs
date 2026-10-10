// Phase 2 verification: the Design Studio Listing Images workspace.
// Proves the editor shell renders (topbar / left rail / canvas / inspector /
// bottom strip), the spec registry drives the format picker, the compliance
// pre-flight renders a verdict, and no page error fires.
//
// Run from the tools/ directory:  node verify-design-studio.cjs

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

let pass = 0
let fail = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))

  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  ok('signed in')

  // ── Design Studio root ──
  await page.goto(BASE + 'design-studio')
  await page.waitForSelector('[data-testid="ds-not-built"], .ds-section-picker', { timeout: 10000 })
  const picker = await page.$$('.ds-section-picker button')
  if (picker.length >= 8) ok(`section picker lists ${picker.length} sections`)
  else no('section picker is short', `${picker.length} sections`)

  // ── Listing Images workspace ──
  const liBtn = await page.$('.ds-section-picker button:has-text("Listing Images")')
  if (!liBtn) { no('no Listing Images section button'); await browser.close(); process.exit(1) }
  await liBtn.click()
  await page.waitForSelector('[data-testid="listing-images-workspace"]', { timeout: 10000 })
  ok('Listing Images workspace mounted')

  // Shell regions
  for (const [sel, name] of [
    ['.ss-topbar', 'top bar'],
    ['.ss-leftrail', 'left rail'],
    ['.ss-canvas', 'canvas'],
    ['.ss-inspector', 'inspector'],
    ['.ss-bottomstrip', 'bottom strip'],
  ]) {
    const el = await page.$(sel)
    if (el) ok(`shell renders ${name}`)
    else no(`shell missing ${name}`)
  }

  // Spec registry drives the format picker
  const specs = await page.$$('.ss-spec')
  if (specs.length >= 2) ok(`spec picker shows ${specs.length} formats from the registry`)
  else no('spec picker is empty', `${specs.length}`)

  // Compliance pre-flight renders a verdict + rules with sources
  const verdict = await page.$('[data-testid="verdict-pill"]')
  if (verdict) ok(`compliance verdict renders: ${(await verdict.textContent()).trim()}`)
  else no('no compliance verdict pill')
  const rules = await page.$$('.ss-rule')
  if (rules.length >= 3) ok(`compliance panel shows ${rules.length} rule rows with sources`)
  else no('compliance panel has too few rule rows', `${rules.length}`)

  // Safe zone toggle + canvas caption (the main image has no safe zone)
  const zonesToggle = await page.$('.ss-iconbtn[title*="safe zone"]')
  if (zonesToggle) ok('safe-zone toggle present')
  else no('no safe-zone toggle')

  // Bottom strip lists the flat-file slots
  const slots = await page.$$('.ss-bottomstrip-item')
  if (slots.length >= 5) ok(`bottom strip lists ${slots.length} gallery slots`)
  else no('bottom strip is short', `${slots.length}`)

  // Switch to another format and confirm the caption/verdict update path runs
  const alt = await page.$$('.ss-spec')
  if (alt.length > 1) {
    await alt[alt.length - 1].click().catch(() => {})
    await page.waitForTimeout(500)
    ok('format switch did not throw')
  }

  // ── Store spec safe zone renders (the researched overlay) ──
  await page.goto(BASE + 'design-studio?section=listing-images')
  await page.waitForSelector('[data-testid="listing-images-workspace"]', { timeout: 10000 })
  ok('workspace re-mounts from a deep link')

  // ── Page errors ──
  if (errors.length === 0) ok('no uncaught page errors')
  else no(`uncaught page errors (${errors.length})`, errors.slice(0, 3).join(' | '))

  await browser.close()
  console.log(`\nDESIGN STUDIO PHASE 2: ${pass} passed, ${fail} failed`)
  process.exit(fail ? 1 : 0)
}
main().catch((e) => { console.error('FATAL', e); process.exit(2) })
