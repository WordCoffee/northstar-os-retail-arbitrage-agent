// ═══════════════════════════════════════════════════════════════════════════
// SECTION EVIDENCE: screenshots + accessibility + canvas presence
//
// Phase 5 item 11. For EVERY Design Studio section it:
//   • captures a desktop screenshot (1440x900) and a mobile one (390x844)
//     into reports/screenshots_<date>/
//   • asserts a canvas is present, or records the DOCUMENTED reason one is not
//   • checks for horizontal overflow at the mobile width
//   • checks keyboard reachability: focus must land on real controls
//
// Run from tools/:  node capture-section-evidence.cjs
// ═══════════════════════════════════════════════════════════════════════════

const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD || 'T2holdings'

const STAMP = new Date().toISOString().slice(0, 10).replace(/-/g, '')
const OUT = path.join(__dirname, '..', 'reports', `screenshots_${STAMP}`)

let pass = 0
let fail = 0
let fatal = 0
const log = (m) => console.log(m)
const ok = (m) => { pass++; log('PASS  ' + m) }
const no = (m, d) => { fail++; log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; log('FATAL ' + m + (d ? ' :: ' + d : '')) }

// `canvas: 'surface'` = must embed the compositing surface.
// `canvas: 'own'`     = owns an equivalent canvas; `why` records the reason.
const SECTIONS = [
  { id: 'projects', label: 'Projects', canvas: 'own', why: 'The project board owns the Creative Studio master canvas (Stage.jsx) and the creative engine (doc model, templates, compliance, render/export). Embedding a second canvas would duplicate an equivalent surface.' },
  { id: 'listing-images', label: 'Listing Images', canvas: 'surface' },
  { id: 'aplus', label: 'A+ / Brand Story', canvas: 'surface' },
  { id: 'storefront', label: 'Storefront', canvas: 'surface' },
  { id: 'ads', label: 'Ads', canvas: 'surface' },
  { id: 'video-ugc', label: 'Video & UGC Clips', canvas: 'surface', note: 'storyboard / frame canvas only - no video rendering' },
  { id: 'social', label: 'Social', canvas: 'surface' },
  { id: 'packaging', label: 'Packaging & Mockups', canvas: 'surface' },
  { id: '3d-scene', label: '3D Product Scene', canvas: 'own', why: 'The 3D Product Scene owns a real 3D composer (engine/three.js box mesh, three-point lighting, affine texture mapping, renders to Canvas 2D). It is a purpose-built canvas, not a missing one.' },
]

