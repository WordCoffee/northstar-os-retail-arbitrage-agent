// SECTION OUTPUT PACKS — browser harness (item 9 of the 2026-10-11 directive)
//
// Video & UGC, Social and Packaging must each offer a downloadable OUTPUT
// DOCUMENT (storyboard / asset pack / spec sheet) built from the operator's
// fields and the section pre-flight. This harness proves:
//   • the Pack control renders on each section;
//   • it is DISABLED exactly when the pre-flight verdict blocks;
//   • when enabled, clicking it downloads a markdown pack whose content names
//     its kind, carries the pre-flight summary, and states that nothing is
//     rendered or generated;
//   • a section where the pre-flight still blocks after the shared fields are
//     answered keeps the control disabled (the pack would be a checklist).
//
// Run:  node tools/verify-section-packs.cjs   (test build on :8200)
// Exit: 0 = all green, 1 = a failure, 2 = harness error.

const { chromium } = require('playwright')
const fs = require('fs')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8200/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const SECTIONS = [
  { label: 'Video & UGC Clips', testid: 'video-ugc-workspace', kind: 'storyboard_pack', extra: { 'Clip duration (seconds)': '15', 'Hook (first 3 seconds)': 'Cold all day' } },
  { label: 'Social', testid: 'social-workspace', kind: 'social_asset_pack', extra: {} },
  { label: 'Packaging & Mockups', testid: 'packaging-workspace', kind: 'packaging_spec', extra: { 'Pack format': 'Carton' } },
]

async function answerSharedFields(page) {
  // Fields tab
  const fieldsTab = await page.$('.ss-leftrail button:has-text("Fields")')
  if (fieldsTab) await fieldsTab.click()
  await page.waitForTimeout(300)
  const rail = page.locator('.ss-leftrail')
  // Product fidelity select -> first real option
  const fid = rail.locator('label.ss-field', { hasText: 'Product fidelity' }).locator('select').first()
  if (await fid.count()) await fid.selectOption({ index: 1 })
  // People in this asset -> first real option
  const people = rail.locator('label.ss-field', { hasText: 'People in this asset' }).locator('select').first()
  if (await people.count()) await people.selectOption({ index: 1 })
  // Export filename
  const fname = rail.locator('label.ss-field', { hasText: 'Export filename' }).locator('input').first()
  if (await fname.count()) await fname.fill('pack-harness-test.png')
}

async function setExtra(page, extra) {
  const rail = page.locator('.ss-leftrail')
  for (const [label, value] of Object.entries(extra)) {
    const input = rail.locator('label.ss-field', { hasText: label }).locator('input, textarea').first()
    if (await input.count()) await input.fill(value)
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, acceptDownloads: true })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)))

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  try {
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
  } catch { ftl('sign-in failed'); await browser.close(); return report() }

  await page.goto(BASE + 'design-studio')
  await page.waitForSelector('.ds-section-picker', { timeout: 15000 })

  let downloads = 0
  for (const s of SECTIONS) {
    try {
      const btn = await page.$(`.ds-section-picker button:has-text("${s.label}")`)
      if (!btn) { no(`${s.label}: no section button`); continue }
      await btn.click()
      await page.waitForSelector(`[data-testid="${s.testid}"]`, { timeout: 12000 })
      const packBtn = await page.$('[data-testid="pack-download"]')
      if (!packBtn) { no(`${s.label}: no pack control`); continue }
      ok(`${s.label}: pack control renders`)

      await answerSharedFields(page)
      await setExtra(page, s.extra)
      await page.waitForTimeout(400)

      const verdict = (await page.$eval('[data-testid="verdict-pill"]', el => el.textContent.trim()).catch(() => '')) || ''
      const disabled = await packBtn.isDisabled()
      const blocks = /block/i.test(verdict)

      if (disabled) {
        if (blocks) ok(`${s.label}: pack disabled while the pre-flight blocks (${verdict})`)
        else no(`${s.label}: pack disabled but the verdict does not block (${verdict})`)
        continue
      }
      if (blocks) { no(`${s.label}: pre-flight blocks but the pack is enabled (${verdict})`); continue }

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 15000 }),
        packBtn.click(),
      ])
      const path = await download.path()
      const text = fs.readFileSync(path, 'utf8')
      downloads++
      if (text.includes(s.kind)) ok(`${s.label}: pack downloaded and names its kind (${s.kind})`)
      else no(`${s.label}: pack does not name its kind`, text.slice(0, 120))
      if (/preflight/i.test(text) && /(block|flag|pass|UNKNOWN)/i.test(text)) ok(`${s.label}: pack carries the pre-flight summary`)
      else no(`${s.label}: pack has no pre-flight summary`)
      if (/no_rendering|nothing is rendered|Rendering and generation are out of scope/i.test(text)) ok(`${s.label}: pack states that nothing is rendered/generated`)
      else no(`${s.label}: pack does not state the no-rendering boundary`)
      if (/UNKNOWN/.test(text)) ok(`${s.label}: pack carries an UNKNOWN for a field the operator did not supply`)
      else console.log(`NOTE  ${s.label}: every field was supplied, so no UNKNOWN appeared`)
    } catch (e) {
      no(`${s.label}: ${String(e).slice(0, 160)}`)
    }
  }
  if (downloads === 0) no('no pack was downloaded at all - the enabled path is unproven')
  if (errors.length) no('uncaught page errors', errors.slice(0, 2).join(' | '))
  else ok('no uncaught page errors')

  await browser.close()
  return report()
}

function report() {
  console.log(`\nSECTION PACKS: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  process.exit(fatal ? 2 : fail ? 1 : 0)
}

main().catch((e) => { ftl('harness crashed', String(e).slice(0, 200)); report() })
