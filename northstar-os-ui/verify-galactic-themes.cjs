// ═══════════════════════════════════════════════════════════════════════════
// GALACTIC THEME SHIFTS — browser harness (Thorn v5.0 card T-2)
//
// Proves the atmosphere actually follows the active Master Brain focus:
//   1. the canvas mounts without falling back to the CSS gradient;
//   2. switching focus changes data-cosmic-theme AND drives the tint toward that
//      focus's target (read from the live element, not from a comment);
//   3. the transition is EASED — the value is caught mid-flight, so a hard cut
//      would fail;
//   4. each focus's settled palette is distinct from the others;
//   5. the reading system is untouched (composer still 16.5px, column still 820px)
//      — a background change must never cost legibility;
//   6. no console errors.
//
// Run:  NS_TEST_PASSWORD=<pw> node verify-galactic-themes.cjs
// Exit: 0 = contract holds, 1 = a violation, 2 = FATAL/watchdog.
// ═══════════════════════════════════════════════════════════════════════════
const { chromium } = require('playwright')

const BASE = process.env.HARNESS_BASE_URL || 'http://127.0.0.1:8101/ui/'
const EMAIL = process.env.NS_TEST_EMAIL || 't2'
const PW = process.env.NS_TEST_PASSWORD
const OUT = __dirname + '/screenshots'
const WATCHDOG_MS = Number(process.env.HARNESS_TIMEOUT_MS || 240000)

// Expected targets, duplicated on purpose: if the app's table drifts, this fails.
const EXPECTED = {
  auto: [1.00, 0.95, 0.86],
  create: [1.00, 0.86, 0.66],
  grow: [0.80, 1.00, 0.86],
  research: [0.74, 0.86, 1.00],
  operate: [0.92, 0.95, 1.00],
  autothink: [0.84, 0.80, 1.00],
}
const TOL = 0.02
const ORDER = ['create', 'grow', 'research', 'operate', 'autothink', 'auto']

let pass = 0
let fail = 0
let fatal = 0
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m, d) => { fail++; console.log('FAIL  ' + m + (d ? ' :: ' + d : '')) }
const ftl = (m, d) => { fatal++; console.log('FATAL ' + m + (d ? ' :: ' + d : '')) }

const readTint = (page) => page.evaluate(() => {
  const c = document.querySelector('.cosmic-canvas')
  if (!c) return null
  return {
    theme: c.dataset.cosmicTheme || '',
    tint: (c.dataset.cosmicTint || '').split(',').filter(Boolean).map(Number),
    fallback: c.dataset.cosmicFallback || null,
  }
})

const near = (a, b) => Array.isArray(a) && a.length === 3
  && a.every((v, i) => Math.abs(v - b[i]) <= TOL)

async function settle(page, target, ms = 9000) {
  const t0 = Date.now()
  let last = null
  while (Date.now() - t0 < ms) {
    last = await readTint(page)
    if (last && near(last.tint, target)) return { ...last, ms: Date.now() - t0 }
    await page.waitForTimeout(150)
  }
  return { ...(last || {}), ms: Date.now() - t0, timedOut: true }
}