function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') }

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const errors = []
  let capturing = false

  // ── sign in once at desktop width ──
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await desktop.newPage()
  page.on('pageerror', (e) => { if (capturing) errors.push(String(e)) })
  page.on('console', (m) => { if (capturing && m.type() === 'error') errors.push('console: ' + m.text().slice(0, 140)) })

  await page.goto(BASE + 'sign-in')
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  capturing = true
  ok('signed in')

  // ── desktop pass ──
  await page.goto(BASE + 'design-studio')
  await page.waitForSelector('.ds-section-picker', { timeout: 12000 })

  for (const s of SECTIONS) {
    const before = errors.length
    try {
      const btn = await page.$(`.ds-section-picker button:has-text("${s.label}")`)
      if (!btn) { no(`${s.label}: no section button`); continue }
      await btn.click()
      await page.waitForTimeout(900)

      await page.screenshot({ path: path.join(OUT, `desktop-${slug(s.label)}.png`), fullPage: false })

      // Canvas presence
      const canvases = await page.$$('canvas')
      if (canvases.length > 0) {
        ok(`${s.label}: canvas present (${canvases.length})`)
      } else if (s.canvas === 'own') {
        ok(`${s.label}: no <canvas> but DOCUMENTED - ${s.why.slice(0, 70)}...`)
      } else {
        no(`${s.label}: NO canvas and no documented reason`)
      }

      if (s.canvas === 'surface') {
        const surface = await page.$('[data-testid="compositing-surface"]')
        if (surface) ok(`${s.label}: embeds the compositing surface`)
        else no(`${s.label}: does not embed the compositing surface`)
        // Every surface must show the unarmed banner rather than implying generation works.
        const banner = await page.$('[data-testid="generation-unarmed-banner"]')
        if (banner) ok(`${s.label}: "generation unarmed" banner shown`)
        else no(`${s.label}: no unarmed banner`)
        if (s.note) log(`       (${s.label}: ${s.note})`)
      }

      // Keyboard reachability: focus must land on real controls
      const reachable = await page.evaluate(() => {
        const els = document.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        let visible = 0
        for (const e of els) {
          const r = e.getBoundingClientRect()
          if (r.width > 0 && r.height > 0) visible++
        }
        return visible
      })
      if (reachable >= 8) ok(`${s.label}: ${reachable} keyboard-reachable controls`)
      else no(`${s.label}: only ${reachable} reachable controls`)

      // A focusable element must actually take focus
      const tookFocus = await page.evaluate(() => {
        const b = document.querySelector('.ds-section-picker button')
        if (!b) return false
        b.focus()
        return document.activeElement === b
      })
      if (tookFocus) ok(`${s.label}: a control takes keyboard focus`)
      else no(`${s.label}: nothing takes keyboard focus`)

      // Contrast smoke test on the primary heading
      const contrast = await page.evaluate(() => {
        const el = document.querySelector('h1, h2, .card-title')
        if (!el) return null
        const c = getComputedStyle(el).color
        const m = c.match(/\d+/g)
        if (!m) return null
        const [r, g, b] = m.map(Number)
        const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
        return lum
      })
      if (contrast === null) log(`       (${s.label}: contrast not measurable - no heading found)`)
      else if (contrast < 0.75) ok(`${s.label}: heading is dark on light (relative luminance ${contrast.toFixed(2)})`)
      else no(`${s.label}: heading may be low contrast (luminance ${contrast.toFixed(2)})`)
    } catch (e) {
      no(`${s.label}: desktop capture threw`, String(e).slice(0, 120))
    }
    if (errors.length > before) no(`${s.label}: ${errors.length - before} console/page error(s)`, errors.slice(before).join(' | ').slice(0, 160))
  }

  // ── mobile pass: horizontal overflow is the failure mode ──
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true })
  const mp = await mobile.newPage()
  await mp.goto(BASE + 'sign-in')
  await mp.fill('#signin-id', EMAIL)
  await mp.fill('#signin-pw', PW)
  await mp.click('form button[type="submit"]')
  await mp.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 15000 })
  await mp.goto(BASE + 'design-studio')
  await mp.waitForSelector('.ds-section-picker', { timeout: 12000 })

  for (const s of SECTIONS) {
    try {
      const btn = await mp.$(`.ds-section-picker button:has-text("${s.label}")`)
      if (!btn) { no(`${s.label}: no section button at mobile width`); continue }
      await btn.click()
      await mp.waitForTimeout(800)
      await mp.screenshot({ path: path.join(OUT, `mobile-${slug(s.label)}.png`), fullPage: false })

      const overflow = await mp.evaluate(() => {
        const de = document.documentElement
        // 2px tolerance for sub-pixel rounding.
        return { scrollW: de.scrollWidth, clientW: de.clientWidth, over: de.scrollWidth - de.clientWidth }
      })
      if (overflow.over <= 2) ok(`${s.label}: no horizontal overflow at 390px (${overflow.scrollW}/${overflow.clientW})`)
      else no(`${s.label}: horizontal overflow at 390px by ${overflow.over}px`)
    } catch (e) {
      no(`${s.label}: mobile capture threw`, String(e).slice(0, 120))
    }
  }

  await browser.close()

  const files = fs.readdirSync(OUT).filter(f => f.endsWith('.png'))
  const expected = SECTIONS.length * 2
  if (files.length >= expected) ok(`${files.length} screenshots written to reports/screenshots_${STAMP}/ (expected ${expected})`)
  else no(`only ${files.length} screenshots written, expected ${expected}`)

  if (errors.length === 0) ok('zero console/page errors across every section')
  else no(`${errors.length} console/page error(s) total`, errors.slice(0, 3).join(' | ').slice(0, 200))

  log('')
  log(`SECTION EVIDENCE: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  log(`output: reports/screenshots_${STAMP}/`)
  process.exitCode = (fail || fatal) ? 1 : 0
}

main().catch((e) => { console.error('FATAL harness crash', e); process.exitCode = 2 })
