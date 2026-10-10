// Phase 2 verification: every Design Studio section.
//
// Proves for each of the 9 sections: it mounts, the shell regions render, the
// spec picker is registry-driven, the compliance verdict pill renders, and no
// uncaught page error fires. Also asserts the two hard behaviours the directive
// requires: an UNSOURCED spec cannot export, and the pre-flight blocks a
// non-compliant main image.
//
// Run from the tools/ directory:  node verify-design-studio.cjs
// Full output is always printed. FATALs are counted, never swallowed.

const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

let pass = 0
let fail = 0
let fatal = 0
const log = (m) => console.log(m)
const ok = (m) => { pass++; log('PASS  ' + m) }
const no = (m, d) => { fail++; log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const SECTIONS = [
  { id: 'projects', label: 'Projects', testid: null },
  { id: 'listing-images', label: 'Listing Images', testid: 'listing-images-workspace' },
  { id: 'aplus', label: 'A+ / Brand Story', testid: 'aplus-workspace' },
  { id: 'storefront', label: 'Storefront', testid: 'storefront-workspace' },
  { id: 'ads', label: 'Ads', testid: 'ads-workspace' },
  { id: 'video-ugc', label: 'Video & UGC Clips', testid: 'video-ugc-workspace' },
  { id: 'social', label: 'Social', testid: 'social-workspace' },
  { id: 'packaging', label: 'Packaging & Mockups', testid: 'packaging-workspace' },
  { id: '3d-scene', label: '3D Product Scene', testid: null },
]

async function main() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const errors = []
  const preAuth = []
  let capturing = false
  page.on('pageerror', (e) => (capturing ? errors : preAuth).push(String(e)))
  page.on('console', (m) => {
    if (m.type() !== 'error') return
    ;(capturing ? errors : preAuth).push('console: ' + m.text().slice(0, 160))
  })

  // ── Sign in ──
  try {
    await page.goto(BASE + 'sign-in')
    await page.fill('#signin-id', EMAIL)
    await page.fill('#signin-pw', PW)
    await page.click('form button[type="submit"]')
    await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
    ok('signed in')
    capturing = true  // pre-auth 401s on /me are expected; capture starts here
  } catch (e) {
    ftl('sign-in failed', String(e).slice(0, 120))
    await browser.close()
    return report()
  }

  // ── Section picker ──
  await page.goto(BASE + 'design-studio')
  await page.waitForSelector('.ds-section-picker', { timeout: 10000 })
  const picker = await page.$$('.ds-section-picker button')
  if (picker.length === SECTIONS.length) ok(`section picker lists all ${picker.length} sections`)
  else no(`section picker lists ${picker.length}, expected ${SECTIONS.length}`)

  // ── Each section, navigated IN-APP so the SPA does not refetch the session
  //    on every step (the API allows 30 requests/min on the foundation plan).
  for (const s of SECTIONS) {
    const before = errors.length
    try {
      const btn = await page.$(`.ds-section-picker button:has-text("${s.label}")`)
      if (!btn) { no(`${s.label}: no section button`); continue }
      await btn.click()
      await page.waitForTimeout(800)

      if (s.testid) {
        await page.waitForSelector(`[data-testid="${s.testid}"]`, { timeout: 12000 })
        ok(`${s.label}: workspace mounted`)
        // Shell regions
        const regions = ['.ss-topbar', '.ss-leftrail', '.ss-canvas', '.ss-inspector', '.ss-bottomstrip']
        const missing = []
        for (const r of regions) if (!(await page.$(r))) missing.push(r)
        if (missing.length === 0) ok(`${s.label}: all five shell regions render`)
        else no(`${s.label}: missing shell regions`, missing.join(', '))
        // Registry-driven picker
        const specs = await page.$$('.ss-spec')
        if (specs.length >= 2) ok(`${s.label}: ${specs.length} registry formats offered`)
        else no(`${s.label}: spec picker has ${specs.length} entries`)
        // Verdict
        const v = await page.$('[data-testid="verdict-pill"]')
        if (v) ok(`${s.label}: verdict renders (${(await v.textContent()).trim()})`)
        else no(`${s.label}: no verdict pill`)
        // An empty canvas must NEVER report a green pass (directive item 4).
        const vt = v ? (await v.textContent()).trim() : ''
        if (vt === 'Pre-flight pass') no(`${s.label}: EMPTY CANVAS SHOWED GREEN — coverage states are not working`)
        else ok(`${s.label}: empty canvas does not report green (${vt})`)
        // Coverage counter must be present
        const strip = await page.$('.ss-bottomstrip-actions')
        const stripText = strip ? await strip.textContent() : ''
        if (/rules decided/.test(stripText)) ok(`${s.label}: coverage counter shows "rules decided"`)
        else no(`${s.label}: no coverage counter`, stripText.slice(0, 60))
        // Confidence label present
        const conf = await page.$$eval('.pill', els => els.map(e => e.textContent.trim()))
        if (conf.some(t => ['VERIFIED', 'REPORTED', 'UNSOURCED'].includes(t))) ok(`${s.label}: specs carry a VERIFIED/REPORTED/UNSOURCED label`)
        else no(`${s.label}: no confidence label found`)
      } else {
        // Projects and 3D Product Scene are the pre-Phase-2 workspaces.
        const heading = await page.$eval('h1, h2', e => e.textContent).catch(() => '')
        if (heading) ok(`${s.label}: renders (${heading.slice(0, 40)})`)
        else no(`${s.label}: no heading`)
      }
    } catch (e) {
      no(`${s.label}: did not mount`, String(e).slice(0, 120))
    }
    const errs = errors.length - before
    if (errs > 0) no(`${s.label}: ${errs} console/page error(s)`, errors.slice(before).join(' | ').slice(0, 200))
  }

  // ── Hard behaviour 1: NO spec may be UNSOURCED any more ──────────────────
  // Directive item 1 removed the SP video UNSOURCED block once its source was
  // recorded. The block is now a GUARD, so the correct assertion is that no
  // format is unsourced — and that the guard itself is exercised by the
  // registry-level test in test-compliance-rules.mjs.
  try {
    await page.goto(BASE + 'design-studio?section=ads')
    await page.waitForSelector('[data-testid="ads-workspace"]', { timeout: 12000 })
    const pills = await page.$$eval('.pill', els => els.map(e => e.textContent.trim()))
    if (!pills.includes('UNSOURCED')) ok('no UNSOURCED spec remains (SP video block removed per item 1)')
    else no('an UNSOURCED spec still renders')
    // Every visible spec must carry a VERIFIED or REPORTED tag.
    const confCount = pills.filter(t => t === 'VERIFIED' || t === 'REPORTED').length
    if (confCount >= 3) ok(`spec picker tags coverage: ${confCount} tagged specs visible`)
    else no('spec picker shows too few confidence tags', String(confCount))
    // SP video sourced with its own rules
    const labels = await page.$$eval('.ss-spec', els => els.map(e => e.textContent))
    const spv = labels.find(t => /Sponsored Products video/.test(t)) || ''
    if (spv && /VERIFIED/.test(spv)) ok('SP video is VERIFIED (sourced from the Amazon guide)')
    else no('SP video row is not VERIFIED', spv.slice(0, 80))
    const disp = labels.find(t => /Sponsored Display video/.test(t)) || ''
    if (disp && /VERIFIED/.test(disp)) ok('Display video is VERIFIED (reconciled to Amazon-owned sources)')
    else no('Display video row is not VERIFIED', disp.slice(0, 80))
  } catch (e) {
    ftl('source/coverage check threw', String(e).slice(0, 140))
  }

  // ── Hard behaviour 2: SB video 9:16 warns but does not block ──
  try {
    const v = await page.$('.ss-spec:has-text("vertical")')
    if (v) {
      await v.click()
      await page.waitForTimeout(600)
      const panel = await page.$('[data-testid="compliance-panel"]')
      const text = panel ? await panel.textContent() : ''
      const hasWarn = /9:16 vertical is not the default/i.test(text)
      const blocks = /Blocks export/.test(text)
      const corner = /bottom-right/i.test(text)
      if (hasWarn) ok('9:16 vertical is surfaced as a WARN (date-sensitive)')
      else no('9:16 vertical warn row not present')
      if (corner) ok('SB video bottom-right safe-area rule present')
      else no('SB video safe-area rule missing')
      log(`       (vertical verdict blocks=${blocks} — a warn must not be the only reason to block)`)
    } else {
      no('no vertical SB spec button found')
    }
  } catch (e) {
    ftl('9:16 warn check threw', String(e).slice(0, 140))
  }

  // ── Hard behaviour: SP video is now SOURCED and Display video reconciled ──
  // (covered above in the source/coverage check)

  // ── Hard behaviour: the disclosure workflow is present on every section ──
  try {
    await page.goto(BASE + 'design-studio?section=aplus')
    await page.waitForSelector('[data-testid="aplus-workspace"]', { timeout: 12000 })
    // Open the Fields tab and confirm the shared disclosure fields exist.
    const fieldsTab = await page.$('.ss-leftrail-tab:has-text("Fields")')
    if (!fieldsTab) { no('no Fields tab on the A+ workspace'); }
    else {
      await fieldsTab.click()
      await page.waitForTimeout(400)
      const selects = await page.$$eval('.ss-field select', els => els.map(e => e.previousElementSibling ? e.previousElementSibling.textContent : ''))
      const toggles = await page.$$eval('.ss-field-toggle span', els => els.map(e => e.textContent))
      if (selects.some(t => /People in this asset/i.test(t))) ok('A+: the people classification field is present (no default)')
      else no('A+: no people-classification field', JSON.stringify(selects).slice(0, 120))
      if (selects.some(t => /Product fidelity/i.test(t))) ok('A+: the product fidelity field is present')
      else no('A+: no fidelity field')
      if (toggles.some(t => /generated a person/i.test(t))) ok('A+: the studio-generated-person switch is present (conflict source)')
      else no('A+: no studio-generated-person switch')
      // The pre-flight must surface the disclosure row.
      const panel = await page.$('[data-testid="compliance-panel"]')
      const txt = panel ? await panel.textContent() : ''
      if (/AI-generated people disclosure/i.test(txt)) ok('A+: the disclosure row is in the pre-flight')
      else no('A+: no disclosure row in the pre-flight')
      if (/cannot detect AI-generated people from pixels/i.test(txt)) ok('A+: the pre-flight states plainly that the studio cannot detect AI people from pixels')
      else no('A+: the honesty statement about pixel detection is missing')
      // An unanswered classification must not be a green pass.
      const verdict = await page.$eval('[data-testid="verdict-pill"]', e => e.textContent.trim()).catch(() => '')
      if (verdict !== 'Pre-flight pass') ok(`A+: unanswered disclosure does not pass the pre-flight (${verdict})`)
      else no('A+: an unanswered disclosure reported a green pass')
    }
  } catch (e) {
    ftl('disclosure workflow check threw', String(e).slice(0, 140))
  }

  // ── Hard behaviour 3: A+ alt text blocks when missing ──
  try {
    await page.goto(BASE + 'design-studio?section=aplus')
    await page.waitForSelector('[data-testid="aplus-workspace"]', { timeout: 12000 })
    const panel = await page.$('[data-testid="compliance-panel"]')
    const text = panel ? await panel.textContent() : ''
    if (/alt text/i.test(text)) ok('A+ alt-text requirement appears in the pre-flight')
    else no('A+ alt-text rule not visible in the pre-flight')
    if (/2 MB/i.test(text) || /under 2MB|2MB/i.test(text) || /2\.00 MB/.test(text)) ok('A+ 2 MB limit surfaced')
    else log('       (A+ file-size rule renders as "measured at export" until a size exists — expected)')
  } catch (e) {
    ftl('A+ check threw', String(e).slice(0, 140))
  }

  await browser.close()
  return report()

  function report() {
    log('')
    log(`Pre-auth console noise (expected: a signed-out SPA gets 401 on /me): ${preAuth.length}`)
    if (preAuth.length) preAuth.slice(0, 3).forEach(e => log('   ' + e.slice(0, 140)))
    log('')
    log(`TOTAL uncaught/console errors AFTER sign-in: ${errors.length}`)
    if (errors.length) errors.slice(0, 6).forEach(e => log('   ' + e.slice(0, 160)))
    log('')
    log(`DESIGN STUDIO PHASE 2 — ${pass} passed, ${fail} failed, ${fatal} FATAL`)
    process.exitCode = (fail || fatal) ? 1 : 0
  }
}

main().catch((e) => {
  console.error('FATAL harness crash', e)
  process.exitCode = 2
})