async function main() {
  if (!PW) {
    console.error('NS_TEST_PASSWORD is required (the local operator account password).')
    process.exit(2)
  }
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await ctx.newPage()
  const problems = []
  const preAuth = []
  const postAuth = []
  let authed = false
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text().slice(0, 160)) })
  page.on('pageerror', (e) => problems.push('pageerror: ' + String(e).slice(0, 160)))
  page.on('response', (r) => {
    if (r.status() < 400) return
    const path = r.url().replace(/^https?:\/\/[^/]+/, '')
    ;(authed ? postAuth : preAuth).push(`${r.status()} ${path}`)
  })
  // Before sign-in the SPA probes its context and the API fails closed with 401
  // by design. That is the documented posture, not a failure — asserted below.
  const EXPECTED_PREAUTH = new Set([
    '401 /api/v1/foundation/me',
    '401 /api/v1/foundation/environment',
    '401 /api/v1/foundation/preview/active',
  ])

  await page.goto(BASE + 'sign-in', { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForSelector('#signin-id', { timeout: 30000 })
  await page.fill('#signin-id', EMAIL)
  await page.fill('#signin-pw', PW)
  await page.click('form button[type="submit"]')
  await page.waitForFunction(() => location.pathname === '/ui/home', null, { timeout: 30000 })
  authed = true
  await page.waitForSelector('.cosmic-canvas', { timeout: 15000 })
  await page.waitForTimeout(2500)

  // ── 1. the canvas is live, not the CSS fallback ──────────────────────────
  const boot = await readTint(page)
  if (!boot) ftl('cosmic canvas never mounted')
  else if (boot.fallback) no('the canvas fell back to the CSS gradient', boot.fallback)
  else ok('galactic canvas renders live (no fallback)')

  const settled = {}
  for (const id of ORDER) {
    const chip = await page.$(`[data-testid="mb-focus-${id}"]`)
    if (!chip) { no(`focus chip ${id} is missing`); continue }
    const locked = await chip.evaluate((el) => el.className.includes('locked'))
    if (locked) {
      console.log(`SKIP  ${id} is locked for this plan — nothing to verify`)
      continue
    }

    await chip.click()
    await page.waitForTimeout(220)                 // catch it mid-transition
    const mid = await readTint(page)
    const target = EXPECTED[id]
    const res = await settle(page, target)

    if (res.theme !== id) no(`${id}: data-cosmic-theme is ${res.theme}`)
    else if (res.timedOut) no(`${id}: tint never reached the target`, JSON.stringify(res.tint))
    else ok(`${id}: atmosphere settled to [${target.map((v) => v.toFixed(2)).join(', ')}] in ~${res.ms}ms`)
    settled[id] = res.tint

    if (mid && Array.isArray(mid.tint) && mid.tint.length === 3) {
      const isEasing = !near(mid.tint, target) && !near(mid.tint, settled[id] || target)
        && JSON.stringify(mid.tint) !== JSON.stringify(res.tint)
      isEasing ? ok(`${id}: transition is eased, not a hard cut`)
        : no(`${id}: no eased mid-flight value observed`, JSON.stringify(mid.tint))
    }
    await page.screenshot({ path: `${OUT}/v42-theme-${id}.png` })
  }

  // ── 4. the palettes are genuinely distinct ──────────────────────────────
  const ids = Object.keys(settled)
  let dupes = 0
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = i + 1; j < ids.length; j += 1) {
      if (near(settled[ids[i]], settled[ids[j]])) dupes += 1
    }
  }
  dupes === 0 ? ok(`${ids.length} focus palettes measured, all distinct`)
    : no(`${dupes} focus palette pair(s) are indistinguishable`)

  // ── 5. legibility is untouched by the scenery ───────────────────────────
  const reading = await page.evaluate(() => {
    const box = document.querySelector('.mb-shell .chat-composer-box textarea')
    const stream = document.querySelector('.mb-shell .chat-stream')
    const panel = document.querySelector('.mb-shell .chat-shell')
    return {
      composerFs: box && getComputedStyle(box).fontSize,
      columnW: stream && Math.round(stream.getBoundingClientRect().width),
      panelBg: panel && getComputedStyle(panel).backgroundColor,
    }
  })
  reading.composerFs === '16.5px'
    ? ok('composer still reads at 16.5px with the theme shifting behind it')
    : no('composer font size changed', reading.composerFs)
  reading.columnW === 820
    ? ok('reading column still 820px')
    : no('reading column changed', String(reading.columnW))
  const parts = String(reading.panelBg || '').match(/rgba?\(([^)]+)\)/)
  const panelAlpha = parts ? Number(parts[1].split(',')[3] ?? 1) : 0
  panelAlpha >= 0.94
    ? ok(`panel still near-opaque (alpha ${panelAlpha}) — scenery cannot eat the prose`)
    : no('panel opacity dropped — background would eat the text', reading.panelBg)

  // Chrome logs a console error for every failed response. The only expected
  // ones are the pre-auth 401 probes already asserted (and counted) below, so a
  // console error is only a failure when it is something OTHER than that.
  const EXPECTED_CONSOLE = /Failed to load resource: the server responded with a status of (401|503)/
  const unexpectedConsole = problems.filter((p) => !EXPECTED_CONSOLE.test(p))
  unexpectedConsole.length === 0
    ? ok(`no unexpected console errors (${problems.length - unexpectedConsole.length} expected pre-auth 401 line(s) excluded)`)
    : no('console errors during the run', unexpectedConsole.slice(0, 3).join(' | '))
  postAuth.length === 0
    ? ok('no failed requests once authenticated')
    : (() => {
        // The voice engine is an OPTIONAL external service (127.0.0.1:8321). A 503
        // from it is the documented state - the picker disables itself and says so -
        // not a regression. Anything else still fails.
        const optional = new Set(['503 /api/chat/voice/voices', '503 /api/chat/voice/speak'])
        const unexpected = postAuth.filter((p) => !optional.has(p))
        unexpected.length === 0
          ? ok(`no unexpected failed requests (${postAuth.length} optional-engine 503(s) allowed)`)
          : no(`${unexpected.length} authenticated request(s) failed`, [...new Set(unexpected)].slice(0, 5).join(' | '))
      })()
  const unexpected = [...new Set(preAuth)].filter((p) => !EXPECTED_PREAUTH.has(p))
  unexpected.length === 0
    ? ok(`pre-auth probes failed closed exactly as documented (${new Set(preAuth).size} endpoint(s), 401)`)
    : no('unexpected pre-auth failures', unexpected.slice(0, 4).join(' | '))

  await browser.close()
  console.log('')
  console.log(`GALACTIC THEMES: ${pass} passed, ${fail} failed, ${fatal} FATAL`)
  process.exitCode = (fail || fatal) ? 1 : 0
}

const guard = new Promise((_, rej) => setTimeout(() => rej(new Error(`WATCHDOG after ${WATCHDOG_MS}ms`)), WATCHDOG_MS))
Promise.race([main(), guard]).then(
  () => process.exit(process.exitCode || 0),
  (e) => { console.error('FATAL ' + e.message); process.exit(2) },
)
